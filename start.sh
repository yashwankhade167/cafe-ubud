#!/usr/bin/env bash
# Render start script
# 1. Seed the database (safe to re-run — drops & recreates tables)
# 2. Launch gunicorn with 2 workers on the port Render assigns

set -e

echo "Seeding database..."
python seed.py

echo "Starting gunicorn..."
exec gunicorn "app:create_app()" \
  --workers 2 \
  --bind "0.0.0.0:${PORT:-5000}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
