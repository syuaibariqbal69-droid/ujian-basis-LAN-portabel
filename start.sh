#!/bin/sh
cd "$(dirname "$0")"
if [ -x runtime/python/bin/python3 ]; then PY=runtime/python/bin/python3; else PY=python3; fi
exec "$PY" portable.py
