# SigilX — Product Requirements Document (PRD)

**Project:** SigilX — Chain Portrait  
**Hackathon:** OKX AI Genesis Hackathon 2026  
**Track:** Artistic Excellence (primary), Social Buzz, Revenue Rocket (secondary)  
**ASP Type:** A2MCP  
**Version:** 1.0 — Pre-submission  
**Last updated:** 2026-07-08

---

## 1. Product Overview

### 1.1 Problem Statement

A wallet address is a 42-character string. It carries no identity, no personality, no story — yet behind every address is a behavioral history: burst trading sessions, long dormant stretches, methodical DCA patterns, chaotic degeneracy. That story is invisible.

### 1.2 Solution

SigilX extracts the behavioral fingerprint embedded in a wallet's on-chain transaction history using chaos mathematics, then maps that fingerprint deterministically to a generative SVG artwork — a **Chain Portrait**. The portrait is:

- **Unique** — no two distinct wallets produce the same art
- **Deterministic** — same wallet always produces the same art
- **Verifiable** — the SVG hash and feature vector are stored on-chain
- **Shareable** — every mint produces a page with OG tags for rich social previews
- **Paid-per-call** — delivered as an A2MCP service via OKX's Onchain OS

### 1.3 One-line Pitch

> "Turn any wallet's on-chain history into a unique, algorithmically generated artwork — deterministic, personal, and shareable."

---

## 2. Goals & Success Metrics

### 2.1 Hackathon Goals

| Goal | Definition of done |
|---|---|
| ASP live and approved | Listed on OKX.AI marketplace, callable by agents |
| Generative algorithm complete | Same wallet always produces identical SVG |
| NFT minting live on X Layer mainnet | At least one end-to-end mint demonstrated |
| Shareable page with OG preview | Pasting link to X shows rich card |
| Demo video ≤90s | Uploaded to X with #OKXAI |
| Submission before deadline | Google form submitted before Jul 17, 23:59 UTC |

### 2.2 Quality Metrics

| Metric | Target |
|---|---|
| Generation latency (p95) | < 3s from wallet address to SVG |
| Determinism | 100% — same input always same output |
| OKX API dependency | 100% of tx data from OKX Market API (no own indexer) |
| Uptime during judging window | 99.9% |

---

## 3. User Stories

### Primary User: AI Agent (A2MCP caller)

> **As an AI agent**, I want to call a single MCP tool with a wallet address and receive a complete artwork + metadata, so I can incorporate on-chain identity art into my application without building generative art capabilities myself.

**Acceptance criteria:**
- MCP tool `generate_portrait` accepts `wallet_address` (string) and `chain` (string)
- Returns `portrait_id`, `svg` (full SVG string), `features` (object), `metadata` (object)
- Returns HTTP 402 with payment instructions if no valid x402 payment header
- Deterministic: identical inputs → identical outputs always

### Secondary User: End User (web UI / direct API caller)

> **As a crypto user**, I want to paste my wallet address, see my unique Chain Portrait generated, and mint it as an NFT — then share it on X and see a rich preview — so that my on-chain identity has a visual representation I can show off.

**Acceptance criteria:**
- Web UI accepts wallet address input
- Portrait renders in < 3 seconds
- "Mint" button triggers X Layer transaction
- Minted portrait page has correct OG meta tags
- Share button pre-fills post copy

---

## 4. Feature Specification

### 4.1 Feature Extraction Engine

**Module:** `services/extractor/`

**Data sources:**
- OKX Market API: Transaction History by Address
- OKX Market API: Address Analysis (supplemental)

**Feature vector (8 dimensions, all normalized 0.0–1.0):**

| Index | Name | Algorithm | Interpretation |
|---|---|---|---|
| 0 | `activity_entropy` | Sample Entropy on inter-tx time series | High = chaotic scheduler, low = bot/regular |
| 1 | `timing_regularity` | Autocorrelation of tx timestamp gaps | High = periodic, low = random |
| 2 | `amount_variance` | Normalized std dev of tx value distribution | High = wide spread of amounts |
| 3 | `interaction_diversity` | Unique counterparties / total txs | High = many unique interactions |
| 4 | `burst_coefficient` | Burstiness parameter B from Goh & Barabási | High = bursts of activity |
| 5 | `recency_decay` | Exponential decay from last tx to now | High = recent, low = dormant |
| 6 | `volume_skew` | Fisher-Pearson skewness of tx values | High = few large tx dominate |
| 7 | `chaos_dimension` | Correlation dimension estimate (Grassberger-Procaccia) | High = complex, fractal-like |

**Constraints:**
- Minimum 10 transactions required; below this threshold returns `{"error": "insufficient_history"}`
- Maximum 1000 transactions fetched (most recent 1000)
- Feature calculation is pure-function: same tx list → same vector, always

### 4.2 Generative Renderer

**Module:** `services/renderer/`

**Output:** SVG, 600×600 px, with embedded CSS animations

**Parameter mapping table:**

| Feature | Visual Parameter | Low value → | High value → |
|---|---|---|---|
| `activity_entropy` | Color palette hue range | Cool blues/greens (HSL 180–240) | Warm reds/oranges (HSL 0–60) |
| `timing_regularity` | Symmetry order | Fully asymmetric / organic | 6-fold or 8-fold crystalline |
| `amount_variance` | Shape edge count | Smooth curves (circle-like) | Complex polygons / splines |
| `interaction_diversity` | Element density | 10–30 elements | 80–200 elements |
| `burst_coefficient` | Spatial clustering | Uniform distribution | Tightly grouped clusters |
| `recency_decay` | Global opacity | 30% (faded / ghost) | 95% (vivid / present) |
| `volume_skew` | Scale ratio (max/min element) | Uniform sizes (~1:1) | Extreme contrast (1:20) |
| `chaos_dimension` | Recursion / fractal depth | 1–2 iterations | 5–6 iterations |

**Determinism requirements:**
- All random number generation seeded from `keccak256(wallet_address + chain)`
- No calls to `random()` without seeded PRNG
- SVG output character-for-character identical for identical inputs

### 4.3 Core API

**Module:** `services/api/`

#### `POST /generate`

Request:
```json
{
  "wallet_address": "0x...",
  "chain": "eth-mainnet | polygon-mainnet | bsc-mainnet | ..."
}
```

Response (200):
```json
{
  "portrait_id": "cp_<hex>",
  "svg": "<svg xmlns=...>...</svg>",
  "features": {
    "activity_entropy": 0.73,
    "timing_regularity": 0.21,
    "amount_variance": 0.88,
    "interaction_diversity": 0.55,
    "burst_coefficient": 0.67,
    "recency_decay": 0.90,
    "volume_skew": 0.43,
    "chaos_dimension": 0.61
  },
  "metadata": {
    "title": "Chain Portrait #4921",
    "wallet": "0x...",
    "chain": "eth-mainnet",
    "generated_at": "2026-07-08T18:00:00Z",
    "tx_count": 847,
    "svg_hash": "0xabc..."
  }
}
```

Response (402 — no payment):
```json
{
  "error": "payment_required",
  "x402_details": { ... }
}
```

Response (400 — insufficient history):
```json
{
  "error": "insufficient_history",
  "tx_count": 3,
  "minimum_required": 10
}
```

#### `GET /portrait/{portrait_id}`

Returns cached portrait (SVG + metadata) without billing.

#### `GET /health`

Returns service uptime + version. No auth, no payment.

### 4.4 MCP Tool (FastMCP)

**Tool name:** `generate_chain_portrait`

**Description:** Analyzes a wallet's on-chain transaction history using chaos mathematics and generates a unique, deterministic SVG artwork reflecting its behavioral fingerprint.

**Input schema:**
```json
{
  "wallet_address": { "type": "string", "description": "EVM wallet address (0x...)" },
  "chain": { "type": "string", "enum": ["eth-mainnet","polygon-mainnet","bsc-mainnet","xlayer-mainnet"], "default": "eth-mainnet" }
}
```

**Output schema:** Same as `/generate` 200 response.

### 4.5 Minting Contract

**File:** `contracts/ChainPortrait.sol`
**Standard:** ERC-721
**Network:** X Layer (testnet first, then mainnet)

**On-chain metadata stored per token:**
```solidity
struct Portrait {
    address wallet;          // analyzed wallet
    string  chain;           // source chain
    string  portraitId;      // deterministic ID
    bytes32 svgHash;         // keccak256 of SVG
    string  featureVector;   // JSON-encoded features
    uint256 generatedAt;     // block timestamp
}
```

**Key functions:**
- `mint(address to, Portrait calldata p)` — mints; emits `PortraitMinted`
- `tokenURI(uint256 tokenId)` — returns on-chain metadata JSON
- `getPortrait(uint256 tokenId)` — returns full Portrait struct

### 4.6 Shareable Frontend

**File:** `frontend/index.html`

**Required OG tags:**
```html
<meta property="og:title" content="My Chain Portrait — SigilX" />
<meta property="og:description" content="My wallet's on-chain history, turned into art. #ChainPortrait" />
<meta property="og:image" content="https://sigilx.xyz/og/{portrait_id}.png" />
<meta property="og:url" content="https://sigilx.xyz/portrait/{portrait_id}" />
<meta name="twitter:card" content="summary_large_image" />
```

**Page sections:**
1. Portrait SVG (animated, full-width)
2. Feature radar chart (8 dimensions, labeled)
3. Wallet address + chain badge
4. Mint button (if not yet minted) / NFT link (if minted)
5. Share button with pre-filled X copy

---

## 5. Technical Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| API framework | FastAPI |
| MCP wrapper | FastMCP |
| Payment middleware | OKX Onchain OS Payment SDK (x402) |
| Tx data | OKX Market API |
| Art format | SVG + CSS animations |
| Smart contracts | Solidity 0.8.x, Hardhat |
| Chain | X Layer (EVM-compatible, OKB gas) |
| Frontend | Vanilla HTML/CSS/JS |
| Hosting | Hong Kong VPS, nginx reverse proxy, Let's Encrypt |
| Container | Docker + docker-compose |

---

## 6. Payment Model

**Type:** A2MCP (pay-per-call, no negotiation)
**Gate:** x402 — every request to `/generate` requires a valid payment header
**Price:** TBD (set during ASP registration; recommend starting at ~$0.10–$0.50 USD equivalent in OKB)
**Settlement:** Instant via OKX Payment SDK
**Free tier:** None (hackathon demo uses a demo key that bypasses payment for judges)

---

## 7. Non-Functional Requirements

| Requirement | Specification |
|---|---|
| Determinism | 100% — same wallet + chain always produces identical SVG |
| Latency (p50) | < 1.5s |
| Latency (p95) | < 3.0s |
| Availability | 99.9% during judging window (Jul 8–17) |
| Security | API keys in env vars only; no keys in source code |
| Rate limiting | 60 req/min per IP (before payment); unlimited per valid payment |
| Data retention | Portraits cached server-side for 30 days minimum |

---

## 8. Out of Scope (v1)

- Multi-wallet comparison view
- Animation export (GIF/video)
- Custom palette overrides by user
- Non-EVM chains (Solana, Bitcoin)
- Mobile-native app
- Secondary marketplace royalties

---

## 9. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| OKX.AI review takes > 2 days | Medium | Submit registration on Day 1 of dev, not Day 10 |
| OKX Market API rate limits during demo | Low | Cache all API responses server-side; demo wallets pre-fetched |
| X Layer testnet instability | Low | Keep local Hardhat fallback for contract testing |
| HTTPS cert provisioning delay | Low | Use Let's Encrypt + certbot; provision before testing x402 |
| Wallet with < 10 txs used in demo | Medium | Pre-screen both demo wallets; have backups ready |

---

## 10. Build Timeline

| Day | Milestone |
|---|---|
| Day 1 | Env setup, OKX API client, raw tx fetch working |
| Day 2 | Entropy math ported, feature vector output verified |
| Day 3–4 | Generative SVG renderer complete, determinism verified |
| Day 5 | FastAPI service + all endpoints |
| Day 6 | FastMCP wrapper, MCP Inspector test passes |
| Day 7 | Deploy to HK server, HTTPS live, x402 middleware wired |
| Day 8 | ChainPortrait.sol on X Layer testnet, mint end-to-end test |
| Day 9 | Shareable page, OG tags tested on X |
| Day 10 | A2MCP registration submitted to OKX.AI |
| Day 11–12 | Buffer: review wait + any revisions needed |
| Day 13 | Mainnet deploy, full end-to-end demo rehearsal |
| Day 14 | Demo video recorded, X post published, Google form submitted |

---

*SigilX / Suganthan96 — OKX AI Genesis Hackathon 2026*
