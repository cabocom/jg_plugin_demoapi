"""Esquemas Pydantic para herramientas de jg_plugin_demoapi."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoadOpenApiInput(BaseModel):
    """Esquema de entrada para ingesta dinámica de contratos OpenAPI."""

    openapi_url: str = Field(
        ...,
        description="URL absoluta HTTP/HTTPS del contrato OpenAPI/Swagger (JSON o YAML), o 'mock' para el contrato de prueba.",
    )
    force_refresh: bool = Field(
        default=False,
        description="Fuerza la descarga ignorando la memoria en caliente del Nivel 1.",
    )


class GetMockSpecInput(BaseModel):
    """Esquema de entrada para consulta de especificación mock."""

    include_json: bool = Field(
        default=False,
        description="Indica si debe incluirse la cadena JSON íntegra en la respuesta.",
    )


__all__ = ["GetMockSpecInput", "LoadOpenApiInput"]

