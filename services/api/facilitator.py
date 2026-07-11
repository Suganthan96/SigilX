"""
services/api/facilitator.py

Self-hosted x402 facilitator for SigilX.

x402 (https://github.com/coinbase/x402) splits payment handling into two
independent steps: (1) verify the payer's EIP-712 signature really
authorizes the transfer, and (2) submit that authorization on-chain
(settlement). Both are public, standard mechanisms — EIP-712 signature
recovery and ERC-3009 `transferWithAuthorization` calls work the same way
for any compatible token. OKX offers a hosted facilitator ("Broker") that
does this for you, but its endpoint/auth were only ever documented through
an interactive installer this project didn't have access to. Nothing about
running the facilitator role yourself is OKX-specific, so this module does
both steps directly against `PaymentToken` (contracts/src/PaymentToken.sol),
using SigilX's own wallet as the relayer that submits (and pays gas for)
the settlement transaction.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_typed_data

load_dotenv()

try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

XLAYER_RPC_URL = os.getenv("XLAYER_RPC_URL", "https://testrpc.xlayer.tech/terigon")
XLAYER_PRIVATE_KEY = os.getenv("XLAYER_PRIVATE_KEY", "")
XLAYER_CHAIN_ID = int(os.getenv("XLAYER_CHAIN_ID", "1952"))

X402_ASSET = os.getenv("X402_ASSET", "")
X402_TOKEN_NAME = os.getenv("X402_TOKEN_NAME", "SigilX Test USD")
X402_TOKEN_VERSION = os.getenv("X402_TOKEN_VERSION", "1")

ABI_PATH = (
    Path(__file__).parent.parent.parent / "contracts" / "artifacts" / "src" / "PaymentToken.sol" / "PaymentToken.json"
)

_TRANSFER_WITH_AUTH_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


class FacilitatorError(Exception):
    pass


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_authorization(payload: dict[str, Any]) -> dict[str, Any]:
    authorization = payload.get("payload", {}).get("authorization", {})
    return {
        "from": Web3.to_checksum_address(authorization["from"]),
        "to": Web3.to_checksum_address(authorization["to"]),
        "value": int(authorization["value"]),
        "validAfter": int(authorization["validAfter"]),
        "validBefore": int(authorization["validBefore"]),
        "nonce": _to_bytes32(authorization["nonce"]),
    }


def _to_bytes32(hex_value: str) -> bytes:
    raw = bytes.fromhex(hex_value[2:] if hex_value.startswith("0x") else hex_value)
    return raw.rjust(32, b"\x00")


def _parse_signature(signature_hex: str) -> tuple[int, bytes, bytes]:
    """Split a packed 65-byte r+s+v hex signature into (v, r, s)."""
    raw = bytes.fromhex(signature_hex[2:] if signature_hex.startswith("0x") else signature_hex)
    if len(raw) != 65:
        raise FacilitatorError("malformed_signature")
    r, s, v = raw[:32], raw[32:64], raw[64]
    if v < 27:
        v += 27
    return v, r, s


# ---------------------------------------------------------------------------
# Step 1: signature verification (pure, no network — unit-testable)
# ---------------------------------------------------------------------------

def recover_signer(
    authorization: dict[str, Any],
    v: int,
    r: bytes,
    s: bytes,
    token_address: str,
    chain_id: int = XLAYER_CHAIN_ID,
    token_name: str = X402_TOKEN_NAME,
    token_version: str = X402_TOKEN_VERSION,
) -> str:
    """
    Recover the address that produced the EIP-712 signature over a
    TransferWithAuthorization message. This is the "is this coin real"
    check — it doesn't touch the network, so it can't be fooled by anyone
    other than someone who actually holds the payer's private key.
    """
    domain = {
        "name": token_name,
        "version": token_version,
        "chainId": chain_id,
        "verifyingContract": Web3.to_checksum_address(token_address),
    }
    encoded = encode_typed_data(domain_data=domain, message_types=_TRANSFER_WITH_AUTH_TYPES, message_data=authorization)
    return Account.recover_message(encoded, vrs=(v, int.from_bytes(r, "big"), int.from_bytes(s, "big")))


# ---------------------------------------------------------------------------
# Step 2: on-chain settlement
# ---------------------------------------------------------------------------

def _load_abi() -> list:
    if not ABI_PATH.exists():
        raise FacilitatorError(f"PaymentToken ABI not found at {ABI_PATH}. Run `npm run compile` in contracts/.")
    with open(ABI_PATH) as f:
        artifact = json.load(f)
    return artifact.get("abi", artifact)


def _get_contract():
    w3 = Web3(Web3.HTTPProvider(XLAYER_RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        raise FacilitatorError(f"Cannot connect to X Layer RPC: {XLAYER_RPC_URL}")
    contract = w3.eth.contract(address=Web3.to_checksum_address(X402_ASSET), abi=_load_abi())
    return w3, contract


async def verify_and_settle(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """
    Facilitator entry point: verify the payer's signature, then submit the
    real transferWithAuthorization transaction on-chain using SigilX's own
    relayer wallet (paying gas on the payer's behalf, same as a hosted
    facilitator would).
    """
    if not WEB3_AVAILABLE:
        return False, {"reason": "web3_not_installed"}
    if not XLAYER_PRIVATE_KEY:
        return False, {"reason": "relayer_key_not_configured"}
    if not X402_ASSET:
        return False, {"reason": "payment_asset_not_configured"}

    try:
        authorization = _parse_authorization(payload)
        v, r, s = _parse_signature(payload.get("payload", {}).get("signature", ""))
    except (KeyError, ValueError, TypeError, FacilitatorError) as e:
        return False, {"reason": "malformed_authorization", "detail": str(e)}

    recovered = recover_signer(authorization, v, r, s, X402_ASSET)
    if recovered.lower() != authorization["from"].lower():
        return False, {"reason": "signature_does_not_match_payer"}

    try:
        w3, contract = _get_contract()
    except FacilitatorError as e:
        return False, {"reason": "facilitator_unavailable", "detail": str(e)}

    try:
        relayer = w3.eth.account.from_key(XLAYER_PRIVATE_KEY)
        tx_nonce = w3.eth.get_transaction_count(relayer.address)

        settle_fn = contract.functions.transferWithAuthorization(
            authorization["from"], authorization["to"], authorization["value"],
            authorization["validAfter"], authorization["validBefore"], authorization["nonce"],
            v, r, s,
        )
        estimated_gas = settle_fn.estimate_gas({"from": relayer.address})
        gas_limit = int(estimated_gas * 1.2)

        tx = settle_fn.build_transaction({
            "from": relayer.address,
            "nonce": tx_nonce,
            "gas": gas_limit,
            "gasPrice": w3.eth.gas_price,
        })
        signed = w3.eth.account.sign_transaction(tx, XLAYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex = "0x" + tx_hash.hex()

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt["status"] != 1:
            return False, {"reason": "settlement_reverted", "tx_hash": tx_hash_hex}

        return True, {
            "settled": True,
            "tx_hash": tx_hash_hex,
            "block_number": receipt["blockNumber"],
            "payer": authorization["from"],
            "amount": str(authorization["value"]),
        }
    except Exception as e:  # on-chain call can fail in many ways (revert, RPC error, timeout)
        return False, {"reason": "settlement_failed", "detail": str(e)}
