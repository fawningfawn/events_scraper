#!/usr/bin/env bash

echo "Running architecture + schema guardrails..."
/usr/local/bin/python -m unittest -v \
	tests.lib.core.test_schema_authority \
	tests.lib.core.test_architecture_boundaries \
	tests.lib.regression.test_runtime_regression_matrix
GUARD_EXIT=$?
if [ "$GUARD_EXIT" -ne 0 ]; then
	echo "Guardrails failed with exit code: $GUARD_EXIT"
	exit "$GUARD_EXIT"
fi
