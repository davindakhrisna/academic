#!/usr/bin/env bash
# Compatibility launcher for existing Linux shortcuts; all behavior is Python.
SCRIPT_PATH=$(realpath -- "${BASH_SOURCE[0]}") || exit 1
DIR=$(dirname -- "$SCRIPT_PATH") || exit 1
exec python3 "$DIR/main.py" "$@"
