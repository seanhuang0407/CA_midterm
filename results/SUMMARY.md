# 實測結果

固定 seed=2026；Spike v1.1.0；GCC 15.2.0；RV64IMC + privileged CSR；數字為退休指令，非硬體 cycles。

| 算子 | MACs | B0 指令數 | B1 指令數 | 指令減少 |
|---|---:|---:|---:|---:|
| expand | 5,419,008 | 56,896,642 | 46,754,827 | 17.82% |
| depthwise | 2,032,128 | 49,213,055 | 49,213,055 | 0.00% |
| project | 5,419,008 | 47,981,278 | 36,484,711 | 23.96% |
| residual | 0 | 8,767,869 | 8,767,869 | 0.00% |
| fc | 1,228,800 | 9,907,914 | 7,154,649 | 27.79% |
| 合計 | 14,098,944 | 172,766,758 | 148,375,111 | 14.12% |

B0/B1 指令數比為 1.1644×。這不是 cycle speedup 或完整模型加速比。

| 指標 | B0 | B1 |
|---|---:|---:|
| whole_program_retired | 181180021 | 156790020 |
| ROI_retired | 172766758 | 148375111 |
| ROI_MAC_per_instruction | 0.08160681003228643 | 0.09502229791086728 |
| kernel_memory_instructions | 36846169 | 36871267 |
| kernel_load_store_per_MAC | 2.6133992020962706 | 2.6151793354168937 |
| disassembled_text_bytes | 2042 | 2198 |

## Kernel 指令組成

| 類別 | B0 | B1 |
|---|---:|---:|
| load | 34,407,194 | 34,426,013 |
| store | 2,438,975 | 2,445,254 |
| integer_ALU | 95,295,774 | 79,626,799 |
| multiply | 14,852,864 | 14,852,864 |
| branch_jump | 25,771,844 | 17,024,074 |
| divide_remainder | 0 | 0 |
| system | 0 | 0 |
| floating_point | 0 | 0 |

Microbenchmark：128 MAC，1,182 retired instructions，PASS。

資料範圍：ROI 為各算子呼叫前後 minstret 差值，含少量呼叫／取樣開銷。Kernel histogram 為 pointwise、depthwise、residual、requant、qmul 函式內的精確 PC 計數，不含驗證／列印。兩者範圍略有差異，不能混用分母。Whole-program 包含啟動、比對、列印及 reset ROM，其中 6 條 reset ROM 指令不在 ELF 反組譯內。

Code size 使用反組譯 .text 指令長度總和；build/*.size 的 text 同時含 rodata（模型權重與測試 reference），兩者不可混稱。

固定 seed 與工具版本才應得到上述指令數；其他輸入可能改變 rounding、clamp、padding 分支數。
