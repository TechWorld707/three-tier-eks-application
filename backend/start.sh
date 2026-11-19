#!/bin/sh
set -eu
export PROMETHEUS_MULTIPROC_DIR="$(mktemp -d)"
exec gunicorn --config gunicorn.conf.py "$@"
