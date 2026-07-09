"""
services/api/main.py

FastAPI application entry point for SigilX.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from .routes import router
from .payment import x402_middleware


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    print("SigilX Chain Portrait - starting up")
    yield
    print("SigilX Chain Portrait - shutting down")


app = FastAPI(
    title="SigilX Chain Portrait",
    description=(
        "Turn any wallet's on-chain transaction history into a unique, "
        "deterministic SVG artwork. A2MCP service — wallet address in, "
        "Chain Portrait out. Powered by OKX Market API + X Layer."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (allow all for hackathon; restrict in production) ──────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── x402 payment gate ────────────────────────────────────────────────────────
app.middleware("http")(x402_middleware)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(router)


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    import os

    uvicorn.run(
        "services.api.main:app",
        host=os.getenv("SERVICE_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVICE_PORT", "8000")),
        reload=True,
        log_level="info",
    )
