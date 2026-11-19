"""Herramientas canónicas base y factories para jg_plugin_demoapi."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from jg_sdk.contracts import (
    AgentTool,
    RiskLevel,
    ToolResult,
    ToolType,
)

from jg_plugin_demoapi.mock import DEMO_MOCK_OPENAPI_SPEC, get_mock_spec_json
from jg_plugin_demoapi.schemas import GetMockSpecInput, LoadOpenApiInput
from jg_plugin_demoapi.ssrf import SSRFValidationError

if TYPE_CHECKING:
    from jg_plugin_demoapi.tools import DemoApiToolManager

logger = logging.getLogger("jg_plugin_demoapi.canonical_tools")

_default_manager: DemoApiToolManager | None = None


def get_default_manager() -> DemoApiToolManager:
    """Retorna la instancia singleton del manager por defecto."""
    global _default_manager
    if _default_manager is None:
        from jg_plugin_demoapi.tools import DemoApiToolManager

        _default_manager = DemoApiToolManager()
    return _default_manager


def _summarize_tools_manifest(
    tools: list[AgentTool], openapi_url: str, telemetry: dict[str, Any]
) -> dict[str, Any]:
    """Genera el resumen estructurado y manifiesto de herramientas ingeridas."""
    mutations = [t for t in tools if t.tool_type == ToolType.MUTATION]
    high_risk = [t for t in tools if t.risk_level == RiskLevel.HIGH]
    low_risk = [t for t in tools if t.risk_level == RiskLevel.LOW]
    sensitive_reads = [t for t in tools if t.metadata.get("is_sensitive_read") is True]

    return {
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
                "description": t.description,
                "risk_level": t.risk_level.value,
                "tool_type": t.tool_type.value,
                "read_only": t.read_only,
                "requires_hitl": t.metadata.get("requires_hitl", False),
                "is_sensitive_read": t.metadata.get("is_sensitive_read", False),
                "required_permissions": t.required_permissions,
            }
            for t in tools
        ],
    }


def _format_ssrf_error(
    err: SSRFValidationError, openapi_url: str, duration_ms: float
) -> ToolResult:
    """Registra y formatea el fallo por bloqueo SSRF."""
    logger.warning("Intento de acceso SSRF bloqueado al cargar OpenAPI '%s': %s", openapi_url, err)
    return ToolResult(
        success=False,
        output="",
        error=f"Bloqueo de seguridad Anti-SSRF: {err}",
        duration_ms=duration_ms,
        metadata={"security_event": "ssrf_violation", "target": err.target},
    )


def _format_generic_error(err: Exception, openapi_url: str, duration_ms: float) -> ToolResult:
    """Registra y formatea errores genéricos durante la ingesta."""
    logger.error("Error durante la ingesta del contrato OpenAPI '%s': %s", openapi_url, err)
    return ToolResult(
        success=False,
        output="",
        error=f"Error durante la ingesta del contrato OpenAPI: {err}",
        duration_ms=duration_ms,
    )


async def _execute_ingest_safely(
    manager: DemoApiToolManager,
    openapi_url: str,
    force_refresh: bool,
    start_time: float,
) -> ToolResult:
    """Ejecuta la ingesta OpenAPI capturando excepciones de seguridad y operativas."""
    try:
        tools, telemetry = await manager.ingest_openapi(
            openapi_url=openapi_url,
            force_refresh=force_refresh,
        )
        summary = _summarize_tools_manifest(tools, openapi_url, telemetry)
        return ToolResult(
            success=True,
            output=summary,
            error=None,
            duration_ms=(time.time() - start_time) * 1000,
            metadata=telemetry,
        )
    except SSRFValidationError as err:
        return _format_ssrf_error(err, openapi_url, (time.time() - start_time) * 1000)
    except Exception as err:
        return _format_generic_error(err, openapi_url, (time.time() - start_time) * 1000)


def create_load_openapi_tool(manager: DemoApiToolManager | None = None) -> AgentTool:
    """Crea la herramienta canónica de carga de contratos OpenAPI."""
    active_manager = manager or get_default_manager()

    async def _load_openapi(openapi_url: str, force_refresh: bool = False) -> ToolResult:
        start_time = time.time()
        return await _execute_ingest_safely(active_manager, openapi_url, force_refresh, start_time)

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
        description=(
            "Obtiene el resumen y endpoints del contrato OpenAPI mock de demostración, "
            "útil para validaciones sin conexión o entornos aislados."
        ),
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
    )


def get_canonical_tools(manager: DemoApiToolManager | None = None) -> list[AgentTool]:
    """Retorna las herramientas canónicas base del plugin."""
    return [
        create_load_openapi_tool(manager),
        create_get_mock_spec_tool(),
    ]


__all__ = [
    "create_get_mock_spec_tool",
    "create_load_openapi_tool",
    "get_canonical_tools",
    "get_default_manager",
]
