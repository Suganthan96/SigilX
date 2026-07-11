/**
 * deploy/deploy_payment_token_testnet.js
 *
 * Deploy PaymentToken (a minimal EIP-3009 test asset) to X Layer Testnet.
 * Used as the x402 payment asset for SigilX's own self-hosted facilitator —
 * there's no live EIP-3009 token (e.g. USDC) on X Layer testnet to point at.
 *
 * Run: npx hardhat run deploy/deploy_payment_token_testnet.js --network xlayer-testnet
 *
 * After deploy: save the address to ../.env as X402_ASSET
 */

const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();

  console.log("═══════════════════════════════════════════════════════");
  console.log("  SigilX — PaymentToken (x402 test asset) Testnet Deploy");
  console.log("═══════════════════════════════════════════════════════");
  console.log(`  Deployer:  ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`  Balance:   ${ethers.formatEther(balance)} OKB`);
  console.log("═══════════════════════════════════════════════════════\n");

  if (balance === 0n) {
    throw new Error("Deployer has 0 OKB. Get testnet OKB from: https://www.okx.com/xlayer/faucet");
  }

  const initialSupply = ethers.parseUnits("1000000", 18); // 1,000,000 sUSD to deployer

  console.log("Deploying PaymentToken...");
  const PaymentToken = await ethers.getContractFactory("PaymentToken");
  const token = await PaymentToken.deploy(initialSupply);
  await token.waitForDeployment();

  const address = await token.getAddress();
  const deployTx = token.deploymentTransaction();

  console.log("\n✅ PaymentToken deployed!");
  console.log(`   Contract:  ${address}`);
  console.log(`   Tx hash:   ${deployTx?.hash}`);
  console.log(`   Explorer:  https://www.oklink.com/xlayer-test/address/${address}`);

  console.log("\n─── Add to .env ──────────────────────────────────────────");
  console.log(`X402_ASSET=${address}`);
  console.log("─────────────────────────────────────────────────────────\n");

  return address;
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("\n❌ Deploy failed:", err.message);
    process.exit(1);
  });
