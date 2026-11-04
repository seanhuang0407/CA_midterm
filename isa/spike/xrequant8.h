// Project-local Xrequant8; all sources are captured before WRITE_RD.
require_rv64;
const reg_t input = RS1;
const reg_t descriptor = RS2;
const uint32_t q = uint32_t(descriptor);
const int raw_shift = int((descriptor >> 32) & 63);
const int shift = raw_shift < 32 ? raw_shift : raw_shift - 64;
const int raw_zero = int((descriptor >> 38) & 255);
const int raw_low = int((descriptor >> 46) & 255);
const int raw_high = int((descriptor >> 54) & 255);
const int zero = raw_zero < 128 ? raw_zero : raw_zero - 256;
const int low = raw_low < 128 ? raw_low : raw_low - 256;
const int high = raw_high < 128 ? raw_high : raw_high - 256;
require((descriptor >> 62) == 0 && q <= 0x7fffffffU &&
        shift >= -31 && shift <= 0 && low <= high);
const int64_t acc = int64_t(sext32(input));
const int64_t product = acc * int64_t(q);
int64_t value = (product + (product >= 0 ? (INT64_C(1) << 30) :
                         1 - (INT64_C(1) << 30))) / (INT64_C(1) << 31);
if (shift < 0) {
  const int64_t divisor = INT64_C(1) << -shift;
  // Nearest integer, halfway away from zero; avoid negative signed shifts.
  value = value >= 0 ? (value + divisor / 2) / divisor :
                     -((-value + divisor / 2) / divisor);
}
value += zero; // INT64 prevents overflow for INT32_MAX + positive zero-point.
value = value < low ? low : value > high ? high : value;
WRITE_RD(reg_t(value));
