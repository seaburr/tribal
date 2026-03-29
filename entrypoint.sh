#!/bin/sh
set -e

# Create data directory for SQLite (no-op for MySQL)
mkdir -p data

echo "Starting database migrations..."

# Apply any pending Alembic migrations
alembic upgrade head

echo "Database migrations complete."

# Starting the application
echo "  _____    _ _          _ ";
echo " |_   _| _(_) |__  __ _| |";
echo "   | || '_| | '_ \\/ _\` | |";
echo "   |_||_| |_|_.__/\\__,_|_|";
echo "                          ";
echo "Live in stere-ereo.";
echo ""
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-config log_config.json
