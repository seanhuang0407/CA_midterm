# 自訂 ISA 設計與實作

狀態：Xqmac8、Xrequant8 已在獨立 Spike 修改版實作、驗證並量測。原始碼位於 [isa/](../isa/README.md)，C wrapper 位於 [custom_isa.h](../src/custom_isa.h)。這是本專案自訂 encoding，不是標準 RISC-V extension。

## 量測驅動的設計

B0 的 block+FC 有 14,098,944 MAC，需 172,766,758 條退休指令。三個主要開銷為 scalar MAC、逐 byte load／位址與迴圈操作，以及 requantization。B1 展開迴圈後仍有 14,098,944 次 scalar MAC multiply，memory instructions/MAC 約 2.615。

原 B0/B1 的 qmul+requant 共約 29.89M 指令，但含 noinline 呼叫與 stack 成本。因此新增 S 控制組：bias folding、四路 scalar unroll、inline／shift-range-specialized requant。另設 P 控制組，以 packed 64-bit load + 明確展開的八路 scalar unpack/MAC 比較相同資料布局，避免將純軟體收益歸給新指令。

## Xqmac8：packed signed INT8 MAC

| 欄位 | 設定 |
|---|---|
| opcode | custom-0 `0x0b` |
| funct3 / funct7 | `000` / `0000000` |
| match / mask | `0x0000000b` / `0xfe00707f` |
| 格式 | R-type，RV64 only；rd 同時為來源 accumulator |

```text
old = signed32(X[rd][31:0])
a, b = snapshot(X[rs1]), snapshot(X[rs2])
sum = Σ signed8(a[8*i+7:8*i]) × signed8(b[8*i+7:8*i]), i=0..7
X[rd] = sign_extend_64(wrap_signed32(old + sum))
```

所有來源在寫入之前讀取，允許 rd=rs1、rd=rs2、rs1=rs2 或三者相同。X[0] 永遠為零；rd=x0 的結果丟棄。累加器只讀低 32 bits，輸出 sign-extend 至 64 bits。溢位為 modulo 2^32，Spike 以 unsigned arithmetic 實作，不依賴 signed overflow。

此指令需要讀 rd、rs1、rs2 三個來源。未來 RTL 必須決定額外讀取埠或 pipeline cycle；本次不宣稱硬體 latency 或 area。

### Activation zero-point

```text
Σ (x[k]-zx) × w[k] + bias
= Σ x[k] × w[k] + (bias - zx × Σ w[k])
```

模型權重 zero-point=0，因此 export script 離線產生 folded bias。S、P、X1、XR、X2 全部使用相同 folded bias；不是只有 custom 版本得到這個最佳化。x 保持原 INT8，不將 x-zx 截斷回 INT8。Depthwise 保留原來中心化計算，避免邊界 padding 語意改變。

Pointwise 的 K=24、72、FC 的 K=960 都是 8 的倍數。通用 prepared kernel 仍支援任意 K：每次處理完整 8 lanes，尾端使用 scalar MAC；未對齊地址使用安全的逐 byte packing，不假設未對齊 ld 合法。對齊路徑用 memcpy + assume_aligned，避免 strict-aliasing 違規。

## Xrequant8：per-channel 輸出整數量化

| 欄位 | 設定 |
|---|---|
| opcode | custom-0 `0x0b` |
| funct3 / funct7 | `001` / `0000000` |
| match / mask | `0x0000100b` / `0xfe00707f` |
| 格式 | R-type，RV64 only；rs1=acc、rs2=descriptor |

```text
acc = signed32(X[rs1][31:0])
q,s,zp,lo,hi = decode(snapshot(X[rs2]))
high = SRDHM(acc,q)
v = RoundingDivideByPOT(high,-s)
X[rd] = sign_extend_64(clamp(INT64(v)+zp,lo,hi))
```

| Descriptor bits | 語意 |
|---|---|
| 31:0 | 非負 Q31 multiplier q，0..INT32_MAX |
| 37:32 | 6-bit signed shift s，-31..0 |
| 45:38 | signed INT8 output zero-point |
| 53:46 | signed INT8 clamp minimum |
| 61:54 | signed INT8 clamp maximum |
| 63:62 | reserved，必須為零 |

q 的 bit31=1、s>0、s=-32、reserved 非零、lo>hi 都觸發 illegal instruction（mcause=2），即使 rd=x0 也要檢查。驗證通過才寫 rd。RV32 執行會 trap；來源／目的暫存器可以重疊。

High multiply 使用 INT64 product 加 signed nudge，再向零除以 2^31；等價於本次非負 q 範圍的 `floor((acc*q+2^30)/2^31)`。下一步獨立做 power-of-two rounding，halfway away from zero，保留 double-rounding。最後 zero-point addition 使用 INT64，避免 INT32_MAX+正 zero-point 溢位。

所有選定模型層的 multiplier/shift 符合範圍，export 時會斷言檢查；不符合的模型不能使用這個 prepared path，需用一般軟體 kernel 或擴充設計。Descriptor 離線產生，載入指令與資料大小包含在評估中。

Xrequant8 用於 expand/depthwise/project/FC 的每個輸出；Residual ADD 仍全部使用相同 inline 軟體實作，兩個 input scaling 不提前 clamp 成 INT8。

## 實驗與結果

| 組態 | 使用內容 |
|---|---|
| B0 / B1 | 原始 baseline / scalar unroll |
| S | folded bias、scalar unroll、inline requant |
| P | S + packed ld、scalar unpack/MAC |
| X1 | P + Xqmac8 |
| XR | P + Xrequant8，消融實驗 |
| X2 | P + 兩條 custom instructions |

相同 layout 的 P/X1/XR/X2 形成 2×2 指令消融，另與較快的純軟體 S 比較。所有版本使用相同 seed 與 pretrained weights，輸出完全相同。

X2 ROI 為 72,303,636 指令；相對 B0 172,766,758 為約 2.389× instruction-count reduction。相對最快純軟體 S，expand/project/FC 分別約 3.0065×、2.9495×、2.9256×，達到 major GEMM/FC ≥2× 指令減少目標。最新精確數字與每 output 指令數由 [SUMMARY.md](../results/SUMMARY.md) 自動產生；不是 cycles 或完整模型加速比。

P 的 scalar unpack 反而較慢，顯示單純改 packed layout 不保證收益；不能只用 P 當有利 baseline。X2 執行 1,508,352 次 Xqmac8、528,128 次 Xrequant8。Depthwise 仍為 scalar spatial MAC，在 X2 占約 54.4% ROI，成為下一個主要瓶頸。

## 驗證與重現

```bash
source scripts/env.sh
make isa-test             # 自動建置獨立 custom Spike，執行下列驗證
make all benchmark       # 原版／修改版 Spike 的 workload 與 microbenchmarks
python3 scripts/summarize.py
```

- Python 任意精度 oracle 產生 10,216 組 MAC 與 10,576 組 requant vectors（各含 10,000 組 randomized）。與 Spike 實作使用不同的數學表達式，沒有以 simulator 自己的函式產生 expected。
- Bare-metal 指令測試共 155,800 項斷言，涵蓋 lane 符號／順序、INT32 wrap、完整 64-bit sign extension、來源 alias、x0、極值、負數 halfway、shift 邊界、clamp。
- 13 次預期 illegal traps：6 種非法 descriptor 各測一般 rd 和 x0，以及保留 encoding；檢查 mcause 和 mtval。
- 19,008 項 prepared kernel 比對：K=0..65、offset=0..7、4 個 zero-points、tail、未對齊 rows/weights。
- 原版 Spike 拒絕兩條 custom 指令；修改版在 RV32 也拒絕兩條 RV64-only 指令。
- B0/B1/S/P/X1/XR/X2 都對原模型 reference 做完整 block+FC 逐元素比對；另以 seed=17 驗證 S/X2。

細節見 [VERIFICATION.md](../results/VERIFICATION.md)。功能選擇是由 simulator binary 區分，不宣稱支援標準 ISA extension string 或 runtime enable CSR。沒有 CV-Wally RTL、PPA、Fmax 或 cycle model。
