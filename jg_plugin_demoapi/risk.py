"""Módulo de clasificación determinista de riesgos y gobernanza para OpenAPI endpoints."""

from __future__ import annotations

import re
from typing import Any

from jg_sdk.contracts import RiskLevel, ToolType

# Patrones de rutas sensibles que elevan lecturas GET a RiskLevel.HIGH / HITL
SENSITIVE_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"/admin(/|$)", re.IGNORECASE),
    re.compile(r"/private(/|$)", re.IGNORECASE),
    re.compile(r"/(salaries|salary)(/|$)", re.IGNORECASE),
    re.compile(r"/billing(/|$)", re.IGNORECASE),
    re.compile(r"/audit(-logs?)?(/|$)", re.IGNORECASE),
    re.compile(r"/credentials?(/|$)", re.IGNORECASE),
    re.compile(r"/(secret|key)s?(/|$)", re.IGNORECASE),
    re.compile(r"/finance(/|$)", re.IGNORECASE),
    re.compile(r"/payroll(/|$)", re.IGNORECASE),
    re.compile(r"/users/export(/|$)", re.IGNORECASE),
]

MUTATIVE_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
READ_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}


class RiskClassification:
    """Resultado de la evaluación de riesgo para una operación HTTP."""

    def __init__(
        self,
        risk_level: RiskLevel,
        read_only: bool,
        tool_type: ToolType,
        requires_hitl: bool,
        is_sensitive_read: bool,
        required_permissions: list[str],
        reason: str,
    ) -> None:
        self.risk_level = risk_level
        self.read_only = read_only
        self.tool_type = tool_type
        self.requires_hitl = requires_hitl
        self.is_sensitive_read = is_sensitive_read
        self.required_permissions = required_permissions
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "read_only": self.read_only,
            "tool_type": self.tool_type.value,
            "requires_hitl": self.requires_hitl,
            "is_sensitive_read": self.is_sensitive_read,
            "required_permissions": self.required_permissions,
            "reason": self.reason,
        }


class RiskClassifier:
    """Clasificador determinista de riesgo según método HTTP, ruta y directivas de seguridad OpenAPI."""

    @classmethod
    def is_sensitive_path(cls, path: str) -> bool:
        """Determina si una ruta coincide con algún patrón de endpoints sensibles."""
        clean_path = path.strip()
        return any(pattern.search(clean_path) for pattern in SENSITIVE_PATH_PATTERNS)

    @classmethod
    def extract_security_scopes(cls, operation_dict: dict[str, Any]) -> list[str]:
        """Extrae los scopes o permisos requeridos definidos en la cláusula 'security' de la operación."""
        scopes: list[str] = []
        security_list = operation_dict.get("security", [])
        if isinstance(security_list, list):
            for sec_req in security_list:
                if isinstance(sec_req, dict):
                    for scheme_name, scheme_scopes in sec_req.items():
                        if isinstance(scheme_scopes, list):
                            scopes.extend(scheme_scopes)
                        elif isinstance(scheme_scopes, str):
                            scopes.append(scheme_scopes)
                        else:
                            scopes.append(scheme_name)
        return sorted(set(scopes))

    @classmethod
    def classify_operation(
        cls,
        method: str,
        path: str,
        operation_dict: dict[str, Any] | None = None,
    ) -> RiskClassification:
        """Clasifica el riesgo operativo de una llamada OpenAPI.

        Reglas:
        1. Métodos mutativos (POST, PUT, PATCH, DELETE):
           - RiskLevel.HIGH, read_only=False, tool_type=ToolType.MUTATION, requires_hitl=True.
        2. Métodos de lectura (GET, HEAD):
           - Si la ruta es sensible o requiere scopes RBAC:
             RiskLevel.HIGH, read_only=True, tool_type=ToolType.READ, requires_hitl=True (o permiso explícito).
           - De lo contrario:
             RiskLevel.LOW, read_only=True, tool_type=ToolType.READ, requires_hitl=False.
        """
        method_upper = method.upper()
        op_dict = operation_dict or {}
        scopes = cls.extract_security_scopes(op_dict)
        sensitive = cls.is_sensitive_path(path)

        if method_upper in MUTATIVE_HTTP_METHODS:
            return RiskClassification(
                risk_level=RiskLevel.HIGH,
                read_only=False,
                tool_type=ToolType.MUTATION,
                requires_hitl=True,
                is_sensitive_read=False,
                required_permissions=scopes,
                reason=f"Método mutativo {method_upper}: modifica estado y requiere aprobación HITL.",
            )

        if sensitive or len(scopes) > 0:
            reasons: list[str] = []
            if sensitive:
                reasons.append(f"Ruta sensible detectada en '{path}'")
            if scopes:
                reasons.append(f"Requiere scopes de seguridad: {', '.join(scopes)}")

            return RiskClassification(
                risk_level=RiskLevel.HIGH,
                read_only=True,
                tool_type=ToolType.READ,
                requires_hitl=True,
                is_sensitive_read=True,
                required_permissions=scopes,
                reason=f"Lectura sensible: {'; '.join(reasons)}. Exige elevación a HITL o permisos RBAC.",
            )

        return RiskClassification(
            risk_level=RiskLevel.LOW,
            read_only=True,
            tool_type=ToolType.READ,
            requires_hitl=False,
            is_sensitive_read=False,
            required_permissions=scopes,
            reason=f"Lectura pública estándar {method_upper} en '{path}'. Ejecución directa autorizada.",
        )
