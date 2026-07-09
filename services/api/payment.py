"""
services/api/payment.py

x402 payment middleware for SigilX.

Implements the wire format of the real x402 protocol (https://github.com/coinbase/x402,
which OKX's Onchain OS Payment SDK is explicitly built on):

  - Unpaid POST /generate -> HTTP 402 with a body listing payment requirements
    (`x402Version` + `accepts[]`), not an ad-hoc shape.
  - Paid retries carry an `X-PAYMENT` header: base64 JSON containing an EIP-3009
    `transferWithAuthorization` payload signed via EIP-712.
  - Verification/settlement of that signed authorization is done by a facilitator
    (OKX calls theirs the "Broker") — sellers don't submit transactions themselves.

What's still open: the actual call to OKX's Broker (its endpoint, auth, and exact
request/response shape) is only documented through their interactive
`npx skills add okx/onchainos-skills` installer, not the public docs, so it isn't
implemented here. `_facilitator_verify_and_settle` is the single integration point —
wire the real Broker call in there once that's available. Until `X402_FACILITATOR_URL`
is set, this module does structural/expiry/amount validation only and logs a warning
instead of settling on-chain, so local dev and DEMO_MODE keep working.

Reference: https://web3.okx.com/onchainos/dev-docs/payments/service-seller
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any, Callable

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger("sigilx.payment")

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_API_KEY = os.getenv("DEMO_API_KEY", "")
PAYMENT_WALLET = os.getenv("PAYMENT_WALLET", "")
SERVICE_PRICE_OKB = os.getenv("SERVICE_PRICE_OKB", "0.1")

X402_VERSION = 1
X402_NETWORK = os.getenv("X402_NETWORK", "eip155:196")  # X Layer mainnet
X402_ASSET = os.getenv("X402_ASSET", "")  # ERC-20/3009-compatible payment token address
X402_FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "")  # OKX Broker endpoint, once known
X402_MAX_TIMEOUT_SECONDS = 300


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

async def x402_middleware(request: Request, call_next: Callable) -> Response:
    """
    FastAPI middleware that gates POST /generate behind x402 payment.

    Flow:
      1. Skip non-generate routes.
      2. In DEMO_MODE, allow requests with the demo API key.
      3. Otherwise, require and validate the X-PAYMENT header.
      4. Reject with 402 if payment is missing or invalid.
    """
    if request.url.path == "/generate" and request.method == "POST":
        if DEMO_MODE and DEMO_API_KEY:
            demo_key = request.headers.get("X-Demo-Key", "")
            if demo_key == DEMO_API_KEY:
                return await call_next(request)

        payment_header = request.headers.get("X-PAYMENT", "")
        if not payment_header:
            return _payment_required_response(request)

        valid, reason, payload = _parse_and_validate_payment(payment_header)
        if not valid:
            return JSONResponse(
                status_code=402,
                content={
                    "x402Version": X402_VERSION,
                    "error": reason,
                    "accepts": [_payment_requirements(request)],
                },
            )

        settled, settlement_info = await _facilitator_verify_and_settle(payload)
        if not settled:
            return JSONResponse(
                status_code=402,
                content={
                    "x402Version": X402_VERSION,
                    "error": "settlement_failed",
                    "accepts": [_payment_requirements(request)],
                },
            )

        response = await call_next(request)
        response.headers["X-PAYMENT-RESPONSE"] = base64.b64encode(
            json.dumps(settlement_info).encode()
        ).decode()
        return response

    return await call_next(request)


# ---------------------------------------------------------------------------
# X-PAYMENT header parsing + structural validation
# ---------------------------------------------------------------------------

def _parse_and_validate_payment(header_value: str) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Decode and structurally validate the X-PAYMENT header.

    This checks shape, expiry, recipient, and amount — everything that can be
    verified without a facilitator. It does NOT verify the EIP-712 signature
    itself; that's the facilitator's job (see `_facilitator_verify_and_settle`).
    """
    try:
        padded = header_value + "=" * (-len(header_value) % 4)
        decoded = base64.b64decode(padded).decode("utf-8")
        envelope = json.loads(decoded)
    except Exception:
        return False, "malformed_payment_header", None

    if envelope.get("x402Version") != X402_VERSION:
        return False, "unsupported_x402_version", None
    if envelope.get("scheme") != "exact":
        return False, "unsupported_scheme", None

    payload = envelope.get("payload", {})
    authorization = payload.get("authorization", {})
    signature = payload.get("signature", "")

    if not signature or not isinstance(authorization, dict):
        return False, "missing_signature_or_authorization", None

    required_fields = ("from", "to", "value", "validAfter", "validBefore", "nonce")
    if any(field not in authorization for field in required_fields):
        return False, "incomplete_authorization", None

    now = int(time.time())
    try:
        valid_after = int(authorization["validAfter"])
        valid_before = int(authorization["validBefore"])
    except (TypeError, ValueError):
        return False, "invalid_authorization_window", None

    if not (valid_after <= now < valid_before):
        return False, "authorization_expired_or_not_yet_valid", None

    if PAYMENT_WALLET and authorization["to"].lower() != PAYMENT_WALLET.lower():
        return False, "wrong_recipient", None

    try:
        paid_value = int(authorization["value"])
    except (TypeError, ValueError):
        return False, "invalid_value", None

    required_atomic = _required_atomic_amount()
    if required_atomic is not None and paid_value < required_atomic:
        return False, "insufficient_payment", None

    return True, "ok", envelope


# ---------------------------------------------------------------------------
# Facilitator (OKX "Broker") integration point
# ---------------------------------------------------------------------------

async def _facilitator_verify_and_settle(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """
    Hand the signed authorization to the facilitator for signature verification
    and on-chain settlement.

    TODO: point this at OKX's Broker once its endpoint/auth are known (via the
    `onchainos-skills` installer referenced in README.md). Expected shape, per
    the x402 facilitator pattern: POST {url}/verify then POST {url}/settle with
    this envelope, returning a settlement receipt (tx hash, payer, amount).
    """
    if not X402_FACILITATOR_URL:
        logger.warning(
            "X402_FACILITATOR_URL not set — skipping on-chain settlement. "
            "Payment passed structural validation only; wire in the real OKX "
            "Broker call before accepting this in production."
        )
        return True, {"settled": False, "reason": "no_facilitator_configured"}

    async with httpx.AsyncClient(base_url=X402_FACILITATOR_URL, timeout=15.0) as client:
        verify_resp = await client.post("/verify", json=payload)
        if verify_resp.status_code != 200 or not verify_resp.json().get("isValid"):
            return False, {"settled": False, "reason": "facilitator_rejected"}

        settle_resp = await client.post("/settle", json=payload)
        if settle_resp.status_code != 200:
            return False, {"settled": False, "reason": "facilitator_settlement_failed"}

        return True, settle_resp.json()


# ---------------------------------------------------------------------------
# 402 response builders
# ---------------------------------------------------------------------------

def _payment_required_response(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=402,
        headers={"X-Payment-Required": "true"},
        content={
            "x402Version": X402_VERSION,
            "error": "payment_required",
            "accepts": [_payment_requirements(request)],
        },
    )


def _payment_requirements(request: Request) -> dict[str, Any]:
    return {
        "scheme": "exact",
        "network": X402_NETWORK,
        "maxAmountRequired": str(_required_atomic_amount() or 0),
        "resource": str(request.url),
        "description": "SigilX Chain Portrait generation",
        "mimeType": "application/json",
        "payTo": PAYMENT_WALLET,
        "maxTimeoutSeconds": X402_MAX_TIMEOUT_SECONDS,
        "asset": X402_ASSET,
    }


def _required_atomic_amount() -> int | None:
    """Service price in whole OKB converted to wei (18 decimals)."""
    try:
        return int(float(SERVICE_PRICE_OKB) * 10**18)
    except (TypeError, ValueError):
        return None
