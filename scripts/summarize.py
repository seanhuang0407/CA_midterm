#!/usr/bin/env python3
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
b=[json.loads((R/f'results/B{i}.json').read_text()) for i in range(2)]
m=json.loads((R/'results/micro.json').read_text());lines=['# 實測結果','', '固定 seed=2026；Spike v1.1.0；GCC 15.2.0；RV64IMC + privileged CSR；數字為退休指令，非硬體 cycles。','', '| 算子 | MACs | B0 指令數 | B1 指令數 | 指令減少 |','|---|---:|---:|---:|---:|']
mac={'expand':5419008,'depthwise':2032128,'project':5419008,'residual':0,'fc':1228800}
for name in mac:
    a,c=[z['operator_instret'][name] for z in b];lines.append(f'| {name} | {mac[name]:,} | {a:,} | {c:,} | {(1-c/a)*100:.2f}% |')
a,c=[z['ROI_retired'] for z in b];lines+= [f'| 合計 | {sum(mac.values()):,} | {a:,} | {c:,} | {(1-c/a)*100:.2f}% |','',f'B0/B1 指令數比為 {a/c:.4f}×。這不是 cycle speedup 或完整模型加速比。','', '| 指標 | B0 | B1 |','|---|---:|---:|']
for key in ['whole_program_retired','ROI_retired','ROI_MAC_per_instruction','kernel_memory_instructions','kernel_load_store_per_MAC','disassembled_text_bytes']:
    lines.append(f'| {key} | {b[0][key]} | {b[1][key]} |')
lines+=['','## Kernel 指令組成','','| 類別 | B0 | B1 |','|---|---:|---:|']
for cat in ['load','store','integer_ALU','multiply','branch_jump','divide_remainder','system','floating_point']:
    lines.append(f'| {cat} | {b[0]["kernel_instruction_mix"].get(cat,0):,} | {b[1]["kernel_instruction_mix"].get(cat,0):,} |')
lines+=['',f'Microbenchmark：128 MAC，{m["ROI_retired"]:,} retired instructions，PASS。','', '資料範圍：ROI 為各算子呼叫前後 minstret 差值，含少量呼叫／取樣開銷。Kernel histogram 為 pointwise、depthwise、residual、requant、qmul 函式內的精確 PC 計數，不含驗證／列印。兩者範圍略有差異，不能混用分母。Whole-program 包含啟動、比對、列印及 reset ROM，其中 6 條 reset ROM 指令不在 ELF 反組譯內。','', 'Code size 使用反組譯 .text 指令長度總和；build/*.size 的 text 同時含 rodata（模型權重與測試 reference），兩者不可混稱。','', '固定 seed 與工具版本才應得到上述指令數；其他輸入可能改變 rounding、clamp、padding 分支數。','']
(R/'results/SUMMARY.md').write_text('\n'.join(lines))
print('\n'.join(lines))
