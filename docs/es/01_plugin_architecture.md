# 01. Arquitectura del Plugin (`jg_plugin_demoapi`)

[← Volver al Índice](README.md) | [02. Especificación de Herramientas →](02_tools_specification.md)

---

## 1. Visión y Misión Arquitectónica

`jg_plugin_demoapi` es una extensión canónica para el runtime cognitivo `jg_agente` construida estrictamente sobre `jg_agente_sdk`. Su objetivo es permitir la **ingesta dinámica de contratos OpenAPI/Swagger v3.x** y traducirlos de forma determinista a herramientas de agente (`AgentTool`).

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        CONTRATO OPENAPI / SWAGGER                      │
│        (URL externa del prospecto o definición Mock interna)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ CAPA 1: VALIDACIÓN ANTI-SSRF Y ATADO DE SOCKET (ssrf.py)               │
│   • Resolución DNS asíncrona y validación de todas las IPs             │
│   • Veto a rangos privados RFC 1918, loopback y metadatos cloud        │
│   • Retorno de PinnedEndpoint para atar la conexión (Anti-Rebinding)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Petición Segura
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ CAPA 2: CACHÉ EN DOS NIVELES (cache.py)                                │
│   • Nivel 1: Memoria en caliente con TTL (<1 ms)                       │
│   • Nivel 2: Revalidación HTTP con cabecera ETag y 304 Not Modified    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Especificación Parseada
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ CAPA 3: CLASIFICACIÓN DE RIESGO Y GENERACIÓN DE HERRAMIENTAS           │
│   • GETs públicos ────────► RiskLevel.LOW (Ejecución Directa)          │
│   • GETs sensibles / RBAC ─► RiskLevel.HIGH (Gobernanza HITL)          │
│   • POST / PUT / DELETE ───► RiskLevel.HIGH (Gobernanza HITL)          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Desacoplamiento Absoluto

- Cero dependencias de frameworks web como FastAPI o LangGraph.
- Consumo exclusivo de los contratos de `jg_agente_sdk`.
- Interacción para prospectos canalizada a través del portal público `jg_hub` (`ApiDemoComponent`), sin acoplar la consola de `jg_dashboard`.

