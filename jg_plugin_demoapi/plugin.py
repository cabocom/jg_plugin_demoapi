"""Implementación principal de DemoApiPlugin para jg_agente."""

from __future__ import annotations

import logging
from typing import Any

from jg_sdk.contracts import (
    AgentTool,
    BaseEngine,
    BasePlugin,
    PluginMetadata,
    RiskLevel,
)

from jg_plugin_demoapi.cache import TwoLevelCache
from jg_plugin_demoapi.parser import OpenAPIParser
from jg_plugin_demoapi.tools import DemoApiToolManager, get_canonical_tools

logger = logging.getLogger("jg_plugin_demoapi")


class DemoApiPlugin(BasePlugin):
    """Plugin de ingesta dinámica de OpenAPI, gobierno granular de riesgos y caché ETag."""

    def __init__(self) -> None:
        self._is_started: bool = False
        self.cache = TwoLevelCache(default_ttl_seconds=300.0)
        self.parser = OpenAPIParser()
        self.manager = DemoApiToolManager(cache=self.cache, parser=self.parser)

    def get_plugin_metadata(self) -> PluginMetadata:
        """Retorna los metadatos canónicos del plugin demoapi."""
        return PluginMetadata(
            name="demoapi",
            version="1.0.0",
            description="Ingesta dinámica de contratos OpenAPI 3.x, clasificación determinista de riesgo (HITL) y caché en dos niveles.",
            author="Javier Gálvez",
            dependencies=[],
            jg_agente_version_min="1.0.0",
            tags=["demo", "api", "openapi", "hitl", "security", "cache"],
            extra={"risk_level": RiskLevel.HIGH},
        )

    def register_tools(self) -> list[AgentTool]:
        """Declara las herramientas canónicas del plugin y cualquier tool generada dinámicamente."""
        canonical = get_canonical_tools(self.manager)
        dynamic = list(self.manager.dynamic_tools.values())
        return canonical + dynamic

    def register_engines(self) -> dict[str, BaseEngine]:
        """Declara motores de dominio cognitivo (no requeridos en v1.0.0)."""
        return {}

    async def startup(self) -> None:
        """Inicialización del plugin en jg_agente."""
        logger.info("Inicializando DemoApiPlugin v1.0.0...")
        self._is_started = True

    async def shutdown(self) -> None:
        """Liberación de recursos y limpieza de caché."""
        logger.info("Deteniendo DemoApiPlugin y liberando recursos...")
        self.cache.clear()
        self.manager.dynamic_tools.clear()
        self._is_started = False

    async def health_check(self) -> dict[str, Any]:
        """Reporta el estado operativo y telemetría de la caché."""
        return {
            "status": "ok",
            "plugin": "demoapi",
            "version": "1.0.0",
            "started": self._is_started,
            "tools_count": len(self.register_tools()),
            "cache_stats": self.cache.stats(),
        }


# Exportación canónica para autodescubrimiento
PLUGIN_CLASS = DemoApiPlugin
