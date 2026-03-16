#!/usr/bin/env bash
set -euo pipefail
echo "Running migrations..."
python manage.py migrate --noinput
echo "Migrations complete."
