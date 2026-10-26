#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f "$PROJECT_ROOT/.venv/bin/pytest" ]; then
    PYTEST="$PROJECT_ROOT/.venv/bin/pytest"
elif [ -f "$PROJECT_ROOT/../jg_plugin_sales/.venv/bin/pytest" ]; then
    PYTEST="$PROJECT_ROOT/../jg_plugin_sales/.venv/bin/pytest"
else
    PYTEST="pytest"
fi

if [ -f "$PROJECT_ROOT/.venv/bin/ruff" ]; then
    RUFF="$PROJECT_ROOT/.venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
    RUFF="$(command -v ruff)"
else
    RUFF=""
fi

echo "========================================"
echo "🔍 Verificando jg_plugin_demoapi..."
echo "========================================"

if [ -n "$RUFF" ]; then
    echo ""
    echo "1️⃣  [Ruff] Linter y formato de código..."
    "$RUFF" check .
    "$RUFF" format --check .
fi

echo ""
echo "2️⃣  [Pytest] Ejecución de suite de tests unitarios..."
"$PYTEST" -v tests

echo ""
echo "========================================"
echo "✅ ¡Todas las comprobaciones de jg_plugin_demoapi pasaron con éxito!"
echo "========================================"
