#!/bin/sh
set -e

# Create data directory for SQLite (no-op for MySQL)
mkdir -p data

# Apply any pending Alembic migrations
alembic upgrade head

# Start the application
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-config log_config.json
