/**
 * test/ChainPortrait.test.js
 *
 * Full test suite for ChainPortrait.sol
 * Run: npx hardhat test
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-toolbox/network-helpers");

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

function makePortraitId(wallet, chain) {
  const hash = ethers.keccak256(ethers.toUtf8Bytes(`${wallet}:${chain}`));
  return `cp_${hash.slice(2, 18)}`;
}

function makeSvgHash(svgString) {
  return ethers.keccak256(ethers.toUtf8Bytes(svgString));
}

const SAMPLE_FEATURE_VECTOR = JSON.stringify({
  activity_entropy: 0.73,
  timing_regularity: 0.21,
  amount_variance: 0.88,
  interaction_diversity: 0.55,
  burst_coefficient: 0.67,
  recency_decay: 0.90,
  volume_skew: 0.43,
  chaos_dimension: 0.61,
});

const SAMPLE_SVG = "<svg><circle cx='300' cy='300' r='100'/></svg>";

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

async function deployFixture() {
  const [owner, minter, user, other] = await ethers.getSigners();

  const mintFee = ethers.parseEther("0");   // free for tests
  const ChainPortrait = await ethers.getContractFactory("SigilX");
  const contract = await ChainPortrait.deploy(owner.address, mintFee);
  await contract.waitForDeployment();

  // Authorize minter
  await contract.connect(owner).setMinter(minter.address, true);

  return { contract, owner, minter, user, other, mintFee };
}

async function deployWithFeeFixture() {
  const [owner, minter, user] = await ethers.getSigners();
  const mintFee = ethers.parseEther("0.01");
  const ChainPortrait = await ethers.getContractFactory("SigilX");
  const contract = await ChainPortrait.deploy(owner.address, mintFee);
  await contract.waitForDeployment();
  await contract.connect(owner).setMinter(minter.address, true);
  return { contract, owner, minter, user, mintFee };
}

// ---------------------------------------------------------------------------
// Helper to mint one portrait
// ---------------------------------------------------------------------------

async function mintPortrait(contract, minter, { to, wallet, sourceChain, portraitId, svgHash, featureVector, txCount, svg, imageUri, metadataUri, value } = {}) {
  const _to          = to          ?? minter.address;
  const _wallet      = wallet      ?? minter.address;
  const _sourceChain = sourceChain ?? "eth-mainnet";
  const _portraitId  = portraitId  ?? makePortraitId(_wallet, _sourceChain);
  const _svgHash     = svgHash     ?? makeSvgHash(SAMPLE_SVG);
  const _fv          = featureVector ?? SAMPLE_FEATURE_VECTOR;
  const _txCount     = txCount     ?? 100;
  const _svg         = svg         ?? SAMPLE_SVG;
  const _imageUri    = imageUri    ?? "";
  const _metadataUri = metadataUri ?? "";
  const _value       = value       ?? 0n;

  return contract.connect(minter).mint(
    _to, _wallet, _sourceChain, _portraitId, _svgHash, _fv, _txCount, _svg, _imageUri, _metadataUri,
    { value: _value }
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChainPortrait", function () {

  // ─── Deployment ────────────────────────────────────────────────────────────

  describe("Deployment", function () {
    it("should set the correct name and symbol", async function () {
      const { contract } = await loadFixture(deployFixture);
      expect(await contract.name()).to.equal("SigilX");
      expect(await contract.symbol()).to.equal("SIGIL");
    });

    it("should set the correct owner", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      expect(await contract.owner()).to.equal(owner.address);
    });

    it("should authorize owner as minter by default", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      expect(await contract.authorizedMinters(owner.address)).to.equal(true);
    });

    it("should set mint fee correctly", async function () {
      const { contract } = await loadFixture(deployWithFeeFixture);
      expect(await contract.mintFee()).to.equal(ethers.parseEther("0.01"));
    });

    it("should start with zero total supply", async function () {
      const { contract } = await loadFixture(deployFixture);
      expect(await contract.totalSupply()).to.equal(0n);
    });
  });

  // ─── Minting ───────────────────────────────────────────────────────────────

  describe("Minting", function () {
    it("should mint a portrait and increment supply", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      await mintPortrait(contract, minter, { to: user.address });
      expect(await contract.totalSupply()).to.equal(1n);
    });

    it("should assign token to the recipient", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      await mintPortrait(contract, minter, { to: user.address });
      expect(await contract.ownerOf(1)).to.equal(user.address);
    });

    it("should emit PortraitMinted event", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      const wallet = user.address;
      const chain = "eth-mainnet";
      const pid = makePortraitId(wallet, chain);

      await expect(mintPortrait(contract, minter, { to: user.address, wallet, sourceChain: chain, portraitId: pid }))
        .to.emit(contract, "PortraitMinted")
        .withArgs(1n, user.address, wallet, pid, chain);
    });

    it("should store portrait data on-chain", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      const wallet = user.address;
      const chain = "polygon-mainnet";
      const pid = makePortraitId(wallet, chain);
      const svgHash = makeSvgHash(SAMPLE_SVG);

      await mintPortrait(contract, minter, {
        to: user.address, wallet, sourceChain: chain,
        portraitId: pid, svgHash, featureVector: SAMPLE_FEATURE_VECTOR, txCount: 847,
      });

      const portrait = await contract.getPortrait(1);
      expect(portrait.wallet.toLowerCase()).to.equal(wallet.toLowerCase());
      expect(portrait.sourceChain).to.equal(chain);
      expect(portrait.portraitId).to.equal(pid);
      expect(portrait.svgHash).to.equal(svgHash);
      expect(portrait.featureVector).to.equal(SAMPLE_FEATURE_VECTOR);
      expect(portrait.txCount).to.equal(847n);
    });

    it("should map portraitId → tokenId", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      const pid = makePortraitId(user.address, "eth-mainnet");
      await mintPortrait(contract, minter, { to: user.address, portraitId: pid });
      expect(await contract.getTokenByPortraitId(pid)).to.equal(1n);
    });

    it("should reject minting from unauthorized caller", async function () {
      const { contract, user } = await loadFixture(deployFixture);
      await expect(
        mintPortrait(contract, user)
      ).to.be.revertedWithCustomError(contract, "NotAuthorizedMinter");
    });

    it("should reject duplicate portraitId", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      const pid = makePortraitId(user.address, "eth-mainnet");
      await mintPortrait(contract, minter, { portraitId: pid });
      await expect(
        mintPortrait(contract, minter, { portraitId: pid })
      ).to.be.revertedWithCustomError(contract, "PortraitAlreadyMinted");
    });

    it("should reject zero address recipient", async function () {
      const { contract, minter } = await loadFixture(deployFixture);
      await expect(
        mintPortrait(contract, minter, { to: ZERO_ADDRESS })
      ).to.be.revertedWithCustomError(contract, "InvalidAddress");
    });

    it("should reject empty portraitId", async function () {
      const { contract, minter } = await loadFixture(deployFixture);
      await expect(
        mintPortrait(contract, minter, { portraitId: "" })
      ).to.be.revertedWithCustomError(contract, "EmptyPortraitId");
    });

    it("should reject zero svgHash", async function () {
      const { contract, minter } = await loadFixture(deployFixture);
      await expect(
        mintPortrait(contract, minter, { svgHash: ethers.ZeroHash })
      ).to.be.revertedWithCustomError(contract, "EmptySVGHash");
    });

    it("should reject insufficient mint fee", async function () {
      const { contract, minter, user, mintFee } = await loadFixture(deployWithFeeFixture);
      await expect(
        mintPortrait(contract, minter, { to: user.address, value: mintFee - 1n })
      ).to.be.revertedWithCustomError(contract, "InsufficientMintFee");
    });

    it("should accept exact mint fee", async function () {
      const { contract, minter, user, mintFee } = await loadFixture(deployWithFeeFixture);
      await expect(
        mintPortrait(contract, minter, { to: user.address, value: mintFee })
      ).to.not.be.reverted;
    });

    it("should accept overpayment of mint fee", async function () {
      const { contract, minter, user, mintFee } = await loadFixture(deployWithFeeFixture);
      await expect(
        mintPortrait(contract, minter, { to: user.address, value: mintFee * 2n })
      ).to.not.be.reverted;
    });

    it("should mint multiple distinct portraits", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      const chains = ["eth-mainnet", "polygon-mainnet", "bsc-mainnet"];
      for (const chain of chains) {
        const pid = makePortraitId(user.address, chain);
        await mintPortrait(contract, minter, { to: user.address, sourceChain: chain, portraitId: pid });
      }
      expect(await contract.totalSupply()).to.equal(3n);
      expect(await contract.ownerOf(1)).to.equal(user.address);
      expect(await contract.ownerOf(2)).to.equal(user.address);
      expect(await contract.ownerOf(3)).to.equal(user.address);
    });
  });

  // ─── Token URI ─────────────────────────────────────────────────────────────

  describe("Token URI", function () {
    it("should return a data URI", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      await mintPortrait(contract, minter, { to: user.address });
      const uri = await contract.tokenURI(1);
      expect(uri).to.match(/^data:application\/json;base64,/);
    });

    it("should decode to valid JSON with required fields", async function () {
      const { contract, minter, user } = await loadFixture(deployFixture);
      await mintPortrait(contract, minter, { to: user.address });
      const uri = await contract.tokenURI(1);
      const base64 = uri.replace("data:application/json;base64,", "");
      const json = JSON.parse(Buffer.from(base64, "base64").toString("utf-8"));

      expect(json).to.have.property("name");
      expect(json).to.have.property("description");
      expect(json).to.have.property("external_url");
      expect(json).to.have.property("image");
      expect(json).to.have.property("attributes");
      expect(Array.isArray(json.attributes)).to.equal(true);
    });

    it("should revert for non-existent token", async function () {
      const { contract } = await loadFixture(deployFixture);
      await expect(contract.tokenURI(999)).to.be.reverted;
    });
  });

  // ─── Admin ─────────────────────────────────────────────────────────────────

  describe("Admin", function () {
    it("should allow owner to authorize a minter", async function () {
      const { contract, owner, other } = await loadFixture(deployFixture);
      await contract.connect(owner).setMinter(other.address, true);
      expect(await contract.authorizedMinters(other.address)).to.equal(true);
    });

    it("should emit MinterUpdated event", async function () {
      const { contract, owner, other } = await loadFixture(deployFixture);
      await expect(contract.connect(owner).setMinter(other.address, true))
        .to.emit(contract, "MinterUpdated")
        .withArgs(other.address, true);
    });

    it("should allow owner to revoke a minter", async function () {
      const { contract, owner, minter } = await loadFixture(deployFixture);
      await contract.connect(owner).setMinter(minter.address, false);
      expect(await contract.authorizedMinters(minter.address)).to.equal(false);
    });

    it("should reject setMinter from non-owner", async function () {
      const { contract, user, other } = await loadFixture(deployFixture);
      await expect(
        contract.connect(user).setMinter(other.address, true)
      ).to.be.revertedWithCustomError(contract, "OwnableUnauthorizedAccount");
    });

    it("should allow owner to update mint fee", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      const newFee = ethers.parseEther("0.05");
      await expect(contract.connect(owner).setMintFee(newFee))
        .to.emit(contract, "MintFeeUpdated");
      expect(await contract.mintFee()).to.equal(newFee);
    });

    it("should allow owner to withdraw collected fees", async function () {
      const { contract, minter, user, owner, mintFee } = await loadFixture(deployWithFeeFixture);
      await mintPortrait(contract, minter, { to: user.address, value: mintFee });

      const ownerBalBefore = await ethers.provider.getBalance(owner.address);
      const tx = await contract.connect(owner).withdraw();
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const ownerBalAfter = await ethers.provider.getBalance(owner.address);

      expect(ownerBalAfter).to.equal(ownerBalBefore + mintFee - gasCost);
    });

    it("should reject withdraw from non-owner", async function () {
      const { contract, user } = await loadFixture(deployFixture);
      await expect(
        contract.connect(user).withdraw()
      ).to.be.revertedWithCustomError(contract, "OwnableUnauthorizedAccount");
    });
  });

  // ─── ERC-721 standard compliance ──────────────────────────────────────────

  describe("ERC-721 Compliance", function () {
    it("should support transferring tokens", async function () {
      const { contract, minter, user, other } = await loadFixture(deployFixture);
      await mintPortrait(contract, minter, { to: user.address });
      await contract.connect(user).transferFrom(user.address, other.address, 1);
      expect(await contract.ownerOf(1)).to.equal(other.address);
    });

    it("should support approve and transferFrom", async function () {
      const { contract, minter, user, other } = await loadFixture(deployFixture);
      await mintPortrait(contract, minter, { to: user.address });
      await contract.connect(user).approve(other.address, 1);
      await contract.connect(other).transferFrom(user.address, other.address, 1);
      expect(await contract.ownerOf(1)).to.equal(other.address);
    });

    it("should report supportsInterface for ERC721 and ERC165", async function () {
      const { contract } = await loadFixture(deployFixture);
      expect(await contract.supportsInterface("0x80ac58cd")).to.equal(true); // ERC721
      expect(await contract.supportsInterface("0x01ffc9a7")).to.equal(true); // ERC165
    });
  });
});
