#!/bin/sh
docker run -it -v $(dirname "$0"):/app python:2.7 /bin/bash -c "pip install -r /app/requirements.txt ; python /app/manage.py scrape"

