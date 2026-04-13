#!/bin/bash
# Test runner for radiostats project using Docker
# Compatible with Python 2.7 and can easily be adapted for Python 3

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
DOCKER_IMAGE="${1:-python:3.12}"
PYTEST_ARGS="${2:---verbose --cov=scraper --cov-report=html}"

echo "=========================================="
echo "Running tests with Docker image: $DOCKER_IMAGE"
echo "=========================================="
echo ""

docker run \
  -it \
  --rm \
  -v "$PROJECT_DIR:/app" \
  -w /app \
  "$DOCKER_IMAGE" \
  /bin/bash -c "
    set -e
    echo 'Installing dependencies...'
    pip install -q -r requirements.txt
    echo 'Running pytest...'
    pytest $PYTEST_ARGS
    echo ''
    echo 'Tests completed successfully!'
  "

echo ""
echo "=========================================="
echo "Test run completed!"
echo "=========================================="
