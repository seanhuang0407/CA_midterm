# Spike custom ISA source

Base: riscv-isa-sim v1.1.0, commit `530af85d83781a3dae31a4ace84a573ec255fefa`.

- `spike/xqmac8.h`: RV64 packed signed INT8 dot product with read/write INT32 rd accumulator.
- `spike/xrequant8.h`: descriptor validation, double rounding, zero-point, clamp.
- `spike.patch`: opcode/mask declarations and Spike disassembler registration.
- `../src/custom_isa.h`: GCC `.insn` wrappers; no binutils modifications are needed.

```bash
source scripts/env.sh
make custom-spike
make isa-test
```

The build script verifies the base tarball hash, restores the two patched upstream
files, applies the patch, copies instruction bodies, and builds an independent
`tools/spike-xq/bin/spike`. Source and build directories are `tools/spike-xq-src`
and `tools/spike-xq-build`. The original `tools/spike/bin/spike` is unchanged.
A source hash invalidates the custom binary when the patch/instruction bodies or
build script change. `tools/` and generated test-vector headers are not committed.

Selection is by simulator binary. The modified binary always supports these
project-local instructions under `--isa=RV64IMC`; there is no standard ISA extension
string or feature-enable CSR. RV32 execution traps. Stock Spike traps on both
opcodes. This is an ISA simulator implementation, not RTL or a latency model.

GNU objdump displays unknown custom words as `.4byte`; `profile.py` decodes the
raw encoding (`mask=0xfe00707f`, matches `0x0b` / `0x100b`) so instruction mix and
custom frequency remain accurate. Spike's patched disassembler prints the names.
See `../docs/ISA_PROPOSAL.md` for the final specification and limitations.
