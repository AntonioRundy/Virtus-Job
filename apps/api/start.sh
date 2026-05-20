#!/bin/sh
# Startup script: corre migrações e inicia a API
set -e

echo "[startup] A correr migrações Alembic..."
alembic upgrade head

echo "[startup] Migrações concluídas. A iniciar API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
