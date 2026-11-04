# 02. Especificación de Herramientas (`jg_plugin_demoapi`)

[← 01. Arquitectura](01_architecture.md) | [03. Gobernanza de Riesgo y HITL →](03_risk_governance_hitl.md)

---

## 1. Herramientas Canónicas de Orquestación

### 1.1 `demoapi_load_openapi`
- **Tipo:** `observer`
- **Nivel de Riesgo:** `RiskLevel.LOW`
- **Reversibilidad:** No reversible
- **Propósito:** Ingiere una especificación OpenAPI desde una URL externa o el fixture `mock`. Aplica validación anti-SSRF, verifica la caché en dos niveles y genera dinámicamente el catálogo de herramientas operativas en memoria.
- **Salida:** Manifiesto estructurado con las operaciones descubiertas, sus parámetros y los niveles de riesgo asignados.

### 1.2 `demoapi_get_mock_spec`
- **Tipo:** `observer`
- **Nivel de Riesgo:** `RiskLevel.LOW`
- **Reversibilidad:** No reversible
- **Propósito:** Retorna el contrato OpenAPI mock local preconfigurado, permitiendo pruebas deterministas en offline o entornos de integración continua.

---

## 2. Herramientas Dinámicas Generadas (`demoapi_{operationId}`)

A partir de cada endpoint y método HTTP del contrato OpenAPI ingerido, el plugin genera una herramienta dedicada:
- **Nombre:** Derivado del `operationId` OpenAPI (ej. `demoapi_listUsers`, `demoapi_deleteOrder`).
- **Esquema de Entrada:** Modelo Pydantic v2 dinámico generado al vuelo (`pydantic.create_model`) tipando parámetros de ruta, query y body.
- **Ejecución HTTP:** Cliente asíncrono `httpx.AsyncClient` con DNS Pinning inyectado en el transporte.

