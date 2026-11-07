#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install Python packages
pip install -r requirements.txt

# Collect static files into STATIC_ROOT for WhiteNoise
python manage.py collectstatic --noinput

# Run database migrations against Supabase
python manage.py migrate
