# CA Midterm：MobileNetV3 整數 workload 與自訂 RISC-V ISA

已完成 bare-metal baseline、Spike profiling、`Xqmac8`／`Xrequant8` 實作與新增指令驗證。評估範圍是 **主要 kernels＋完整 residual block＋FC**；不做 CV-Wally/PPA，不將指令數當作 cycles。

Repository：[seanhuang0407/CA_midterm](https://github.com/seanhuang0407/CA_midterm)（private）。

## 執行方式

目前環境已備妥工具：

```bash
cd /home/sean/CA_midterm
source scripts/env.sh
bash scripts/run_all.sh
```

會匯出原模型、跑 host tests、建置 custom Spike、跑新增指令測試、編譯並評估所有版本。各層應為 `mismatches=0`，所有測試為 `PASS`；輸出寫入 results/。

新環境先準備 bash、curl、tar、sha256sum、cut、cat、cp、patch、timeout、dpkg-deb、make、GCC/G++、Python 3.8，再執行：

```bash
git clone https://github.com/seanhuang0407/CA_midterm.git
cd CA_midterm
bash scripts/setup.sh
source scripts/env.sh
bash scripts/run_all.sh
```

驗證平台為 Ubuntu 20.04 x86_64／Python 3.8.2。setup 下載固定版本及驗證 hash；GCC 約 414 MB，工具僅裝在 tools/，不需 sudo。其他平台／Python wheel 未驗證。

分步執行：

```bash
source scripts/env.sh
make export                  # 真實 pretrained weights → C 靜態資料／整數 reference
make test                    # Host C、rounding 與 prepared quantization 驗證
make isa-test                # 建置 custom Spike + 指令／tail／非法指令測試
make all                     # 所有 workload、microbenchmark ELF 與反組譯
make benchmark               # Spike 精確 PC histogram + minstret ROI
python3 scripts/summarize.py # 自動產生結果總表
```

原版 `spike` 執行純軟體組態；修改版路徑是 `tools/spike-xq/bin/spike`：

```bash
tools/spike-xq/bin/spike --isa=RV64IMC -g build/X2.elf > results/X2.stdout 2> results/X2.histogram
python3 scripts/profile.py --variant X2
```

GCC 15.2.0、Spike v1.1.0 commit `530af85d83781a3dae31a4ace84a573ec255fefa`。編譯使用 `-O2 -march=rv64imc_zicsr -mabi=lp64`，Zicsr 只用於 M-mode counters/control；不啟用 F/D/V。ELF entry=0x80000000，HTIF 列印／結束；不使用 Linux、pk、malloc 或浮點 runtime。

## 模型內容

上游 [LiteRT MobileNet-v3-large](https://huggingface.co/litert-community/MobileNet-v3-large)，固定 revision `9a4fd87358f71befb4de2f5ecdce1a159486b1f2`，卷積／FC 權重共 **5,451,272** 個元素，約 **216.59M MAC/inference**。來源與 hash 見 [manifest](models/manifest.json)，結構見 [MODEL.md](docs/MODEL.md)。

本次執行原圖 ops 14–17：

```text
56×56×24 INT8
 → 1×1 Conv (24→72) + ReLU
 → 3×3 depthwise Conv + ReLU
 → 1×1 Conv (72→24)
 → residual ADD（加回 block input）
 → 56×56×24 INT8
```

另含實際模型 FC（960→1280）及 128 MAC microbenchmark。block+FC 共 14,098,944 MAC，權重／activation INT8，bias／accumulator INT32，fixed-point multiply INT64，所有 buffer 靜態配置。

原圖輸入端含浮點算子，Python host 先擷取真實中間 activation，RISC-V 僅執行上述整數範圍；**尚非完整模型 bare-metal inference**。使用固定 seed=2026 隨機輸入驗證數值，未測 ImageNet accuracy。

## 已實作的兩條指令

- **Xqmac8**：兩個 packed 64-bit operands，各 8 個 signed INT8 lane，讀寫 rd 的 INT32 accumulator；32-bit modular overflow，結果 sign-extend。
- **Xrequant8**：讀 INT32 accumulator 與 64-bit per-channel descriptor，合併 Q31 multiply、double rounding、right shift、zero-point、clamp。非法 descriptor 觸發 illegal instruction。

[ISA 規格與分析](docs/ISA_PROPOSAL.md) 說明 encoding、alias/x0、rounding、限制與增量實驗；[isa/README.md](isa/README.md) 說明 upstream patch 與可重建 source。選擇 custom simulator binary 才會執行新指令；GNU objdump 顯示 `.4byte`，profiling script 會直接解碼 instruction bits。

## 實測結果

所有版本都對相同 reference 逐元素驗證；詳見 [SUMMARY.md](results/SUMMARY.md)。

| 組態 | 行為 | block+FC retired instructions |
|---|---|---:|
| B0 | 原始 baseline | 172,766,758 |
| B1 | scalar unroll | 148,375,111 |
| S | folded bias、scalar unroll、inline requant | 132,932,061 |
| P | packed load + scalar unpack/MAC 控制組 | 198,993,870 |
| X1 | P + Xqmac8 | 92,779,463 |
| XR | P + Xrequant8 消融組 | 178,543,138 |
| X2 | P + 兩條自訂指令 | **72,303,636** |

X2 相對 B0 約 **2.389× 指令數縮減（減少 58.15%）**；相對最快純軟體 S 約 **1.839×**。Expand/project/FC 相對最快純軟體各約 **3.01×／2.95×／2.93×**，達成題目 major GEMM/FC ≥2× dynamic instruction reduction 目標。這些都不是 cycle speedup 或完整模型加速比。

P 的 unpack 指令成本使它比 S 慢，因此報告同時提供 S 比較；不能只用較慢的 P 宣稱效益。X2 執行 1,508,352 次 Xqmac8、528,128 次 Xrequant8。最佳化後 depthwise 占約 54.4% ROI，是下一個主要瓶頸。

預期 seed=2026 所有層為 `mismatches=0`；checksum：expand=2998823028、depthwise=4184350541、project=1727378119、residual=612828347、fc=1427406882。工具版本／輸入改變時指令數可能改變。

ROI 為算子前後 minstret 差值，含少量呼叫／取樣；kernel histogram 排除驗證／列印；whole-program 包含全部開銷。資料範圍不可混用。沒有測 cache misses、bandwidth、CPI、Fmax 或 PPA。

## 驗證與繳交狀態

指令測試有 10,216 組 MAC、10,576 組 requant vectors，共 155,800 項斷言；另有 19,008 項 kernel tail／alignment 比對。涵蓋 alias、x0、wrap、sign extension、負數 rounding、非法 descriptor、原版 Spike 拒絕 custom、RV32 拒絕 RV64-only 指令。詳細證據見 [VERIFICATION.md](results/VERIFICATION.md)。

| 期中繳交項目 | 狀態／位置 |
|---|---|
| C/C++ bare-metal workload | 完成目前 block/FC 範圍：src/ |
| Quantized model / Python conversion | scripts/export_model.py、models/manifest.json、固定模型下載 |
| Spike/custom ISA source | 完成：isa/spike/、isa/spike.patch、scripts/build_spike_custom.sh |
| Added-instruction verification tests | 完成：tests/isa_test.c、isa_alias.S、gen_isa_vectors.py 等 |
| Reproducible workload benchmarks | 完成目前 block+FC 範圍：scripts/run_all.sh／benchmark.sh／profile.py |
| 5–6 分鐘 slides | 尚未製作 |
| GitHub README / expected measurements | 本文件與 results/ |

`tools/`、`build/`、模型二進位與 verbose build logs 不納入 Git。新指令源碼與 patch 都有追蹤；第三方原始碼由固定 hash 的 upstream tarball 重建。上游模型／Spike 依原始授權；AI 協作見 [AI_USAGE.md](AI_USAGE.md)。
