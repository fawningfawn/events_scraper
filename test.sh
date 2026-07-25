#!/usr/bin/env bash

# Docker wrapper for test runner
# Usage examples:
#   ./test.sh                                           # Run all tests
#   ./test.sh tests.lib.core.test_database_loading      # Run specific tests
#   ./test.sh tests.lib.tui                             # Run all TUI tests
#
# Benefits:
# - Much faster development cycle (seconds vs minutes)
# - Still runs in consistent Docker environment
# - Coverage reports generated for tested modules

mkdir -p reports

# Isolate docker-compose resources per CI build to avoid cross-build conflicts.
# Jenkins sets BUILD_TAG; fall back to a local unique value.
RAW_PROJECT_NAME="${BUILD_TAG:-events_local_$(date +%s)_$$}"
SANITIZED_PROJECT_NAME="$(echo "$RAW_PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '-')"
SANITIZED_PROJECT_NAME="${SANITIZED_PROJECT_NAME#-}"
SANITIZED_PROJECT_NAME="${SANITIZED_PROJECT_NAME:-events}"
export COMPOSE_PROJECT_NAME="$SANITIZED_PROJECT_NAME"

# Create output file with timestamp FIRST
OUTPUT_FILE="reports/test_output_$(date +%Y%m%d_%H%M%S).log"
echo "Test output will be saved to: $OUTPUT_FILE"
echo "Using COMPOSE_PROJECT_NAME: $COMPOSE_PROJECT_NAME"

# Check if any arguments look like file paths (contain / or end with .py)
for arg in "$@"; do
	if [[ "$arg" == /* ]] || [[ "$arg" == */* ]] || [[ "$arg" == *.py ]]; then
		echo "Error: test.sh expects Python module names, not file paths"
		echo "Example: test.sh tests.lib.core.test_database_loading"
		echo "NOT: test.sh tests/lib/core/test_database_loading.py"
		exit 1
	fi
done

# Pass test arguments to docker compose via environment variable
export TEST_ARGS="$*"

rm -fv reports/test_output_* 2>/dev/null || true

# Build Docker images first (fail fast if build fails)
echo "Building Docker images..."
if ! DOCKER_UID=$(id -u) DOCKER_GID=$(id -g) docker compose build; then
	echo "Docker build failed"
	exit 1
fi

# Run tests and capture output
echo "Running tests with args: $TEST_ARGS"
trap 'DOCKER_UID=$(id -u) DOCKER_GID=$(id -g) docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
DOCKER_UID=$(id -u) DOCKER_GID=$(id -g) docker compose up --exit-code-from runningpy 2>&1 | tee "$OUTPUT_FILE"
EXIT_CODE=${PIPESTATUS[0]}

echo "Tests completed with exit code: $EXIT_CODE"
echo "Full output saved to: $OUTPUT_FILE"

exit "$EXIT_CODE"
