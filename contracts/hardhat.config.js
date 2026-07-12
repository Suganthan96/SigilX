require("@nomicfoundation/hardhat-toolbox");
require("@nomicfoundation/hardhat-verify");
require("hardhat-contract-sizer");
require("dotenv").config({ path: "../.env" });

// Only treat a key as usable if it's a well-formed 32-byte hex string —
// otherwise placeholder values (e.g. from .env.example) would break `compile`/`test`,
// which don't need a real account at all.
const _normalizeKey = (raw) =>
  /^(0x)?[0-9a-fA-F]{64}$/.test(raw || "") ? (raw.startsWith("0x") ? raw : `0x${raw}`) : "";

// Testnet keeps using the shared XLAYER_PRIVATE_KEY (also the ongoing minter/
// facilitator relayer key). Mainnet deploys use a dedicated key so a fresh
// deploy-only wallet never needs to touch the testnet-facing key.
const TESTNET_DEPLOYER_PRIVATE_KEY = _normalizeKey(process.env.XLAYER_PRIVATE_KEY);
const MAINNET_DEPLOYER_PRIVATE_KEY = _normalizeKey(
  process.env.XLAYER_PRIVATE_KEY_MAINNET || process.env.XLAYER_PRIVATE_KEY
);
const XLAYER_TESTNET_RPC   = process.env.XLAYER_RPC_TESTNET || "https://testrpc.xlayer.tech/terigon";
const XLAYER_MAINNET_RPC   = process.env.XLAYER_RPC_MAINNET || "https://rpc.xlayer.tech";

// Explorer API keys for contract verification
const XLAYER_EXPLORER_API_KEY = process.env.XLAYER_EXPLORER_API_KEY || "placeholder";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      // Required once mint() carries the extra `svg` calldata param (Portrait.svg
      // on-chain storage) — otherwise solc hits "stack too deep".
      viaIR: true,
      // Pinned explicitly (rather than relying on solc's shifting default) so a future
      // solc bump doesn't silently start emitting opcodes X Layer may not yet support.
      // X Layer's Cancun (MCOPY/EIP-5656) support isn't confirmed as of this writing;
      // shanghai is a safe, widely-supported target. @openzeppelin/contracts is pinned
      // to 5.0.2 (predates the MCOPY-using Bytes.sol utility) to match.
      evmVersion: "shanghai",
    },
  },

  networks: {
    // ── Local dev ─────────────────────────────────────────────────────────
    hardhat: {
      chainId: 31337,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },

    // ── X Layer Testnet (Chain ID 1952) ───────────────────────────────────
    "xlayer-testnet": {
      url: XLAYER_TESTNET_RPC,
      chainId: 1952,
      accounts: TESTNET_DEPLOYER_PRIVATE_KEY ? [TESTNET_DEPLOYER_PRIVATE_KEY] : [],
      gasPrice: "auto",
      gas: "auto",
    },

    // ── X Layer Mainnet (Chain ID 196) ────────────────────────────────────
    "xlayer-mainnet": {
      url: XLAYER_MAINNET_RPC,
      chainId: 196,
      accounts: MAINNET_DEPLOYER_PRIVATE_KEY ? [MAINNET_DEPLOYER_PRIVATE_KEY] : [],
      gasPrice: "auto",
      gas: "auto",
    },
  },

  // Contract verification (OKLink / X Layer explorer)
  etherscan: {
    apiKey: {
      "xlayer-testnet": XLAYER_EXPLORER_API_KEY,
      "xlayer-mainnet": XLAYER_EXPLORER_API_KEY,
    },
    customChains: [
      {
        network: "xlayer-testnet",
        chainId: 1952,
        urls: {
          apiURL:  "https://www.oklink.com/api/v5/explorer/contract/verify-source-code-plugin/XLAYER_TESTNET",
          browserURL: "https://www.oklink.com/xlayer-test",
        },
      },
      {
        network: "xlayer-mainnet",
        chainId: 196,
        urls: {
          apiURL:  "https://www.oklink.com/api/v5/explorer/contract/verify-source-code-plugin/XLAYER",
          browserURL: "https://www.oklink.com/xlayer",
        },
      },
    ],
  },

  contractSizer: {
    alphaSort: true,
    disambiguatePaths: false,
    runOnCompile: true,
    strict: false,
  },

  paths: {
    // "./src" (not "./") so Hardhat's source scan doesn't collide with
    // ./node_modules, which lives alongside the contracts in this repo layout.
    sources:   "./src",
    tests:     "./test",
    cache:     "./cache",
    artifacts: "./artifacts",
  },
};
