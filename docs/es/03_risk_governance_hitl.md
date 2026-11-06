# 03. Gobernanza Granular de Riesgo y HITL (`jg_plugin_demoapi`)

[← 02. Herramientas](02_tools_specification.md) | [04. Testing y CI/CD →](04_testing_quality_cicd.md)

---

## 1. Clasificación Determinista de Riesgo (`risk.py`)

A diferencia de aproximaciones simplistas donde todas las consultas `GET` se catalogan ciegamente como seguras, `jg_plugin_demoapi` implementa evaluación semántica rigurosa:

### 1.1 Métodos Mutativos
- `POST`, `PUT`, `PATCH`, `DELETE`
- **Riesgo:** `RiskLevel.HIGH`
- **Gobernanza:** Provoca pausa obligatoria `WAITING_APPROVAL` en el nodo `human_approval`. Requiere autorización humana previa antes de efectuar la petición HTTP.

### 1.2 Métodos de Lectura Pública
- `GET` estándar sin rutas críticas ni scopes privilegiados (ej. `/items`, `/products/123`).
- **Riesgo:** `RiskLevel.LOW`
- **Gobernanza:** Ejecución directa inmediata sin interrupción humana.

### 1.3 Métodos de Lectura Sensible y Scopes Privilegiados
- Consultas `GET` hacia endpoints que contienen términos sensibles (`/admin/`, `/billing/`, `/salaries`, `/audit`, `/credentials`) o que exigen scopes de seguridad en la especificación OpenAPI (ej. `security: [{"admin_auth": ["write:all"]}]`).
- **Riesgo:** `RiskLevel.HIGH`
- **Gobernanza:** Escala a `RiskLevel.HIGH` y exige autorización humana previa para evitar exfiltración pasiva de información corporativa sensible.

