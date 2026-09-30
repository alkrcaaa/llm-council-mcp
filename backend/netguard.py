"""SSRF guard for outbound fetches on behalf of models or users.

`safe_get` resolves the host itself, rejects anything that is not a public unicast
address, pins the connection to the validated IP (so DNS cannot change between check
and connect), follows redirects by hand with the same checks on every hop, and caps
the body size.
"""

import ipaddress
import socket
from typing import Iterable, Optional, Tuple, Union
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 4
MAX_BODY_BYTES = 2_000_000
DEFAULT_CONTENT_TYPES = (
    "text/",
    "application/xhtml+xml",
    "application/xml",
    "application/json",
)


class BlockedURL(Exception):
    """Raised when a URL targets a non-public address or breaks a fetch limit."""


def _is_public(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def resolve_public(host: str, port: int) -> str:
    """Return one validated public IP for host, or raise BlockedURL."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise BlockedURL(f"cannot resolve host: {host}") from e
    addrs = []
    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if not _is_public(ip):
            raise BlockedURL(f"host resolves to a non-public address: {host}")
        addrs.append(str(ip))
    if not addrs:
        raise BlockedURL(f"cannot resolve host: {host}")
    return addrs[0]


def check_url(url: str) -> Tuple[str, str, int, str]:
    """Validate scheme/host/port. Returns (scheme, host, port, resolved_ip)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise BlockedURL("only http and https URLs are allowed")
    if not parts.hostname:
        raise BlockedURL("URL has no host")
    if parts.username or parts.password:
        raise BlockedURL("credentials in URL are not allowed")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.scheme, parts.hostname, port, resolve_public(parts.hostname, port)


async def safe_get(
    url: str,
    headers: Optional[dict] = None,
    timeout: float = 10.0,
    max_bytes: int = MAX_BODY_BYTES,
    content_types: Iterable[str] = DEFAULT_CONTENT_TYPES,
) -> Tuple[httpx.Response, bytes]:
    """GET url with SSRF protection. Returns (final response, body bytes)."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, port, ip = check_url(current)
        parts = urlsplit(current)
        ip_host = f"[{ip}]" if ":" in ip else ip
        netloc = f"{ip_host}:{port}"
        pinned = parts._replace(netloc=netloc).geturl()
        req_headers = {**(headers or {}), "Host": parts.netloc.rsplit("@", 1)[-1]}
        ext = {"sni_hostname": host} if scheme == "https" else {}

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("GET", pinned, headers=req_headers, extensions=ext) as resp:
                if resp.is_redirect:
                    loc = resp.headers.get("location")
                    if not loc:
                        raise BlockedURL("redirect without Location")
                    current = urljoin(current, loc)
                    continue

                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if resp.status_code == 200 and not any(ctype.startswith(t) for t in content_types):
                    raise BlockedURL(f"unsupported content type: {ctype or 'unknown'}")

                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        del body[max_bytes:]
                        break
                return resp, bytes(body)
    raise BlockedURL("too many redirects")
