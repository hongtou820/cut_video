#!/bin/bash
# Javrate 采集器启动脚本
PYTHON="/usr/local/opt/python@3.12/bin/python3.12"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"
exec "$PYTHON" main.py "$@"
