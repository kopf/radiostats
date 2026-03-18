#!/bin/sh
docker run -it -v $(dirname "$0"):/app python:3.12 /bin/bash -c "pip install -r /app/requirements.txt ; python /app/manage.py scrape" && \
  docker run -it -v $(dirname "$0"):/app python:3.12 /bin/bash -c "pip install -r /app/requirements.txt ; python /app/manage.py normalize"
