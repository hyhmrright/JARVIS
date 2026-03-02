#!/bin/sh
# Docker entrypoint: run DB migrations before starting the app server.
set -e

# Auto-migrate on startup (single retry for transient connection issues)
echo "Running database migrations..."
alembic upgrade head || { echo "Migration failed, retrying in 3s..."; sleep 3; alembic upgrade head; }
echo "Migrations complete. Starting server..."

# Enable --reload only when UVICORN_RELOAD is set; dev default in docker-compose
RELOAD_FLAG="${UVICORN_RELOAD:+--reload}"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 $RELOAD_FLAG
