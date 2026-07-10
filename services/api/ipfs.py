"""
services/api/ipfs.py

Pins a portrait's SVG and ERC-721 metadata JSON to IPFS via Pinata so both are
reachable at real https:// URLs. Needed because explorers/marketplaces (e.g.
OKLink) generally only index tokenURI() when it resolves to a real http(s)/
ipfs link — they don't decode inline `data:application/json;base64,...` URIs,
so pinning only the image and leaving tokenURI() itself as a data URI isn't
enough; the whole metadata document needs a real address too.

If PINATA_JWT isn't configured, both functions return None and callers should
fall back to on-chain data URIs (tokenURI() already does this).
"""

from __future__ import annotations

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

PINATA_JWT = os.getenv("PINATA_JWT", "")
PINATA_GATEWAY = os.getenv("PINATA_GATEWAY", "https://gateway.pinata.cloud")
PINATA_PIN_FILE_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
PINATA_PIN_JSON_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"


async def upload_svg_to_ipfs(svg: str, portrait_id: str) -> str | None:
    """
    Pin an SVG string to IPFS via Pinata.

    Args:
        svg:         Full SVG string.
        portrait_id: Used as the pinned file's display name.

    Returns:
        A native ipfs://<cid> URI for the pinned SVG — most explorers/wallets
        resolve this via their own gateway and use the scheme itself to
        classify the asset as IPFS-hosted (a foreign https:// gateway URL
        isn't recognized the same way). None if Pinata isn't configured or
        the upload fails.
    """
    if not PINATA_JWT:
        return None

    files = {"file": (f"{portrait_id}.svg", svg.encode("utf-8"), "image/svg+xml")}
    data = {"pinataMetadata": f'{{"name":"{portrait_id}.svg"}}'}
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(PINATA_PIN_FILE_URL, headers=headers, files=files, data=data)
            response.raise_for_status()
            cid = response.json()["IpfsHash"]
            return f"ipfs://{cid}"
    except Exception:
        return None


async def upload_png_to_ipfs(png_bytes: bytes, portrait_id: str) -> str | None:
    """
    Pin a PNG image to IPFS via Pinata.

    Args:
        png_bytes:   Raw PNG file bytes.
        portrait_id: Used as the pinned file's display name.

    Returns:
        A native ipfs://<cid> URI for the pinned PNG, or None if Pinata isn't
        configured or the upload fails.
    """
    if not PINATA_JWT:
        return None

    files = {"file": (f"{portrait_id}.png", png_bytes, "image/png")}
    data = {"pinataMetadata": f'{{"name":"{portrait_id}.png"}}'}
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(PINATA_PIN_FILE_URL, headers=headers, files=files, data=data)
            response.raise_for_status()
            cid = response.json()["IpfsHash"]
            return f"ipfs://{cid}"
    except Exception:
        return None


async def upload_json_to_ipfs(metadata: dict, portrait_id: str) -> str | None:
    """
    Pin an ERC-721 metadata JSON document to IPFS via Pinata.

    Args:
        metadata:    The metadata dict (name, description, image, attributes, ...).
        portrait_id: Used as the pinned file's display name.

    Returns:
        A native ipfs://<cid> URI for the pinned JSON (see upload_svg_to_ipfs
        for why the scheme matters), or None if Pinata isn't configured or
        the upload fails.
    """
    if not PINATA_JWT:
        return None

    body = {
        "pinataMetadata": {"name": f"{portrait_id}.json"},
        "pinataContent": metadata,
    }
    headers = {"Authorization": f"Bearer {PINATA_JWT}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(PINATA_PIN_JSON_URL, headers=headers, content=json.dumps(body))
            response.raise_for_status()
            cid = response.json()["IpfsHash"]
            return f"ipfs://{cid}"
    except Exception:
        return None


def gateway_url(ipfs_uri: str) -> str:
    """Convert an ipfs://<cid> URI to a fetchable https gateway URL, for our own verification use."""
    if ipfs_uri.startswith("ipfs://"):
        return f"{PINATA_GATEWAY}/ipfs/{ipfs_uri[len('ipfs://'):]}"
    return ipfs_uri
