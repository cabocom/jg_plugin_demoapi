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
from pydantic import BaseModel, Field, create_model

from jg_plugin_demoapi.risk import RiskClassifier

logger = logging.getLogger("jg_plugin_demoapi.parser")


def _sanitize_tool_name(name: str) -> str:
    """Normaliza un nombre para cumplir con el estándar de nombres de herramientas LLM."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean or clean[0].isdigit():
        clean = f"tool_{clean}"
    return clean[:64]


def _build_pydantic_schema_from_operation(
    operation_id: str,
    parameters: list[dict[str, Any]],
    request_body: dict[str, Any] | None = None,
) -> type[BaseModel]:
    """Genera dinámicamente un esquema Pydantic v2 para los argumentos de la herramienta."""
    fields: dict[str, tuple[Any, Any]] = {}

    # Mapeo de tipos OpenAPI a tipos Python
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    # Procesar parámetros (path, query, header)
    for param in parameters:
        name = param.get("name")
        if not name:
            continue

        schema = param.get("schema", {})
        param_type_str = schema.get("type", "string")
        py_type = type_map.get(param_type_str, str)

        desc = param.get("description", f"Parámetro {param.get('in', 'query')} '{name}'")
        required = param.get("required", False)

        if required:
            field_def = Field(..., description=desc)
        else:
            py_type = py_type | None
            default_val = schema.get("default", None)
            field_def = Field(default=default_val, description=desc)

        fields[name] = (py_type, field_def)

    # Procesar requestBody si existe
    if request_body and isinstance(request_body, dict):
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        body_schema = json_content.get("schema", {})

        if body_schema:
            body_type_str = body_schema.get("type", "object")
            py_type = dict if body_type_str == "object" else type_map.get(body_type_str, Any)
            required = request_body.get("required", False)
            desc = request_body.get("description", "Cuerpo JSON de la petición")

            if required:
                fields["body"] = (py_type, Field(..., description=desc))
            else:
                fields["body"] = (py_type | None, Field(None, description=desc))

    model_name = f"Schema_{_sanitize_tool_name(operation_id)}"
    return create_model(model_name, **fields)


class OpenAPIParser:
    """Parser para contratos OpenAPI 3.x que traduce endpoints a herramientas AgentTool."""

    def __init__(self, http_client: httpx.AsyncClient | None = None, timeout: float = 30.0) -> None:
        self.http_client = http_client
        self.timeout = timeout

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
            raise ValueError(
                f"No se pudo parsear el contrato OpenAPI (JSON ni YAML válidos): {err}"
            ) from err

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

        # Determinar base URL
        servers = spec.get("servers", [])
        if base_url_override:
            default_base_url = base_url_override.rstrip("/")
        elif (
            servers
            and isinstance(servers, list)
            and isinstance(servers[0], dict)
            and "url" in servers[0]
        ):
            default_base_url = servers[0]["url"].rstrip("/")
        else:
            default_base_url = ""

        paths: dict[str, Any] = spec.get("paths", {})
        tools: list[AgentTool] = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            path_params = path_item.get("parameters", [])

            for method in ("get", "post", "put", "patch", "delete", "head", "options"):
                if method not in path_item:
                    continue

                op: dict[str, Any] = path_item[method]
                if not isinstance(op, dict):
                    continue

                op_id = op.get("operationId")
                if not op_id:
                    clean_path_for_id = re.sub(r"[{}]", "", path).replace("/", "_").strip("_")
                    op_id = f"{method}_{clean_path_for_id}"

                tool_name = _sanitize_tool_name(f"demoapi_{op_id}")
                summary = (
                    op.get("summary")
                    or op.get("description")
                    or f"Llamada {method.upper()} a {path}"
                )
                desc = (
                    f"[{method.upper()} {path}] {summary}. "
                    f"Generado automáticamente desde especificación OpenAPI."
                )

                # Clasificar riesgo y permisos
                classification = RiskClassifier.classify_operation(method, path, op)

                # Parámetros combinados
                all_params = list(path_params) + list(op.get("parameters", []))
                request_body = op.get("requestBody")

                # Esquema Pydantic dinámico
                schema_cls = _build_pydantic_schema_from_operation(op_id, all_params, request_body)

                # Construcción de la función ejecutable para el AgentTool
                tool_func = self._create_execution_func(
                    method=method.upper(),
                    path=path,
                    base_url=default_base_url,
                    parameters_def=all_params,
                )

                tool = AgentTool(
                    name=tool_name,
                    description=desc,
                    category="demoapi",
                    version="1.0.0",
                    args_schema=schema_cls,
                    func=tool_func,
                    risk_level=classification.risk_level,
                    required_permissions=classification.required_permissions,
                    tool_type=classification.tool_type,
                    read_only=classification.read_only,
                    reversible=False,
                    idempotent=(method.upper() in ("GET", "HEAD", "PUT", "DELETE")),
                    makes_http_requests=True,
                    timeout_sec=self.timeout,
                    metadata={
                        "openapi_method": method.upper(),
                        "openapi_path": path,
                        "operation_id": op_id,
                        "requires_hitl": classification.requires_hitl,
                        "is_sensitive_read": classification.is_sensitive_read,
                        "risk_reason": classification.reason,
                    },
                )
                tools.append(tool)

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

            # Separar path params, query params y body
            path_param_names = {p["name"] for p in parameters_def if p.get("in") == "path"}
            query_param_names = {p["name"] for p in parameters_def if p.get("in") == "query"}

            resolved_path = path
            for p_name in path_param_names:
                if p_name in clean_kwargs:
                    resolved_path = resolved_path.replace(
                        f"{{{p_name}}}", str(clean_kwargs[p_name])
                    )

            query_params = {k: v for k, v in clean_kwargs.items() if k in query_param_names}
            body_payload = clean_kwargs.get("body")

            target_url = (
                urljoin(base_url.rstrip("/") + "/", resolved_path.lstrip("/"))
                if base_url
                else resolved_path
            )

            # Cliente HTTP para la ejecución
            client = self.http_client or httpx.AsyncClient(timeout=self.timeout)
            should_close = self.http_client is None

            try:
                headers = {"Accept": "application/json"}
                req_kwargs: dict[str, Any] = {"headers": headers, "params": query_params}
                if body_payload is not None:
                    req_kwargs["json"] = body_payload

                response = await client.request(method, target_url, **req_kwargs)
                duration_ms = (time.time() - start_time) * 1000

                try:
                    res_data = response.json()
                except Exception:
                    res_data = response.text

                is_success = 200 <= response.status_code < 300
                return ToolResult(
                    success=is_success,
                    output=res_data,
                    error=None if is_success else f"HTTP {response.status_code}: {res_data}",
                    duration_ms=duration_ms,
                    metadata={
                        "status_code": response.status_code,
                        "url": target_url,
                        "method": method,
                    },
                )
            except Exception as err:
                duration_ms = (time.time() - start_time) * 1000
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Error durante la ejecución HTTP de {method} {target_url}: {err}",
                    duration_ms=duration_ms,
                    metadata={"url": target_url, "method": method},
                )
            finally:
                if should_close:
                    await client.aclose()

        return _exec
