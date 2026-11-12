"""Herramientas canónicas y cargador dinámico de APIs para jg_plugin_demoapi."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from jg_sdk.contracts import (
    AgentTool,
    RiskLevel,
    ToolResult,
    ToolType,
)

from jg_plugin_demoapi.cache import TwoLevelCache
from jg_plugin_demoapi.mock import DEMO_MOCK_OPENAPI_SPEC, get_mock_spec_json
from jg_plugin_demoapi.parser import OpenAPIParser
from jg_plugin_demoapi.schemas import GetMockSpecInput, LoadOpenApiInput
from jg_plugin_demoapi.ssrf import SSRFValidationError, SSRFValidator

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
        self.parser = parser or OpenAPIParser()
        self.allowlist = allowlist or ["localhost", "127.0.0.1", "mock-api"]
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

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url_stripped, headers=headers)

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


# Instancia singleton del manager por defecto
_default_manager: DemoApiToolManager | None = None


def get_default_manager() -> DemoApiToolManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = DemoApiToolManager()
    return _default_manager


def create_load_openapi_tool(manager: DemoApiToolManager | None = None) -> AgentTool:
    """Crea la herramienta canónica de carga de contratos OpenAPI."""
    active_manager = manager or get_default_manager()

    async def _load_openapi(openapi_url: str, force_refresh: bool = False) -> ToolResult:
        start_time = time.time()
        try:
            tools, telemetry = await active_manager.ingest_openapi(
                openapi_url=openapi_url,
                force_refresh=force_refresh,
            )

            # Clasificación del inventario
            mutations = [t for t in tools if t.tool_type == ToolType.MUTATION]
            high_risk = [t for t in tools if t.risk_level == RiskLevel.HIGH]
            low_risk = [t for t in tools if t.risk_level == RiskLevel.LOW]
            sensitive_reads = [t for t in tools if t.metadata.get("is_sensitive_read") is True]

            summary = {
                "openapi_url": openapi_url,
                "telemetry": telemetry,
                "total_tools": len(tools),
                "summary": {
                    "low_risk_public_reads": len(low_risk),
                    "high_risk_mutations": len(mutations),
                    "sensitive_reads_requiring_hitl_or_rbac": len(sensitive_reads),
                    "total_requiring_hitl": len(high_risk),
                },
                "tools_manifest": [
                    {
                        "name": t.name,
                        "method": t.metadata.get("openapi_method"),
                        "path": t.metadata.get("openapi_path"),
                        "risk_level": t.risk_level.value,
                        "tool_type": t.tool_type.value,
                        "requires_hitl": t.metadata.get("requires_hitl", False),
                        "required_permissions": t.required_permissions,
                    }
                    for t in tools
                ],
            }

            duration_ms = (time.time() - start_time) * 1000
            return ToolResult(
                success=True,
                output=summary,
                error=None,
                duration_ms=duration_ms,
                metadata=telemetry,
            )
        except SSRFValidationError as err:
            duration_ms = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                output="",
                error=f"Bloqueo de seguridad Anti-SSRF: {err}",
                duration_ms=duration_ms,
                metadata={"security_event": "ssrf_violation", "target": err.target},
            )
        except Exception as err:
            duration_ms = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                output="",
                error=f"Error durante la ingesta del contrato OpenAPI: {err}",
                duration_ms=duration_ms,
            )

    return AgentTool(
        name="demoapi_load_openapi",
        description=(
            "Ingiere dinámicamente una especificación OpenAPI/Swagger v3.x desde una URL o el entorno mock, "
            "validando directivas anti-SSRF, aplicando caché en dos niveles (Memoria + ETag) "
            "y clasificando granularmente las herramientas generadas según riesgo operativo (HITL/RBAC)."
        ),
        category="demoapi",
        version="1.0.0",
        args_schema=LoadOpenApiInput,
        func=_load_openapi,
        risk_level=RiskLevel.LOW,
        tool_type=ToolType.OBSERVER,
        read_only=True,
        reversible=False,
        idempotent=True,
        makes_http_requests=True,
        timeout_sec=30.0,
    )


def create_get_mock_spec_tool() -> AgentTool:
    """Crea la herramienta canónica de consulta de contrato mock local."""

    async def _get_mock_spec(include_json: bool = False) -> ToolResult:
        summary = {
            "title": DEMO_MOCK_OPENAPI_SPEC["info"]["title"],
            "version": DEMO_MOCK_OPENAPI_SPEC["info"]["version"],
            "paths_count": len(DEMO_MOCK_OPENAPI_SPEC["paths"]),
            "paths": list(DEMO_MOCK_OPENAPI_SPEC["paths"].keys()),
        }
        if include_json:
            summary["json_spec"] = get_mock_spec_json()

        return ToolResult(
            success=True,
            output=summary,
            duration_ms=0.5,
        )

    return AgentTool(
        name="demoapi_get_mock_spec",
        description="Consulta la definición y estructura del contrato OpenAPI mock integrado para pruebas locales.",
        category="demoapi",
        version="1.0.0",
        args_schema=GetMockSpecInput,
        func=_get_mock_spec,
        risk_level=RiskLevel.LOW,
        tool_type=ToolType.OBSERVER,
        read_only=True,
        reversible=False,
        idempotent=True,
        makes_http_requests=False,
        timeout_sec=5.0,
    )


def get_canonical_tools(manager: DemoApiToolManager | None = None) -> list[AgentTool]:
    """Retorna las herramientas canónicas base provistas por el plugin."""
    mgr = manager or get_default_manager()
    return [
        create_load_openapi_tool(mgr),
        create_get_mock_spec_tool(),
    ]


__all__ = [
    "DemoApiToolManager",
    "GetMockSpecInput",
    "LoadOpenApiInput",
    "create_get_mock_spec_tool",
    "create_load_openapi_tool",
    "get_canonical_tools",
    "get_default_manager",
]
