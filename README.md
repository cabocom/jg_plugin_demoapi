> ⚠️ **Nota:** Este repositorio es un *mirror* público sincronizado automáticamente desde [GitLab](https://gitlab.com/javiergalvez-ia). El desarrollo activo, pipelines CI/CD, *issues* y discusiones técnicas se gestionan en https://gitlab.com/javiergalvez-ia

<div align="center">

# 🔌 `jg_plugin_demoapi`

### Plugin de Ingesta Dinámica de OpenAPI para `jg_agente`
*Caché ETag en 2 Niveles, Gobierno Granular HITL y Protección Anti-SSRF con DNS Pinning*

[![GitLab CI/CD](https://img.shields.io/badge/GitLab_CI-Pipeline_Passing-108548?style=flat-square&logo=gitlab&logoColor=white)](https://gitlab.com/javiergalvez-ia/jg_plugin_demoapi)
[![Mirror to GitHub](https://img.shields.io/badge/GitHub-Mirror_Active-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/cabocom/jg_plugin_demoapi)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-v3.x-6BA539?style=flat-square&logo=openapi-initiative&logoColor=white)](https://www.openapis.org/)
[![SDK](https://img.shields.io/badge/SDK-jg--agente--sdk-e92063?style=flat-square)](https://pypi.org/project/jg-agente-sdk/)
[![Security](https://img.shields.io/badge/Security-SSRF_%26_DNS_Pinning-crimson?style=flat-square&logo=shield&logoColor=white)](#1-misión-del-componente)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/Tests-21_passing-success?style=flat-square&logo=pytest&logoColor=white)](#1-misión-del-componente)

</div>

---

Plugin oficial de ingesta dinámica de OpenAPI, gobierno granular de riesgos (HITL), caché en dos niveles (ETag) y simulación de APIs para el runtime cognitivo **`jg_agente`**, desarrollado sobre **`jg_agente_sdk`**.

---

## 1. Misión del Componente

`jg_plugin_demoapi` permite a clientes y prospectos conectar contratos OpenAPI/Swagger v3.x en tiempo de ejecución o evaluar el comportamiento del agente mediante un entorno mock integrado. 

### Invariantes y Principios de Diseño:
1. **Desacoplamiento Radical de la Interfaz:** Cero uso de `jg_dashboard`. Toda la experiencia de interacción, visualización y gobernanza HITL de cara al cliente se gestiona exclusivamente dentro de `jg_hub` (Livewire 3).
2. **Acceso Determinista Permanente (Zero Fricción):** Prohibido el uso de tokens temporales que expiren con errores 419 o 403. El acceso se autentica mediante hash HMAC-SHA256 firmado con la clave de la aplicación:
   ```php
   $accessHash = hash_hmac('sha256', $lead->email, config('app.key'));
   // Ruta: /demo/api/{accessHash}
   ```
3. **Gobierno Granular de Riesgos (No todos los GET son de bajo riesgo):**
   - **Verbos Mutativos (`POST`, `PUT`, `PATCH`, `DELETE`):** Clasificados como `RiskLevel.HIGH`, `ToolType.MUTATION` y compuerta HITL obligatoria.
   - **Lecturas Públicas (`GET` estándar):** Clasificadas como `RiskLevel.LOW`, `ToolType.READ`, ejecución directa permitida.
   - **Lecturas Sensibles / RBAC:** Rutas coincidentes con `/admin/`, `/private/`, `/salaries`, `/billing`, `/audit` o con scopes OAuth/RBAC declarados en OpenAPI se catalogan como `RiskLevel.HIGH` y escalan obligatoriamente a HITL o verificación de permisos explícitos.
4. **Seguridad de Red y Anti-SSRF:** Toda resolución de dominio externa para descargar especificaciones o ejecutar endpoints pasa por `SSRFValidator.resolve_and_pin_url_async()` con DNS Pinning a nivel de socket TCP, bloqueando metadatos de cloud (`169.254.169.254`), interfaces loopback y rangos privados RFC 1918.
5. **Caché en Dos Niveles:**
   - **Nivel 1 (Memoria en caliente):** Reutiliza las instancias `AgentTool` ya parseadas en `<1 ms` si el TTL sigue vigente.
   - **Nivel 2 (Revalidación HTTP condicional):** Emite `If-None-Match` con el último ETag. Ante respuesta `304 Not Modified`, extiende el TTL sin transferir ni re-parsear el documento.

---

## 2. Instalación Rápida con `install.sh`

El plugin incluye un script que aprovisiona el entorno virtual `.venv`, vincula la copia local del SDK (`jg-agente-sdk`) e instala las dependencias:

```bash
./install.sh
source .venv/bin/activate
```

---

## 3. Instalación Manual

```bash
python3 -m venv .venv
source .venv/bin/activate

# 1. Instalar jg-agente-sdk local
pip install -e ../jg_agente_sdk

# 2. Instalar el plugin en modo editable con dependencias de desarrollo
pip install -e ".[dev]"
```

---

## 4. Ejecución de Pruebas y Validación CI/CD

El repositorio dispone de un pipeline local automatizado de calidad (`scripts/check.sh`):

```bash
./scripts/check.sh
```

O ejecución directa de la suite de pruebas:
```bash
pytest tests/ -v
```

---

## 5. Integración en `jg_agente`

Una vez instalado en el entorno de `jg_agente`, el runtime detectará automáticamente el entry-point `demoapi` declarado en `pyproject.toml`.

Para activarlo en el runtime cognitivo:
```bash
ENABLED_PLUGINS=jg_plugin_demoapi
```

---

## 6. Estructura de Módulos

```text
jg_plugin_demoapi/
├── jg_plugin_demoapi/
│   ├── cache.py            # Caché Nivel 1 (Memoria) y Nivel 2 (ETag / 304)
│   ├── mock.py             # Fixture OpenAPI 3.x canónico
│   ├── parser.py           # Parser OpenAPI 3.x y generador de AgentTools
│   ├── plugin.py           # Clase principal DemoApiPlugin (BasePlugin)
│   ├── risk.py             # Clasificador determinista de riesgos y directivas HITL
│   ├── ssrf.py             # Validador Anti-SSRF y resolución con DNS Pinning
│   └── tools.py            # Herramientas canónicas y gestor de ingesta
├── tests/                  # Suite de 21 tests unitarios
├── scripts/
│   └── check.sh            # Pipeline de verificación (Ruff + Pytest)
├── install.sh              # Script de instalación de entorno virtual
├── pyproject.toml          # Configuración del paquete y reglas de linter
└── PROJECT_CONTEXT.md      # Contexto técnico y especificaciones vivas del componente
```
