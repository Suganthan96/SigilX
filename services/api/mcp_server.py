"""
services/api/mcp_server.py

FastMCP server — exposes SigilX as an MCP tool callable by any AI agent.

Tool: generate_chain_portrait
  Input:  wallet_address (str), chain (str)
  Output: portrait_id, svg, features, metadata

Run standalone:
  python -m services.api.mcp_server

Or mount on the FastAPI app for combined serving.

Docs: https://web3.okx.com/onchainos/dev-docs/okxai/howtomcp
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys

# FastMCP: pip install fastmcp
try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP not installed. Run: pip install fastmcp")
    sys.exit(1)

from web3 import Web3

from ..extractor.okx_client import OKXClient, SUPPORTED_CHAINS
from ..extractor.fingerprint import build_fingerprint, MINIMUM_TX_COUNT
from ..renderer.composer import render_portrait


def _keccak_hex(svg: str) -> str:
    """keccak256(svg), 0x-prefixed — matches the hash mint.py computes on-chain."""
    raw = Web3.keccak(text=svg).hex()
    return raw if raw.startswith("0x") else f"0x{raw}"


# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="SigilX Chain Portrait",
    instructions=(
        "SigilX analyzes any EVM wallet's on-chain transaction history using "
        "chaos mathematics (Sample Entropy, Correlation Dimension, Burstiness) "
        "and generates a unique, deterministic SVG artwork — a Chain Portrait — "
        "reflecting that wallet's behavioral fingerprint. "
        "Same wallet always produces the same portrait. Fully reproducible. "
        "Built natively on OKX Market API + X Layer."
    ),
)

# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_chain_portrait(
    wallet_address: str,
    chain: str = "eth-mainnet",
) -> dict:
    """
    Analyze a wallet's on-chain transaction history and generate a unique,
    deterministic SVG artwork (Chain Portrait) reflecting its behavioral fingerprint.

    Args:
        wallet_address: EVM wallet address (0x-prefixed, 42 characters).
        chain:          Blockchain to query. Supported values:
                        eth-mainnet, polygon-mainnet, bsc-mainnet,
                        xlayer-mainnet, arbitrum-mainnet, optimism-mainnet, base-mainnet.
                        Defaults to eth-mainnet.

    Returns:
        A dict with:
          - portrait_id: Deterministic ID for this wallet+chain combination.
          - svg:         Complete SVG string (600×600px) with CSS animations.
          - features:    8-dimension behavioral fingerprint (all values in [0,1]).
          - metadata:    title, wallet, chain, tx_count, svg_hash, generated_at.

    Errors:
        - ValueError if wallet_address is not a valid EVM address.
        - ValueError if chain is not supported.
        - RuntimeError if the wallet has fewer than 10 transactions.
    """
    # Normalize
    wallet_address = wallet_address.strip().lower()
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise ValueError(f"Invalid EVM address: '{wallet_address}'")

    if chain not in SUPPORTED_CHAINS:
        raise ValueError(
            f"Unsupported chain '{chain}'. Supported: {list(SUPPORTED_CHAINS)}"
        )

    # Fetch OKX tx data
    async with OKXClient() as client:
        txs = await client.get_tx_history(wallet_address, chain, limit=1000)
        try:
            analysis = await client.get_address_analysis(wallet_address, chain)
        except Exception:
            analysis = None

    if len(txs) < MINIMUM_TX_COUNT:
        raise RuntimeError(
            f"Wallet has only {len(txs)} transactions. "
            f"Minimum {MINIMUM_TX_COUNT} required to generate a portrait."
        )

    # Extract fingerprint
    fv = build_fingerprint(txs, analysis)

    # Render SVG
    svg = render_portrait(wallet_address, chain, fv)
    svg_hash = _keccak_hex(svg)

    # Portrait ID
    portrait_id = "cp_" + hashlib.sha256(f"{wallet_address}:{chain}".encode()).hexdigest()[:16]

    import time
    return {
        "portrait_id": portrait_id,
        "svg": svg,
        "features": fv.to_dict(),
        "metadata": {
            "title": f"Chain Portrait · {wallet_address[:6]}…{wallet_address[-4:]}",
            "wallet": wallet_address,
            "chain": chain,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tx_count": len(txs),
            "svg_hash": svg_hash,
            "portrait_id": portrait_id,
        },
    }


# ---------------------------------------------------------------------------
# Standalone entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8001"))
    print(f"SigilX MCP server starting on port {port}")
    mcp.run(transport="sse", port=port)
