# Backlog QA & Seguridad Consolidado — `jg_plugin_demoapi`

**Repositorio GitLab:** `https://gitlab.com/javiergalvez-ia/jg_plugin_demoapi`  
**Responsable Asignado:** `cabocom` / Javier Gálvez (`assignee_ids: [553306]`)  
**Total de Issues en `jg_plugin_demoapi`:** **2**

## Índice de Issues de Remediación

| ID | Severidad | Categoría | Título | Consenso Modelos | Archivo Local | Issue GitLab |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| `ISSUE-18` | **Blocker** | `Seguridad` | fix(security): Validar SSRF en ejecución de herramientas dinámicas OpenAPI, aplicar IP de DNS Pinning en ingest_openapi y limpiar allowlist por defecto | Detectado por: `argon` (`tools.py:38` mencionado en texto por `claude-sonnet`) | [ISSUE-18_fix_2nd_order_openapi_ssrf_and_dns_pinning.md](./ISSUE-18_fix_2nd_order_openapi_ssrf_and_dns_pinning.md) | [#3](https://gitlab.com/javiergalvez-ia/jg_plugin_demoapi/-/work_items/3) |
| `ISSUE-19` | **Major** | `DRY-Duplicación / Complejidad-CodeSmell` | refactor(dry): Eliminar ssrf.py duplicado migrando a jg_sdk.security.ssrf y dividir funciones >40 líneas | Detectado por: `argon`, `claude-sonnet`, `flash-3.8`, `hydrogen` (Unánime 4/4) | [ISSUE-19_remove_duplicated_ssrf_and_split_parser.md](./ISSUE-19_remove_duplicated_ssrf_and_split_parser.md) | [#4](https://gitlab.com/javiergalvez-ia/jg_plugin_demoapi/-/work_items/4) |
