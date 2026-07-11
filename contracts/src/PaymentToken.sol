// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/// @title PaymentToken
/// @notice Minimal EIP-3009 (transferWithAuthorization) ERC-20, used as the
/// x402 payment asset for SigilX's own self-hosted facilitator. Real payment
/// providers (e.g. USDC) already implement EIP-3009; on X Layer testnet there
/// isn't one available to point at, so this stands in for local/testnet use.
/// `mint` is intentionally unrestricted — this is a test-only asset, not a
/// store of real value.
contract PaymentToken is ERC20, EIP712 {
    bytes32 public constant TRANSFER_WITH_AUTHORIZATION_TYPEHASH = keccak256(
        "TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)"
    );

    mapping(address => mapping(bytes32 => bool)) private _authorizationStates;

    event AuthorizationUsed(address indexed authorizer, bytes32 indexed nonce);

    constructor(uint256 initialSupply)
        ERC20("SigilX Test USD", "sUSD")
        EIP712("SigilX Test USD", "1")
    {
        _mint(msg.sender, initialSupply);
    }

    function authorizationState(address authorizer, bytes32 nonce) external view returns (bool) {
        return _authorizationStates[authorizer][nonce];
    }

    /// @notice Move `value` from `from` to `to`, authorized by `from`'s EIP-712
    /// signature rather than a prior on-chain approve() — lets a relayer (the
    /// SigilX facilitator) submit the transfer and pay gas on the payer's behalf.
    function transferWithAuthorization(
        address from,
        address to,
        uint256 value,
        uint256 validAfter,
        uint256 validBefore,
        bytes32 nonce,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        require(block.timestamp > validAfter, "PaymentToken: authorization not yet valid");
        require(block.timestamp < validBefore, "PaymentToken: authorization expired");
        require(!_authorizationStates[from][nonce], "PaymentToken: authorization already used");

        bytes32 structHash = keccak256(
            abi.encode(TRANSFER_WITH_AUTHORIZATION_TYPEHASH, from, to, value, validAfter, validBefore, nonce)
        );
        bytes32 digest = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(digest, v, r, s);
        require(signer == from, "PaymentToken: invalid signature");

        _authorizationStates[from][nonce] = true;
        emit AuthorizationUsed(from, nonce);

        _transfer(from, to, value);
    }

    /// @notice Testnet-only faucet so payer wallets can be funded for demos/tests.
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
