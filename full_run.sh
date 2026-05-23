#!/bin/sh
cd "$(dirname "$0")"
uv run python manage.py scrape
uv run python manage.py normalize
