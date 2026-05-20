#!/bin/sh
# Startup: migrações + API
set -e

echo "[startup] A correr migrações..."
alembic upgrade head

echo "[startup] A iniciar API na porta ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
