"""Tests unitarios para la caché en dos niveles (TwoLevelCache)."""

import time
from unittest.mock import MagicMock

from jg_sdk.contracts import AgentTool

from jg_plugin_demoapi.cache import TwoLevelCache


def _make_dummy_tool(name: str) -> AgentTool:
    return AgentTool(
        name=name,
        description=f"Dummy tool {name}",
        func=MagicMock(),
    )


def test_level_1_memory_hit_and_ttl():
    cache = TwoLevelCache(default_ttl_seconds=10.0)
    tools = [_make_dummy_tool("tool_a")]
    url = "https://api.example.com/openapi.json"

    cache.put(url, raw_content="{}", etag='"etag-123"', tools=tools)

    # Nivel 1: Retorno inmediato en caliente (<1 ms)
    start = time.perf_counter()
    cached = cache.get_fresh(url)
    duration = time.perf_counter() - start

    assert cached is not None
    assert len(cached) == 1
    assert cached[0].name == "tool_a"
    assert duration < 0.005  # < 5ms (habitualmente < 0.1ms)
    assert cache.get_etag(url) == '"etag-123"'


def test_level_1_expiration():
    cache = TwoLevelCache(default_ttl_seconds=0.05)  # 50 ms
    tools = [_make_dummy_tool("tool_a")]
    url = "https://api.example.com/openapi.json"

    cache.put(url, raw_content="{}", etag='"etag-123"', tools=tools)
    assert cache.get_fresh(url) is not None

    time.sleep(0.06)
    assert cache.get_fresh(url) is None  # Expirado


def test_level_2_revalidate_304():
    cache = TwoLevelCache(default_ttl_seconds=0.05)
    tools = [_make_dummy_tool("tool_a")]
    url = "https://api.example.com/openapi.json"

    cache.put(url, raw_content="{}", etag='"etag-123"', tools=tools)
    time.sleep(0.06)
    assert cache.get_fresh(url) is None  # Expirado en memoria

    # Simulación de respuesta 304 Not Modified
    revalidated = cache.revalidate_304(url, new_etag='"etag-123"')
    assert len(revalidated) == 1
    # Ahora vuelve a estar vigente en el Nivel 1
    assert cache.get_fresh(url) is not None


def test_cache_stats_and_invalidate():
    cache = TwoLevelCache()
    url = "https://api.example.com/spec.json"
    cache.put(url, raw_content="{}", etag="abc", tools=[])

    stats = cache.stats()
    assert stats["total_entries"] == 1
    assert stats["active_entries"] == 1

    assert cache.invalidate(url) is True
    assert cache.get_fresh(url) is None
    assert cache.stats()["total_entries"] == 0
