"""
tests/test_facilitator.py

Tests the pure, no-network half of the self-hosted x402 facilitator:
recovering the signer of an EIP-712 TransferWithAuthorization message and
confirming it matches the claimed payer. This is the actual "is this
payment real" check — the part that used to be a stub.
"""

from __future__ import annotations

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_checksum_address

from services.api.facilitator import _TRANSFER_WITH_AUTH_TYPES, recover_signer

TOKEN_ADDRESS = to_checksum_address("0x" + "abc".rjust(40, "0"))
CHAIN_ID = 1952

# Fixed test-only private key (Hardhat's well-known account #0) — never used
# for anything with real funds.
PAYER_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
PAYER_ADDRESS = Account.from_key(PAYER_PRIVATE_KEY).address

OTHER_PRIVATE_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690"


def _authorization(**overrides) -> dict:
    base = {
        "from": PAYER_ADDRESS,
        "to": to_checksum_address("0x" + "1aaaa".rjust(40, "1")),
        "value": 10**18,
        "validAfter": 0,
        "validBefore": 9_999_999_999,
        "nonce": (b"\x01" * 32),
    }
    base.update(overrides)
    return base


def _sign(authorization: dict, private_key: str) -> tuple[int, bytes, bytes]:
    domain = {
        "name": "SigilX Test USD",
        "version": "1",
        "chainId": CHAIN_ID,
        "verifyingContract": TOKEN_ADDRESS,
    }
    encoded = encode_typed_data(domain_data=domain, message_types=_TRANSFER_WITH_AUTH_TYPES, message_data=authorization)
    signed = Account.sign_message(encoded, private_key=private_key)
    return signed.v, signed.r.to_bytes(32, "big"), signed.s.to_bytes(32, "big")


def test_recover_signer_matches_the_actual_signer():
    authorization = _authorization()
    v, r, s = _sign(authorization, PAYER_PRIVATE_KEY)

    recovered = recover_signer(authorization, v, r, s, TOKEN_ADDRESS, chain_id=CHAIN_ID)

    assert recovered.lower() == PAYER_ADDRESS.lower()


def test_recover_signer_does_not_match_a_different_signer():
    authorization = _authorization()
    # Signed by someone else, but the authorization still claims to be from PAYER_ADDRESS
    v, r, s = _sign(authorization, OTHER_PRIVATE_KEY)

    recovered = recover_signer(authorization, v, r, s, TOKEN_ADDRESS, chain_id=CHAIN_ID)

    assert recovered.lower() != PAYER_ADDRESS.lower()


def test_recover_signer_fails_if_a_signed_field_is_tampered():
    authorization = _authorization()
    v, r, s = _sign(authorization, PAYER_PRIVATE_KEY)

    # Attacker bumps the value after signing, before it reaches the facilitator
    tampered = dict(authorization, value=10**19)

    recovered = recover_signer(tampered, v, r, s, TOKEN_ADDRESS, chain_id=CHAIN_ID)

    assert recovered.lower() != PAYER_ADDRESS.lower()


def test_recover_signer_fails_on_wrong_chain_id():
    authorization = _authorization()
    v, r, s = _sign(authorization, PAYER_PRIVATE_KEY)

    recovered = recover_signer(authorization, v, r, s, TOKEN_ADDRESS, chain_id=CHAIN_ID + 1)

    assert recovered.lower() != PAYER_ADDRESS.lower()
