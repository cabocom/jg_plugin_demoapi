"""Paquete principal de jg_plugin_demoapi para el ecosistema javiergalvez-ia."""

from jg_plugin_demoapi.cache import CacheEntry, TwoLevelCache
from jg_plugin_demoapi.mock import DEMO_MOCK_OPENAPI_SPEC
from jg_plugin_demoapi.parser import OpenAPIParser
from jg_plugin_demoapi.plugin import DemoApiPlugin
from jg_plugin_demoapi.risk import RiskClassification, RiskClassifier
from jg_plugin_demoapi.ssrf import PinnedEndpoint, SSRFValidationError, SSRFValidator
from jg_plugin_demoapi.tools import DemoApiToolManager

__all__ = [
    "DemoApiPlugin",
    "OpenAPIParser",
    "TwoLevelCache",
    "CacheEntry",
    "RiskClassifier",
    "RiskClassification",
    "SSRFValidator",
    "SSRFValidationError",
    "PinnedEndpoint",
    "DemoApiToolManager",
    "DEMO_MOCK_OPENAPI_SPEC",
]
