#!/usr/bin/env bash
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PROJECT_ROOT/tools/python${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$PROJECT_ROOT/tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin:$PROJECT_ROOT/tools/spike/bin:$PROJECT_ROOT/tools/sysroot/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PROJECT_ROOT/tools/sysroot/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
