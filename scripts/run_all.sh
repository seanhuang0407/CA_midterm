#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
mkdir -p build results
make export
make test 2>&1 | tee results/host-tests.txt
make all
make benchmark 2>&1 | tee results/benchmark.log
python3 scripts/summarize.py
