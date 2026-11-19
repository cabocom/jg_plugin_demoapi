"""Ejecutor HTTP encapsulado con soporte de DNS Pinning para herramientas dinámicas OpenAPI."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from jg_sdk.contracts import ToolResult

from jg_plugin_demoapi.ssrf import PinnedEndpoint

logger = logging.getLogger("jg_plugin_demoapi.http_executor")


def build_pinned_http_kwargs(
    target_url: str,
    pinned: PinnedEndpoint,
    has_custom_client: bool,
    query_params: dict[str, Any],
    body_payload: Any,
) -> tuple[str, dict[str, Any]]:
    """Construye la URL de ejecución fijada y los argumentos de petición HTTP."""
    headers = {"Accept": "application/json"}
    if not has_custom_client:
        parsed_target = urlparse(target_url)
        exec_url = pinned.build_pinned_url(parsed_target.path)
        host_header = pinned.hostname
        if (pinned.is_ssl and pinned.port != 443) or (not pinned.is_ssl and pinned.port != 80):
            host_header = f"{host_header}:{pinned.port}"
        headers["Host"] = host_header
    else:
        exec_url = target_url

    req_kwargs: dict[str, Any] = {"headers": headers, "params": query_params}
    if body_payload is not None:
        req_kwargs["json"] = body_payload
    return exec_url, req_kwargs


async def execute_and_parse_http(
    client: httpx.AsyncClient,
    method: str,
    exec_url: str,
    req_kwargs: dict[str, Any],
    target_url: str,
    start_time: float,
) -> ToolResult:
    """Ejecuta la llamada HTTP y parsea el cuerpo de la respuesta."""
    response = await client.request(method, exec_url, follow_redirects=False, **req_kwargs)
    duration_ms = (time.time() - start_time) * 1000

    try:
        res_data = response.json()
    except Exception as parse_err:
        logger.debug("Respuesta no es JSON válido, usando texto plano: %s", parse_err)
        res_data = response.text

    is_success = 200 <= response.status_code < 300
    if not is_success:
        logger.warning(
            "HTTP %d al ejecutar %s %s: %s",
            response.status_code,
            method,
            target_url,
            str(res_data)[:200],
        )

    return ToolResult(
        success=is_success,
        output=res_data,
        error=None if is_success else f"HTTP {response.status_code}: {res_data}",
        duration_ms=duration_ms,
        metadata={"status_code": response.status_code, "url": target_url, "method": method},
    )


def handle_exec_error(
    err: Exception, method: str, target_url: str, start_time: float
) -> ToolResult:
    """Registra y construye el resultado de fallo para una llamada de herramienta."""
    logger.error("Error durante ejecución HTTP de %s %s: %s", method, target_url, err)
    return ToolResult(
        success=False,
        output="",
        error=f"Error durante la ejecución HTTP de {method} {target_url}: {err}",
        duration_ms=(time.time() - start_time) * 1000,
        metadata={"url": target_url, "method": method},
    )


__all__ = [
    "build_pinned_http_kwargs",
    "execute_and_parse_http",
    "handle_exec_error",
]
