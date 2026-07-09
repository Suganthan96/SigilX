# 🎨 SigilX — Chain Portrait

> **Turn any wallet's on-chain history into a unique, deterministic work of art.**

[![OKX AI Genesis Hackathon](https://img.shields.io/badge/OKX%20AI%20Genesis-Hackathon%202026-blue?style=for-the-badge)](https://okx.com)
[![Track: Artistic Excellence](https://img.shields.io/badge/Track-Artistic%20Excellence-purple?style=for-the-badge)](#)
[![ASP Type: A2MCP](https://img.shields.io/badge/ASP%20Type-A2MCP-orange?style=for-the-badge)](#)
[![X Layer](https://img.shields.io/badge/Network-X%20Layer-green?style=for-the-badge)](#)

---

## ✨ What Is SigilX?

**SigilX** is an on-chain identity art engine. Submit any EVM wallet address; SigilX pulls its full transaction history from the **OKX Market API**, runs chaos-math / entropy analysis on the behavioral fingerprint embedded in that history, and maps that fingerprint deterministically to a generative SVG artwork — your personal *Chain Portrait*.

No two wallets produce the same portrait. Same wallet always produces the same portrait. The algorithm is the art.

```
Wallet Address → OKX Tx History API → Entropy Analysis → Generative Renderer → NFT on X Layer
```

---

## 🏗️ Architecture

```
┌──────────────┐   ┌──────────────────────┐   ┌───────────────────────────┐
│ Wallet Addr  │──▶│ OKX Market API        │──▶│ Feature Extraction        │
│ (input)      │   │ (Tx History +         │   │ (Sample Entropy, Corr.    │
└──────────────┘   │  Address Analysis)    │   │  Dimension, Lyapunov)     │
                   └──────────────────────┘   └────────────┬──────────────┘
                                                            │
                                                            ▼
┌─────────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│ Shareable Page       │◀─│ Mint on X Layer   │◀─│ Generative SVG Renderer  │
│ (OG tags, captions)  │  │ (ERC-721 + meta)  │  │ (palette, shapes, motion)│
└─────────────────────┘  └──────────────────┘  └──────────────────────────┘

FastAPI ──▶ FastMCP ──▶ HTTPS ──▶ x402 payment gate ──▶ OKX.AI A2MCP listing
```

### OKX Infrastructure Mapping

| Need | OKX Component |
|---|---|
| Wallet transaction history | Market API → Transaction History API |
| Behavioral signals | Market API → Address Analysis API |
| ASP identity + wallet | Onchain OS Agentic Wallet |
| NFT minting | X Layer (testnet ID `1952` → mainnet ID `196`) |
| Per-generation billing | Onchain OS Payment SDK / x402 |
| Agent-callable interface | Onchain OS Skills + FastMCP |

---

## 🗂️ Repository Structure

```
SigilX/
├── README.md
├── PRD.md                      ← Full Product Requirements Document
├── ARCHITECTURE.md             ← Detailed system design
├── docs/
│   ├── api-reference.md
│   ├── entropy-math.md
│   └── art-algorithm.md
├── services/
│   ├── extractor/              ← Entropy/chaos analysis engine
│   │   ├── okx_client.py       ← OKX Market API wrapper
│   │   ├── entropy.py          ← Sample Entropy, Correlation Dimension
│   │   └── fingerprint.py      ← Feature vector builder
│   ├── renderer/               ← Generative SVG renderer
│   │   ├── palette.py
│   │   ├── shapes.py
│   │   ├── composer.py
│   │   └── animator.py
│   └── api/
│       ├── main.py             ← FastAPI entry point
│       ├── routes.py           ← /generate, /status, /metadata
│       ├── payment.py          ← x402 middleware
│       └── mcp_server.py       ← FastMCP wrapper
├── contracts/
│   ├── ChainPortrait.sol       ← ERC-721 minting contract
│   ├── deploy/
│   │   ├── deploy_testnet.js
│   │   └── deploy_mainnet.js
│   └── hardhat.config.js
├── frontend/
│   ├── index.html              ← Share page with OG tags
│   ├── style.css
│   └── app.js
├── tests/
│   ├── test_extractor.py
│   ├── test_renderer.py
│   └── test_api.py
├── scripts/
│   ├── register_asp.sh
│   └── list_marketplace.sh
├── .env.example
├── requirements.txt
└── docker-compose.yml
```

---

## 🚀 Build Phases

### Phase 1 — Feature Extraction Engine
Pull tx history from OKX Market API, run entropy/chaos math, output a normalized 8-dimension feature vector.

| Dimension | What it captures |
|---|---|
| `activity_entropy` | Randomness of tx frequency over time |
| `timing_regularity` | How periodic/rhythmic the wallet's activity is |
| `amount_variance` | Spread of tx values (HODLer vs. trader) |
| `interaction_diversity` | Unique contract / counterparty count |
| `burst_coefficient` | Clustering of activity in time bursts |
| `recency_decay` | How recently the wallet has been active |
| `volume_skew` | Heavy tails in tx size distribution |
| `chaos_dimension` | Correlation dimension proxy (fractal complexity) |

### Phase 2 — Generative Renderer
Deterministic mapping: feature vector → SVG visual parameters.

```
activity_entropy      → color palette (warm/chaotic vs cool/ordered)
timing_regularity     → symmetry level (asymmetric vs crystalline)
amount_variance       → shape complexity (organic curves vs geometric)
interaction_diversity → element density (sparse vs dense)
burst_coefficient     → cluster pattern (scattered vs grouped)
recency_decay         → opacity / fade effects
volume_skew           → scale contrast (large/small element ratio)
chaos_dimension       → recursion depth / fractal iterations
```

Output: deterministic SVG (600×600 px) with CSS animation layer.

### Phase 3 — FastAPI Service

```http
POST /generate
Content-Type: application/json
{"wallet_address": "0xabc...", "chain": "eth-mainnet"}

→ 200 OK
{
  "portrait_id": "cp_abc123",
  "svg": "<svg>...</svg>",
  "features": { ... },
  "metadata": { "title": "Chain Portrait #4921", ... }
}
```

### Phase 4 — FastMCP Wrapper
Expose `/generate` as an MCP tool. ~1 day effort per OKX docs.

### Phase 5 — Deploy + HTTPS
Recommended: **Hong Kong node** (best latency for OKX, no ICP filing required).

### Phase 6 — x402 Payment Gate
`payment.py` middleware: unpaid POST → HTTP 402 intercept. Paid → generate. Settlement instant via OKX Payment SDK.

### Phase 7 — Minting Contract (X Layer)
`ChainPortrait.sol` — ERC-721 storing:
- `portraitId` — deterministic hash of wallet + chain
- `featureVector` — JSON-encoded, on-chain
- `svgHash` — keccak256 of SVG for verifiability
- `wallet` — analyzed wallet address

**Testnet:** Chain ID `1952`, RPC `https://testrpc.xlayer.tech/terigon`
**Mainnet:** Chain ID `196`, RPC `https://rpc.xlayer.tech`

### Phase 8 — Shareable Page
Static frontend:
- Renders SVG portrait inline
- Shows feature vector breakdown
- Open Graph meta tags for rich X/Twitter card previews
- Pre-filled share caption: *"My wallet's on-chain history is literally art 🎨 #ChainPortrait #OKXAI"*

### Phase 9 — Register as A2MCP on OKX.AI

```bash
> Help me register an A2MCP ASP on OKX.AI using Onchain OS
# Provide: service name, description, price per call, endpoint URL
```

### Phase 10 — List on Marketplace

```bash
> Help me list my ASP on OKX.AI using Onchain OS
# Review: up to 2 business days — list EARLY, not near the deadline
```

### Phase 11 — Go Live
A2MCP is fully automatic once listed. Every call bills instantly.

---

## 🔧 Local Development

### Prerequisites

```bash
python --version    # 3.11+
node --version      # 18+
npx skills add okx/onchainos-skills --yes -g
```

### Environment

```bash
cp .env.example .env
# Fill in: OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE
# XLAYER_RPC_URL, XLAYER_PRIVATE_KEY, PAYMENT_WALLET
```

### Run Services

```bash
# API service
pip install -r requirements.txt
uvicorn services.api.main:app --reload --port 8000

# MCP server (separate terminal)
python services/api/mcp_server.py

# Contracts — testnet deploy
cd contracts && npm install
npx hardhat run deploy/deploy_testnet.js --network xlayer-testnet

# Frontend (static)
cd frontend && python -m http.server 3000
```

### Test

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc454e4438f44e","chain":"eth-mainnet"}'
```

---

## 🎬 Demo Script (90 seconds)

| Time | Action |
|---|---|
| 0–10s | Paste high-frequency trading wallet → chaotic/dense portrait |
| 10–25s | Paste HODLer wallet → calm/structured portrait, clearly different |
| 25–50s | Walk through feature panel — explain each dimension |
| 50–70s | Mint one → show X Layer txn → open shareable link |
| 70–80s | Paste link to X → show rich OG preview auto-populate |
| 80–90s | Close line |

> *"Every wallet has a fingerprint. SigilX turns it into art — powered end-to-end by OKX's Market API, Agentic Wallet, X Layer, and the OKX Payment SDK."*

---

## 📋 Submission Checklist

- [ ] ASP live and **passing OKX.AI review** (approved + callable)
- [ ] X post with `#OKXAI` + ≤90s demo video
- [ ] Google form submitted **before Jul 17, 23:59 UTC**

---

## 🔗 Key References

| Resource | URL |
|---|---|
| ASP Overview | https://web3.okx.com/onchainos/dev-docs/okxai/asp |
| A2MCP Guide | https://web3.okx.com/onchainos/dev-docs/okxai/howtomcp |
| ASP Registration | https://web3.okx.com/onchainos/dev-docs/okxai/registerasp |
| Payments Overview | https://web3.okx.com/onchainos/dev-docs/payments/overview |
| x402 Seller Integration | https://web3.okx.com/onchainos/dev-docs/payments/service-seller |
| Market API | https://web3.okx.com/onchainos/dev-docs/market/market-api-introduction |
| X Layer Network | https://web3.okx.com/onchainos/dev-docs/xlayer/developer/build-on-xlayer/network-information |
| Agent Installation | https://web3.okx.com/onchainos/dev-docs/okxai/agent-installation-guide |

---

## 🏆 Track Alignment

| Track | Qualification |
|---|---|
| **Artistic Excellence** (primary) | Pure math → art; no wrapped third-party image model |
| **Social Buzz** (secondary) | Every mint → shareable OG-tagged link built for viral spread |
| **Revenue Rocket** (secondary) | Shares → new users → paid mints → organic loop |

---

*MIT © 2026 SigilX / Suganthan96 — Built for the OKX AI Genesis Hackathon 2026.*
