# 第 3 項：自訂 ISA 設計提案（尚未在 Spike 實作）

## 量測依據與實作順序

詳見 ../results/SUMMARY.md。B0 在 block + FC 共有 14,098,944 MAC，卻需 172,766,758 條退休指令（0.08161 MAC/instruction）。B1 展開內迴圈後降為 148,375,111，但 multiply 數量不變，memory 指令約 36.87M，並未隨展開減少。

1. **Scalar dot-product 開銷**：B0 kernel 有 14,098,944 次 `mulw`，另需逐項加總、扣 activation zero-point 和迴圈操作。B1 仍未減少 MAC 的乘法數。
2. **載入／位址與迴圈開銷**：B0 kernel 36,846,169 次 load/store，約 2.6134 memory instructions/MAC；25,771,844 次 branch/jump。B1 展開可降 branch/jump 至 17,024,074，卻幾乎沒有降低記憶體指令數。這是指令開銷的證據，不能從 Spike 推論 cache miss 或 memory bandwidth bottleneck。
3. **整數 requantization 開銷**：B0/B1 的 `qmul` + `requant` 函式共有 29,886,836 條指令，約占 B0 ROI 17.30%、B1 ROI 20.14%。目前為可獨立驗證與歸因而保留 noinline；此數包含呼叫／stack 開銷，並非全部可視為硬體運算收益。加入 ISA 前應再比較 inlining 和常數特化版本，避免誇大改善。
4. **Depthwise 的索引與邊界檢查**：B1 depthwise 占總 ROI 33.17%，高於其他單一算子；只有 2.032M MAC 卻需 49.213M 指令。應先將 interior/border 分離、簡化索引，不能假設連續 packed dot 可直接加速 depthwise。

## Xqmac8：先針對 pointwise／FC

提議 encoding：custom-0 opcode `0x0b`，funct3=`000`，funct7=`0000000`，R-type。此為本專案草案，未由標準保留，也尚未驗證 decoder 整合。

```text
xqmac8 rd, rs1, rs2
old = signed32(X[rd][31:0])
sum = Σ signed8(X[rs1][8*i+7:8*i]) * signed8(X[rs2][8*i+7:8*i]), i=0..7
X[rd] = sign_extend_64(wrap_signed32(old + sum))
```

- 是 rd read-modify-write：除 rs1、rs2 外必須讀舊 rd。Spike 實作前先保存所有來源，處理 rd=rs1／rs2 alias。硬體最終需第三個來源讀取，或額外 pipeline cycle；期中不做 PPA，但必須清楚記錄這個選擇。
- `rd=x0`：來源 accumulator 為零、結果丟棄；rs1／rs2=x0 各 lane 為零。
- 最低位 byte 是 lane 0；所有 lane 都是 signed INT8，非 unsigned activation。accumulator 每次以 32-bit modular arithmetic 更新，輸出 sign-extend 至 XLEN；需用 unsigned C++ 算術避免 signed-overflow UB。
- 本 workload 累加範圍經 reference 驗證安全；仍需 directed tests 測試 wrap 規則。
- packed operands 以 8-byte 對齊資料配合 `ld`，C wrapper 用 `uint64_t`/安全載入，避免違反 strict aliasing 或未對齊存取。

### 非零 activation zero-point

```text
Σ (x[k] - zx) * w[k] + bias
= Σ x[k] * w[k] + (bias - zx * Σ w[k])
```

模型權重 zero-point 為 0，可離線把括號內項目折入 INT32 bias。避免將 x-zx 硬塞回 INT8（可能超過範圍）。這個前處理也要提供純 RV64IMC 比較版，以區分軟體改善與 ISA 改善。

選定 pointwise 的 K=24、72，FC 的 K=960 都是 8 的倍數，無尾端；一般 kernel 必須有 scalar tail。depthwise 的同一 channel 空間值不連續，先不假設同等收益；量測 gather/packing 成本後才決定擴充。

理想內迴圈每 8 MAC 使用兩次 64-bit load、一條 Xqmac，再加指標與迴圈操作。這是設計推估，不是實測的 8× 加速；原始 byte-load 到 packed-load 的改善與 zero-point folding 必須分開比較。

## Xrequant8：保留與 reference 相同的 rounding

提議 encoding：custom-0 `0x0b`，funct3=`001`，funct7=`0000000`，R-type。

```text
xrequant8 rd, rs1, rs2
acc = signed32(X[rs1][31:0])
q, s, zp, lo, hi = decode_descriptor(X[rs2])
v = RoundingDivideByPOT(SaturatingRoundingDoublingHighMul(acc,q), -s)
X[rd] = sign_extend_64(clamp(v + zp, lo, hi))
```

初版限制：非負 Q31 multiplier，shift s ∈ [-31,0]。本次輸出的 convolution／FC multiplier 都在此範圍；尚不支援大於 1 的倍率，超出時使用軟體 fallback。

Descriptor 草案：

| Bits | 欄位 |
|---|---|
| 31:0 | q：非負 signed Q31 multiplier |
| 37:32 | s：6-bit signed shift |
| 45:38 | zp：signed INT8 output zero-point |
| 53:46 | lo：signed INT8 clamp minimum |
| 61:54 | hi：signed INT8 clamp maximum |
| 63:62 | reserved，必須為零 |

非法 q、正 shift、reserved 非零、lo>hi 應觸發 illegal instruction。rounding 必須與 src/kernels.c 的 qmul 一致，特別是負數 halfway 情況：high-multiply 使用帶符號 nudge 與向零除法，再做 rounding divide by power of two。不能簡化成單一 `(acc*q)>>shift`。descriptor 可離線預打包；載入 descriptor 的指令與資料大小必須計入成本。

本指令直接支援 per-channel Conv/FC 的輸出 requant。Residual ADD 具有兩個 input multiplier 及一個 output multiplier，需要保留中間 INT32 精度；不可把兩個 input scaling 用會提前 clamp 至 INT8 的 Xrequant8 取代。初版 ADD 保留軟體實作，或之後另評估不 clamp 的 Xqmul32。

## 增量實驗與驗證

比較 B0 → B1 → B1+zero-point folding/packing → X1（只加 Xqmac8）→ X2（Xqmac8 + Xrequant8）。另跑 Xrequant-only 消融實驗，避免把兩指令效果混在一起。

每一版本對相同輸入與 reference 逐元素比對，並記錄 kernel ROI 指令數、MAC/instruction、memory instructions/MAC、custom utilization、.text bytes。用 microbenchmark、expand/project 兩個主要算子、FC、完整 residual block 比較。達標優先觀察 major GEMM/FC kernel 的 ≥2× instruction reduction；目前 B1 尚未達到此門檻。

指令實作階段需要新增：

- Xqmac directed：±128/127、全零、lane 排列、混合符號、非零累加、溢位、rd/source alias、x0；至少 10,000 組 randomized。
- Xrequant directed：負數 rounding、halfway、shift=0/-31、zero-point、clamp、非法 descriptor；randomized 對照 Python 任意精度 reference。
- 對 Spike decoder/execute 的原始碼 patch、C inline assembly wrapper，以及 fail 時非零 exit 的 bare-metal tests。
- 回歸本次所有 block/FC 輸出，並另外測 K 非 8 倍數的尾端。

目前未修改 Spike ISA，custom frequency=0；上述收益均未量測。期中依使用者提供格式，不要求 CV-Wally、PPA、CPI 或 Fmax。
