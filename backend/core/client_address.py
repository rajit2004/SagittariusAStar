
from __future__ import annotations

import ipaddress
import os
from typing import Iterable, List, Optional, Sequence

TRUSTED_PROXY_IPS_ENV = "TRUSTED_PROXY_IPS"

TRUSTED_PROXY_HOPS_ENV = "TRUSTED_PROXY_HOPS"

TRUST_ANY_PEER = "*"

UNKNOWN_ADDRESS = "unknown"

MAX_FORWARDED_ENTRIES = 32

MAX_ADDRESS_CHARS = 64

def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()

def trusted_proxy_spec() -> List[str]:
    raw = _env(TRUSTED_PROXY_IPS_ENV)
    if not raw:
        return []
    return [entry.strip() for entry in raw.split(",") if entry.strip()]

def trusted_proxy_hops() -> int:
    raw = _env(TRUSTED_PROXY_HOPS_ENV)
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return 0
    return value if value > 0 else 0

def _parse_networks(entries: Sequence[str]) -> List[ipaddress._BaseNetwork]:
    networks: List[ipaddress._BaseNetwork] = []
    for entry in entries:
        if entry == TRUST_ANY_PEER:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return networks

def _as_ip(value: str) -> Optional[ipaddress._BaseAddress]:
    text = (value or "").strip()
    if not text or len(text) > MAX_ADDRESS_CHARS:
        return None

    if text.startswith("["):
        closing = text.find("]")
        if closing == -1:
            return None
        text = text[1:closing]
    elif text.count(":") == 1:

        text = text.split(":", 1)[0]

    try:
        parsed = ipaddress.ip_address(text)
    except ValueError:
        return None

    mapped = getattr(parsed, "ipv4_mapped", None)
    return mapped or parsed

def _is_trusted(address: Optional[ipaddress._BaseAddress], networks: Iterable) -> bool:
    if address is None:
        return False
    return any(address in network for network in networks)

def forwarded_chain(header_value: Optional[str]) -> List[str]:
    if not header_value:
        return []

    parsed: List[str] = []
    for entry in header_value.split(",")[:MAX_FORWARDED_ENTRIES]:
        address = _as_ip(entry)
        if address is not None:
            parsed.append(str(address))
    return parsed

def resolve_client_address(
    peer: Optional[str],
    forwarded_header: Optional[str] = None,
) -> str:
    if not peer:
        return UNKNOWN_ADDRESS

    spec = trusted_proxy_spec()
    if not spec:
        return peer

    trust_any = TRUST_ANY_PEER in spec
    networks = _parse_networks(spec)

    peer_address = _as_ip(peer)
    if not trust_any and not _is_trusted(peer_address, networks):

        return peer

    chain = forwarded_chain(forwarded_header)
    if not chain:
        return peer

    remaining_hops = trusted_proxy_hops()
    for candidate in reversed(chain):
        if remaining_hops > 0:
            remaining_hops -= 1
            continue
        if _is_trusted(_as_ip(candidate), networks):

            continue
        return candidate

    return peer

def client_address(request: Optional[object]) -> str:
    if request is None:
        return UNKNOWN_ADDRESS

    try:
        headers = getattr(request, "headers", None)
        forwarded = headers.get("X-Forwarded-For") if headers is not None else None
    except Exception:
        forwarded = None

    try:
        client = getattr(request, "client", None)
        peer = getattr(client, "host", None) if client is not None else None
    except Exception:
        peer = None

    return resolve_client_address(peer, forwarded)

__all__ = [
    "MAX_ADDRESS_CHARS",
    "MAX_FORWARDED_ENTRIES",
    "TRUSTED_PROXY_HOPS_ENV",
    "TRUSTED_PROXY_IPS_ENV",
    "TRUST_ANY_PEER",
    "UNKNOWN_ADDRESS",
    "client_address",
    "forwarded_chain",
    "resolve_client_address",
    "trusted_proxy_hops",
    "trusted_proxy_spec",
]
