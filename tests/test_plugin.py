"""Tests de integración y contratos para DemoApiPlugin."""

import pytest

from jg_plugin_demoapi.plugin import DemoApiPlugin


def test_demoapi_plugin_metadata():
    plugin = DemoApiPlugin()
    meta = plugin.get_plugin_metadata()

    assert meta.name == "demoapi"
    assert meta.version == "1.0.0"
    assert "openapi" in meta.tags
    assert "hitl" in meta.tags
    assert "security" in meta.tags
    assert "cache" in meta.tags


def test_demoapi_plugin_tools_registration():
    plugin = DemoApiPlugin()
    tools = plugin.register_tools()

    assert len(tools) >= 2
    names = {t.name for t in tools}
    assert "demoapi_load_openapi" in names
    assert "demoapi_get_mock_spec" in names


@pytest.mark.asyncio
async def test_demoapi_plugin_lifecycle():
    plugin = DemoApiPlugin()
    await plugin.startup()
    health = await plugin.health_check()

    assert health["status"] == "ok"
    assert health["started"] is True
    assert health["plugin"] == "demoapi"
    assert health["tools_count"] >= 2
    assert "cache_stats" in health

    await plugin.shutdown()
    health_stopped = await plugin.health_check()
    assert health_stopped["started"] is False


@pytest.mark.asyncio
async def test_demoapi_load_mock_spec():
    plugin = DemoApiPlugin()
    await plugin.startup()

    tools_dict = {t.name: t for t in plugin.register_tools()}
    load_tool = tools_dict["demoapi_load_openapi"]

    # Invocar con 'mock' para usar el fixture local
    result = await load_tool.func(openapi_url="mock")
    assert result.success is True
    assert result.output["total_tools"] > 0
    assert result.output["summary"]["high_risk_mutations"] >= 3
    assert result.output["summary"]["low_risk_public_reads"] >= 2
    assert result.output["summary"]["sensitive_reads_requiring_hitl_or_rbac"] >= 3

    # Comprobar que las herramientas dinámicas se han registrado en el plugin
    all_tools = plugin.register_tools()
    dynamic_names = {t.name for t in all_tools}
    assert "demoapi_createorder" in dynamic_names
    assert "demoapi_getpublicstatus" in dynamic_names

    await plugin.shutdown()
