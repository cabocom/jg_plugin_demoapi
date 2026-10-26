"""Tests unitarios para OpenAPIParser y generación dinámica de AgentTools."""

from jg_sdk.contracts import RiskLevel, ToolType

from jg_plugin_demoapi.mock import DEMO_MOCK_OPENAPI_SPEC
from jg_plugin_demoapi.parser import OpenAPIParser


def test_parse_mock_spec_to_tools():
    parser = OpenAPIParser()
    tools = parser.parse_spec_to_tools(DEMO_MOCK_OPENAPI_SPEC)

    assert len(tools) > 0
    tool_names = {t.name for t in tools}

    # Verificar que existen herramientas para cada endpoint clave
    assert "demoapi_getpublicstatus" in tool_names
    assert "demoapi_listpublicproducts" in tool_names
    assert "demoapi_getadminauditlogs" in tool_names
    assert "demoapi_getsalaries" in tool_names
    assert "demoapi_createorder" in tool_names
    assert "demoapi_updateuser" in tool_names
    assert "demoapi_deleteuser" in tool_names


def test_tool_risk_attributes_from_parser():
    parser = OpenAPIParser()
    tools = parser.parse_spec_to_tools(DEMO_MOCK_OPENAPI_SPEC)
    tools_by_name = {t.name: t for t in tools}

    # 1. Endpoint público
    public_tool = tools_by_name["demoapi_getpublicstatus"]
    assert public_tool.risk_level == RiskLevel.LOW
    assert public_tool.tool_type == ToolType.READ
    assert public_tool.read_only is True

    # 2. Endpoint sensible por ruta y scopes
    audit_tool = tools_by_name["demoapi_getadminauditlogs"]
    assert audit_tool.risk_level == RiskLevel.HIGH
    assert audit_tool.tool_type == ToolType.READ
    assert audit_tool.read_only is True
    assert "admin" in audit_tool.required_permissions

    # 3. Endpoint sensible por ruta (salaries)
    salaries_tool = tools_by_name["demoapi_getsalaries"]
    assert salaries_tool.risk_level == RiskLevel.HIGH
    assert salaries_tool.metadata.get("is_sensitive_read") is True

    # 4. Endpoints mutativos
    order_tool = tools_by_name["demoapi_createorder"]
    assert order_tool.risk_level == RiskLevel.HIGH
    assert order_tool.tool_type == ToolType.MUTATION
    assert order_tool.read_only is False
    assert order_tool.metadata.get("requires_hitl") is True


def test_pydantic_schema_dynamic_generation():
    parser = OpenAPIParser()
    tools = parser.parse_spec_to_tools(DEMO_MOCK_OPENAPI_SPEC)
    tools_by_name = {t.name: t for t in tools}

    # Verificar args_schema en herramienta con parámetros
    products_tool = tools_by_name["demoapi_listpublicproducts"]
    assert products_tool.args_schema is not None
    fields = products_tool.args_schema.model_fields
    assert "category" in fields
    assert "limit" in fields

    # Verificar args_schema en herramienta con body y path params
    update_user_tool = tools_by_name["demoapi_updateuser"]
    assert update_user_tool.args_schema is not None
    user_fields = update_user_tool.args_schema.model_fields
    assert "id" in user_fields
    assert "body" in user_fields
