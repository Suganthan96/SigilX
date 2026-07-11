/**
 * test/PaymentToken.test.js
 *
 * Tests transferWithAuthorization (EIP-3009) — the on-chain settlement half
 * of SigilX's self-hosted x402 facilitator.
 * Run: npx hardhat test
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-toolbox/network-helpers");

async function deployTokenFixture() {
  const [deployer, payer, payee, other] = await ethers.getSigners();
  const PaymentToken = await ethers.getContractFactory("PaymentToken");
  const token = await PaymentToken.deploy(ethers.parseUnits("1000000", 18));
  await token.waitForDeployment();

  // Fund the payer so there's something to transfer
  await token.mint(payer.address, ethers.parseUnits("100", 18));

  return { token, deployer, payer, payee, other };
}

async function signAuthorization(token, signer, { from, to, value, validAfter, validBefore, nonce }) {
  const network = await ethers.provider.getNetwork();
  const domain = {
    name: "SigilX Test USD",
    version: "1",
    chainId: network.chainId,
    verifyingContract: await token.getAddress(),
  };
  const types = {
    TransferWithAuthorization: [
      { name: "from", type: "address" },
      { name: "to", type: "address" },
      { name: "value", type: "uint256" },
      { name: "validAfter", type: "uint256" },
      { name: "validBefore", type: "uint256" },
      { name: "nonce", type: "bytes32" },
    ],
  };
  const message = { from, to, value, validAfter, validBefore, nonce };
  const signature = await signer.signTypedData(domain, types, message);
  return ethers.Signature.from(signature);
}

function randomNonce() {
  return ethers.hexlify(ethers.randomBytes(32));
}

describe("PaymentToken (EIP-3009)", function () {
  describe("transferWithAuthorization", function () {
    it("transfers funds with a valid signed authorization", async function () {
      const { token, payer, payee } = await loadFixture(deployTokenFixture);
      const now = Math.floor(Date.now() / 1000);
      const value = ethers.parseUnits("10", 18);
      const nonce = randomNonce();

      const sig = await signAuthorization(token, payer, {
        from: payer.address, to: payee.address, value,
        validAfter: 0, validBefore: now + 3600, nonce,
      });

      await expect(
        token.transferWithAuthorization(payer.address, payee.address, value, 0, now + 3600, nonce, sig.v, sig.r, sig.s)
      ).to.emit(token, "AuthorizationUsed").withArgs(payer.address, nonce);

      expect(await token.balanceOf(payee.address)).to.equal(value);
    });

    it("rejects a replayed (already-used) nonce", async function () {
      const { token, payer, payee } = await loadFixture(deployTokenFixture);
      const now = Math.floor(Date.now() / 1000);
      const value = ethers.parseUnits("5", 18);
      const nonce = randomNonce();

      const sig = await signAuthorization(token, payer, {
        from: payer.address, to: payee.address, value,
        validAfter: 0, validBefore: now + 3600, nonce,
      });

      await token.transferWithAuthorization(payer.address, payee.address, value, 0, now + 3600, nonce, sig.v, sig.r, sig.s);

      await expect(
        token.transferWithAuthorization(payer.address, payee.address, value, 0, now + 3600, nonce, sig.v, sig.r, sig.s)
      ).to.be.revertedWith("PaymentToken: authorization already used");
    });

    it("rejects a signature from a different signer than 'from'", async function () {
      const { token, payer, payee, other } = await loadFixture(deployTokenFixture);
      const now = Math.floor(Date.now() / 1000);
      const value = ethers.parseUnits("5", 18);
      const nonce = randomNonce();

      // Signed by `other`, but claims to be from `payer`
      const sig = await signAuthorization(token, other, {
        from: payer.address, to: payee.address, value,
        validAfter: 0, validBefore: now + 3600, nonce,
      });

      await expect(
        token.transferWithAuthorization(payer.address, payee.address, value, 0, now + 3600, nonce, sig.v, sig.r, sig.s)
      ).to.be.revertedWith("PaymentToken: invalid signature");
    });

    it("rejects an expired authorization", async function () {
      const { token, payer, payee } = await loadFixture(deployTokenFixture);
      const now = Math.floor(Date.now() / 1000);
      const value = ethers.parseUnits("5", 18);
      const nonce = randomNonce();

      const sig = await signAuthorization(token, payer, {
        from: payer.address, to: payee.address, value,
        validAfter: 0, validBefore: now - 1, nonce,
      });

      await expect(
        token.transferWithAuthorization(payer.address, payee.address, value, 0, now - 1, nonce, sig.v, sig.r, sig.s)
      ).to.be.revertedWith("PaymentToken: authorization expired");
    });

    it("rejects an authorization that isn't valid yet", async function () {
      const { token, payer, payee } = await loadFixture(deployTokenFixture);
      const now = Math.floor(Date.now() / 1000);
      const value = ethers.parseUnits("5", 18);
      const nonce = randomNonce();

      const sig = await signAuthorization(token, payer, {
        from: payer.address, to: payee.address, value,
        validAfter: now + 3600, validBefore: now + 7200, nonce,
      });

      await expect(
        token.transferWithAuthorization(payer.address, payee.address, value, now + 3600, now + 7200, nonce, sig.v, sig.r, sig.s)
      ).to.be.revertedWith("PaymentToken: authorization not yet valid");
    });

    it("rejects moving more than the payer's balance", async function () {
      const { token, payer, payee } = await loadFixture(deployTokenFixture);
      const now = Math.floor(Date.now() / 1000);
      const value = ethers.parseUnits("999", 18); // payer only has 100
      const nonce = randomNonce();

      const sig = await signAuthorization(token, payer, {
        from: payer.address, to: payee.address, value,
        validAfter: 0, validBefore: now + 3600, nonce,
      });

      await expect(
        token.transferWithAuthorization(payer.address, payee.address, value, 0, now + 3600, nonce, sig.v, sig.r, sig.s)
      ).to.be.reverted;
    });
  });

  describe("authorizationState", function () {
    it("reports false before use and true after", async function () {
      const { token, payer, payee } = await loadFixture(deployTokenFixture);
      const now = Math.floor(Date.now() / 1000);
      const value = ethers.parseUnits("1", 18);
      const nonce = randomNonce();

      expect(await token.authorizationState(payer.address, nonce)).to.equal(false);

      const sig = await signAuthorization(token, payer, {
        from: payer.address, to: payee.address, value,
        validAfter: 0, validBefore: now + 3600, nonce,
      });
      await token.transferWithAuthorization(payer.address, payee.address, value, 0, now + 3600, nonce, sig.v, sig.r, sig.s);

      expect(await token.authorizationState(payer.address, nonce)).to.equal(true);
    });
  });
});
