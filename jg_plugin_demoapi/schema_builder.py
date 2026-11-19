"""Constructor dinámico de esquemas Pydantic v2 a partir de operaciones OpenAPI."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, create_model


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

    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

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


__all__ = [
    "_build_pydantic_schema_from_operation",
    "_sanitize_tool_name",
]
