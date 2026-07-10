# SigilX — Chain Portrait

> Turn any wallet's on-chain history into a unique, deterministic work of art.

[![OKX AI Genesis Hackathon](https://img.shields.io/badge/OKX%20AI%20Genesis-Hackathon%202026-blue?style=for-the-badge)](https://okx.com)
[![Track: Artistic Excellence](https://img.shields.io/badge/Track-Artistic%20Excellence-purple?style=for-the-badge)](#)
[![ASP Type: A2MCP](https://img.shields.io/badge/ASP%20Type-A2MCP-orange?style=for-the-badge)](#)
[![X Layer](https://img.shields.io/badge/Network-X%20Layer-green?style=for-the-badge)](#)

---

## What Does the Agent Service Do?

SigilX is registered on OKX.AI as an Agent Service Provider (ASP) — a paid, agent-callable
service that any AI agent (or human, over the same REST API) can invoke. In one call, it does
three things:

1. **Analyzes.** Given an EVM wallet address, it pulls that wallet's transaction history from
   the OKX Market API and runs it through entropy/chaos math (Sample Entropy, Correlation
   Dimension, Burstiness, and related measures) to extract an 8-dimension behavioral
   fingerprint — a numeric summary of *how* that wallet behaves on-chain (bursty vs. steady,
   diverse vs. repetitive, high-variance vs. consistent, and so on).
2. **Renders.** That fingerprint is mapped, deterministically, to a generative SVG artwork —
   a Chain Portrait. There is no image-generation model involved; the art is pure math. The
   same wallet on the same chain always produces the exact same portrait, byte for byte.
3. **Mints (optional).** The caller can then mint the portrait as an ERC-721 NFT on X Layer,
   with the feature vector and a hash of the SVG stored on-chain for verifiability.

The service is callable two ways:

- **As a plain REST API**, gated behind an x402 payment (pay-per-call, settled on-chain).
- **As an MCP tool** (`generate_chain_portrait`), so an agent framework such as Claude can call
  it directly as a tool rather than writing HTTP client code.

Nothing about the analysis or rendering depends on which path is used — both call the same
underlying pipeline.

```
Wallet address -> OKX transaction history -> entropy/chaos analysis -> SVG renderer -> optional mint on X Layer
```

---

## Architecture

```
+--------------+   +-----------------------+   +----------------------------+
| Wallet addr  |-->| OKX Market API        |-->| Feature extraction         |
| (input)      |   | (tx history +         |   | (Sample Entropy, corr.     |
+--------------+   |  address analysis)    |   |  dimension, burstiness)    |
                   +-----------------------+   +-------------+--------------+
                                                              |
                                                              v
+----------------------+   +-------------------+   +----------------------------+
| Shareable page       |<--| Mint on X Layer   |<--| Generative SVG renderer    |
| (OG tags, radar      |   | (ERC-721 + on-    |   | (palette, shapes, motion,  |
|  chart, mint button) |   |  chain metadata)  |   |  deterministic seeding)    |
+----------------------+   +-------------------+   +----------------------------+

FastAPI --> FastMCP --> HTTPS --> x402 payment gate --> OKX.AI ASP listing
```

### OKX Infrastructure Mapping

| Need | OKX component |
|---|---|
| Wallet transaction history | Market API -> Transaction History API |
| Behavioral signals | Market API -> Address Analysis API |
| ASP identity + wallet | Onchain OS Agentic Wallet |
| NFT minting | X Layer (testnet ID `1952`, mainnet ID `196`) |
| Per-generation billing | Onchain OS Payment SDK / x402 |
| Agent-callable interface | Onchain OS Skills + FastMCP (A2MCP) |

---

## Repository Structure

```
SigilX/
├── README.md
├── PRD.md                            Product requirements
├── ARCHITECTURE.md                   Detailed system design
├── STATUS.md                         Build status / open items
├── services/
│   ├── extractor/                    Entropy/chaos analysis engine
│   │   ├── okx_client.py             OKX Market API wrapper
│   │   ├── entropy.py                Sample Entropy, Correlation Dimension, Burstiness
│   │   └── fingerprint.py            8D feature vector builder
│   ├── renderer/                     Generative art renderer
│   │   ├── palette.py
│   │   ├── shapes.py
│   │   ├── composer.py               SVG composition
│   │   ├── animator.py               CSS animation layer
│   │   └── attractor.py              Chaotic-attractor raster renderer
│   └── api/
│       ├── main.py                   FastAPI entry point
│       ├── routes.py                 /generate, /mint, /portrait, /chains, /health
│       ├── payment.py                x402 payment middleware
│       ├── mint.py                   On-chain minting logic
│       ├── ipfs.py                   IPFS pinning (Pinata) for image/metadata
│       └── mcp_server.py             FastMCP wrapper — agent-callable tool
├── contracts/
│   ├── src/SigilX.sol                ERC-721 minting contract
│   ├── deploy/
│   │   ├── deploy_testnet.js
│   │   └── deploy_mainnet.js
│   └── test/ChainPortrait.test.js
├── web/                              Next.js frontend
│   ├── app/
│   │   ├── generate/                 Wallet input -> generate -> mint flow
│   │   ├── docs/                     This service's own docs page
│   │   └── portrait/[id]/            Shareable portrait page (OG tags)
│   └── components/
├── tests/                            Python test suite (pytest)
├── .env.example
└── requirements.txt
```

---

## The Behavioral Fingerprint

Each wallet is reduced to eight normalized dimensions in `[0, 1]`, which drive both the
analysis and the art:

| Dimension | What it captures |
|---|---|
| `activity_entropy` | Randomness of transaction frequency over time |
| `timing_regularity` | How periodic/rhythmic the wallet's activity is |
| `amount_variance` | Spread of transaction values (HODLer vs. active trader) |
| `interaction_diversity` | Unique contract/counterparty count |
| `burst_coefficient` | Clustering of activity into time bursts |
| `recency_decay` | How recently the wallet has been active |
| `volume_skew` | Heavy tails in the transaction-size distribution |
| `chaos_dimension` | Correlation-dimension proxy (fractal complexity) |

The renderer maps these deterministically to visual parameters — palette, symmetry, shape
complexity, element density, cluster pattern, opacity, scale contrast, and iteration depth —
so that the resulting portrait is a direct, reproducible visualization of the fingerprint, not
a random or model-generated image.

---

## REST API

Run the service locally:

```bash
pip install -r requirements.txt
uvicorn services.api.main:app --reload --port 8000
```

Endpoints:

| Method | Path | Description |
|---|---|---|
| POST | `/generate` | Analyze a wallet and render its Chain Portrait. Gated by x402. |
| POST | `/mint` | Mint a previously generated portrait as an ERC-721 on X Layer. |
| GET | `/portrait/{id}` | Fetch a cached portrait. No payment required. |
| GET | `/mint/{id}/status` | Check whether a portrait has been minted. |
| GET | `/chains` | List supported chains. |
| GET | `/health` | Service health check. |

Example call:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc454e4438f44e","chain":"eth-mainnet"}'
```

Response:

```json
{
  "portrait_id": "cp_abc123",
  "svg": "<svg>...</svg>",
  "features": { "activity_entropy": 0.62, "chaos_dimension": 0.31, "...": "..." },
  "metadata": { "title": "Chain Portrait · 0x742d…f44e", "tx_count": 184, "svg_hash": "0x..." }
}
```

---

## MCP / Agent Integration

The same pipeline is also exposed as an MCP tool (`services/api/mcp_server.py`, built on
FastMCP), so an agent doesn't need to write any HTTP client code:

```bash
# Start the MCP server (SSE transport, default port 8001)
python -m services.api.mcp_server
```

Tool signature:

```
generate_chain_portrait(wallet_address: str, chain: str = "eth-mainnet") -> {
  portrait_id: str
  svg: str
  features: dict[str, float]   # the 8-dimension behavioral fingerprint
  metadata: dict
}
```

To add it to Claude Code as a remote MCP server:

```bash
claude mcp add sigilx --transport sse http://localhost:8001/sse
```

Once added, an agent can call `generate_chain_portrait` directly like any other MCP tool. For
stdio-only MCP clients (e.g. Claude Desktop), bridge the SSE endpoint with `mcp-remote` in the
client's server configuration.

---

## x402 Payments

`POST /generate` is gated behind [x402](https://github.com/coinbase/x402), the protocol OKX's
Onchain OS Payment SDK is built on:

- An unpaid request gets back HTTP 402 with a body listing payment requirements
  (`x402Version` + `accepts[]`).
- A paid retry carries an `X-PAYMENT` header — a base64-encoded, EIP-712-signed EIP-3009
  `transferWithAuthorization` payload — which OKX's facilitator (the "Broker") verifies and
  settles on-chain.

For local development and reviewer/judge testing, set `DEMO_MODE=true` and `DEMO_API_KEY` in
`.env`, then pass a matching `X-Demo-Key` header to bypass the payment gate entirely:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -H "X-Demo-Key: $DEMO_API_KEY" \
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc454e4438f44e","chain":"eth-mainnet"}'
```

---

## Smart Contract

`contracts/src/SigilX.sol` — an ERC-721 that stores, per token:

- `portraitId` — deterministic hash of wallet + chain
- `featureVector` — the 8-dimension fingerprint, on-chain
- `svgHash` — keccak256 of the SVG, for verifiability
- `wallet` — the analyzed wallet address
- `imageUri` / `metadataUri` — IPFS links, when pinned, so explorers and marketplaces that
  don't render inline data URIs can still display the image

Testnet: chain ID `1952`, RPC `https://testrpc.xlayer.tech/terigon`.
Mainnet: chain ID `196`, RPC `https://rpc.xlayer.tech`.

---

## Local Development

### Prerequisites

```bash
python --version    # 3.11+
node --version      # 18+
```

### Environment

```bash
cp .env.example .env
# Fill in: OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE
# XLAYER_RPC_URL, XLAYER_PRIVATE_KEY, PAYMENT_WALLET
```

### Run services

```bash
# API service
pip install -r requirements.txt
uvicorn services.api.main:app --reload --port 8000

# MCP server (separate terminal)
python -m services.api.mcp_server

# Contracts — testnet deploy
cd contracts && npm install
npx hardhat run deploy/deploy_testnet.js --network xlayer-testnet

# Frontend (Next.js)
cd web && pnpm install && pnpm dev
```

### Test

```bash
pytest                          # Python: extractor, renderer, API, payment middleware
cd contracts && npx hardhat test  # Solidity: contract behavior
```

---

## References

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

## Track Alignment

| Track | Qualification |
|---|---|
| Artistic Excellence (primary) | Pure math to art; no wrapped third-party image model |
| Social Buzz (secondary) | Every mint produces a shareable, OG-tagged link |
| Revenue Rocket (secondary) | Shares drive new users, new users drive paid mints |

---

*MIT © 2026 SigilX / Suganthan96 — built for the OKX AI Genesis Hackathon 2026.*
