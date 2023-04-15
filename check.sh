#!/bin/env bash
# py - check Python script with mypy and flake8, then execute it

export PATH=".:$PATH"
# Put this script in same folder of the program to test.
program="$(readlink -f ${0%%/*})/geprotondl.py"
export MYPY_CACHE_DIR="/tmp/.mypy_cache"
mkdir -p "$MYPY_CACHE_DIR"

mypy --pretty --strict "$program" \
    && flake8 --color always --max-complexity 15 "$program" \
    && python3 -I -b -X warn_default_encoding "$program" "$@"
