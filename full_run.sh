#!/bin/sh
uv run python manage.py scrape
uv run python manage.py normalize
