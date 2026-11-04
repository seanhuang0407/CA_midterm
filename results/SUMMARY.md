# ISA 實測結果

固定 seed=2026；GCC 15.2.0；原版／修改版 Spike v1.1.0。全部數字為 retired instructions，不是 cycles、CPI、PPA 或完整模型 speedup。

## 比較組

| 版本 | 行為 | ROI retired |
|---|---|---:|
| B0 | 原始 scalar、noinline requant | 172,766,758 |
| B1 | 四路 scalar unroll | 148,375,111 |
| S | folded bias、四路 scalar unroll、inline requant | 132,932,061 |
| P | S 的 packed ld + 八路 scalar unpack/MAC 控制組 | 198,993,870 |
| X1 | P + Xqmac8 | 92,779,463 |
| XR | P + Xrequant8（消融） | 178,543,138 |
| X2 | P + Xqmac8 + Xrequant8 | 72,303,636 |

## 各算子退休指令

| 算子 | MACs | B0 | B1 | S | P | X1 | XR | X2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| expand | 5,419,008 | 56,896,642 | 46,754,827 | 40,835,044 | 69,962,207 | 22,081,758 | 61,475,079 | 13,582,085 |
| depthwise | 2,032,128 | 49,213,055 | 49,213,055 | 48,477,790 | 48,477,790 | 48,477,790 | 39,315,305 | 39,315,305 |
| project | 5,419,008 | 47,981,278 | 36,484,711 | 30,737,021 | 60,767,352 | 13,187,959 | 58,012,933 | 10,420,995 |
| residual | 0 | 8,767,869 | 8,767,869 | 6,961,493 | 6,961,493 | 6,961,493 | 6,961,493 | 6,961,493 |
| fc | 1,228,800 | 9,907,914 | 7,154,649 | 5,920,713 | 12,825,028 | 2,070,463 | 12,778,328 | 2,023,758 |
| 合計 | 14,098,944 | 172,766,758 | 148,375,111 | 132,932,061 | 198,993,870 | 92,779,463 | 178,543,138 | 72,303,636 |

## 增量收益與消融

| 比較 | 指令數比（前/後） | 指令減少 |
|---|---:|---:|
| B0 → X2 | 2.3895× | 58.15% |
| B1 → X2 | 2.0521× | 51.27% |
| S → X1 | 1.4328× | 30.21% |
| S → X2 | 1.8385× | 45.61% |
| P → X1 | 2.1448× | 53.38% |
| P → XR | 1.1145× | 10.28% |
| X1 → X2 | 1.2832× | 22.07% |
| XR → X2 | 2.4694× | 59.50% |

P 將 packed registers 在軟體拆成 8 lanes，指令成本高於 S。P→X1／XR 只用來控制資料布局；實際收益必須同時看較快的純軟體 S，不能只挑較慢的 P 當 baseline。S 已內聯 requant，避免將原始 noinline 呼叫開銷當成 ISA 的全部收益。

## 相對最快純軟體的 major GEMM/FC 改善

| 算子 | 最快純軟體 | 純軟體 instructions | X2 instructions | 指令數比 |
|---|---|---:|---:|---:|
| expand | S | 40,835,044 | 13,582,085 | 3.0065× |
| project | S | 30,737,021 | 10,420,995 | 2.9495× |
| fc | S | 5,920,713 | 2,023,758 | 2.9256× |

因此達成題目「major GEMM/FC kernel ≥2× dynamic instruction reduction」目標。未宣稱完整模型推論或 cycle speedup。

## ISA-level metrics

| 指標 | B0 | B1 | S | P | X1 | XR | X2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ROI_MAC_per_instruction | 0.081607 | 0.095022 | 0.106061 | 0.070851 | 0.151962 | 0.078967 | 0.194996 |
| kernel_memory_instructions | 36846169 | 36871267 | 33728736 | 12611808 | 12007136 | 13996418 | 13391746 |
| kernel_load_store_per_MAC | 2.613399 | 2.615179 | 2.392288 | 0.894521 | 0.851634 | 0.992728 | 0.94984 |
| disassembled_text_bytes | 2042 | 2198 | 2542 | 2832 | 2552 | 2468 | 2176 |
| custom_instruction_frequency | 0.0 | 0.0 | 0.0 | 0.0 | 0.016257 | 0.002958 | 0.028166 |
| xqmac8 count | 0 | 0 | 0 | 0 | 1,508,352 | 0 | 1,508,352 |
| xrequant8 count | 0 | 0 | 0 | 0 | 0 | 528,128 | 528,128 |

custom_instruction_frequency 的分母為 kernel histogram 指令數。MAC/instruction 的分母為 ROI，兩者範圍略有差異。Custom MAC coverage = 8×Xqmac8_count / logical_MAC_count。

## Kernel 指令組成

| 類別 | B0 | B1 | S | P | X1 | XR | X2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| load | 34,407,194 | 34,426,013 | 32,037,502 | 10,920,574 | 10,618,238 | 11,493,713 | 11,191,377 |
| store | 2,438,975 | 2,445,254 | 1,691,234 | 1,691,234 | 1,388,898 | 2,502,705 | 2,200,369 |
| integer_ALU | 95,295,774 | 79,626,799 | 68,984,530 | 154,352,585 | 59,301,314 | 136,023,306 | 40,946,940 |
| multiply | 14,852,864 | 14,852,864 | 14,852,864 | 14,852,864 | 2,786,048 | 14,324,736 | 2,257,920 |
| branch_jump | 25,771,844 | 17,024,074 | 15,365,851 | 17,176,533 | 17,176,533 | 13,670,470 | 13,670,470 |
| custom_mac | 0 | 0 | 0 | 0 | 1,508,352 | 0 | 1,508,352 |
| custom_requant | 0 | 0 | 0 | 0 | 0 | 528,128 | 528,128 |
| floating_point | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Requant 增量：每個輸出元素的指令數

此數包含整個算子，X1→X2 的變化是加上 requant 指令後的增量，不是單獨 requant latency。

| 算子 | X1 instructions/output | X2 instructions/output |
|---|---:|---:|
| expand | 97.7969 | 60.1531 |
| depthwise | 214.7011 | 174.1218 |
| project | 175.2227 | 138.4592 |
| fc | 1617.5492 | 1581.0609 |

## Microbenchmark：128 MAC

| 版本 | ROI retired |
|---|---:|
| micro | 1,182 |
| micro-S | 770 |
| micro-P | 1,479 |
| micro-X1 | 352 |
| micro-XR | 1,433 |
| micro-X2 | 301 |

## 下一個瓶頸

X2 的 depthwise 占 ROI 54.38%，residual ADD 占 9.63%。Xqmac8 目前只用在連續 K 維度的 pointwise/FC，depthwise 保留 scalar MAC 與邊界／索引計算。下一步應先分離 interior/border、改善 loop layout，再量測是否值得加 gather 或 memory ISA。

Memory 指令減少只證明 load/store 指令開銷下降；沒有 cache-miss 或 bandwidth 測量，不能推論硬體 cache bottleneck 已解決。

## 量測範圍與資料成本

ROI 是算子呼叫前後的 minstret 差值，含少量參數準備／取樣開銷。Kernel histogram 僅計 pointwise/depthwise（含 prepared 版本）、residual、qmul、requant；不含驗證與列印。Whole-program JSON 含啟動、比對、列印，以及 ELF 外的 6 條 reset ROM 指令。

Code size 是反組譯 .text 指令長度總和。build/*.size 的 text 也包含 rodata，不可混稱。Prepared 版本使用離線 folded bias 與每 channel 8-byte descriptor；其輸出 header、load 成本及 ELF data/rodata 都保留，沒有把 descriptor decode/loading 當作免費。

評估範圍為完整 residual block（12,870,144 MAC）加一個 FC（1,228,800 MAC）。全部版本使用相同輸入並逐元素對照獨立 reference；未執行整個模型的 bare-metal inference。
