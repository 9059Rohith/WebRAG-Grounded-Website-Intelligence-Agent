"""Canonical URLs and public-address validation for untrusted crawl links."""

from __future__ import annotations

import ipaddress
import posixpath
import re
import socket
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from rag_agent.config import Settings


def normalize_url(url: str) -> str:
    """Normalize host, default ports, dot segments and fragments deterministically."""
    if not isinstance(url, str) or not url or re.search(r"[\x00-\x20\x7f\\]", url):
        raise ValueError("URL contains empty, control, whitespace or backslash characters")
    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        port = parsed.port
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid URL") from exc
    if scheme not in {"http", "https"} or not host:
        raise ValueError("Only absolute HTTP(S) URLs are accepted")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL userinfo is forbidden")
    if "%" in host:
        raise ValueError("IPv6 zone identifiers are forbidden")
    authority = f"[{host}]" if ":" in host else host
    if port and port != (443 if scheme == "https" else 80):
        authority += f":{port}"
    # Repeated decoding prevents encoded traversal/slashes from bypassing path scope.
    decoded = parsed.path or "/"
    for _ in range(4):
        new = unquote(decoded)
        if new == decoded:
            break
        decoded = new
    if re.search(r"[\x00-\x1f\x7f\\]", decoded):
        raise ValueError("URL path contains unsafe characters")
    path = posixpath.normpath("/" + decoded.lstrip("/"))
    if decoded.endswith("/") and path != "/":
        path += "/"
    path = quote(path, safe="/-._~!$&'()*+,;=:@")
    return urlunsplit((scheme, authority, path, parsed.query, ""))


def is_allowed_address(address: str, settings: Settings) -> bool:
    """Only globally routable addresses, or explicitly enabled loopback fixtures."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if settings.test_allow_localhost and ip.is_loopback:
        return True
    if ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and (
        ip.sixtofour is not None or ip.teredo is not None
    ):
        return False
    return ip.is_global


def resolve_public_addresses(host: str, port: int, settings: Settings) -> list[str]:
    """Validate every DNS answer; mixed public/private results fail closed."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("Hostname DNS lookup failed") from exc
        addresses = list(dict.fromkeys(str(answer[4][0]) for answer in answers))
    else:
        addresses = [str(literal)]
    if not addresses or any(not is_allowed_address(address, settings) for address in addresses):
        raise ValueError("URL must resolve exclusively to public IP addresses")
    return addresses


def validate_url(url: str, settings: Settings, check_scope: bool = True) -> str:
    """Return a canonical URL only after scope, port and DNS/IP safety checks."""
    normalized = normalize_url(url)
    parsed = urlsplit(normalized)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    host = parsed.hostname or ""
    if port not in {80, 443}:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if not (settings.test_allow_localhost and loopback):
            raise ValueError("Only standard HTTP(S) ports are permitted")
    if check_scope:
        prefix = urlsplit(normalize_url(settings.allowed_prefix))
        base_path = prefix.path.rstrip("/")
        if (parsed.scheme, parsed.netloc) != (prefix.scheme, prefix.netloc):
            raise ValueError("URL is outside allowed origin")
        if parsed.path != base_path and not parsed.path.startswith(base_path + "/"):
            raise ValueError("URL is outside allowed path prefix")
    resolve_public_addresses(host, port, settings)
    return normalized
