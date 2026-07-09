"""
tests/test_api.py

Tests the FastAPI route handlers directly (mounted without the x402
payment middleware, since that's a separate concern) with the OKX Market
API mocked via respx so no network calls happen.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.mint import MintResult
from services.api.routes import router

OKX_TX_LIST_RE = r".*/api/v5/wallet/post-transaction/transactions-by-address.*"
OKX_ADDR_SUMMARY_RE = r".*/api/v5/explorer/address/address-summary.*"


def _addr(tag: str) -> str:
    """Build a syntactically valid 0x + 40 hex-char address, unique per test."""
    return "0x" + tag.rjust(40, "0")


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app())


def _tx_list_response(n: int) -> httpx.Response:
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
        for i in range(n)
    ]
    return httpx.Response(
        200, json={"code": "0", "data": [{"cursor": "", "transactionList": records}]}
    )


def _mock_okx(respx_mock, tx_count: int) -> None:
    respx_mock.get(url__regex=OKX_TX_LIST_RE).mock(return_value=_tx_list_response(tx_count))
    respx_mock.get(url__regex=OKX_ADDR_SUMMARY_RE).mock(
        return_value=httpx.Response(200, json={"code": "1"})  # degrade gracefully -> AddressAnalysis()
    )


# ---------------------------------------------------------------------------
# Simple endpoints
# ---------------------------------------------------------------------------

def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "uptime_seconds" in body


def test_chains(client: TestClient):
    resp = client.get("/chains")
    assert resp.status_code == 200
    chains = resp.json()["supported_chains"]
    assert any(c["id"] == "eth-mainnet" for c in chains)


# ---------------------------------------------------------------------------
# /generate
# ---------------------------------------------------------------------------

@respx.mock
def test_generate_success(client: TestClient):
    _mock_okx(respx.mock, tx_count=15)
    wallet = _addr("1")

    resp = client.post("/generate", json={"wallet_address": wallet, "chain": "eth-mainnet"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["portrait_id"].startswith("cp_")
    assert body["svg"].startswith("<svg")
    assert set(body["features"].keys()) == {
        "activity_entropy", "timing_regularity", "amount_variance",
        "interaction_diversity", "burst_coefficient", "recency_decay",
        "volume_skew", "chaos_dimension",
    }
    assert body["metadata"]["svg_hash"].startswith("0x")
    assert len(body["metadata"]["svg_hash"]) == 66  # 0x + 64 hex chars
    assert body["metadata"]["tx_count"] == 15


@respx.mock
def test_generate_is_cached_on_second_call(client: TestClient):
    _mock_okx(respx.mock, tx_count=12)
    wallet = _addr("2")

    first = client.post("/generate", json={"wallet_address": wallet, "chain": "eth-mainnet"})
    second = client.post("/generate", json={"wallet_address": wallet, "chain": "eth-mainnet"})

    assert first.json()["svg"] == second.json()["svg"]
    assert second.json()["cached"] is True


@respx.mock
def test_generate_insufficient_history_returns_400(client: TestClient):
    _mock_okx(respx.mock, tx_count=3)
    wallet = _addr("3")

    resp = client.post("/generate", json={"wallet_address": wallet, "chain": "eth-mainnet"})

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "insufficient_history"


def test_generate_rejects_malformed_wallet_address(client: TestClient):
    resp = client.post("/generate", json={"wallet_address": "not-an-address", "chain": "eth-mainnet"})
    assert resp.status_code == 422


def test_generate_rejects_unsupported_chain(client: TestClient):
    resp = client.post("/generate", json={"wallet_address": _addr("4"), "chain": "not-a-real-chain"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /portrait/{id}
# ---------------------------------------------------------------------------

def test_portrait_not_found(client: TestClient):
    resp = client.get("/portrait/cp_doesnotexist")
    assert resp.status_code == 404


@respx.mock
def test_portrait_roundtrip(client: TestClient):
    _mock_okx(respx.mock, tx_count=12)
    wallet = _addr("5")

    generated = client.post("/generate", json={"wallet_address": wallet, "chain": "eth-mainnet"}).json()
    portrait_id = generated["portrait_id"]

    as_json = client.get(f"/portrait/{portrait_id}")
    assert as_json.status_code == 200
    assert as_json.json()["svg"] == generated["svg"]

    as_svg = client.get(f"/portrait/{portrait_id}", params={"format": "svg"})
    assert as_svg.status_code == 200
    assert as_svg.headers["content-type"].startswith("image/svg+xml")
    assert as_svg.text == generated["svg"]


# ---------------------------------------------------------------------------
# /mint
# ---------------------------------------------------------------------------

def test_mint_unknown_portrait_returns_404(client: TestClient):
    resp = client.post("/mint", json={"portrait_id": "cp_doesnotexist", "to_address": _addr("6")})
    assert resp.status_code == 404


@respx.mock
@patch("services.api.routes.mint_portrait", new_callable=AsyncMock)
def test_mint_success(mock_mint_portrait: AsyncMock, client: TestClient):
    _mock_okx(respx.mock, tx_count=12)
    wallet = _addr("7")
    generated = client.post("/generate", json={"wallet_address": wallet, "chain": "eth-mainnet"}).json()

    mock_mint_portrait.return_value = MintResult(
        success=True,
        tx_hash="0xdeadbeef",
        token_id=1,
        block_number=42,
        explorer_url="https://www.oklink.com/xlayer-test/tx/0xdeadbeef",
    )

    resp = client.post("/mint", json={"portrait_id": generated["portrait_id"], "to_address": _addr("8")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["token_id"] == 1
    mock_mint_portrait.assert_awaited_once()
