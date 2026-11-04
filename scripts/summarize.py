#!/usr/bin/env python3
"""Generate the ISA evaluation tables from measured JSON, without hand-entered gains."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
variants=['B0','B1','S','P','X1','XR','X2']
data={v:json.loads((R/f'results/{v}.json').read_text()) for v in variants}
mac={'expand':5419008,'depthwise':2032128,'project':5419008,'residual':0,'fc':1228800}
descriptions={'B0':'原始 scalar、noinline requant','B1':'四路 scalar unroll','S':'folded bias、四路 scalar unroll、inline requant','P':'S 的 packed ld + 八路 scalar unpack/MAC 控制組','X1':'P + Xqmac8','XR':'P + Xrequant8（消融）','X2':'P + Xqmac8 + Xrequant8'}
lines=['# ISA 實測結果','','固定 seed=2026；GCC 15.2.0；原版／修改版 Spike v1.1.0。全部數字為 retired instructions，不是 cycles、CPI、PPA 或完整模型 speedup。','','## 比較組','','| 版本 | 行為 | ROI retired |','|---|---|---:|']
for v in variants:lines.append(f'| {v} | {descriptions[v]} | {data[v]["ROI_retired"]:,} |')
lines+=['','## 各算子退休指令','','| 算子 | MACs | '+' | '.join(variants)+' |','|---|---:|'+'---:|'*len(variants)]
for op in mac:lines.append('| '+op+f' | {mac[op]:,} | '+' | '.join(f'{data[v]["operator_instret"][op]:,}' for v in variants)+' |')
lines.append(f'| 合計 | {sum(mac.values()):,} | '+' | '.join(f'{data[v]["ROI_retired"]:,}' for v in variants)+' |')
lines+=['','## 增量收益與消融','','| 比較 | 指令數比（前/後） | 指令減少 |','|---|---:|---:|']
for before,after in [('B0','X2'),('B1','X2'),('S','X1'),('S','X2'),('P','X1'),('P','XR'),('X1','X2'),('XR','X2')]:
    a,b=data[before]['ROI_retired'],data[after]['ROI_retired'];lines.append(f'| {before} → {after} | {a/b:.4f}× | {(1-b/a)*100:.2f}% |')
lines+=['','P 將 packed registers 在軟體拆成 8 lanes，指令成本高於 S。P→X1／XR 只用來控制資料布局；實際收益必須同時看較快的純軟體 S，不能只挑較慢的 P 當 baseline。S 已內聯 requant，避免將原始 noinline 呼叫開銷當成 ISA 的全部收益。','','## 相對最快純軟體的 major GEMM/FC 改善','','| 算子 | 最快純軟體 | 純軟體 instructions | X2 instructions | 指令數比 |','|---|---|---:|---:|---:|']
for op in ['expand','project','fc']:
    best=min(['B0','B1','S','P'],key=lambda v:data[v]['operator_instret'][op]);a=data[best]['operator_instret'][op];b=data['X2']['operator_instret'][op]
    assert a/b>=2
    lines.append(f'| {op} | {best} | {a:,} | {b:,} | {a/b:.4f}× |')
lines+=['','因此達成題目「major GEMM/FC kernel ≥2× dynamic instruction reduction」目標。未宣稱完整模型推論或 cycle speedup。','','## ISA-level metrics','','| 指標 | '+' | '.join(variants)+' |','|---|'+'---:|'*len(variants)]
for key in ['ROI_MAC_per_instruction','kernel_memory_instructions','kernel_load_store_per_MAC','disassembled_text_bytes','custom_instruction_frequency']:
    lines.append('| '+key+' | '+' | '.join(str(round(data[v][key],6)) for v in variants)+' |')
for name in ['xqmac8','xrequant8']:
    lines.append('| '+name+' count | '+' | '.join(f'{data[v]["custom_instruction_counts"][name]:,}' for v in variants)+' |')
lines+=['','custom_instruction_frequency 的分母為 kernel histogram 指令數。MAC/instruction 的分母為 ROI，兩者範圍略有差異。Custom MAC coverage = 8×Xqmac8_count / logical_MAC_count。','','## Kernel 指令組成','','| 類別 | '+' | '.join(variants)+' |','|---|'+'---:|'*len(variants)]
for cat in ['load','store','integer_ALU','multiply','branch_jump','custom_mac','custom_requant','floating_point']:
    lines.append('| '+cat+' | '+' | '.join(f'{data[v]["kernel_instruction_mix"].get(cat,0):,}' for v in variants)+' |')
lines+=['','## Requant 增量：每個輸出元素的指令數','','此數包含整個算子，X1→X2 的變化是加上 requant 指令後的增量，不是單獨 requant latency。','','| 算子 | X1 instructions/output | X2 instructions/output |','|---|---:|---:|']
for op in ['expand','depthwise','project','fc']:lines.append(f'| {op} | {data["X1"]["operator_instructions_per_output"][op]:.4f} | {data["X2"]["operator_instructions_per_output"][op]:.4f} |')
lines+=['','## Microbenchmark：128 MAC','','| 版本 | ROI retired |','|---|---:|']
for v in ['micro','micro-S','micro-P','micro-X1','micro-XR','micro-X2']:
    a=json.loads((R/f'results/{v}.json').read_text());lines.append(f'| {v} | {a["ROI_retired"]:,} |')
x=data['X2'];lines+=['','## 下一個瓶頸','',f'X2 的 depthwise 占 ROI {100*x["operator_share"]["depthwise"]:.2f}%，residual ADD 占 {100*x["operator_share"]["residual"]:.2f}%。Xqmac8 目前只用在連續 K 維度的 pointwise/FC，depthwise 保留 scalar MAC 與邊界／索引計算。下一步應先分離 interior/border、改善 loop layout，再量測是否值得加 gather 或 memory ISA。', '', 'Memory 指令減少只證明 load/store 指令開銷下降；沒有 cache-miss 或 bandwidth 測量，不能推論硬體 cache bottleneck 已解決。','', '## 量測範圍與資料成本','', 'ROI 是算子呼叫前後的 minstret 差值，含少量參數準備／取樣開銷。Kernel histogram 僅計 pointwise/depthwise（含 prepared 版本）、residual、qmul、requant；不含驗證與列印。Whole-program JSON 含啟動、比對、列印，以及 ELF 外的 6 條 reset ROM 指令。','', 'Code size 是反組譯 .text 指令長度總和。build/*.size 的 text 也包含 rodata，不可混稱。Prepared 版本使用離線 folded bias 與每 channel 8-byte descriptor；其輸出 header、load 成本及 ELF data/rodata 都保留，沒有把 descriptor decode/loading 當作免費。','', '評估範圍為完整 residual block（12,870,144 MAC）加一個 FC（1,228,800 MAC）。全部版本使用相同輸入並逐元素對照獨立 reference；未執行整個模型的 bare-metal inference。','']
(R/'results/SUMMARY.md').write_text('\n'.join(lines))
print('\n'.join(lines))
