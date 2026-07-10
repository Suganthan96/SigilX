// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Base64.sol";
import "@openzeppelin/contracts/utils/Strings.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title SigilX
 * @notice ERC-721 contract for SigilX NFTs.
 *
 * Each token represents a unique, algorithmically generated artwork
 * derived from a wallet's on-chain behavioral fingerprint.
 *
 * Key properties:
 *  - Deterministic: same (wallet, chain) pair always produces the same portraitId
 *  - On-chain metadata: feature vector + SVG hash stored immutably per token
 *  - tokenURI returns a fully on-chain base64-encoded JSON metadata blob
 *  - One portrait per (wallet, sourceChain) combination (enforced)
 *  - Mint fee collected; owner can withdraw
 *
 * Deployed on X Layer:
 *   Testnet  — Chain ID 1952, RPC https://testrpc.xlayer.tech/terigon
 *   Mainnet  — Chain ID 196,  RPC https://rpc.xlayer.tech
 */
contract SigilX is ERC721URIStorage, Ownable, ReentrancyGuard {
    using Strings for uint256;
    using Strings for address;

    // -------------------------------------------------------------------------
    // Types
    // -------------------------------------------------------------------------

    /**
     * @dev On-chain metadata stored per token.
     */
    struct Portrait {
        address wallet;          // analyzed wallet address
        string  sourceChain;     // e.g. "eth-mainnet"
        string  portraitId;      // deterministic ID: "cp_<hex16>"
        bytes32 svgHash;         // keccak256 of the SVG string for verifiability
        string  featureVector;   // JSON-encoded 8D feature vector
        uint256 mintedAt;        // block.timestamp at mint
        uint256 txCount;         // number of txs analyzed
        string  svg;             // full SVG string, embedded on-chain for tokenURI()
        string  imageUri;        // optional IPFS gateway URL for the image
        string  metadataUri;     // optional IPFS gateway URL for the full metadata JSON;
                                  // returned directly by tokenURI() when set, since most
                                  // explorers only index tokenURI() when it's a real link
                                  // rather than an inline data URI
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    uint256 private _tokenCounter;

    /// @notice Mint fee in wei (OKB on X Layer). Owner can update.
    uint256 public mintFee;

    /// @notice portrait data per tokenId
    mapping(uint256 => Portrait) public portraits;

    /// @notice Prevent double-minting: portraitId → tokenId
    mapping(string => uint256) public portraitIdToToken;

    /// @notice Authorized minters (the SigilX backend service wallet)
    mapping(address => bool) public authorizedMinters;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    event PortraitMinted(
        uint256 indexed tokenId,
        address indexed to,
        address indexed wallet,
        string  portraitId,
        string  sourceChain
    );

    event MinterUpdated(address indexed minter, bool authorized);
    event MintFeeUpdated(uint256 oldFee, uint256 newFee);
    event FundsWithdrawn(address indexed to, uint256 amount);

    // -------------------------------------------------------------------------
    // Errors
    // -------------------------------------------------------------------------

    error NotAuthorizedMinter(address caller);
    error PortraitAlreadyMinted(string portraitId, uint256 existingTokenId);
    error InsufficientMintFee(uint256 sent, uint256 required);
    error InvalidAddress();
    error WithdrawFailed();
    error EmptyPortraitId();
    error EmptySVGHash();
    error EmptySVG();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    /**
     * @param initialOwner  Contract owner (deployer recommended)
     * @param _mintFee      Initial mint fee in wei (set to 0 for free minting)
     */
    constructor(address initialOwner, uint256 _mintFee)
        ERC721("SigilX", "SIGIL")
        Ownable(initialOwner)
    {
        mintFee = _mintFee;
        // Owner is also an authorized minter by default
        authorizedMinters[initialOwner] = true;
    }

    // -------------------------------------------------------------------------
    // Minting
    // -------------------------------------------------------------------------

    /**
     * @notice Mint a Chain Portrait NFT.
     *
     * @dev Only callable by authorized minters (the SigilX API backend).
     *      Enforces uniqueness per portraitId — one mint per (wallet, chain) pair.
     *      Caller must send at least `mintFee` wei.
     *
     * @param to             Recipient address (the user's wallet)
     * @param wallet         The analyzed wallet address
     * @param sourceChain    Source chain identifier (e.g. "eth-mainnet")
     * @param portraitId     Deterministic portrait ID ("cp_<hex16>")
     * @param svgHash        keccak256 of the generated SVG string
     * @param featureVector  JSON-encoded feature vector string
     * @param txCount        Number of transactions analyzed
     * @param svg            Full SVG string, stored on-chain and embedded in tokenURI()
     * @param imageUri       Optional IPFS gateway URL for the SVG; pass "" if unavailable
     * @param metadataUri    Optional IPFS gateway URL for the full metadata JSON; returned
     *                       directly by tokenURI() when set. Pass "" if unavailable.
     *
     * @return tokenId       The newly minted token ID
     */
    function mint(
        address to,
        address wallet,
        string  calldata sourceChain,
        string  calldata portraitId,
        bytes32 svgHash,
        string  calldata featureVector,
        uint256 txCount,
        string  calldata svg,
        string  calldata imageUri,
        string  calldata metadataUri
    )
        external
        payable
        nonReentrant
        returns (uint256 tokenId)
    {
        // ── Auth ────────────────────────────────────────────────────────────
        if (!authorizedMinters[msg.sender]) revert NotAuthorizedMinter(msg.sender);

        // ── Validation ──────────────────────────────────────────────────────
        if (to == address(0))    revert InvalidAddress();
        if (wallet == address(0)) revert InvalidAddress();
        if (bytes(portraitId).length == 0) revert EmptyPortraitId();
        if (svgHash == bytes32(0)) revert EmptySVGHash();
        if (bytes(svg).length == 0) revert EmptySVG();

        // ── Uniqueness ──────────────────────────────────────────────────────
        if (portraitIdToToken[portraitId] != 0) {
            revert PortraitAlreadyMinted(portraitId, portraitIdToToken[portraitId]);
        }

        // ── Mint fee ────────────────────────────────────────────────────────
        if (msg.value < mintFee) revert InsufficientMintFee(msg.value, mintFee);

        // ── Mint ────────────────────────────────────────────────────────────
        tokenId = ++_tokenCounter;
        _mint(to, tokenId);

        // ── Store metadata ──────────────────────────────────────────────────
        portraits[tokenId] = Portrait({
            wallet:        wallet,
            sourceChain:   sourceChain,
            portraitId:    portraitId,
            svgHash:       svgHash,
            featureVector: featureVector,
            mintedAt:      block.timestamp,
            txCount:       txCount,
            svg:           svg,
            imageUri:      imageUri,
            metadataUri:   metadataUri
        });

        portraitIdToToken[portraitId] = tokenId;

        emit PortraitMinted(tokenId, to, wallet, portraitId, sourceChain);
    }

    // -------------------------------------------------------------------------
    // Token URI (fully on-chain)
    // -------------------------------------------------------------------------

    /**
     * @notice Returns the token's metadata URI.
     *
     *  If a pinned IPFS metadata document is available (metadataUri), that's
     *  returned directly — most explorers/marketplaces (including OKLink) only
     *  index tokenURI() when it resolves to a real http(s)/ipfs link, not an
     *  inline data URI, so this is required for the image to actually render
     *  there. Otherwise falls back to a base64-encoded JSON data URI built
     *  entirely on-chain:
     *  {
     *    "name": "Chain Portrait #1",
     *    "description": "...",
     *    "image": "https://gateway.pinata.cloud/ipfs/...",  ← or a data URI fallback
     *    "external_url": "https://sigilx.xyz/portrait/<id>",
     *    "attributes": [ { "trait_type": "...", "value": ... }, ... ]
     *  }
     */
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721URIStorage)
        returns (string memory)
    {
        _requireOwned(tokenId);
        Portrait memory p = portraits[tokenId];

        if (bytes(p.metadataUri).length > 0) {
            return p.metadataUri;
        }

        string memory name = string.concat("SigilX #", tokenId.toString());
        string memory description = string.concat(
            "A unique, deterministic artwork generated from the on-chain behavioral ",
            "fingerprint of wallet ",
            _shortAddr(p.wallet),
            " on ",
            p.sourceChain,
            ". Generated by SigilX - built on OKX Market API + X Layer."
        );

        string memory externalUrl = string.concat(
            "https://sigilx.xyz/portrait/",
            p.portraitId
        );

        // Prefer the pinned IPFS gateway URL (renders in explorers/marketplaces
        // that don't parse inline data URIs, e.g. OKLink); fall back to the
        // on-chain SVG if it's unset.
        string memory image = bytes(p.imageUri).length > 0
            ? p.imageUri
            : string.concat("data:image/svg+xml;base64,", Base64.encode(bytes(p.svg)));

        string memory attributes = _buildAttributes(p);

        string memory json = string.concat(
            '{"name":"', name, '",'
            '"description":"', description, '",'
            '"external_url":"', externalUrl, '",'
            '"image":"', image, '",'
            '"attributes":', attributes, '}'
        );

        return string.concat(
            "data:application/json;base64,",
            Base64.encode(bytes(json))
        );
    }

    // -------------------------------------------------------------------------
    // Views
    // -------------------------------------------------------------------------

    /// @notice Get full Portrait struct for a tokenId.
    function getPortrait(uint256 tokenId) external view returns (Portrait memory) {
        _requireOwned(tokenId);
        return portraits[tokenId];
    }

    /// @notice Get tokenId for a given portraitId (returns 0 if not minted).
    function getTokenByPortraitId(string calldata portraitId)
        external
        view
        returns (uint256)
    {
        return portraitIdToToken[portraitId];
    }

    /// @notice Total number of minted portraits.
    function totalSupply() external view returns (uint256) {
        return _tokenCounter;
    }

    // -------------------------------------------------------------------------
    // Admin
    // -------------------------------------------------------------------------

    /// @notice Add or remove an authorized minter.
    function setMinter(address minter, bool authorized) external onlyOwner {
        if (minter == address(0)) revert InvalidAddress();
        authorizedMinters[minter] = authorized;
        emit MinterUpdated(minter, authorized);
    }

    /// @notice Update the mint fee.
    function setMintFee(uint256 newFee) external onlyOwner {
        emit MintFeeUpdated(mintFee, newFee);
        mintFee = newFee;
    }

    /// @notice Withdraw accumulated mint fees to owner.
    function withdraw() external onlyOwner nonReentrant {
        uint256 balance = address(this).balance;
        (bool ok, ) = owner().call{value: balance}("");
        if (!ok) revert WithdrawFailed();
        emit FundsWithdrawn(owner(), balance);
    }

    // -------------------------------------------------------------------------
    // Internal helpers
    // -------------------------------------------------------------------------

    function _shortAddr(address addr) internal pure returns (string memory) {
        bytes memory full = bytes(Strings.toHexString(uint160(addr), 20));
        bytes memory result = new bytes(13); // "0x" + 4 + "..." + 4 = 13
        // first 6 chars (0x + 4 hex)
        for (uint256 i = 0; i < 6; i++) result[i] = full[i];
        result[6] = 0x2E; result[7] = 0x2E; result[8] = 0x2E; // "..."
        // last 4 chars
        for (uint256 i = 0; i < 4; i++) result[9 + i] = full[38 + i];
        return string(result);
    }

    function _buildAttributes(Portrait memory p)
        internal
        pure
        returns (string memory)
    {
        return string.concat(
            '[',
            '{"trait_type":"Source Chain","value":"', p.sourceChain, '"},',
            '{"trait_type":"Portrait ID","value":"', p.portraitId, '"},',
            '{"trait_type":"SVG Hash","value":"', _bytes32ToHex(p.svgHash), '"},',
            '{"trait_type":"Transactions Analyzed","display_type":"number","value":', p.txCount.toString(), '},',
            '{"trait_type":"Minted At","display_type":"date","value":', p.mintedAt.toString(), '},',
            '{"trait_type":"Wallet","value":"', Strings.toHexString(uint160(p.wallet), 20), '"}',
            ']'
        );
    }

    function _bytes32ToHex(bytes32 b) internal pure returns (string memory) {
        bytes memory hexChars = "0123456789abcdef";
        bytes memory result = new bytes(66); // "0x" + 64
        result[0] = "0"; result[1] = "x";
        for (uint256 i = 0; i < 32; i++) {
            result[2 + i * 2]     = hexChars[uint8(b[i]) >> 4];
            result[2 + i * 2 + 1] = hexChars[uint8(b[i]) & 0x0f];
        }
        return string(result);
    }
}
