#!/usr/bin/env bash
# Thin wrapper for src/manage.py

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ENV_DIR="$SCRIPT_DIR/.venv"

if [[ $1 = restart ]]; then
	systemctl --user restart events.service
	exit 0
fi

if [[ ! -d "$ENV_DIR" ]]; then
	python3 -m venv --system-site-packages "$ENV_DIR"
	"$ENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

export PYTHONPATH="$SCRIPT_DIR/src"
exec "$ENV_DIR/bin/python" "$SCRIPT_DIR/src/manage.py" "$@"
