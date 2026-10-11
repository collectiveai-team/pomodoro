"""Resolve the client IP half of the rate-limit key (User Story 12).

The backend sits behind exactly one proxy, the frontend, and its container preload
(`frontend/edge/stamp-client-address.cjs`) overwrites `X-Forwarded-For` with the socket address
it accepted the request from, because Next on its own keeps whatever header the browser sent.
The rightmost entry is therefore the only one the browser cannot write, and it is the one used
here: taking the first untrusted entry from the right (uvicorn's `--forwarded-allow-ips` rule)
lets a client on a trusted private network choose its own key with a forged prefix. The header
is honoured only when the direct peer is a trusted proxy; anyone else is keyed by their own
address.
"""

from __future__ import annotations

from ipaddress import ip_address, ip_network


def client_ip(peer: str | None, forwarded_for: str | None, trusted_proxies: list[str]) -> str:
    """Return the address the trusted proxy saw, or the direct peer's own address."""
    if peer is None:
        return "unknown"
    if not forwarded_for or not _is_trusted(peer, trusted_proxies):
        return peer
    rightmost = forwarded_for.rsplit(",", 1)[-1].strip()
    return rightmost or peer


def _is_trusted(peer: str, trusted_proxies: list[str]) -> bool:
    try:
        address = ip_address(peer)
    except ValueError:
        return False
    return any(address in ip_network(cidr, strict=False) for cidr in trusted_proxies)
