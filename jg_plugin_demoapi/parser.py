"""Motor de parseo OpenAPI 3.x y mapeador dinámico de AgentTool con Pydantic v2."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import urljoin

import httpx
import yaml
from jg_sdk.contracts import AgentTool, ToolResult

from jg_plugin_demoapi.http_executor import (
    build_pinned_http_kwargs,
    execute_and_parse_http,
    handle_exec_error,
)
from jg_plugin_demoapi.risk import RiskClassification, RiskClassifier
from jg_plugin_demoapi.schema_builder import (
    _build_pydantic_schema_from_operation,
    _sanitize_tool_name,
)
from jg_plugin_demoapi.ssrf import SSRFValidator

logger = logging.getLogger("jg_plugin_demoapi.parser")


def _extract_default_base_url(spec: dict[str, Any], base_url_override: str | None) -> str:
    """Determina la base URL a partir de un override o de la lista de servers de OpenAPI."""
    if base_url_override:
        return base_url_override.rstrip("/")
    servers = spec.get("servers", [])
    if (
        servers
        and isinstance(servers, list)
        and isinstance(servers[0], dict)
        and "url" in servers[0]
    ):
        return str(servers[0]["url"]).rstrip("/")
    return ""


def _resolve_request_target_and_payload(
    path: str,
    base_url: str,
    parameters_def: list[dict[str, Any]],
    clean_kwargs: dict[str, Any],
) -> tuple[str, dict[str, Any], Any]:
    """Resuelve la URL destino, reemplaza path parameters y extrae query params y body."""
    path_param_names = {p["name"] for p in parameters_def if p.get("in") == "path"}
    query_param_names = {p["name"] for p in parameters_def if p.get("in") == "query"}

    resolved_path = path
    for p_name in path_param_names:
        if p_name in clean_kwargs:
            resolved_path = resolved_path.replace(f"{{{p_name}}}", str(clean_kwargs[p_name]))

    query_params = {k: v for k, v in clean_kwargs.items() if k in query_param_names}
    body_payload = clean_kwargs.get("body")
    target_url = (
        urljoin(base_url.rstrip("/") + "/", resolved_path.lstrip("/"))
        if base_url
        else resolved_path
    )
    return target_url, query_params, body_payload


class OpenAPIParser:
    """Parser para contratos OpenAPI 3.x que traduce endpoints a herramientas AgentTool."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
        allowlist: list[str] | None = None,
    ) -> None:
        self.http_client = http_client
        self.timeout = timeout
        self.allowlist = list(allowlist) if allowlist is not None else []

    @classmethod
    def parse_raw_spec(cls, raw_content: str) -> dict[str, Any]:
        """Parsea la especificación OpenAPI desde cadena en formato JSON o YAML."""
        raw_stripped = raw_content.strip()
        if raw_stripped.startswith("{") or raw_stripped.startswith("["):
            try:
                return json.loads(raw_stripped)
            except json.JSONDecodeError as err:
                logger.debug("Fallo al parsear como JSON, intentando YAML: %s", err)
        try:
            return yaml.safe_load(raw_stripped)
        except Exception as err:
            logger.error("Error al parsear especificación OpenAPI como YAML/JSON: %s", err)
            raise ValueError(
                f"No se pudo parsear el contrato OpenAPI (JSON ni YAML válidos): {err}"
            ) from err

    def _assemble_tool(
        self,
        tool_name: str,
        desc: str,
        schema_cls: Any,
        tool_func: Any,
        cls_info: RiskClassification,
        meta: dict[str, Any],
        method: str,
    ) -> AgentTool:
        """Instancia la herramienta AgentTool con directivas de seguridad y riesgo."""
        return AgentTool(
            name=tool_name,
            description=desc,
            category="demoapi",
            version="1.0.0",
            args_schema=schema_cls,
            func=tool_func,
            risk_level=cls_info.risk_level,
            required_permissions=cls_info.required_permissions,
            tool_type=cls_info.tool_type,
            read_only=cls_info.read_only,
            reversible=False,
            idempotent=(method.upper() in ("GET", "HEAD", "PUT", "DELETE")),
            makes_http_requests=True,
            timeout_sec=self.timeout,
            metadata=meta,
        )

    def _build_single_tool(
        self,
        path: str,
        method: str,
        op: dict[str, Any],
        path_params: list[dict[str, Any]],
        default_base_url: str,
    ) -> AgentTool:
        """Construye un AgentTool individual a partir de una operación OpenAPI."""
        op_id = op.get("operationId")
        if not op_id:
            clean_path_for_id = re.sub(r"[{}]", "", path).replace("/", "_").strip("_")
            op_id = f"{method}_{clean_path_for_id}"

        tool_name = _sanitize_tool_name(f"demoapi_{op_id}")
        summary = op.get("summary") or op.get("description") or f"Llamada {method.upper()} a {path}"
        desc = (
            f"[{method.upper()} {path}] {summary}. "
            f"Generado automáticamente desde especificación OpenAPI."
        )

        classification = RiskClassifier.classify_operation(method, path, op)
        all_params = list(path_params) + list(op.get("parameters", []))
        schema_cls = _build_pydantic_schema_from_operation(op_id, all_params, op.get("requestBody"))
        tool_func = self._create_execution_func(method.upper(), path, default_base_url, all_params)

        metadata = {
            "openapi_method": method.upper(),
            "openapi_path": path,
            "operation_id": op_id,
            "requires_hitl": classification.requires_hitl,
            "is_sensitive_read": classification.is_sensitive_read,
            "risk_reason": classification.reason,
        }
        return self._assemble_tool(
            tool_name, desc, schema_cls, tool_func, classification, metadata, method
        )

    def _extract_path_operations(
        self, path: str, path_item: dict[str, Any], default_base_url: str
    ) -> list[AgentTool]:
        """Extrae todas las herramientas para un path específico de OpenAPI."""
        tools: list[AgentTool] = []
        path_params = path_item.get("parameters", [])
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            if method in path_item and isinstance(path_item[method], dict):
                tools.append(
                    self._build_single_tool(
                        path, method, path_item[method], path_params, default_base_url
                    )
                )
        return tools

    def parse_spec_to_tools(
        self,
        spec: dict[str, Any],
        base_url_override: str | None = None,
    ) -> list[AgentTool]:
        """Convierte una especificación OpenAPI 3.x en una lista de herramientas AgentTool."""
        openapi_version = spec.get("openapi") or spec.get("swagger", "")
        if not openapi_version:
            raise ValueError(
                "El documento no contiene una versión de 'openapi' o 'swagger' reconocible."
            )

        default_base_url = _extract_default_base_url(spec, base_url_override)
        paths: dict[str, Any] = spec.get("paths", {})
        tools: list[AgentTool] = []

        for path, path_item in paths.items():
            if isinstance(path_item, dict):
                tools.extend(self._extract_path_operations(path, path_item, default_base_url))

        logger.info("OpenAPI parseado exitosamente: %d herramientas generadas.", len(tools))
        return tools

    def _create_execution_func(
        self,
        method: str,
        path: str,
        base_url: str,
        parameters_def: list[dict[str, Any]],
    ):
        """Crea la función callable encapsulada para una herramienta generada."""

        async def _exec(**kwargs: Any) -> ToolResult:
            start_time = time.time()
            clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            target_url, query_params, body_payload = _resolve_request_target_and_payload(
                path, base_url, parameters_def, clean_kwargs
            )

            pinned = await SSRFValidator.resolve_and_pin_url_async(
                target_url, allowlist=self.allowlist
            )
            client = self.http_client or httpx.AsyncClient(timeout=self.timeout)
            should_close = self.http_client is None

            try:
                exec_url, req_kwargs = build_pinned_http_kwargs(
                    target_url, pinned, self.http_client is not None, query_params, body_payload
                )
                return await execute_and_parse_http(
                    client, method, exec_url, req_kwargs, target_url, start_time
                )
            except Exception as err:
                return handle_exec_error(err, method, target_url, start_time)
            finally:
                if should_close:
                    await client.aclose()

        return _exec
