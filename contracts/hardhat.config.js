require("@nomicfoundation/hardhat-toolbox");
require("@nomicfoundation/hardhat-verify");
require("hardhat-contract-sizer");
require("dotenv").config({ path: "../.env" });

const DEPLOYER_PRIVATE_KEY = process.env.XLAYER_PRIVATE_KEY || "";
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
      viaIR: false,
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
    sources:   "./",
    tests:     "./test",
    cache:     "./cache",
    artifacts: "./artifacts",
  },
};
