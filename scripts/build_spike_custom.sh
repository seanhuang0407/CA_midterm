#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
revision=530af85d83781a3dae31a4ace84a573ec255fefa
archive="$PROJECT_ROOT/tools/spike-v1.1.0.tar.gz"
[[ -f "$archive" ]] || { echo 'Run scripts/setup.sh first.' >&2; exit 1; }
echo "a58e6a73c828f6305fa4a5b49af42adc9c502b260ac7589e7126d70d32399704  $archive" | sha256sum --check
stamp="$(cat isa/spike/*.h isa/spike.patch scripts/build_spike_custom.sh | sha256sum | cut -d' ' -f1)"
if [[ -x tools/spike-xq/bin/spike && -f tools/spike-xq/source.sha256 ]] && [[ "$(cat tools/spike-xq/source.sha256)" == "$stamp" ]]; then
  echo 'Custom Spike is up to date.'; exit 0
fi
# Reuse generated objects; restore only files changed by our integration patch.
source_dir="$PROJECT_ROOT/tools/spike-xq-src"
mkdir -p "$source_dir" tools/spike-xq-build
for path in riscv/encoding.h disasm/disasm.cc; do
  tar -xOf "$archive" "riscv-isa-sim-$revision/$path" > "$source_dir/${path//\//_}.original"
done
if [[ ! -f "$source_dir/configure" ]]; then tar -xzf "$archive" -C "$source_dir" --strip-components=1; fi
for path in riscv/encoding.h disasm/disasm.cc; do cp "$source_dir/${path//\//_}.original" "$source_dir/$path"; done
patch --batch -d "$source_dir" -p1 < isa/spike.patch
cp isa/spike/xqmac8.h isa/spike/xrequant8.h "$source_dir/riscv/insns/"
(
 cd tools/spike-xq-build
 if [[ ! -f Makefile ]]; then
   ../spike-xq-src/configure --prefix="$PROJECT_ROOT/tools/spike-xq" --enable-histogram --enable-commitlog
 fi
 instructions='$(riscv_insn_ext_i) $(riscv_insn_ext_m) $(riscv_insn_ext_c) $(riscv_insn_priv) xqmac8 xrequant8'
 make -j"${JOBS:-4}" riscv_insn_list="$instructions"
 make install riscv_insn_list="$instructions"
)
printf '%s\n' "$stamp" > tools/spike-xq/source.sha256
