# [ISSUE-18] [jg_plugin_demoapi] fix(security): Validar SSRF en ejecución de herramientas dinámicas OpenAPI, aplicar IP de DNS Pinning en ingest_openapi y limpiar allowlist por defecto

- **ID Maestro QA:** `ISSUE-18`
- **Proyecto Destino:** `javiergalvez-ia/jg_plugin_demoapi`
- **Asignado a:** `cabocom` / Javier Gálvez (`assignee_ids: [553306]`)
- **Milestone:** `QA & Anti-Fallback Hardening (Nov-Dic 2026)`
- **Labels:** `qa-audit, priority::blocker, security`
- **GitLab Issue Remoto:** [jg_plugin_demoapi#3](https://gitlab.com/javiergalvez-ia/jg_plugin_demoapi/-/work_items/3)

---

- **Severidad y Categoría:** `Blocker` | `Seguridad`
- **Consenso de Auditores:** Detectado por: `argon` (`tools.py:38` mencionado en texto por `claude-sonnet`)
- **Evidencia Exacta:**
  - `jg_plugin_demoapi/jg_plugin_demoapi/parser.py:128-139, 248-264`
  - `jg_plugin_demoapi/jg_plugin_demoapi/tools.py:38, 78-93`
  ```python
  # jg_plugin_demoapi/jg_plugin_demoapi/parser.py:248, 255-264
  target_url = f"{base_url.rstrip('/')}/{actual_path.lstrip('/')}"
  ...
  async with httpx.AsyncClient(timeout=15.0) as client:
      resp = await client.request(method, target_url, **req_kwargs)
  ```
  ```python
  # jg_plugin_demoapi/jg_plugin_demoapi/tools.py:38, 78-93
  self.allowlist = allowlist or ["localhost", "127.0.0.1", "mock-api"]
  ...
  pinned = await SSRFValidator.resolve_and_pin_url_async(url_stripped, allowlist=self.allowlist)
  ...
  async with httpx.AsyncClient(timeout=15.0) as client:
      resp = await client.get(url_stripped, headers=headers)
  ```
- **Solución Técnica Propuesta:**
  1. En `OpenAPIParser._create_execution_func` (`parser.py:248-264`), validar `target_url` con `SSRFValidator` y ejecutar la petición fijando la IP resuelta (o mediante transporte con DNS pinning) y `follow_redirects=False`.
  2. En `DemoApiToolManager.ingest_openapi` (`tools.py:78-93`), utilizar efectivamente la IP fijada en `pinned` (o transporte con pinning del SDK) en lugar de hacer `client.get(url_stripped)`.
  3. En `DemoApiToolManager.__init__` (`tools.py:38`), eliminar `"localhost"` y `"127.0.0.1"` de la `allowlist` por defecto en producción (`self.allowlist = allowlist if allowlist is not None else []`).
- **Criterios de Aceptación (Checklist verificable):**
  - [ ] Un spec OpenAPI cuyo `servers[0]["url"]` apunte a `http://127.0.0.1` o `http://169.254.169.254` es bloqueado por `SSRFValidationError` al invocar cualquiera de las herramientas generadas.
  - [ ] Nuevos tests de seguridad en `jg_plugin_demoapi/tests/test_parser.py` y `test_ssrf.py`.
