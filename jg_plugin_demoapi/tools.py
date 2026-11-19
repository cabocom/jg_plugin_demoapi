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
from jg_plugin_demoapi.ssrf import SSRFValidator

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

    async def ingest_openapi(
        self,
        openapi_url: str,
        force_refresh: bool = False,
    ) -> tuple[list[AgentTool], dict[str, Any]]:
        """Descarga e ingiere una especificación OpenAPI con validación anti-SSRF y caché en 2 niveles."""
        start_time = time.time()
        url_stripped = openapi_url.strip()

        # Caso especial: Contrato mock local
        if url_stripped.lower() in ("mock", "demo", "mock-api", "local"):
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

        # Nivel 1: Memoria rápida si no se fuerza refresco
        if not force_refresh:
            cached_tools = self.cache.get_fresh(url_stripped)
            if cached_tools is not None:
                duration_ms = (time.time() - start_time) * 1000
                for t in cached_tools:
                    self.dynamic_tools[t.name] = t
                return cached_tools, {
                    "source": "cache",
                    "cache_level": "level_1_memory",
                    "duration_ms": duration_ms,
                    "endpoints_count": len(cached_tools),
                }

        # Validación Anti-SSRF y DNS Pinning
        pinned = await SSRFValidator.resolve_and_pin_url_async(
            url_stripped,
            allowlist=self.allowlist,
        )

        # Nivel 2: Petición HTTP condicional con ETag si existe entrada previa
        existing_etag = self.cache.get_etag(url_stripped)
        headers = {
            "Accept": "application/json, application/yaml, text/yaml, */*",
            "User-Agent": "jg-plugin-demoapi/1.0",
        }
        if existing_etag and not force_refresh:
            headers["If-None-Match"] = existing_etag

        # Aplicar IP fijada (DNS Pinning) y Host header para evitar DNS rebinding
        parsed_origin = urlparse(url_stripped)
        pinned_request_url = pinned.build_pinned_url(parsed_origin.path)
        if parsed_origin.query:
            pinned_request_url = f"{pinned_request_url}?{parsed_origin.query}"

        host_header = pinned.hostname
        if (pinned.is_ssl and pinned.port != 443) or (not pinned.is_ssl and pinned.port != 80):
            host_header = f"{host_header}:{pinned.port}"
        headers["Host"] = host_header

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            resp = await client.get(pinned_request_url, headers=headers)

            # Revalidación 304 Not Modified
            if resp.status_code == 304:
                new_etag = resp.headers.get("ETag") or existing_etag
                revalidated_tools = self.cache.revalidate_304(url_stripped, new_etag=new_etag)
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

            if resp.status_code != 200:
                raise ValueError(
                    f"Fallo al descargar especificación OpenAPI desde '{url_stripped}'. "
                    f"HTTP {resp.status_code}: {resp.text[:300]}"
                )

            # Respuesta 200 OK: nuevo contenido
            raw_content = resp.text
            new_etag = resp.headers.get("ETag")
            spec_dict = OpenAPIParser.parse_raw_spec(raw_content)
            tools = self.parser.parse_spec_to_tools(spec_dict)

            # Guardar en caché Nivel 1 y 2
            self.cache.put(
                openapi_url=url_stripped,
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


__all__ = [
    "DemoApiToolManager",
    "GetMockSpecInput",
    "LoadOpenApiInput",
    "create_get_mock_spec_tool",
    "create_load_openapi_tool",
    "get_canonical_tools",
    "get_default_manager",
]
