"""
services/extractor/okx_client.py

Thin authenticated wrapper over OKX Market API.
Uses: Transaction History by Address + Address Analysis endpoints.

Docs: https://web3.okx.com/onchainos/dev-docs/market/market-api-introduction
"""

from __future__ import annotations

import hashlib
import hmac
import base64
import time
import os
from dataclasses import dataclass, field
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OKX_BASE_URL = "https://www.okx.com"
OKX_API_KEY = os.getenv("OKX_API_KEY", "")
OKX_SECRET_KEY = os.getenv("OKX_SECRET_KEY", "")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")

# Chain identifiers accepted by OKX Market API
SUPPORTED_CHAINS: dict[str, str] = {
    "eth-mainnet":     "1",
    "polygon-mainnet": "137",
    "bsc-mainnet":     "56",
    "xlayer-mainnet":  "196",
    "arbitrum-mainnet":"42161",
    "optimism-mainnet":"10",
    "base-mainnet":    "8453",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TxRecord:
    """Normalised single transaction record from OKX TX History API."""
    hash: str
    from_addr: str
    to_addr: str
    value_eth: float          # native token amount, normalised to ETH units
    timestamp: int            # Unix epoch seconds
    block_number: int
    gas_used: int
    is_error: bool
    method_id: str            # "0x" for plain transfers, "0xa9059cbb" for ERC-20, etc.


@dataclass
class AddressAnalysis:
    """Summary signals from OKX Address Analysis API."""
    total_tx_count: int = 0
    unique_counterparties: int = 0
    first_tx_timestamp: int = 0
    last_tx_timestamp: int = 0
    total_volume_usd: float = 0.0
    avg_tx_value_usd: float = 0.0
    risk_score: float = 0.0   # 0 = clean, 1 = high risk


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    """Generate OKX HMAC-SHA256 signature."""
    message = f"{timestamp}{method.upper()}{path}{body}"
    mac = hmac.new(OKX_SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def _headers(method: str, path: str, body: str = "") -> dict:
    ts = str(time.time())
    return {
        "OK-ACCESS-KEY":        OKX_API_KEY,
        "OK-ACCESS-SIGN":       _sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP":  ts,
        "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        "Content-Type":         "application/json",
    }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class OKXClient:
    """
    Async-friendly OKX Market API client.

    Usage:
        async with OKXClient() as client:
            txs = await client.get_tx_history("0xabc...", "eth-mainnet")
    """

    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    async def __aenter__(self) -> "OKXClient":
        self._http = httpx.AsyncClient(base_url=OKX_BASE_URL, timeout=self._timeout)
        return self

    async def __aexit__(self, *args) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Transaction History
    # ------------------------------------------------------------------

    async def get_tx_history(
        self,
        wallet_address: str,
        chain: str = "eth-mainnet",
        limit: int = 1000,
    ) -> list[TxRecord]:
        """
        Fetch up to `limit` most-recent transactions for a wallet.

        OKX endpoint: GET /api/v5/explorer/address/transaction-list
        Docs: Transaction History by Address
        """
        chain_id = SUPPORTED_CHAINS.get(chain)
        if chain_id is None:
            raise ValueError(f"Unsupported chain: {chain}. Supported: {list(SUPPORTED_CHAINS)}")

        path = "/api/v5/explorer/address/transaction-list"
        params = {
            "chainShortName": _chain_short(chain),
            "address": wallet_address,
            "limit": min(limit, 100),   # OKX max per page is 100; we paginate
        }

        all_txs: list[TxRecord] = []
        page = 1

        while len(all_txs) < limit:
            params["page"] = str(page)
            response = await self._http.get(
                path,
                params=params,
                headers=_headers("GET", f"{path}?{_build_qs(params)}"),
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "0":
                raise RuntimeError(f"OKX API error: {data.get('msg', 'unknown')}")

            records = data.get("data", [{}])[0].get("transactionLists", [])
            if not records:
                break

            for r in records:
                all_txs.append(_parse_tx(r))

            if len(records) < 100:
                break   # last page
            page += 1

        return all_txs[:limit]

    # ------------------------------------------------------------------
    # Address Analysis
    # ------------------------------------------------------------------

    async def get_address_analysis(
        self,
        wallet_address: str,
        chain: str = "eth-mainnet",
    ) -> AddressAnalysis:
        """
        Fetch high-level address summary from OKX Address Analysis API.

        OKX endpoint: GET /api/v5/explorer/address/address-summary
        """
        path = "/api/v5/explorer/address/address-summary"
        params = {
            "chainShortName": _chain_short(chain),
            "address": wallet_address,
        }

        response = await self._http.get(
            path,
            params=params,
            headers=_headers("GET", f"{path}?{_build_qs(params)}"),
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "0":
            # Address analysis is supplemental — degrade gracefully
            return AddressAnalysis()

        return _parse_analysis(data.get("data", [{}])[0])


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_tx(raw: dict) -> TxRecord:
    """Normalise a raw OKX transaction record."""
    return TxRecord(
        hash=raw.get("txId", ""),
        from_addr=(raw.get("from", [{}])[0].get("address", "") if isinstance(raw.get("from"), list) else raw.get("from", "")),
        to_addr=(raw.get("to", [{}])[0].get("address", "") if isinstance(raw.get("to"), list) else raw.get("to", "")),
        value_eth=_safe_float(raw.get("amount", raw.get("value", "0"))),
        timestamp=_safe_int(raw.get("transactionTime", raw.get("blockTime", 0))) // 1000,
        block_number=_safe_int(raw.get("height", raw.get("blockHeight", 0))),
        gas_used=_safe_int(raw.get("gasUsed", 0)),
        is_error=str(raw.get("state", "2")) not in ("2", "success"),
        method_id=raw.get("methodId", "0x"),
    )


def _parse_analysis(raw: dict) -> AddressAnalysis:
    return AddressAnalysis(
        total_tx_count=_safe_int(raw.get("totalTransactionCount", 0)),
        unique_counterparties=_safe_int(raw.get("uniqueAddressCount", 0)),
        first_tx_timestamp=_safe_int(raw.get("firstTransactionTime", 0)) // 1000,
        last_tx_timestamp=_safe_int(raw.get("lastTransactionTime", 0)) // 1000,
        total_volume_usd=_safe_float(raw.get("totalTransactionValue", "0")),
        avg_tx_value_usd=_safe_float(raw.get("avgTransactionValue", "0")),
        risk_score=_safe_float(raw.get("riskScore", "0")) / 100.0,
    )


def _chain_short(chain: str) -> str:
    mapping = {
        "eth-mainnet": "ETH",
        "polygon-mainnet": "POLYGON",
        "bsc-mainnet": "BSC",
        "xlayer-mainnet": "XLAYER",
        "arbitrum-mainnet": "ARBITRUM",
        "optimism-mainnet": "OPTIMISM",
        "base-mainnet": "BASE",
    }
    return mapping.get(chain, chain.upper())


def _build_qs(params: dict) -> str:
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()))


def _safe_float(val) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0
