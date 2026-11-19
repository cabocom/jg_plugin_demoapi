"""Herramientas canónicas y cargador dinámico de APIs para jg_plugin_demoapi."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from jg_sdk.contracts import AgentTool

from jg_plugin_demoapi.cache import TwoLevelCache
from jg_plugin_demoapi.canonical_tools import (
    create_get_mock_spec_tool,
    create_load_openapi_tool,
    get_canonical_tools,
    get_default_manager,
)
from jg_plugin_demoapi.mock import DEMO_MOCK_OPENAPI_SPEC
from jg_plugin_demoapi.parser import OpenAPIParser
from jg_plugin_demoapi.schemas import GetMockSpecInput, LoadOpenApiInput
from jg_plugin_demoapi.ssrf import PinnedEndpoint, SSRFValidator

logger = logging.getLogger("jg_plugin_demoapi.tools")


class DemoApiToolManager:
    """Gestor de ciclo de vida, caché en dos niveles y descarga segura de contratos OpenAPI."""

    def __init__(
        self,
        cache: TwoLevelCache | None = None,
        parser: OpenAPIParser | None = None,
        allowlist: list[str] | None = None,
        default_ttl: float = 300.0,
    ) -> None:
        self.cache = cache or TwoLevelCache(default_ttl_seconds=default_ttl)
        self.allowlist = list(allowlist) if allowlist is not None else []
        self.parser = parser or OpenAPIParser(allowlist=self.allowlist)
        self.dynamic_tools: dict[str, AgentTool] = {}

    def _handle_mock_spec(self, start_time: float) -> tuple[list[AgentTool], dict[str, Any]]:
        """Procesa e ingiere la especificación mock local."""
        tools = self.parser.parse_spec_to_tools(DEMO_MOCK_OPENAPI_SPEC)
        for t in tools:
            self.dynamic_tools[t.name] = t
        duration_ms = (time.time() - start_time) * 1000
        return tools, {
            "source": "local_mock",
            "cache_level": "memory_mock",
            "duration_ms": duration_ms,
            "endpoints_count": len(tools),
        }

    def _handle_l1_cache(
        self, url: str, start_time: float
    ) -> tuple[list[AgentTool], dict[str, Any]] | None:
        """Recupera herramientas desde la caché en memoria de Nivel 1."""
        cached_tools = self.cache.get_fresh(url)
        if cached_tools is None:
            return None
        duration_ms = (time.time() - start_time) * 1000
        for t in cached_tools:
            self.dynamic_tools[t.name] = t
        return cached_tools, {
            "source": "cache",
            "cache_level": "level_1_memory",
            "duration_ms": duration_ms,
            "endpoints_count": len(cached_tools),
        }

    @staticmethod
    def _build_pinned_http_params(
        url: str,
        pinned: PinnedEndpoint,
        existing_etag: str | None,
        force_refresh: bool,
    ) -> tuple[str, dict[str, str]]:
        """Construye la URL con IP fijada y cabeceras seguras con Host header."""
        headers = {
            "Accept": "application/json, application/yaml, text/yaml, */*",
            "User-Agent": "jg-plugin-demoapi/1.0",
        }
        if existing_etag and not force_refresh:
            headers["If-None-Match"] = existing_etag

        parsed_origin = urlparse(url)
        pinned_request_url = pinned.build_pinned_url(parsed_origin.path)
        if parsed_origin.query:
            pinned_request_url = f"{pinned_request_url}?{parsed_origin.query}"

        host_header = pinned.hostname
        if (pinned.is_ssl and pinned.port != 443) or (not pinned.is_ssl and pinned.port != 80):
            host_header = f"{host_header}:{pinned.port}"
        headers["Host"] = host_header
        return pinned_request_url, headers

    def _handle_304_revalidation(
        self,
        url: str,
        existing_etag: str | None,
        resp: httpx.Response,
        pinned: PinnedEndpoint,
        start_time: float,
    ) -> tuple[list[AgentTool], dict[str, Any]]:
        """Maneja la revalidación 304 Not Modified del Nivel 2."""
        new_etag = resp.headers.get("ETag") or existing_etag
        revalidated_tools = self.cache.revalidate_304(url, new_etag=new_etag)
        for t in revalidated_tools:
            self.dynamic_tools[t.name] = t
        duration_ms = (time.time() - start_time) * 1000
        return revalidated_tools, {
            "source": "revalidated",
            "cache_level": "level_2_etag_304",
            "etag": new_etag,
            "pinned_ip": pinned.ip,
            "duration_ms": duration_ms,
            "endpoints_count": len(revalidated_tools),
        }

    def _handle_200_network_response(
        self,
        url: str,
        resp: httpx.Response,
        pinned: PinnedEndpoint,
        start_time: float,
    ) -> tuple[list[AgentTool], dict[str, Any]]:
        """Parsea la respuesta 200 OK y la almacena en caché de dos niveles."""
        raw_content = resp.text
        new_etag = resp.headers.get("ETag")
        spec_dict = OpenAPIParser.parse_raw_spec(raw_content)
        tools = self.parser.parse_spec_to_tools(spec_dict)

        self.cache.put(
            openapi_url=url,
            raw_content=raw_content,
            etag=new_etag,
            tools=tools,
        )
        for t in tools:
            self.dynamic_tools[t.name] = t

        duration_ms = (time.time() - start_time) * 1000
        return tools, {
            "source": "network_200",
            "cache_level": "new_entry",
            "etag": new_etag,
            "pinned_ip": pinned.ip,
            "duration_ms": duration_ms,
            "endpoints_count": len(tools),
        }

    async def _fetch_from_network(
        self,
        url_stripped: str,
        pinned: PinnedEndpoint,
        existing_etag: str | None,
        force_refresh: bool,
        start_time: float,
    ) -> tuple[list[AgentTool], dict[str, Any]]:
        """Descarga la especificación OpenAPI desde la red con IP fijada y procesa la respuesta."""
        req_url, headers = self._build_pinned_http_params(
            url_stripped, pinned, existing_etag, force_refresh
        )
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            resp = await client.get(req_url, headers=headers)
            if resp.status_code == 304:
                return self._handle_304_revalidation(
                    url_stripped, existing_etag, resp, pinned, start_time
                )
            if resp.status_code != 200:
                logger.error(
                    "Fallo al descargar OpenAPI desde '%s'. HTTP %d: %s",
                    url_stripped,
                    resp.status_code,
                    resp.text[:300],
                )
                raise ValueError(
                    f"Fallo al descargar especificación OpenAPI desde '{url_stripped}'. "
                    f"HTTP {resp.status_code}: {resp.text[:300]}"
                )
            return self._handle_200_network_response(url_stripped, resp, pinned, start_time)

    async def ingest_openapi(
        self,
        openapi_url: str,
        force_refresh: bool = False,
    ) -> tuple[list[AgentTool], dict[str, Any]]:
        """Descarga e ingiere una especificación OpenAPI con validación anti-SSRF y caché en 2 niveles."""
        start_time = time.time()
        url_stripped = openapi_url.strip()

        if url_stripped.lower() in ("mock", "demo", "mock-api", "local"):
            return self._handle_mock_spec(start_time)

        if not force_refresh:
            l1_result = self._handle_l1_cache(url_stripped, start_time)
            if l1_result is not None:
                return l1_result

        pinned = await SSRFValidator.resolve_and_pin_url_async(
            url_stripped,
            allowlist=self.allowlist,
        )
        existing_etag = self.cache.get_etag(url_stripped)
        return await self._fetch_from_network(
            url_stripped, pinned, existing_etag, force_refresh, start_time
        )


__all__ = [
    "DemoApiToolManager",
    "GetMockSpecInput",
    "LoadOpenApiInput",
    "create_get_mock_spec_tool",
    "create_load_openapi_tool",
    "get_canonical_tools",
    "get_default_manager",
]
