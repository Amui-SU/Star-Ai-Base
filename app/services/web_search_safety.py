import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import httpx

from app.config import settings


def is_blocked_address(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def is_proxy_fake_ip_address(host: str) -> bool:
    if not settings.http_proxy.strip():
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address in ipaddress.ip_network("198.18.0.0/15")


async def resolve_hostname(hostname: str, port: int = 80) -> list:
    loop = asyncio.get_running_loop()
    try:
        return await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []


async def resolve_public_hostname(hostname: str) -> list[str]:
    timeout = httpx.Timeout(5.0, connect=3.0)
    headers = {"accept": "application/dns-json"}
    proxy = settings.http_proxy or None
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            proxy=proxy,
            headers=headers,
            trust_env=False,
        ) as client:
            response = await client.get(
                "https://dns.google/resolve",
                params={"name": hostname, "type": "A"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []

    answers = data.get("Answer") if isinstance(data, dict) else None
    if not isinstance(answers, list):
        return []

    hosts: list[str] = []
    for answer in answers:
        if not isinstance(answer, dict) or answer.get("type") != 1:
            continue
        host = str(answer.get("data") or "").strip()
        if host:
            hosts.append(host)
    return hosts


def resolved_host(result) -> str:
    if hasattr(result, "host"):
        return str(result.host)
    if isinstance(result, tuple) and len(result) >= 5:
        sockaddr = result[4]
        if isinstance(sockaddr, tuple) and sockaddr:
            return str(sockaddr[0])
    return ""


async def is_blocked_url(
    url: str,
    *,
    resolve_hostname_fn: Callable[[str, int], Awaitable[list]] = resolve_hostname,
    resolve_public_hostname_fn: Callable[
        [str], Awaitable[list[str]]
    ] = resolve_public_hostname,
) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return True
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return True
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    if is_blocked_address(hostname):
        return True
    try:
        ipaddress.ip_address(hostname)
        return False
    except ValueError:
        pass
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return True
    resolved = await resolve_hostname_fn(hostname, port)
    if not resolved:
        return True
    needs_public_dns_check = False
    for result in resolved:
        host = resolved_host(result)
        if is_proxy_fake_ip_address(host):
            needs_public_dns_check = True
            continue
        if is_blocked_address(host):
            return True
    if needs_public_dns_check:
        public_hosts = await resolve_public_hostname_fn(hostname)
        if not public_hosts:
            return True
        return any(is_blocked_address(host) for host in public_hosts)
    return False


def is_blocked_search_result_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return True
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return True
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    if is_blocked_address(hostname):
        return True
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    try:
        parsed.port
    except ValueError:
        return True
    return False
