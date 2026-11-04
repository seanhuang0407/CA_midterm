#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
mkdir -p results
for variant in B0 B1 S P X1 XR X2 micro micro-S micro-P micro-X1 micro-XR micro-X2; do
 simulator=spike
 case "$variant" in X*|micro-X*) simulator=tools/spike-xq/bin/spike;; esac
 timeout 180 "$simulator" --isa=RV64IMC -g "build/$variant.elf" > "results/$variant.stdout" 2> "results/$variant.histogram"
 grep -qx PASS "results/$variant.stdout"
 python3 scripts/profile.py --variant "$variant"
done
