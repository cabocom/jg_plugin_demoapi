"""Tests E2E simulados con cliente HTTP interceptado para validar ejecución de herramientas."""

import httpx
import pytest

from jg_plugin_demoapi.mock import DEMO_MOCK_OPENAPI_SPEC
from jg_plugin_demoapi.parser import OpenAPIParser


@pytest.mark.asyncio
async def test_execution_of_generated_tool_with_mock_transport():
    # Simular servidor HTTP respondiendo 200 OK con mock transport
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/public/status":
            return httpx.Response(200, json={"status": "operational", "uptime": 99.9})
        if request.url.path == "/api/v1/orders" and request.method == "POST":
            return httpx.Response(201, json={"order_id": "ord-9988", "status": "created"})
        if request.url.path == "/api/v1/users/42" and request.method == "PUT":
            return httpx.Response(200, json={"id": "42", "updated": True})
        return httpx.Response(404, json={"error": "Not Found"})

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    parser = OpenAPIParser(http_client=mock_client)
    tools = parser.parse_spec_to_tools(
        DEMO_MOCK_OPENAPI_SPEC,
        base_url_override="http://mock-api:8080",
    )
    tools_by_name = {t.name: t for t in tools}

    # 1. Probar GET público
    status_tool = tools_by_name["demoapi_getpublicstatus"]
    status_res = await status_tool.func()
    assert status_res.success is True
    assert status_res.output["status"] == "operational"

    # 2. Probar POST mutativo con payload JSON
    order_tool = tools_by_name["demoapi_createorder"]
    order_res = await order_tool.func(body={"product_id": "prod-1", "quantity": 2})
    assert order_res.success is True
    assert order_res.output["order_id"] == "ord-9988"

    # 3. Probar PUT con interpolación de path param y body
    update_tool = tools_by_name["demoapi_updateuser"]
    update_res = await update_tool.func(id="42", body={"name": "Alice", "role": "admin"})
    assert update_res.success is True
    assert update_res.output["id"] == "42"

    await mock_client.aclose()
