"""
services/api/routes.py

FastAPI route handlers for SigilX.

Endpoints:
  POST /generate        — main generation endpoint (x402 gated)
  GET  /portrait/{id}   — retrieve cached portrait (no payment)
  GET  /health          — service health check
  GET  /chains          — list supported chains
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from web3 import Web3

from ..extractor.okx_client import OKXClient, SUPPORTED_CHAINS
from ..extractor.fingerprint import build_fingerprint, MINIMUM_TX_COUNT
from ..renderer.composer import render_portrait
from .mint import mint_portrait, get_portrait_token_id

router = APIRouter()

# ---------------------------------------------------------------------------
# Simple in-memory portrait cache  (replace with Redis for production)
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}

START_TIME = time.time()
VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    wallet_address: str
    chain: str = "eth-mainnet"

    @field_validator("wallet_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Invalid EVM address — must be 0x followed by 40 hex characters")
        return v.lower()

    @field_validator("chain")
    @classmethod
    def validate_chain(cls, v: str) -> str:
        if v not in SUPPORTED_CHAINS:
            raise ValueError(f"Unsupported chain '{v}'. Supported: {list(SUPPORTED_CHAINS)}")
        return v


class PortraitMetadata(BaseModel):
    title: str
    wallet: str
    chain: str
    generated_at: str
    tx_count: int
    svg_hash: str
    portrait_id: str


class GenerateResponse(BaseModel):
    portrait_id: str
    svg: str
    features: dict[str, float]
    metadata: dict[str, Any]
    cached: bool = False


class MintRequest(BaseModel):
    portrait_id: str
    to_address: str
    mint_fee_wei: int = 0

    @field_validator("to_address")
    @classmethod
    def validate_to_address(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Invalid EVM address")
        return v.lower()


class MintResponse(BaseModel):
    success: bool
    tx_hash: str = ""
    token_id: int = 0
    block_number: int = 0
    explorer_url: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=GenerateResponse, summary="Generate a Chain Portrait")
async def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Analyze a wallet's on-chain transaction history and generate a
    unique, deterministic SVG artwork reflecting its behavioral fingerprint.

    Requires x402 payment header in production. Use X-Demo-Key for judge testing.
    """
    portrait_id = _make_portrait_id(req.wallet_address, req.chain)

    # Return cached result if available
    if portrait_id in _cache:
        cached = _cache[portrait_id]
        return GenerateResponse(**cached, cached=True)

    # --- Fetch transaction data from OKX Market API ---
    async with OKXClient() as client:
        txs = await client.get_tx_history(req.wallet_address, req.chain, limit=1000)
        try:
            analysis = await client.get_address_analysis(req.wallet_address, req.chain)
        except Exception:
            analysis = None  # supplemental only — degrade gracefully

    if len(txs) < MINIMUM_TX_COUNT:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "insufficient_history",
                "tx_count": len(txs),
                "minimum_required": MINIMUM_TX_COUNT,
                "message": f"Wallet has only {len(txs)} transactions. Minimum {MINIMUM_TX_COUNT} required.",
            },
        )

    # --- Extract behavioral fingerprint ---
    fv = build_fingerprint(txs, analysis)

    # --- Render SVG ---
    svg = render_portrait(req.wallet_address, req.chain, fv)
    svg_hash = _keccak_hex(svg)

    # --- Build metadata ---
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    metadata = {
        "title": f"Chain Portrait · {req.wallet_address[:6]}…{req.wallet_address[-4:]}",
        "wallet": req.wallet_address,
        "chain": req.chain,
        "generated_at": generated_at,
        "tx_count": len(txs),
        "svg_hash": svg_hash,
        "portrait_id": portrait_id,
    }

    result = {
        "portrait_id": portrait_id,
        "svg": svg,
        "features": fv.to_dict(),
        "metadata": metadata,
    }

    # Cache the result
    _cache[portrait_id] = result

    return GenerateResponse(**result)


@router.get(
    "/portrait/{portrait_id}",
    summary="Retrieve a cached portrait",
    responses={
        200: {"content": {"image/svg+xml": {}}},
        404: {"description": "Portrait not found"},
    },
)
async def get_portrait(portrait_id: str, format: str = "json"):
    """
    Retrieve a previously generated portrait by ID.
    No payment required — this is the shareable endpoint.
    Use ?format=svg to get the raw SVG.
    """
    if portrait_id not in _cache:
        raise HTTPException(status_code=404, detail={"error": "portrait_not_found", "portrait_id": portrait_id})

    cached = _cache[portrait_id]

    if format == "svg":
        return Response(content=cached["svg"], media_type="image/svg+xml")

    return cached


@router.get("/health", summary="Service health check")
async def health():
    """Returns service health, uptime, and version. No auth required."""
    return {
        "status": "ok",
        "service": "SigilX Chain Portrait",
        "version": VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "cached_portraits": len(_cache),
    }


@router.get("/chains", summary="List supported chains")
async def chains():
    """Returns all chains supported by the generation endpoint."""
    return {
        "supported_chains": [
            {"id": chain_id, "chain_id": cid}
            for chain_id, cid in SUPPORTED_CHAINS.items()
        ]
    }


@router.post("/mint", response_model=MintResponse, summary="Mint a Chain Portrait NFT on X Layer")
async def mint(req: MintRequest) -> MintResponse:
    """
    Mint a previously generated portrait as an ERC-721 NFT on X Layer.

    The portrait must have been generated first via POST /generate.
    The to_address receives the NFT. No x402 payment required for this endpoint —
    the on-chain mint fee (if set) is paid via mint_fee_wei.
    """
    # Portrait must exist in cache
    if req.portrait_id not in _cache:
        raise HTTPException(
            status_code=404,
            detail={"error": "portrait_not_found", "portrait_id": req.portrait_id},
        )

    cached = _cache[req.portrait_id]
    meta = cached["metadata"]
    features = cached["features"]

    result = await mint_portrait(
        to_address=req.to_address,
        wallet_address=meta["wallet"],
        source_chain=meta["chain"],
        portrait_id=req.portrait_id,
        svg=cached["svg"],
        feature_vector=features,
        tx_count=meta["tx_count"],
        mint_fee_wei=req.mint_fee_wei,
    )

    if result.success:
        # Store token_id in cache for status lookups
        _cache[req.portrait_id]["token_id"] = result.token_id
        _cache[req.portrait_id]["tx_hash"] = result.tx_hash
        _cache[req.portrait_id]["explorer_url"] = result.explorer_url

    return MintResponse(**result.to_dict())


@router.get("/mint/{portrait_id}/status", summary="Check mint status for a portrait")
async def mint_status(portrait_id: str):
    """
    Check whether a portrait has been minted on X Layer.
    Returns the tokenId if minted, null if not yet minted.
    """
    cached = _cache.get(portrait_id)

    # Check local cache first
    if cached and cached.get("token_id"):
        return {
            "minted": True,
            "token_id": cached["token_id"],
            "tx_hash": cached.get("tx_hash", ""),
            "explorer_url": cached.get("explorer_url", ""),
        }

    # Fallback: query the contract directly
    token_id = await get_portrait_token_id(portrait_id)
    if token_id is not None:
        return {"minted": True, "token_id": token_id, "tx_hash": "", "explorer_url": ""}

    return {"minted": False, "token_id": None}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_portrait_id(wallet: str, chain: str) -> str:
    """Deterministic portrait ID: cp_ + first 16 chars of SHA-256(wallet:chain)."""
    raw = hashlib.sha256(f"{wallet}:{chain}".encode()).hexdigest()
    return f"cp_{raw[:16]}"


def _keccak_hex(svg: str) -> str:
    """keccak256(svg), 0x-prefixed — matches the hash mint.py computes on-chain."""
    raw = Web3.keccak(text=svg).hex()
    return raw if raw.startswith("0x") else f"0x{raw}"
