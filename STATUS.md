# SigilX — Project Status

**Last updated:** 2026-07-10

One-liner: turn a wallet's on-chain transaction history into a unique, deterministic generative SVG artwork via entropy/chaos math, mintable as an NFT on X Layer, served as an OKX A2MCP paid service.

---

## ✅ Done

### Feature extraction (`services/extractor/`)
- `entropy.py` — Sample Entropy, Grassberger-Procaccia correlation dimension, Goh-Barabási burstiness, Hurst exponent. Pure functions, unit tested.
- `fingerprint.py` — builds the normalized 8D `FeatureVector` from a tx list. Deterministic (verified: same input → identical output).
- `okx_client.py` — **rewritten to match the real, live OKX API** (was previously written from doc guesses and had never been run):
  - Correct base URL/endpoint: `web3.okx.com/api/v5/wallet/post-transaction/transactions-by-address` (not the originally-assumed `www.okx.com/api/v5/explorer/...`, which doesn't exist).
  - Fixed timestamp format (OKX requires ISO 8601 UTC, not raw Unix epoch).
  - Fixed a signature bug where the signed query string didn't match the actual sent request due to inconsistent parameter ordering.
  - Fixed response parsing to match the real field names/shape (was assuming a different, incorrect shape).
  - Cursor-based pagination (was assuming page-number pagination, which doesn't exist on this endpoint).
  - Dedupes duplicate transfer-leg rows (each real transaction can appear as 2 rows sharing a hash).
  - Retry-with-backoff on HTTP 429 (trial-tier OKX keys rate-limit easily; a single wallet's paginated history can trip it on its own).
  - `get_address_analysis` (supplemental signal) still uses an **unverified** endpoint path — degrades gracefully on failure, doesn't block generation.

### Generative renderer (`services/renderer/`)
- `palette.py`, `shapes.py`, `composer.py`, `animator.py` — deterministic SVG generation, seeded from `SHA-256(wallet+chain)`.
- Fixed: wallet-address case wasn't normalized consistently (watermark text vs. RNG seed), which broke the "same wallet → same art" guarantee for mixed-case input.
- **Verified live**: two real wallets (Vitalik's, and the Ethereum Foundation donation wallet) produce visibly different feature vectors and byte-different SVGs; the same wallet called twice produces a byte-identical SVG (cached).

### API (`services/api/`)
- `/generate`, `/portrait/{id}`, `/mint`, `/mint/{id}/status`, `/health`, `/chains` — all implemented and tested.
- Fixed a crash bug: `hashlib.keccak_256` doesn't exist in Python's standard library — every `/generate` call would have 500'd. Now uses `Web3.keccak`.
- Fixed a Windows-only crash: an emoji in a startup log line broke under `cp1252` console encoding — the API couldn't start at all on Windows.
- `payment.py` — **rewritten to the real x402 wire format** (proper 402 response body with `x402Version`/`accepts`, `X-PAYMENT` header parsing, EIP-3009 authorization structural/expiry/amount validation). The actual facilitator (OKX's "Broker") verify/settle call is a clearly-marked stub — see "Not done" below.
- `mcp_server.py` — FastMCP wrapper, same keccak fix applied.

### Smart contract (`contracts/`)
- `SigilX.sol` (moved to `contracts/src/`) — ERC-721, on-chain metadata, minter authorization, mint-fee handling, portraitId uniqueness.
- Fixed 5 real bugs blocking compile/test entirely: eager Hardhat account-key validation crashing on placeholder `.env` values, a `sources`/`node_modules` path collision, an em-dash inside a Solidity string literal (invalid — Solidity string literals must be ASCII), wrong contract name (`ChainPortrait` vs. actual `SigilX`) in the test suite and both deploy scripts.
- De-risked the EVM target: pinned `@openzeppelin/contracts` to `5.0.2` and `evmVersion: "shanghai"` instead of the newer OpenZeppelin release's `cancun`/MCOPY requirement, since X Layer's Cancun opcode support isn't confirmed.
- **32/32 Hardhat tests passing.**

### Frontend (`web/`)
- Fully rebuilt — the previous `web/` was an unrelated leftover template (a "v0 IRL NYC" event lanyard generator), not a SigilX frontend at all.
- Wallet-input home page → animated SVG + feature radar chart (Recharts) → mint button.
- `/portrait/[id]` share page with OG/Twitter meta tags.
- OG image generation route repurposed for portrait cards.
- Trimmed dependencies from 599 → 169 installed packages (dropped an unused three.js/react-three-fiber/Expo stack that only existed for the deleted 3D lanyard card).
- Verified via SSR/`curl` + backend integration (no `chromium-cli` available in this environment for a full visual browser screenshot test).

### Tests
- **39 Python tests** (`tests/test_extractor.py`, `test_renderer.py`, `test_api.py`, `test_payment.py`) — all passing. Covers entropy math, fingerprint determinism, SVG determinism, API routes (mocked OKX), and the x402 middleware wire format.
- **32 Hardhat tests** (`contracts/test/ChainPortrait.test.js`) — all passing.

### Live verification
- Real OKX Market API credentials obtained (via OKX's Onchain OS Dev Portal, which turned out to be a separate developer key-issuance flow from the India-restricted consumer exchange signup).
- `/generate` tested end-to-end against live OKX data for two real wallets — confirmed working, deterministic, and visibly distinct art per wallet.

---

## 🔴 Not done / open

- **Testnet contract deploy.** Compiled and tested, `.env` has a funded wallet — deploy itself hasn't been run yet (was about to, pending confirmation).
- **Real facilitator (OKX "Broker") integration.** `payment.py` is wire-correct but the actual verify/settle call is stubbed — OKX's Broker endpoint/auth aren't in their public docs, only surfaced through the interactive `npx skills add okx/onchainos-skills` installer.
- **`get_address_analysis` endpoint is unverified.** Supplemental signal only, degrades gracefully, but the real path/shape was never confirmed like the transaction-history endpoint was.
- **Mainnet deploy.** Explicitly out of scope so far — testnet only.
- **A2MCP registration / OKX.AI marketplace listing.** Not started.
- **Missing docs** referenced by `README.md`'s own repo layout: `docs/api-reference.md`, `docs/entropy-math.md`, `docs/art-algorithm.md`.
- **No deployment/hosting setup** — no `docker-compose.yml`, no server, still fully local dev. Both dev servers (frontend `:3000`, backend `:8000`) are only running locally in this session.
- **Demo submission logistics** (X post, ≤90s video, Google form) — explicitly deprioritized per earlier instruction.

---

## Known issues / caveats (not bugs, just worth knowing)

- `chaos_dimension` came out near-zero for both real wallets tested — a lot of their transactions are zero-native-value contract calls (token/NFT interactions denominated in a token, not ETH), which flattens that particular metric. The math is working correctly on the data it's given.
- OKX's trial-tier API key rate-limits fairly aggressively; a single wallet with heavy activity needs several paginated requests just on its own, which can trip the limit even without concurrent traffic. The retry-with-backoff logic handles this, but expect `/generate` on very active wallets to occasionally take 10-25s.
