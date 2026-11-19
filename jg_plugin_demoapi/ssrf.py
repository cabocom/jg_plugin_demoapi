"""Módulo de mitigación de Server-Side Request Forgery (SSRF) y DNS Pinning.

Delega en la implementación canónica y unificada de `jg_sdk.security.ssrf` (DRY).
"""

from __future__ import annotations

import asyncio
import logging
import socket
from urllib.parse import urlparse

from jg_sdk.security.ssrf import (
    DEFAULT_BLOCKED_NETWORKS,
    SSRFValidationError,
)
from jg_sdk.security.ssrf import (
    SSRFValidator as SdkSSRFValidator,
)

logger = logging.getLogger("jg_plugin_demoapi.ssrf")

BLOCKED_NETWORKS = DEFAULT_BLOCKED_NETWORKS


class PinnedEndpoint:
    """Información de endpoint resuelto y atado (DNS Pinning)."""

    def __init__(self, hostname: str, ip: str, port: int, is_ssl: bool, original_url: str) -> None:
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.is_ssl = is_ssl
        self.original_url = original_url

    def build_pinned_url(self, path: str = "/") -> str:
        """Construye una URL usando la IP atada preservando el scheme y puerto."""
        scheme = "https" if self.is_ssl else "http"
        port_part = (
            f":{self.port}"
            if (self.is_ssl and self.port != 443) or (not self.is_ssl and self.port != 80)
            else ""
        )
        clean_path = ("/" + path.lstrip("/")) if path else ""
        return f"{scheme}://{self.ip}{port_part}{clean_path}"


def _resolve_allowlisted_host(hostname: str, port: int, is_ssl: bool, url: str) -> PinnedEndpoint:
    """Resuelve un host explícitamente autorizado en la allowlist."""
    logger.info("Host '%s' autorizado por allowlist explícita anti-SSRF.", hostname)
    try:
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        resolved_ip = str(addr_info[0][4][0])
    except Exception as err:
        logger.warning("Fallo al resolver host en allowlist '%s': %s", hostname, err)
        resolved_ip = hostname
    return PinnedEndpoint(
        hostname=hostname,
        ip=resolved_ip,
        port=port,
        is_ssl=is_ssl,
        original_url=url,
    )


class SSRFValidator:
    """Validador determinista anti-SSRF con delegación a jg_sdk.security.ssrf."""

    @classmethod
    def is_ip_blocked(cls, ip_str: str) -> bool:
        """Comprueba si una IP pertenece a rangos privados, loopback o metadatos."""
        validator = SdkSSRFValidator()
        is_safe, _ = validator.validate_ip(ip_str)
        return not is_safe

    @classmethod
    async def resolve_and_pin_url_async(
        cls,
        url: str,
        allowlist: list[str] | None = None,
    ) -> PinnedEndpoint:
        """Resuelve el hostname de una URL vía DNS y fija la IP asíncronamente."""
        return await asyncio.to_thread(cls.resolve_and_pin_url, url, allowlist)

    @classmethod
    def resolve_and_pin_url(
        cls,
        url: str,
        allowlist: list[str] | None = None,
    ) -> PinnedEndpoint:
        """Versión síncrona de resolución y fijado de IP delegando en SDK."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SSRFValidationError(
                f"Esquema de URL no permitido: '{parsed.scheme}'. Solo se admite http/https.",
                target=url,
            )
        hostname = parsed.hostname
        if not hostname:
            raise SSRFValidationError("La URL no contiene un hostname válido.", target=url)

        is_ssl = parsed.scheme == "https"
        port = parsed.port or (443 if is_ssl else 80)

        if allowlist and hostname in allowlist:
            return _resolve_allowlisted_host(hostname, port, is_ssl, url)

        validator = SdkSSRFValidator(allowed_hosts=allowlist or [])
        ok, reason, pin_info = validator.resolve_and_pin_url(url)
        if not ok or pin_info is None:
            raise SSRFValidationError(
                f"Acceso denegado por política anti-SSRF: dirección prohibida o restringida. {reason}",
                target=url,
            )

        return PinnedEndpoint(
            hostname=pin_info["hostname"],
            ip=pin_info["pinned_ip"],
            port=pin_info["port"],
            is_ssl=pin_info["scheme"] == "https",
            original_url=url,
        )


__all__ = [
    "BLOCKED_NETWORKS",
    "PinnedEndpoint",
    "SSRFValidationError",
    "SSRFValidator",
]
