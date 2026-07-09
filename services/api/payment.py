"""
services/api/payment.py

x402 payment middleware for SigilX.

In production, this intercepts every POST /generate and verifies an
OKX Payment SDK payment token in the X-Payment header.

In DEMO_MODE (set via env), a DEMO_API_KEY header bypasses the gate
so judges can test without going through the full payment flow.

Reference: https://web3.okx.com/onchainos/dev-docs/payments/service-seller
"""

from __future__ import annotations

import os
import json
import hashlib
import hmac
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse


DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_API_KEY = os.getenv("DEMO_API_KEY", "")
PAYMENT_SECRET = os.getenv("PAYMENT_SECRET", "")
PAYMENT_WALLET = os.getenv("PAYMENT_WALLET", "")
SERVICE_PRICE_OKB = os.getenv("SERVICE_PRICE_OKB", "0.1")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

async def x402_middleware(request: Request, call_next: Callable) -> Response:
    """
    FastAPI middleware that gates POST /generate behind x402 payment.

    Flow:
      1. Skip non-generate routes.
      2. In DEMO_MODE, allow requests with the demo API key.
      3. Otherwise, verify the X-Payment header token.
      4. Reject with 402 if payment is missing or invalid.
    """
    if request.url.path == "/generate" and request.method == "POST":
        # ── Demo bypass ──────────────────────────────────────────────────────
        if DEMO_MODE and DEMO_API_KEY:
            demo_key = request.headers.get("X-Demo-Key", "")
            if demo_key == DEMO_API_KEY:
                return await call_next(request)

        # ── Production x402 gate ─────────────────────────────────────────────
        payment_header = request.headers.get("X-Payment", "")
        if not payment_header:
            return _payment_required_response(request)

        valid, reason = _verify_payment_token(payment_header)
        if not valid:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "payment_invalid",
                    "reason": reason,
                    "x402_details": _payment_details(request),
                },
            )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Payment verification
# ---------------------------------------------------------------------------

def _verify_payment_token(token: str) -> tuple[bool, str]:
    """
    Verify the OKX Payment SDK token from the X-Payment header.

    In the real integration, this calls the OKX Payment SDK's
    verify_payment() function. Here we implement the HMAC check
    that the SDK uses internally.

    Token format (JSON encoded, base64):
      {
        "wallet": "0x...",
        "amount": "0.1",
        "currency": "OKB",
        "timestamp": 1234567890,
        "nonce": "abc123",
        "sig": "<hmac-sha256>"
      }
    """
    import base64

    if not PAYMENT_SECRET:
        # If no secret configured, accept all (dev mode)
        return True, "ok"

    try:
        decoded = base64.b64decode(token + "==").decode("utf-8")
        payload = json.loads(decoded)
    except Exception:
        return False, "malformed token"

    # Check expiry (token valid for 5 minutes)
    token_ts = int(payload.get("timestamp", 0))
    if abs(time.time() - token_ts) > 300:
        return False, "token expired"

    # Verify HMAC
    sig = payload.pop("sig", "")
    message = json.dumps(payload, sort_keys=True)
    expected = hmac.new(PAYMENT_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False, "invalid signature"

    # Check amount
    paid_amount = float(payload.get("amount", 0))
    required = float(SERVICE_PRICE_OKB)
    if paid_amount < required:
        return False, f"insufficient payment: paid {paid_amount} OKB, required {required} OKB"

    return True, "ok"


# ---------------------------------------------------------------------------
# 402 response builder
# ---------------------------------------------------------------------------

def _payment_required_response(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=402,
        headers={"X-Payment-Required": "true"},
        content={
            "error": "payment_required",
            "message": "This endpoint requires payment. Include a valid X-Payment token.",
            "x402_details": _payment_details(request),
        },
    )


def _payment_details(request: Request) -> dict:
    return {
        "service": "SigilX Chain Portrait",
        "price": SERVICE_PRICE_OKB,
        "currency": "OKB",
        "payment_wallet": PAYMENT_WALLET,
        "payment_sdk": "OKX Onchain OS Payment SDK",
        "docs": "https://web3.okx.com/onchainos/dev-docs/payments/service-seller",
        "endpoint": str(request.url),
    }
