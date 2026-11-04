#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
mkdir -p results
for test in isa-test kernel-test; do
 timeout 120 tools/spike-xq/bin/spike --isa=RV64IMC "build/$test.elf" > "results/$test.stdout" 2> "results/$test.stderr"
 grep -qx PASS "results/$test.stdout"
 cat "results/$test.stdout"
done
timeout 30 spike --isa=RV64IMC build/reject-test.elf > results/reject-test.stdout 2> results/reject-test.stderr
grep -qx PASS results/reject-test.stdout
cat results/reject-test.stdout
timeout 30 tools/spike-xq/bin/spike --isa=RV32IMC build/rv32-reject.elf > results/rv32-reject.stdout 2> results/rv32-reject.stderr
echo 'RV32 rejected both RV64-only custom instructions: PASS' | tee results/rv32-reject.stdout
