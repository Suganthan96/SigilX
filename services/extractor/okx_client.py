"""
services/extractor/okx_client.py

Thin authenticated wrapper over OKX's Wallet API (transaction history) and
Market API (address analysis, best-effort/unverified).

The transaction-history endpoint, its request shape, and its response shape
below were confirmed empirically against the live API (the public docs for
this endpoint render client-side and don't expose the spec to a plain fetch).
Real endpoint: GET https://web3.okx.com/api/v5/wallet/post-transaction/transactions-by-address
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import base64
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OKX_BASE_URL = "https://web3.okx.com"
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
    # OKX's V5 signing scheme requires an ISO 8601 UTC timestamp (e.g.
    # "2020-12-08T09:08:57.715Z"), not a raw Unix epoch — a bare epoch fails
    # signature verification with "Invalid OK-ACCESS-TIMESTAMP".
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
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
    # Request helper: retry on 429 with backoff
    # ------------------------------------------------------------------

    async def _get_with_retry(
        self,
        url: str,
        headers: dict,
        max_retries: int = 4,
    ) -> httpx.Response:
        """
        GET with retry-on-429. Trial-tier OKX keys have a low requests/sec
        cap, and a single wallet's paginated tx history can need several
        sequential calls — enough on its own to trip that limit without any
        other traffic. Honors `Retry-After` when OKX sends it, otherwise
        backs off exponentially (0.5s, 1s, 2s, 4s).
        """
        backoff = 0.5
        for attempt in range(max_retries + 1):
            response = await self._http.get(url, headers=headers)
            if response.status_code != 429:
                response.raise_for_status()
                return response

            if attempt == max_retries:
                response.raise_for_status()  # exhausted retries -> surface the 429

            wait = float(response.headers.get("Retry-After", backoff))
            await asyncio.sleep(wait)
            backoff *= 2
            # A fresh timestamp/signature is required for the retried request.
            headers = _headers("GET", url)

        raise RuntimeError("unreachable")  # loop always returns or raises above

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

        OKX endpoint: GET /api/v5/wallet/post-transaction/transactions-by-address
        Pagination is cursor-based (the response's `cursor` feeds the next
        request's `cursor` param), not page-number based.

        Each real on-chain transaction can appear as more than one row (one
        per transfer leg) sharing the same txHash — these are deduplicated
        by hash before returning, so tx_count reflects real transactions.
        """
        chain_id = SUPPORTED_CHAINS.get(chain)
        if chain_id is None:
            raise ValueError(f"Unsupported chain: {chain}. Supported: {list(SUPPORTED_CHAINS)}")

        path = "/api/v5/wallet/post-transaction/transactions-by-address"
        page_size = min(limit, 100)   # OKX max per page is 100; we paginate

        seen_hashes: set[str] = set()
        all_txs: list[TxRecord] = []
        cursor: str = ""

        while len(seen_hashes) < limit:
            params: dict[str, str] = {
                "address": wallet_address,
                "chains": chain_id,
                "limit": str(page_size),
            }
            if cursor:
                params["cursor"] = cursor

            # Build the query string once and reuse it verbatim for both the
            # signature and the actual request — OKX rejects the signature if
            # the signed string doesn't match the request byte-for-byte, and
            # a separately-serialized `params=` dict can reorder relative to
            # what was signed.
            qs = _build_qs(params)
            response = await self._get_with_retry(f"{path}?{qs}", headers=_headers("GET", f"{path}?{qs}"))
            data = response.json()

            if data.get("code") != "0":
                raise RuntimeError(f"OKX API error: {data.get('msg', 'unknown')}")

            page = data.get("data", [{}])[0] if data.get("data") else {}
            records = page.get("transactionList", [])
            if not records:
                break

            for r in records:
                tx = _parse_tx(r)
                if tx.hash and tx.hash not in seen_hashes:
                    seen_hashes.add(tx.hash)
                    all_txs.append(tx)

            next_cursor = page.get("cursor", "")
            if len(records) < page_size or not next_cursor or next_cursor == cursor:
                break   # last page
            cursor = next_cursor

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
        Fetch high-level address summary from OKX's Market API.

        Unlike get_tx_history, this endpoint's real path/response shape
        hasn't been confirmed against the live API (only the transaction
        history endpoint was verified). It's supplemental-only — callers
        already treat any failure here as "no extra signal" — so a wrong
        path degrades gracefully instead of breaking generation.
        """
        path = "/api/v5/explorer/address/address-summary"
        params = {
            "chainShortName": _chain_short(chain),
            "address": wallet_address,
        }
        qs = _build_qs(params)

        try:
            response = await self._get_with_retry(f"{path}?{qs}", headers=_headers("GET", f"{path}?{qs}"))
            data = response.json()
        except (httpx.HTTPStatusError, httpx.HTTPError):
            return AddressAnalysis()

        if data.get("code") != "0":
            # Address analysis is supplemental — degrade gracefully
            return AddressAnalysis()

        return _parse_analysis(data.get("data", [{}])[0])


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_tx(raw: dict) -> TxRecord:
    """
    Normalise a raw transaction record from the real API response shape:
    {chainIndex, txHash, methodId, nonce, txTime, from: [{address, amount}],
     to: [{address, amount}], tokenAddress, amount, symbol, txFee, txStatus,
     hitBlacklist, tag, itype}
    txTime is already milliseconds; there's no block number in this response.
    """
    from_list = raw.get("from") or [{}]
    to_list = raw.get("to") or [{}]
    return TxRecord(
        hash=raw.get("txHash", ""),
        from_addr=from_list[0].get("address", "") if from_list else "",
        to_addr=to_list[0].get("address", "") if to_list else "",
        value_eth=_safe_float(raw.get("amount", "0")),
        timestamp=_safe_int(raw.get("txTime", 0)) // 1000,
        block_number=0,  # not provided by this endpoint; unused downstream
        gas_used=_safe_int(raw.get("txFee", 0)),
        is_error=str(raw.get("txStatus", "success")) != "success",
        method_id=raw.get("methodId") or "0x",
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
