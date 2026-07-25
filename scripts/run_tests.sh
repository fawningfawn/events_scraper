#!/usr/bin/env bash
# Run tests inside Docker container with all report generation
# Called by docker-compose.yml with TEST_ARGS environment variable

# Run flake8 first (fail fast on linting)
echo "Running flake8..."
/usr/local/bin/python -m flake8 src/

# Enforce no-live-network policy during tests.
export EVENTS_TEST_RUN=1

# Run CI guardrails on full-suite runs
if [ -z "${TEST_ARGS:-}" ]; then
	echo "Running CI guardrails..."
	/test/scripts/ci_guardrails.sh
fi

# Run tests with coverage and XML output.
# - Full suite: discover all tests under tests/
# - Targeted runs: accept dotted unittest paths from TEST_ARGS (no report generation)
echo "Running tests with xmlrunner..."
if [ -z "${TEST_ARGS:-}" ]; then
	/usr/local/bin/python -m coverage run -m xmlrunner discover -s tests -p 'test*.py' -o /test/reports/xml -v
	TEST_EXIT=$?

	# Generate HTML test timing report (always run even if tests failed)
	echo "Generating HTML test timing report..."
	/test/.local/bin/junit2html --merge /test/reports/test_timing.xml /test/reports/xml/*xml
	/test/.local/bin/junit2html /test/reports/test_timing.xml /test/reports/test_timing.html

	# Generate coverage reports (always run even if tests failed)
	echo "Generating coverage reports..."
	/usr/local/bin/python -m coverage report
	/usr/local/bin/python -m coverage html
else
	# Split space-delimited args produced by test.sh into an array.
	read -r -a TARGET_TEST_ARGS <<<"$TEST_ARGS"
	echo "Running targeted tests (reports/xml/coverage disabled)..."
	/usr/local/bin/python -m unittest -v "${TARGET_TEST_ARGS[@]}"
	TEST_EXIT=$?
fi

# Exit with the test exit code
exit "$TEST_EXIT"
