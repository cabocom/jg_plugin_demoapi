"""Tests unitarios para el clasificador determinista de riesgo (RiskClassifier)."""

from jg_sdk.contracts import RiskLevel, ToolType

from jg_plugin_demoapi.risk import RiskClassifier


def test_classify_mutative_methods():
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        res = RiskClassifier.classify_operation(method=method, path="/api/v1/items")
        assert res.risk_level == RiskLevel.HIGH
        assert res.read_only is False
        assert res.tool_type == ToolType.MUTATION
        assert res.requires_hitl is True
        assert res.is_sensitive_read is False


def test_classify_public_get_low_risk():
    res = RiskClassifier.classify_operation(method="GET", path="/api/v1/public/products")
    assert res.risk_level == RiskLevel.LOW
    assert res.read_only is True
    assert res.tool_type == ToolType.READ
    assert res.requires_hitl is False
    assert res.is_sensitive_read is False


def test_classify_sensitive_get_routes():
    sensitive_paths = [
        "/api/v1/admin/users",
        "/api/v1/private/dashboard",
        "/api/v1/salaries/executive",
        "/api/v1/salary",
        "/api/v1/billing/invoices",
        "/api/v1/audit/events",
        "/api/v1/audit-logs",
        "/api/v1/credentials/s3",
        "/api/v1/secrets",
        "/api/v1/users/export",
    ]
    for path in sensitive_paths:
        res = RiskClassifier.classify_operation(method="GET", path=path)
        assert res.risk_level == RiskLevel.HIGH, f"Falló en {path}"
        assert res.read_only is True
        assert res.tool_type == ToolType.READ
        assert res.requires_hitl is True
        assert res.is_sensitive_read is True


def test_classify_get_with_security_scopes():
    op = {
        "security": [
            {"OAuth2": ["read:audit", "admin"]},
        ]
    }
    res = RiskClassifier.classify_operation(
        method="GET", path="/api/v1/normal/endpoint", operation_dict=op
    )
    assert res.risk_level == RiskLevel.HIGH
    assert res.requires_hitl is True
    assert "admin" in res.required_permissions
    assert "read:audit" in res.required_permissions
