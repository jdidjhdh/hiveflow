import aiohttp
import ipaddress
import socket
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, input: Dict[str, Any], view) -> Any: ...


def _is_private_ip(host: str) -> bool:
    """Check if host resolves to a private/internal IP address (SSRF protection)."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except (socket.gaierror, OSError):
            return False  # Can't resolve, let the request fail naturally
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


class HTTPRequestTool(Tool):
    name = "http_request"
    description = "Send HTTP request (with SSRF protection)"
    parameters = {
        "type": "object",
        "properties": {
            "method": {"enum": ["GET", "POST", "PUT", "DELETE"]},
            "url": {"type": "string"},
            "headers": {"type": "object"},
            "body": {"type": "string"}
        },
        "required": ["method", "url"]
    }

    def __init__(
        self,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
        block_private_ips: bool = True,
        timeout: int = 30,
    ):
        self.allowed_domains = allowed_domains  # None = no domain whitelist
        self.blocked_domains = set(blocked_domains or [])
        self.block_private_ips = block_private_ips
        self.timeout = timeout

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported scheme: {parsed.scheme}")
        host = parsed.hostname or ""
        if not host:
            raise ValueError("Invalid URL: missing host")
        if host in self.blocked_domains:
            raise ValueError(f"Domain blocked: {host}")
        if self.allowed_domains and host not in self.allowed_domains:
            raise ValueError(f"Domain not in whitelist: {host}")
        if self.block_private_ips and _is_private_ip(host):
            raise ValueError(f"Access to internal/private IP blocked: {host}")

    async def run(self, input, view):
        url = input["url"]
        self._validate_url(url)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                input["method"], url,
                headers=input.get("headers", {}),
                data=input.get("body")
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    return {"status": resp.status, "error": text}
                return {"status": resp.status, "body": text}
