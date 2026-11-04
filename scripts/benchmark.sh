#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
mkdir -p results
for variant in B0 B1; do
  spike --isa=RV64IMC -g "build/$variant.elf" > "results/$variant.stdout" 2> "results/$variant.histogram"
  grep -qx PASS "results/$variant.stdout"
  python3 scripts/profile.py --variant "$variant"
done
spike --isa=RV64IMC -g build/micro.elf > results/micro.stdout 2> results/micro.histogram
grep -qx PASS results/micro.stdout
python3 scripts/profile.py --variant micro
