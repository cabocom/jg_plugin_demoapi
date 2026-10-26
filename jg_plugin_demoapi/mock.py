"""Mock de contrato OpenAPI 3.x y servidor simulado integrado para pruebas locales y CI/CD."""

from __future__ import annotations

import json
from typing import Any

# Especificación OpenAPI 3.0.3 canónica para pruebas locales y demos sin conexión
DEMO_MOCK_OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "API de Demostración y Simulación de Negocio",
        "description": "Especificación mock para validar gobernanza HITL, clasificación de riesgo y caché ETag.",
        "version": "1.0.0",
    },
    "servers": [
        {"url": "http://127.0.0.1:8089", "description": "Servidor mock de desarrollo local"},
        {"url": "http://mock-api:8080", "description": "Contenedor mock en red Docker interna"},
    ],
    "paths": {
        "/api/v1/public/status": {
            "get": {
                "operationId": "getPublicStatus",
                "summary": "Estado general del servicio",
                "description": "Consulta pública del estado de salud del sistema.",
                "responses": {
                    "200": {
                        "description": "Estado saludable",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"status": {"type": "string"}},
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/v1/public/products": {
            "get": {
                "operationId": "listPublicProducts",
                "summary": "Catálogo público de productos",
                "parameters": [
                    {
                        "name": "category",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Categoría a filtrar",
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 10},
                        "description": "Límite de resultados",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Lista de productos",
                        "content": {"application/json": {"schema": {"type": "array"}}},
                    }
                },
            }
        },
        "/api/v1/admin/audit-logs": {
            "get": {
                "operationId": "getAdminAuditLogs",
                "summary": "Registros de auditoría interna",
                "description": "Ruta sensible reservada para administradores de seguridad.",
                "security": [{"BearerAuth": ["admin", "audit:read"]}],
                "responses": {
                    "200": {
                        "description": "Logs de auditoría",
                        "content": {"application/json": {"schema": {"type": "array"}}},
                    }
                },
            }
        },
        "/api/v1/salaries": {
            "get": {
                "operationId": "getSalaries",
                "summary": "Nóminas y retribuciones de empleados",
                "description": "Datos confidenciales y PII sujetos a estricta gobernanza.",
                "responses": {
                    "200": {
                        "description": "Detalle de salarios",
                        "content": {"application/json": {"schema": {"type": "array"}}},
                    }
                },
            }
        },
        "/api/v1/billing/balance": {
            "get": {
                "operationId": "getBillingBalance",
                "summary": "Balance contable y facturación",
                "description": "Información financiera privada.",
                "responses": {
                    "200": {
                        "description": "Balance actual",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"balance_eur": {"type": "number"}},
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/v1/orders": {
            "post": {
                "operationId": "createOrder",
                "summary": "Creación de un nuevo pedido",
                "description": "Operación mutativa que impacta stock e inventario (Requiere HITL).",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "product_id": {"type": "string"},
                                    "quantity": {"type": "integer"},
                                    "customer_email": {"type": "string"},
                                },
                                "required": ["product_id", "quantity"],
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Pedido creado",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        "/api/v1/users/{id}": {
            "put": {
                "operationId": "updateUser",
                "summary": "Actualización de usuario",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Identificador del usuario",
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "role": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Usuario modificado",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            },
            "delete": {
                "operationId": "deleteUser",
                "summary": "Eliminación de usuario",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Identificador del usuario a eliminar",
                    }
                ],
                "responses": {"204": {"description": "Usuario eliminado"}},
            },
        },
    },
}


def get_mock_spec_json() -> str:
    """Devuelve la especificación OpenAPI mock en formato JSON."""
    return json.dumps(DEMO_MOCK_OPENAPI_SPEC, indent=2, ensure_ascii=False)
