"""Módulo de caché en dos niveles con revalidación HTTP condicional (ETag) y memoria en caliente."""

from __future__ import annotations

import logging
import time
from typing import Any

from jg_sdk.contracts import AgentTool

logger = logging.getLogger("jg_plugin_demoapi.cache")


class CacheEntry:
    """Entrada individual de caché OpenAPI."""

    def __init__(
        self,
        openapi_url: str,
        raw_content: str,
        etag: str | None,
        tools: list[AgentTool],
        ttl_seconds: float = 300.0,
    ) -> None:
        self.openapi_url = openapi_url
        self.raw_content = raw_content
        self.etag = etag
        self.tools = tools
        self.ttl_seconds = ttl_seconds
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.hits = 0

    @property
    def is_expired(self) -> bool:
        """Determina si la entrada ha superado su TTL en memoria."""
        return time.time() > self.expires_at

    def touch(self, additional_ttl: float | None = None) -> None:
        """Renueva la expiración en memoria tras una revalidación exitosa (304 Not Modified)."""
        ttl = additional_ttl if additional_ttl is not None else self.ttl_seconds
        self.expires_at = time.time() + ttl
        self.hits += 1


class TwoLevelCache:
    """Gestor de caché en dos niveles para especificaciones OpenAPI.

    Nivel 1: Memoria rápida en caliente (<1 ms de acceso si TTL vigente).
    Nivel 2: Revalidación condicional HTTP con cabecera ETag / If-None-Match ante expiración.
    """

    def __init__(self, default_ttl_seconds: float = 300.0) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._entries: dict[str, CacheEntry] = {}

    def get_fresh(self, openapi_url: str) -> list[AgentTool] | None:
        """Nivel 1: Obtiene las herramientas si existe entrada en memoria y no ha expirado."""
        entry = self._entries.get(openapi_url)
        if entry is not None and not entry.is_expired:
            entry.hits += 1
            logger.debug("Caché Nivel 1 (Memoria) HIT para '%s' (hits=%d)", openapi_url, entry.hits)
            return entry.tools
        return None

    def get_etag(self, openapi_url: str) -> str | None:
        """Obtiene el último ETag conocido para una URL."""
        entry = self._entries.get(openapi_url)
        return entry.etag if entry else None

    def get_existing_entry(self, openapi_url: str) -> CacheEntry | None:
        """Obtiene la entrada existente (incluso si está expirada) para posibilitar revalidación 304."""
        return self._entries.get(openapi_url)

    def revalidate_304(self, openapi_url: str, new_etag: str | None = None) -> list[AgentTool]:
        """Nivel 2: Ante un 304 Not Modified, extiende el TTL de la entrada en memoria."""
        entry = self._entries.get(openapi_url)
        if entry is None:
            raise KeyError(f"No existe entrada de caché para revalidar con 304: {openapi_url}")

        if new_etag:
            entry.etag = new_etag
        entry.touch(self.default_ttl_seconds)
        logger.info("Caché Nivel 2 (ETag 304) revalidada para '%s'. TTL extendido.", openapi_url)
        return entry.tools

    def put(
        self,
        openapi_url: str,
        raw_content: str,
        etag: str | None,
        tools: list[AgentTool],
        ttl_seconds: float | None = None,
    ) -> CacheEntry:
        """Almacena o actualiza una entrada tras una respuesta 200 OK con nuevo contenido."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        entry = CacheEntry(
            openapi_url=openapi_url,
            raw_content=raw_content,
            etag=etag,
            tools=tools,
            ttl_seconds=ttl,
        )
        self._entries[openapi_url] = entry
        logger.info(
            "Caché guardada para '%s' (%d tools, etag=%s, ttl=%.0fs)",
            openapi_url,
            len(tools),
            etag,
            ttl,
        )
        return entry

    def invalidate(self, openapi_url: str) -> bool:
        """Invalida la caché para una URL específica."""
        return self._entries.pop(openapi_url, None) is not None

    def clear(self) -> None:
        """Limpia todas las entradas de caché."""
        self._entries.clear()

    def stats(self) -> dict[str, Any]:
        """Retorna estadísticas operativas de la caché."""
        total = len(self._entries)
        active = sum(1 for e in self._entries.values() if not e.is_expired)
        total_hits = sum(e.hits for e in self._entries.values())
        return {
            "total_entries": total,
            "active_entries": active,
            "expired_entries": total - active,
            "total_hits": total_hits,
        }
