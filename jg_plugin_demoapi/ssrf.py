"""Módulo de mitigación de Server-Side Request Forgery (SSRF) y DNS Pinning."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger("jg_plugin_demoapi.ssrf")


class SSRFValidationError(ValueError):
    """Excepción lanzada cuando una URL o IP viola la política de seguridad anti-SSRF."""

    def __init__(self, message: str, target: str | None = None) -> None:
        super().__init__(message)
        self.target = target


# Redes prohibidas por defecto (RFC 1918, Link-Local, Metadatos de Cloud, Loopback)
BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # Loopback
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    # Cloud Metadata Service (AWS, GCP, Azure, OpenStack, etc.)
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    # Redes privadas RFC 1918 (IPv4)
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Redes privadas IPv6 (RFC 4193 ULA)
    ipaddress.ip_network("fc00::/7"),
    # Especiales y reservadas
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reservada
]


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


class SSRFValidator:
    """Validador determinista anti-SSRF con soporte para resolución previa y DNS Pinning."""

    @classmethod
    def is_ip_blocked(cls, ip_str: str) -> bool:
        """Comprueba si una IP pertenece a rangos privados, loopback o metadatos."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as err:
            raise SSRFValidationError(f"Dirección IP no válida: {ip_str}", target=ip_str) from err

        return any(ip_obj in network for network in BLOCKED_NETWORKS)

    @classmethod
    async def resolve_and_pin_url_async(
        cls,
        url: str,
        allowlist: list[str] | None = None,
    ) -> PinnedEndpoint:
        """Resuelve el hostname de una URL vía DNS, valida la política anti-SSRF y ata la IP (DNS Pinning).

        Raises:
            SSRFValidationError: Si el esquema no es http/https, el host no resuelve,
                                 o resuelve a una IP interna/prohibida fuera de allowlist.
        """
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

        # Allowlist explícita (p. ej. mocks en red Docker o tests locales)
        if allowlist and hostname in allowlist:
            logger.info("Host '%s' autorizado por allowlist explícita anti-SSRF.", hostname)
            # Para hosts en allowlist, intentar resolver o usar directo
            try:
                loop = asyncio.get_running_loop()
                addr_info = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
                resolved_ip = addr_info[0][4][0]
            except Exception:
                resolved_ip = hostname
            return PinnedEndpoint(
                hostname=hostname,
                ip=resolved_ip,
                port=port,
                is_ssl=is_ssl,
                original_url=url,
            )

        # Resolución asíncrona de DNS
        loop = asyncio.get_running_loop()
        try:
            addr_info = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as err:
            raise SSRFValidationError(
                f"Fallo de resolución DNS para el host '{hostname}': {err}",
                target=url,
            ) from err

        if not addr_info:
            raise SSRFValidationError(
                f"No se obtuvieron registros DNS para '{hostname}'.", target=url
            )

        # Validar TODAS las IPs devueltas por DNS para prevenir DNS Rebinding y dual-homed bypass
        verified_ip: str | None = None
        for item in addr_info:
            ip_candidate = item[4][0]
            if cls.is_ip_blocked(ip_candidate):
                logger.warning(
                    "Intento de acceso SSRF bloqueado: host '%s' resuelve a IP prohibida '%s'",
                    hostname,
                    ip_candidate,
                )
                raise SSRFValidationError(
                    f"Acceso denegado por política anti-SSRF: el host '{hostname}' "
                    f"resuelve a la dirección restringida '{ip_candidate}'.",
                    target=url,
                )
            if verified_ip is None:
                verified_ip = ip_candidate

        if not verified_ip:
            raise SSRFValidationError(
                f"No se pudo verificar ninguna IP válida para '{hostname}'.", target=url
            )

        logger.debug("DNS Pinning exitoso para host '%s' -> IP '%s'", hostname, verified_ip)
        return PinnedEndpoint(
            hostname=hostname,
            ip=verified_ip,
            port=port,
            is_ssl=is_ssl,
            original_url=url,
        )
