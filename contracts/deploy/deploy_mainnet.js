/**
 * deploy/deploy_mainnet.js
 *
 * Deploy ChainPortrait to X Layer Mainnet (Chain ID 196).
 *
 * Prerequisites:
 *   1. Contract tested and verified on testnet first
 *   2. Set XLAYER_PRIVATE_KEY in ../.env (funded with real OKB)
 *   3. Set MINTER_ADDRESS in ../.env (the SigilX API service wallet)
 *   4. Run: npm run deploy:mainnet
 *
 * IMPORTANT: This deploys to MAINNET with REAL OKB.
 *   - Double-check all parameters before running.
 *   - Requires Revenue Rocket judging → mainnet is mandatory.
 */

const { ethers } = require("hardhat");

// Safety confirmation for mainnet deploys
const MAINNET_CONFIRMATION_PHRASE = process.env.MAINNET_DEPLOY_CONFIRM || "";
const REQUIRED_PHRASE = "DEPLOY_TO_MAINNET";

async function main() {
  // ── Safety check ────────────────────────────────────────────────────────────
  if (MAINNET_CONFIRMATION_PHRASE !== REQUIRED_PHRASE) {
    throw new Error(
      `Mainnet deploy requires env var MAINNET_DEPLOY_CONFIRM="${REQUIRED_PHRASE}"\n` +
      `Set this explicitly to confirm you intend to deploy to X Layer Mainnet.`
    );
  }

  const [deployer] = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();

  console.log("═══════════════════════════════════════════════════════");
  console.log("  SigilX — ChainPortrait MAINNET Deploy");
  console.log("═══════════════════════════════════════════════════════");
  console.log(`  Network:   X Layer Mainnet (Chain ID ${network.chainId})`);
  console.log(`  Deployer:  ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`  Balance:   ${ethers.formatEther(balance)} OKB`);

  if (network.chainId !== 196n) {
    throw new Error(
      `Wrong network! Expected X Layer Mainnet (196), got ${network.chainId}.\n` +
      `Run with --network xlayer-mainnet`
    );
  }

  if (balance < ethers.parseEther("0.01")) {
    throw new Error("Deployer balance too low. Need at least 0.01 OKB for gas.");
  }

  console.log("═══════════════════════════════════════════════════════\n");

  // ── Deploy parameters ──────────────────────────────────────────────────────
  const initialOwner = deployer.address;

  // Mainnet mint fee: 0.005 OKB (~$0.02 at current prices)
  // Adjust based on OKB price closer to launch
  const mintFeeOKB = process.env.MINT_FEE_OKB || "0.005";
  const mintFee = ethers.parseEther(mintFeeOKB);

  console.log(`  Mint fee:  ${mintFeeOKB} OKB`);
  console.log("");

  // ── Deploy ─────────────────────────────────────────────────────────────────
  console.log("Deploying ChainPortrait to X Layer Mainnet...");
  const ChainPortrait = await ethers.getContractFactory("ChainPortrait");

  // Estimate gas first
  const deployTxData = await ChainPortrait.getDeployTransaction(initialOwner, mintFee);
  const gasEstimate = await ethers.provider.estimateGas(deployTxData);
  const feeData = await ethers.provider.getFeeData();
  const estimatedCost = gasEstimate * (feeData.gasPrice || 0n);
  console.log(`  Est. gas:  ${gasEstimate.toString()} units`);
  console.log(`  Est. cost: ${ethers.formatEther(estimatedCost)} OKB\n`);

  const contract = await ChainPortrait.deploy(initialOwner, mintFee);
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const deployTx = contract.deploymentTransaction();
  const receipt = await deployTx?.wait();

  console.log("\n✅ ChainPortrait deployed to Mainnet!");
  console.log(`   Contract:  ${address}`);
  console.log(`   Tx hash:   ${deployTx?.hash}`);
  console.log(`   Block:     ${receipt?.blockNumber}`);
  console.log(`   Gas used:  ${receipt?.gasUsed?.toString()}`);
  console.log(`   Explorer:  https://www.oklink.com/xlayer/address/${address}`);

  // ── Authorize the SigilX API minter ───────────────────────────────────────
  const minterAddress = process.env.MINTER_ADDRESS;
  if (!minterAddress) {
    console.log("\n⚠️  MINTER_ADDRESS not set. Set it and run setMinter() manually.");
  } else if (minterAddress !== deployer.address) {
    console.log(`\nAuthorizing service minter: ${minterAddress}`);
    const tx = await contract.setMinter(minterAddress, true);
    const minterReceipt = await tx.wait();
    console.log(`   ✅ Minter authorized. Tx: ${tx.hash}, Block: ${minterReceipt?.blockNumber}`);
  }

  // ── Summary ────────────────────────────────────────────────────────────────
  console.log("\n─── Add to .env ──────────────────────────────────────────");
  console.log(`CHAIN_PORTRAIT_ADDRESS_MAINNET=${address}`);
  console.log("─────────────────────────────────────────────────────────");

  console.log("\n─── Verify on OKLink ─────────────────────────────────────");
  console.log(
    `npx hardhat verify --network xlayer-mainnet ${address} "${initialOwner}" "${mintFee}"`
  );
  console.log("─────────────────────────────────────────────────────────\n");

  return address;
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("\n❌ Mainnet deploy failed:", err.message);
    process.exit(1);
  });
