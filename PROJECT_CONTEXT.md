# CONTEXTO DE PROYECTO: jg_plugin_demoapi

**Versión del documento:** 1.0.1  
**Fecha de consolidación:** 9 de noviembre de 2026  
**Componente:** Plugin de Ingesta Dinámica de OpenAPI, Gobierno Granular de Riesgos, Caché ETag y Simulación de APIs  
**Stack Tecnológico:** Python >= 3.11, Pydantic v2, HTTPX, PyYAML, jg-agente-sdk, Pytest, Ruff  
**Estado:** Operativo / Contratos canónicos verificados al 100% y sincronización automática de *mirror* público hacia `https://github.com/cabocom/jg_plugin_demoapi` (`workspace#8`).

---

## 1. Propósito y Misión Arquitectónica

`jg_plugin_demoapi` es una extensión canónica para el runtime cognitivo `jg_agente` construida estrictamente sobre `jg_agente_sdk`. Su objetivo es permitir la ingesta dinámica de contratos OpenAPI/Swagger v3.x (tanto preconfigurados como inyectados en tiempo de ejecución por prospectos o clientes) y traducirlos de forma transparente y determinista a herramientas de agente (`AgentTool`).

El plugin permite a empresas y prospectos evaluar la gobernanza de la plataforma javiergalvez-ia conectando sus propias APIs o utilizando el entorno de simulación mock local, garantizando:
- **Desacoplamiento Radical:** Toda interacción visual y autorización HITL de prospectos se canaliza a través del portal de clientes `jg_hub` (Livewire 3), prohibiendo cualquier dependencia de `jg_dashboard`.
- **Acceso Determinista Permanente (Zero Fricción):** Autenticación sin tokens efímeros que expiren mediante hash HMAC-SHA256 (`/demo/api/{accessHash}`).
- **Gobierno Granular de Riesgos:** Clasificación determinista de métodos mutativos (`RiskLevel.HIGH`, compuerta HITL obligatoria) y diferenciación de llamadas `GET`: las lecturas públicas se autorizan de inmediato (`RiskLevel.LOW`), mientras que rutas sensibles (`/admin/`, `/salaries`, `/billing`, `/audit`) o protegidas por scopes RBAC escalan obligatoriamente a HITL (`RiskLevel.HIGH`).
- **Blindaje Anti-SSRF y DNS Pinning:** Resolución asíncrona de hostnames, validación rigurosa de direcciones IP (bloqueo de RFC 1918, loopback, metadatos de cloud `169.254.169.254`) y atado de conexión por socket para prevenir ataques de DNS Rebinding.
- **Caché en Dos Niveles:** Memoria en caliente con TTL (<1 ms) combinada con revalidación condicional HTTP mediante cabecera `If-None-Match` y respuestas `304 Not Modified`.

---

## 2. Herramientas y Capacidades Expuestas

El plugin implementa en `tools.py` y `parser.py` tanto herramientas canónicas de orquestación como herramientas dinámicas generadas desde OpenAPI:

1. **`demoapi_load_openapi` (Observer, Low Risk, Read-Only):**
   - Ingiere un contrato OpenAPI desde una URL externa o el fixture `mock`.
   - Aplica validación Anti-SSRF y caché en dos niveles.
   - Genera dinámicamente instancias `AgentTool` con esquemas Pydantic v2 (`args_schema`) e inyecta la función ejecutora correspondiente.
   - Retorna un manifiesto estructurado clasificando las herramientas según riesgo, compuertas HITL y permisos RBAC requeridos.

2. **`demoapi_get_mock_spec` (Observer, Low Risk, Read-Only):**
   - Expone la definición del contrato mock local de demostración para pruebas sin conexión y entornos de CI/CD.

3. **Herramientas Dinámicas Generadas (`demoapi_{operationId}`):**
   - Creadas en tiempo de ejecución a partir de cada endpoint y método OpenAPI.
   - Parámetros tipados con esquemas dinámicos Pydantic (`create_model`).
   - Métodos mutativos (`POST`, `PUT`, `PATCH`, `DELETE`): `RiskLevel.HIGH`, `ToolType.MUTATION`, `read_only=False`, `requires_hitl=True`.
   - Métodos de lectura pública (`GET` estándar): `RiskLevel.LOW`, `ToolType.READ`, `read_only=True`, `requires_hitl=False`.
   - Métodos de lectura sensible o RBAC: `RiskLevel.HIGH`, `ToolType.READ`, `read_only=True`, `requires_hitl=True`.

---

## 3. Principios Arquitectónicos y Desacoplamiento

1. **Cero Dependencias de Frameworks Web u Orquestadores:**
   El plugin no depende de FastAPI, Uvicorn ni LangGraph directamente. Todo el contrato funcional se establece a través de las interfaces públicas de `jg_agente_sdk` (`BasePlugin`, `AgentTool`, `RiskLevel`, `ToolType`, `ToolResult`).

2. **Caché en Dos Niveles (`cache.py`):**
   - **Nivel 1 (Memoria en caliente):** Estructura `TwoLevelCache` en memoria que devuelve en <1 ms las herramientas si el TTL sigue vigente.
   - **Nivel 2 (Revalidación condicional ETag):** Si expira la memoria, envía `If-None-Match: <etag>`. Ante `304 Not Modified`, extiende el TTL sin retransferir ni reparsear el contrato. Ante `200 OK`, regenera las herramientas y actualiza el ETag.

3. **Seguridad de Red y DNS Pinning (`ssrf.py`):**
   - Previene Server-Side Request Forgery antes de que cualquier cliente HTTP inicie la conexión TCP.
   - Resuelve el DNS de forma asíncrona y valida todas las IPs contra la lista negra de redes privadas y reservadas.
   - Devuelve un `PinnedEndpoint` para atar la conexión evitando DNS rebinding entre la validación y la transferencia.

4. **Autodescubrimiento e Invocación CLI (`jg`):**
   - Declara el entry-point canónico en `pyproject.toml`:
     ```toml
     [project.entry-points."jg_agente.plugins"]
     demoapi = "jg_plugin_demoapi.plugin:DemoApiPlugin"
     ```
   - Totalmente compatible con la CLI de desarrollo del ecosistema: `jg run`.

---

## 4. Estructura de Módulos

```text
jg_plugin_demoapi/
├── jg_plugin_demoapi/
│   ├── __init__.py         # Re-exportación de contratos, plugin, parser y cache
│   ├── cache.py            # Caché Nivel 1 (Memoria) y Nivel 2 (ETag / 304)
│   ├── mock.py             # Fixture OpenAPI 3.x canónico para pruebas offline
│   ├── parser.py           # Parser OpenAPI 3.x y generador de AgentTools Pydantic v2
│   ├── plugin.py           # Clase principal DemoApiPlugin (BasePlugin)
│   ├── risk.py             # Clasificador determinista de riesgos y directivas HITL/RBAC
│   ├── ssrf.py             # Validador Anti-SSRF y resolución con DNS Pinning
│   └── tools.py            # Herramientas canónicas y gestor de ingesta dinámica
├── tests/                  # Suite de 21 tests unitarios y de integración (100% pasando)
│   ├── test_cache.py       # Validación de memoria <1ms, expiración y revalidación 304
│   ├── test_e2e_mock.py    # Pruebas de ejecución simulada con MockTransport
│   ├── test_parser.py      # Validación de esquemas Pydantic v2 y endpoints generados
│   ├── test_plugin.py      # Ciclo de vida (startup, shutdown, health_check) y carga mock
│   ├── test_risk.py        # Cobertura de métodos mutativos, GET público y GET sensibles
│   └── test_ssrf.py        # Cobertura de vectores SSRF (RFC 1918, metadata, loopback)
├── scripts/
│   └── check.sh            # Pipeline de verificación de calidad (Ruff + Pytest)
├── install.sh              # Script de aprovisionamiento de entorno virtual y dependencias
├── pyproject.toml          # Configuración del paquete, entry points y reglas de linter
├── .gitignore              # Patrones de exclusión de git
└── README.md               # Guía completa de uso, arquitectura e integración
```

---

## 5. Verificación y Suite de Calidad

El proyecto dispone de un script automatizado de verificación de calidad (`scripts/check.sh`) que valida tanto linters como pruebas unitarias:

```bash
# Ejecución del pipeline de verificación
./scripts/check.sh
```

**Resultados de la última validación:**
- **Ruff:** 0 errores, formato 100% verificado (`All checks passed!`).
- **Pytest:** 21 tests unitarios y de integración ejecutados y superados con éxito en 0.21 segundos.
