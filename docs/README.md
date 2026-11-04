# Documentación Técnica de `jg_plugin_demoapi`

Bienvenido a la documentación oficial de **`jg_plugin_demoapi`**, plugin para la ingesta dinámica de contratos OpenAPI 3.x, clasificación determinista de riesgo (HITL), caché en dos niveles y blindaje anti-SSRF con DNS Pinning.

---

## 📚 Índice de Capítulos

1. **[01. Arquitectura del Plugin](01_plugin_architecture.md)**
   - Visión del plugin, pipeline de ingesta OpenAPI, validación anti-SSRF y caché en 2 niveles.
2. **[02. Especificación de Herramientas](02_tools_specification.md)**
   - Herramientas canónicas (`demoapi_load_openapi`, `demoapi_get_mock_spec`) y herramientas generadas al vuelo.
3. **[03. Gobernanza Granular de Riesgo y HITL](03_risk_governance_hitl.md)**
   - Clasificación semántica de operaciones mutativas y GETs sensibles.
4. **[04. Testing, Calidad y CI/CD](04_testing_quality_cicd.md)**
   - Suite unitaria Pytest, entorno mock y pipeline de CI/CD.
