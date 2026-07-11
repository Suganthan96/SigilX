"""
tests/test_payment.py

Tests the x402 middleware wire format directly (401/402 shape, demo bypass,
and structural payload validation) without touching a real facilitator.
"""

from __future__ import annotations

import base64
import json
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import services.api.payment as payment
from services.api.main import app

OKX_TX_LIST_RE = r".*/api/v5/wallet/post-transaction/transactions-by-address.*"
OKX_ADDR_SUMMARY_RE = r".*/api/v5/explorer/address/address-summary.*"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(payment, "DEMO_MODE", False)
    monkeypatch.setattr(payment, "PAYMENT_WALLET", "0x00000000000000000000000000000000000abc")
    monkeypatch.setattr(payment, "SERVICE_PRICE_OKB", "0.1")
    monkeypatch.setattr(payment, "X402_ASSET", "")
    return TestClient(app)


def _encode(envelope: dict) -> str:
    return base64.b64encode(json.dumps(envelope).encode()).decode()


def _valid_authorization(**overrides) -> dict:
    now = int(time.time())
    base = {
        "x402Version": 1,
        "scheme": "exact",
        "network": "eip155:196",
        "payload": {
            "signature": "0xdeadbeef",
            "authorization": {
                "from": "0x1111111111111111111111111111111111aaaa",
                "to": "0x00000000000000000000000000000000000abc",
                "value": str(10**18),  # 1 OKB, well above the 0.1 OKB requirement
                "validAfter": str(now - 10),
                "validBefore": str(now + 300),
                "nonce": "0x01",
            },
        },
    }
    base.update(overrides)
    return base


def test_health_is_never_gated(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_generate_without_payment_header_returns_x402_shape(client: TestClient):
    resp = client.post("/generate", json={"wallet_address": "0x" + "1" * 40, "chain": "eth-mainnet"})
    assert resp.status_code == 402
    body = resp.json()
    assert body["x402Version"] == 1
    assert body["accepts"][0]["scheme"] == "exact"
    assert body["accepts"][0]["payTo"] == "0x00000000000000000000000000000000000abc"


def test_generate_with_malformed_payment_header_returns_402(client: TestClient):
    resp = client.post(
        "/generate",
        json={"wallet_address": "0x" + "1" * 40, "chain": "eth-mainnet"},
        headers={"X-PAYMENT": "not-valid-base64-json"},
    )
    assert resp.status_code == 402
    assert resp.json()["error"] == "malformed_payment_header"


def test_generate_with_expired_authorization_returns_402(client: TestClient):
    now = int(time.time())
    envelope = _valid_authorization()
    envelope["payload"]["authorization"]["validBefore"] = str(now - 1)

    resp = client.post(
        "/generate",
        json={"wallet_address": "0x" + "1" * 40, "chain": "eth-mainnet"},
        headers={"X-PAYMENT": _encode(envelope)},
    )
    assert resp.status_code == 402
    assert resp.json()["error"] == "authorization_expired_or_not_yet_valid"


def test_generate_with_insufficient_value_returns_402(client: TestClient):
    envelope = _valid_authorization()
    envelope["payload"]["authorization"]["value"] = "1"  # far below required amount

    resp = client.post(
        "/generate",
        json={"wallet_address": "0x" + "1" * 40, "chain": "eth-mainnet"},
        headers={"X-PAYMENT": _encode(envelope)},
    )
    assert resp.status_code == 402
    assert resp.json()["error"] == "insufficient_payment"


def test_generate_with_wrong_recipient_returns_402(client: TestClient):
    envelope = _valid_authorization()
    envelope["payload"]["authorization"]["to"] = "0x000000000000000000000000000000000000ff"

    resp = client.post(
        "/generate",
        json={"wallet_address": "0x" + "1" * 40, "chain": "eth-mainnet"},
        headers={"X-PAYMENT": _encode(envelope)},
    )
    assert resp.status_code == 402
    assert resp.json()["error"] == "wrong_recipient"


@respx.mock
def test_demo_mode_bypass_skips_payment_check(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(payment, "DEMO_MODE", True)
    monkeypatch.setattr(payment, "DEMO_API_KEY", "test-demo-key")

    records = [
        {
            "chainIndex": "1",
            "txHash": f"0xhash{i}",
            "methodId": "0x",
            "nonce": str(i),
            "txTime": str(1_700_000_000_000 + i * 3_600_000),
            "from": [{"address": f"0xsender{i:034d}", "amount": ""}],
            "to": [{"address": f"0xreceiver{i:032d}", "amount": ""}],
            "tokenAddress": "",
            "amount": str(0.1 * (i + 1)),
            "symbol": "ETH",
            "txFee": "21000",
            "txStatus": "success",
        }
        for i in range(12)
    ]
    respx.get(url__regex=OKX_TX_LIST_RE).mock(
        return_value=httpx.Response(
            200, json={"code": "0", "data": [{"cursor": "", "transactionList": records}]}
        )
    )
    respx.get(url__regex=OKX_ADDR_SUMMARY_RE).mock(return_value=httpx.Response(200, json={"code": "1"}))

    # No X-PAYMENT header at all, but a valid demo key -> should pass the payment gate.
    resp = client.post(
        "/generate",
        json={"wallet_address": "0x" + "1" * 40, "chain": "eth-mainnet"},
        headers={"X-Demo-Key": "test-demo-key"},
    )
    assert resp.status_code == 200
