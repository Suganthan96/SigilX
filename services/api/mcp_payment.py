"""
services/api/mcp_payment.py

x402 payment gate for the MCP server (mcp_server.py).

FastMCP's SSE transport has no request/response cycle a FastAPI-style
`app.middleware("http")` hook can attach to (see payment.py's docstring for
that one) — each MCP tool call instead arrives as its own HTTP POST to the
transport's message endpoint (default `/messages/`), with the JSON-RPC
envelope in the body and the actual result delivered later over the separate
SSE stream. So this gates payment one level lower, as raw ASGI middleware
that inspects each POST body for a `tools/call` targeting the paid tool,
and reuses payment.py's validation/settlement/pricing logic so both
endpoints stay governed by one set of asset/price env vars.

Docs: https://web3.okx.com/onchainos/dev-docs/okxai/howtomcp
"""

from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from . import payment

PAID_TOOL_NAME = "generate_chain_portrait"


class McpPaymentMiddleware:
    """Gates POST .../messages `tools/call` -> PAID_TOOL_NAME behind x402."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        body, replay_receive = await _buffer_body(receive)

        if not _is_paid_tool_call(body):
            await self.app(scope, replay_receive, send)
            return

        if payment._is_free_tier():
            await self.app(scope, replay_receive, send)
            return

        request = Request(scope, receive=replay_receive)

        if payment.DEMO_MODE and payment.DEMO_API_KEY:
            if request.headers.get("x-demo-key", "") == payment.DEMO_API_KEY:
                await self.app(scope, replay_receive, send)
                return

        payment_header = request.headers.get("x-payment", "")
        if not payment_header:
            await _send_402(scope, send, request, "payment_required")
            return

        valid, reason, payload = payment._parse_and_validate_payment(payment_header)
        if not valid:
            await _send_402(scope, send, request, reason)
            return

        settled, _settlement_info = await payment._facilitator_verify_and_settle(payload)
        if not settled:
            await _send_402(scope, send, request, "settlement_failed")
            return

        await self.app(scope, replay_receive, send)


async def _buffer_body(receive: Receive) -> tuple[bytes, Receive]:
    """Drain the ASGI receive channel and return a replay so the downstream
    MCP handler can still read the same body once we're done inspecting it."""
    chunks: list[bytes] = []
    more_body = True
    while more_body:
        message = await receive()
        chunks.append(message.get("body", b""))
        more_body = message.get("more_body", False)
    body = b"".join(chunks)

    async def replay() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    return body, replay


def _is_paid_tool_call(body: bytes) -> bool:
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return (
        parsed.get("method") == "tools/call"
        and parsed.get("params", {}).get("name") == PAID_TOOL_NAME
    )


async def _send_402(scope: Scope, send: Send, request: Request, reason: str) -> None:
    response = JSONResponse(
        status_code=402,
        headers={"X-Payment-Required": "true"},
        content={
            "x402Version": payment.X402_VERSION,
            "error": reason,
            "resource": payment._resource(request),
            "accepts": [payment._payment_requirements(request)],
        },
    )
    await response(scope, request.receive, send)
