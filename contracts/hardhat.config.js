require("@nomicfoundation/hardhat-toolbox");
require("@nomicfoundation/hardhat-verify");
require("hardhat-contract-sizer");
require("dotenv").config({ path: "../.env" });

// Only treat XLAYER_PRIVATE_KEY as usable if it's a well-formed 32-byte hex key —
// otherwise placeholder values (e.g. from .env.example) would break `compile`/`test`,
// which don't need a real account at all.
const _rawKey = process.env.XLAYER_PRIVATE_KEY || "";
const DEPLOYER_PRIVATE_KEY = /^(0x)?[0-9a-fA-F]{64}$/.test(_rawKey)
  ? (_rawKey.startsWith("0x") ? _rawKey : `0x${_rawKey}`)
  : "";
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
      accounts: DEPLOYER_PRIVATE_KEY ? [DEPLOYER_PRIVATE_KEY] : [],
      gasPrice: "auto",
      gas: "auto",
    },

    // ── X Layer Mainnet (Chain ID 196) ────────────────────────────────────
    "xlayer-mainnet": {
      url: XLAYER_MAINNET_RPC,
      chainId: 196,
      accounts: DEPLOYER_PRIVATE_KEY ? [DEPLOYER_PRIVATE_KEY] : [],
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
