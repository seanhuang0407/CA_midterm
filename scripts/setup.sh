#!/usr/bin/env bash
# Tested on Ubuntu 20.04 x86_64, Python 3.8; installs only beneath tools/.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p tools models build results
fetch() {
  local url="$1" dest="$2" sum="$3"
  if [[ ! -f "$dest" ]] || ! echo "$sum  $dest" | sha256sum --check --status; then
    curl --fail --location --retry 3 "$url" --output "$dest"
  fi
  echo "$sum  $dest" | sha256sum --check
}
fetch https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v15.2.0-1/xpack-riscv-none-elf-gcc-15.2.0-1-linux-x64.tar.gz tools/gcc.tar.gz aaaa8060c914851a3e5ee1ba82cc3d6f80972f90638a05c6e823a37557a33758
[[ -d tools/xpack-riscv-none-elf-gcc-15.2.0-1 ]] || tar -xzf tools/gcc.tar.gz -C tools
fetch https://github.com/riscv-software-src/riscv-isa-sim/archive/530af85d83781a3dae31a4ace84a573ec255fefa.tar.gz tools/spike-v1.1.0.tar.gz a58e6a73c828f6305fa4a5b49af42adc9c502b260ac7589e7126d70d32399704
[[ -d tools/riscv-isa-sim-530af85d83781a3dae31a4ace84a573ec255fefa ]] || tar -xzf tools/spike-v1.1.0.tar.gz -C tools
fetch https://archive.ubuntu.com/ubuntu/pool/main/d/device-tree-compiler/device-tree-compiler_1.5.1-1_amd64.deb tools/device-tree-compiler_1.5.1-1_amd64.deb c9fdcab3a3729ace00c158ce83d563894901f7f82be379eb5280c5d7eb107382
fetch https://archive.ubuntu.com/ubuntu/pool/main/d/device-tree-compiler/libfdt1_1.5.1-1_amd64.deb tools/libfdt1_1.5.1-1_amd64.deb bbccb50c039bdee902c3b56af4839460b8191e68e39cbbd892251f16a9fd008b
mkdir -p tools/sysroot
for pkg in device-tree-compiler_1.5.1-1_amd64.deb libfdt1_1.5.1-1_amd64.deb; do dpkg-deb -x "tools/$pkg" tools/sysroot; done
source scripts/env.sh
if [[ ! -f tools/python/pip/__main__.py ]]; then
  curl --fail --location --retry 3 https://bootstrap.pypa.io/pip/3.8/get-pip.py --output tools/get-pip.py
  python3 tools/get-pip.py --target tools/python pip==24.3.1
fi
if ! python3 - <<'CHECK'
import importlib.metadata as m
for name,version in [('numpy','1.24.4'),('flatbuffers','24.3.25'),('tflite','2.18.0'),('tflite-runtime','2.14.0')]:
    assert m.version(name)==version
CHECK
then
  python3 -m pip install --target tools/python -r scripts/requirements.txt
fi
if [[ ! -x tools/spike/bin/spike ]]; then
  mkdir -p tools/spike-build-v1.1.0
  (
    cd tools/spike-build-v1.1.0
    ../riscv-isa-sim-530af85d83781a3dae31a4ace84a573ec255fefa/configure --prefix="$PROJECT_ROOT/tools/spike" --enable-histogram --enable-commitlog
    # Compile only IMC + privileged handlers; no F/D/V workload support is needed.
    make -j"${JOBS:-4}" riscv_insn_list='$(riscv_insn_ext_i) $(riscv_insn_ext_m) $(riscv_insn_ext_c) $(riscv_insn_priv)'
    make install riscv_insn_list='$(riscv_insn_ext_i) $(riscv_insn_ext_m) $(riscv_insn_ext_c) $(riscv_insn_priv)'
  )
fi
fetch https://huggingface.co/litert-community/MobileNet-v3-large/resolve/9a4fd87358f71befb4de2f5ecdce1a159486b1f2/mobilenet_v3_large_int8_channelwise.tflite models/mobilenet_v3_large_int8_channelwise.tflite 13993dec4dcfdf95d6f671b40e907b6fd6f04897577d23f4f407418fbf73bf48
python3 scripts/export_model.py
