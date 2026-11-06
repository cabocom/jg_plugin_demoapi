# 04. Testing, Calidad y CI/CD (`jg_plugin_demoapi`)

[← 03. Gobernanza de Riesgo y HITL](03_risk_governance_hitl.md) | [Volver al Índice](README.md)

---

## 1. Suite de Pruebas Automatizadas

El plugin dispone de una suite en Pytest con 21 pruebas unitarias y de integración pasando al 100%:
- `test_parser.py`: Ingesta de especificaciones OpenAPI 3.0 en JSON y YAML.
- `test_risk.py`: Clasificación de riesgo determinista para GETs sensibles y métodos mutativos.
- `test_ssrf.py`: Validación de filtrado de IPs prohibidas y DNS Pinning.
- `test_cache.py`: Caché en dos niveles (memoria caliente y ETag condicional 304).
- `test_e2e_mock.py`: Ciclo de vida completo con servidor mock local.
- `test_plugin.py`: Integración con `MockPluginRunner` del SDK.

---

## 2. Pipeline de CI/CD

El pipeline en GitLab garantiza:
1. `ruff check .` y `ruff format --check .`
2. `pytest tests/`
3. Empaquetado `python -m build` y verificación de tipos.

