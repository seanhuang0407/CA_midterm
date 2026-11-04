// Project-local Xqmac8: RV64 only, signed bytes, INT32 modular accumulator.
require_rv64;
const reg_t a = RS1;
const reg_t b = RS2;
uint32_t acc = uint32_t(STATE.XPR[insn.rd()]);
for (unsigned i = 0; i < 8; ++i) {
  const int av = int((a >> (8 * i)) & 255);
  const int bv = int((b >> (8 * i)) & 255);
  const int product = (av < 128 ? av : av - 256) * (bv < 128 ? bv : bv - 256);
  acc += uint32_t(product); // Defined modulo 2^32, including overflow.
}
WRITE_RD(sext32(acc));
