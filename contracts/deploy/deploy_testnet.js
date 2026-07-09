/**
 * deploy/deploy_testnet.js
 *
 * Deploy ChainPortrait to X Layer Testnet (Chain ID 1952).
 *
 * Prerequisites:
 *   1. Set XLAYER_PRIVATE_KEY in ../.env
 *   2. Get testnet OKB from faucet: https://www.okx.com/xlayer/faucet
 *   3. Run: npm run deploy:testnet
 *
 * After deploy:
 *   - Save the contract address to ../.env as CHAIN_PORTRAIT_ADDRESS_TESTNET
 *   - Verify: npm run verify:testnet -- <CONTRACT_ADDRESS> <OWNER_ADDRESS> <MINT_FEE>
 */

const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();

  console.log("═══════════════════════════════════════════════════════");
  console.log("  SigilX — ChainPortrait Testnet Deploy");
  console.log("═══════════════════════════════════════════════════════");
  console.log(`  Network:   X Layer Testnet (Chain ID 1952)`);
  console.log(`  Deployer:  ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`  Balance:   ${ethers.formatEther(balance)} OKB`);
  console.log("═══════════════════════════════════════════════════════\n");

  if (balance === 0n) {
    throw new Error(
      "Deployer has 0 OKB. Get testnet OKB from: https://www.okx.com/xlayer/faucet"
    );
  }

  // ── Deploy parameters ──────────────────────────────────────────────────────
  const initialOwner = deployer.address;
  // Testnet: free mint (0 OKB) for easy testing
  const mintFee = ethers.parseEther("0");

  // ── Deploy ─────────────────────────────────────────────────────────────────
  console.log("Deploying ChainPortrait...");
  const ChainPortrait = await ethers.getContractFactory("SigilX");
  const contract = await ChainPortrait.deploy(initialOwner, mintFee);
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const deployTx = contract.deploymentTransaction();

  console.log("\n✅ ChainPortrait deployed!");
  console.log(`   Contract:  ${address}`);
  console.log(`   Tx hash:   ${deployTx?.hash}`);
  console.log(`   Explorer:  https://www.oklink.com/xlayer-test/address/${address}`);

  // ── Post-deploy setup ──────────────────────────────────────────────────────
  // If a separate minter wallet is specified, authorize it
  const minterAddress = process.env.MINTER_ADDRESS;
  if (minterAddress && minterAddress !== deployer.address) {
    console.log(`\nAuthorizing minter: ${minterAddress}`);
    const tx = await contract.setMinter(minterAddress, true);
    await tx.wait();
    console.log(`   ✅ Minter authorized. Tx: ${tx.hash}`);
  }

  // ── Summary ────────────────────────────────────────────────────────────────
  console.log("\n─── Add to .env ──────────────────────────────────────────");
  console.log(`CHAIN_PORTRAIT_ADDRESS_TESTNET=${address}`);
  console.log("─────────────────────────────────────────────────────────");

  console.log("\n─── Verify command ───────────────────────────────────────");
  console.log(
    `npx hardhat verify --network xlayer-testnet ${address} "${initialOwner}" "${mintFee}"`
  );
  console.log("─────────────────────────────────────────────────────────\n");

  return address;
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("\n❌ Deploy failed:", err.message);
    process.exit(1);
  });
