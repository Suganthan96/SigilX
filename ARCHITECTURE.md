# SigilX — Architecture Reference

**Version:** 1.0 | **Updated:** 2026-07-08

---

## System Overview

SigilX is a single-purpose A2MCP (Agent-to-MCP) service. One tool, one operation: wallet address in, Chain Portrait out. The architecture prioritizes determinism, OKX-native data sourcing, and instant payment settlement.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           SIGILX SYSTEM                                    │
│                                                                            │
│  ┌─────────┐   ┌──────────────┐   ┌────────────────┐   ┌───────────────┐ │
│  │ AI Agent │──▶│ FastMCP      │──▶│ x402 Payment   │──▶│ FastAPI       │ │
│  │ (caller) │   │ (MCP layer)  │   │ (middleware)   │   │ (core API)    │ │
│  └─────────┘   └──────────────┘   └────────────────┘   └───────┬───────┘ │
│                                                                  │        │
│                   ┌──────────────────────────────────────────────┘        │
│                   │                                                        │
│                   ▼                                                        │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                     GENERATION PIPELINE                             │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐  │   │
│  │  │ OKX Client       │    │ Feature Extractor │    │ SVG Renderer  │  │   │
│  │  │ (Market API)     │───▶│ (Entropy / Chaos) │───▶│ (Generative)  │  │   │
│  │  └─────────────────┘    └──────────────────┘    └───────┬───────┘  │   │
│  │                                                          │          │   │
│  └──────────────────────────────────────────────────────────┼──────────┘   │
│                                                             │              │
│                   ┌─────────────────────────────────────────┘              │
│                   │                                                        │
│          ┌────────▼────────┐    ┌─────────────────┐                       │
│          │ Portrait Cache   │    │ X Layer Contract │                       │
│          │ (Redis / FS)     │    │ (ERC-721 mint)   │                       │
│          └─────────────────┘    └─────────────────┘                       │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Breakdown

### `services/extractor/okx_client.py`

Thin wrapper over the OKX Market API.

**Methods:**
- `get_tx_history(wallet, chain, limit=1000)` → `List[TxRecord]`
- `get_address_analysis(wallet, chain)` → `AddressAnalysis`

**Auth:** HMAC-SHA256 signed requests (OKX API key + secret + passphrase)

**Caching:** Responses cached server-side for 1 hour to avoid redundant fetches.

---

### `services/extractor/entropy.py`

Pure functions implementing the chaos mathematics.

**Key functions:**

```python
def sample_entropy(time_series: List[float], m: int = 2, r_factor: float = 0.2) -> float:
    """
    Sample Entropy (SampEn) — measures predictability / regularity.
    r = r_factor * std(time_series)
    Returns: float in [0, ~2.5], normalized to [0, 1] for feature vector.
    """

def correlation_dimension(time_series: List[float], max_m: int = 5) -> float:
    """
    Grassberger-Procaccia correlation dimension estimate.
    Returns: float in [0, max_m], normalized to [0, 1].
    """

def burstiness(inter_event_times: List[float]) -> float:
    """
    Goh & Barabasi burstiness parameter B = (sigma - mu) / (sigma + mu).
    Returns: float in [-1, 1], shifted to [0, 1].
    """
```

All functions are pure (no side effects, same input → same output).

---

### `services/extractor/fingerprint.py`

Orchestrates the extractor pipeline. Converts raw tx list → normalized 8D feature vector.

```python
@dataclass
class FeatureVector:
    activity_entropy: float      # [0, 1]
    timing_regularity: float     # [0, 1]
    amount_variance: float       # [0, 1]
    interaction_diversity: float # [0, 1]
    burst_coefficient: float     # [0, 1]
    recency_decay: float         # [0, 1]
    volume_skew: float           # [0, 1]
    chaos_dimension: float       # [0, 1]

def build_fingerprint(txs: List[TxRecord]) -> FeatureVector:
    ...
```

---

### `services/renderer/`

Determinism contract: **all randomness seeded from wallet fingerprint**.

```python
import hashlib, random

def make_seeded_rng(wallet_address: str, chain: str) -> random.Random:
    seed_bytes = hashlib.sha256(f"{wallet_address.lower()}:{chain}".encode()).digest()
    seed_int = int.from_bytes(seed_bytes, "big")
    return random.Random(seed_int)
```

**`palette.py`** — HSL palette generator; maps `activity_entropy` + `timing_regularity` to hue range, saturation, lightness steps.

**`shapes.py`** — Generates SVG path data; `amount_variance` controls edge count, `chaos_dimension` controls recursion depth.

**`composer.py`** — Assembles final SVG from palette + shape elements + layout.

**`animator.py`** — Injects `<style>` block with `@keyframes` animations; `burst_coefficient` controls animation speed.

---

### `services/api/payment.py`

x402 middleware. Every request to `/generate` is intercepted:

1. Check for `X-Payment` header (OKX Payment SDK format)
2. If absent or invalid → return HTTP 402 with payment instructions
3. If valid → call `verify_payment()` → pass to route handler

```python
@app.middleware("http")
async def x402_gate(request: Request, call_next):
    if request.url.path == "/generate" and request.method == "POST":
        if not await verify_payment(request):
            return payment_required_response()
    return await call_next(request)
```

---

### `services/api/mcp_server.py`

FastMCP wrapper. Exposes one tool to any MCP-compatible AI agent.

```python
from fastmcp import FastMCP
mcp = FastMCP("SigilX Chain Portrait")

@mcp.tool()
async def generate_chain_portrait(wallet_address: str, chain: str = "eth-mainnet") -> dict:
    """
    Analyze a wallet's on-chain transaction history using chaos mathematics
    and return a unique, deterministic SVG artwork reflecting its behavioral fingerprint.
    """
    ...
```

---

### `contracts/ChainPortrait.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";

contract ChainPortrait is ERC721 {
    struct Portrait {
        address wallet;
        string  chain;
        string  portraitId;
        bytes32 svgHash;
        string  featureVector;
        uint256 generatedAt;
    }

    mapping(uint256 => Portrait) public portraits;
    uint256 private _tokenCounter;

    event PortraitMinted(uint256 indexed tokenId, address indexed wallet, string portraitId);

    function mint(address to, Portrait calldata p) external returns (uint256) {
        uint256 tokenId = ++_tokenCounter;
        _mint(to, tokenId);
        portraits[tokenId] = p;
        emit PortraitMinted(tokenId, p.wallet, p.portraitId);
        return tokenId;
    }

    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        Portrait memory p = portraits[tokenId];
        // Returns base64-encoded JSON metadata
        ...
    }
}
```

**Networks:**

| Network | Chain ID | RPC |
|---|---|---|
| X Layer Testnet | 1952 | https://testrpc.xlayer.tech/terigon |
| X Layer Mainnet | 196 | https://rpc.xlayer.tech |

---

## Data Flow (Happy Path)

```
1. Agent sends: POST /generate {"wallet_address": "0xabc", "chain": "eth-mainnet"}
   with X-Payment: <valid x402 token>

2. x402 middleware verifies payment → passes request

3. okx_client.get_tx_history("0xabc", "eth-mainnet") → 847 tx records

4. fingerprint.build_fingerprint(txs) → FeatureVector(0.73, 0.21, 0.88, ...)

5. composer.render(fingerprint, wallet="0xabc", chain="eth-mainnet")
   → deterministic SVG string (600×600 px)

6. API returns: {portrait_id, svg, features, metadata}

7. (Optional) User calls /mint → ChainPortrait.sol.mint() on X Layer → NFT created

8. (Optional) User opens /portrait/{portrait_id} → sees animated SVG + OG tags
   → pastes link to X → rich card preview appears
```

---

## Deployment Topology

```
Internet
   │
   ▼
[nginx reverse proxy]  ← HTTPS (Let's Encrypt), Hong Kong node
   │           │
   ▼           ▼
[FastAPI:8000] [Static frontend: 3000]
   │
   ▼
[FastMCP server]  ← registered as A2MCP on OKX.AI
```

---

*SigilX / Suganthan96 — OKX AI Genesis Hackathon 2026*
