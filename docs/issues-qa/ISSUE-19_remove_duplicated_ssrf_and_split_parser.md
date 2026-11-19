# [ISSUE-19] [jg_plugin_demoapi] refactor(dry): Eliminar ssrf.py duplicado migrando a jg_sdk.security.ssrf y dividir funciones >40 líneas

- **ID Maestro QA:** `ISSUE-19`
- **Proyecto Destino:** `javiergalvez-ia/jg_plugin_demoapi`
- **Asignado a:** `cabocom` / Javier Gálvez (`assignee_ids: [553306]`)
- **Milestone:** `QA & Anti-Fallback Hardening (Nov-Dic 2026)`
- **Labels:** `qa-audit, priority::high, dry, sonar-debt, solid`
- **GitLab Issue Remoto:** [jg_plugin_demoapi#4](https://gitlab.com/javiergalvez-ia/jg_plugin_demoapi/-/work_items/4)

---

- **Severidad y Categoría:** `Major` | `DRY-Duplicación` / `Complejidad-CodeSmell`
- **Consenso de Auditores:** Detectado por: `argon`, `claude-sonnet`, `flash-3.8`, `hydrogen` (Unánime 4/4)
- **Evidencia Exacta:**
  - `jg_plugin_demoapi/jg_plugin_demoapi/ssrf.py:1-172`
  - `jg_plugin_demoapi/jg_plugin_demoapi/parser.py:31-89, 115-297`
  - `jg_plugin_demoapi/jg_plugin_demoapi/tools.py:41-141, 155-241`
  - `jg_plugin_demoapi/jg_plugin_demoapi/risk.py:71-146`
- **Solución Técnica Propuesta:**
  1. Eliminar la implementación duplicada en `jg_plugin_demoapi/ssrf.py` y delegar en `jg_sdk.security.ssrf.SSRFValidator`.
  2. Dividir `parse_spec_to_tools` (`105L`) e `ingest_openapi` (`101L`) en métodos privados `<= 40` líneas y añadir `logger.warning/error` en los bloques `except` de `parser.py` y `tools.py`.
- **Criterios de Aceptación (Checklist verificable):**
  - [x] `ruff check .` y `pytest` pasan al 100% en `jg_plugin_demoapi`.
