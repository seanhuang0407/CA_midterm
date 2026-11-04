# CA Midterm：MobileNetV3 整數 workload 與 Spike profiling

已完成工作 1、2 的 **dominant kernels + complete CNN block** 路線；工作 3 提供 ISA 設計提案，尚未加入 custom instructions。依期中要求不評估 PPA/CV-Wally，不將 Spike 指令數宣稱為 cycles。

## 如何執行

目前環境的工具已安裝於專案內：

```bash
cd /home/sean/CA_midterm
source scripts/env.sh
bash scripts/run_all.sh
```

此流程重新匯出模型、執行 C/Python 正確性測試、編譯 bare-metal ELF、用 Spike 執行 B0/B1/microbenchmark，最後產生 `results/SUMMARY.md` 與 JSON。成功時各層顯示 `mismatches=0`，三個 Spike 測試均為 `PASS`。

新環境需有 bash、curl、tar、sha256sum、dpkg-deb、make、GCC/G++ 與 Python 3.8，先執行：

```bash
bash scripts/setup.sh
source scripts/env.sh
bash scripts/run_all.sh
```

支援條件：Ubuntu 20.04 x86_64／Python 3.8.2；其他平台未驗證。setup 下載固定版本並核對 GCC/Spike/model/DEB 的 SHA256，僅安裝到 tools/，不需 sudo。GCC 下載約 414 MB；不要將 tools/ 放入 GitHub。

可分步執行：

```bash
source scripts/env.sh
make export                  # 原模型 → C 靜態資料與 Python/reference 驗證
make test                    # C B0/B1 + 10,144 組 qmul 邊界/隨機案例與分類器測試
make all                     # B0.elf、B1.elf、micro.elf 與反組譯/symbols
make benchmark               # Spike 量測與解析
python3 scripts/summarize.py # 更新 Markdown 總表
```

單獨量測 B0：

```bash
spike --isa=RV64IMC -g build/B0.elf > results/B0.stdout 2> results/B0.histogram
python3 scripts/profile.py --variant B0
```

使用 GCC 15.2.0、Spike v1.1.0（commit `530af85d83781a3dae31a4ace84a573ec255fefa`）。Spike 只編譯 IMC + privileged handlers。編譯旗標 `-O2 -march=rv64imc_zicsr -mabi=lp64`，Zicsr 用於 M-mode minstret；不啟用 F/D/V。ELF entry 為 0x80000000，startup 設定 stack/gp、清空 BSS，HTIF 負責列印與結束。不使用 Linux、pk、malloc 或浮點 runtime。

## 模型內容與實作範圍

上游 [LiteRT MobileNet-v3-large](https://huggingface.co/litert-community/MobileNet-v3-large)，revision `9a4fd87358f71befb4de2f5ecdce1a159486b1f2`；輸入 [1,3,224,224]、輸出 1000 類。卷積與 FC 權重共 **5,451,272** 個元素（不含 bias），約 **216.59M MAC/inference**，符合題目規模。詳見 [模型說明](docs/MODEL.md) 與 [manifest](models/manifest.json)。

本次移植原圖 ops 14–17 的完整整數 residual block：

```text
56×56×24 INT8
  → 1×1 expand Conv (24→72) + ReLU
  → 3×3 depthwise Conv + ReLU
  → 1×1 project Conv (72→24)
  → residual ADD（加回 block input）
  → 56×56×24 INT8
```

另測原模型第一個 FC（960→1280）與 128 MAC microbenchmark。權重與 activation INT8、bias/accumulator INT32、fixed-point multiply INT64；runtime buffer 靜態配置，量化 scales 由 Python 離線轉成整數 multiplier/shift。

原模型輸入端含浮點算子，因此**沒有完成整個模型的 bare-metal inference**。Python host 執行原圖並擷取真實中間 activation；RISC-V ELF 只跑上述整數範圍。使用 seed=2026 的隨機 INT8 輸入與真實 pretrained 權重驗證數值正確性，未測分類準確率。完整 block 為 12,870,144 MAC；block+FC 為 14,098,944 MAC。

## 實測結果與預期輸出

詳見 [結果總表](results/SUMMARY.md)、[B0 輸出](results/B0.stdout)、[B1 輸出](results/B1.stdout) 及各自 JSON/histogram。

| 算子 | B0 retired instructions | B1 retired instructions |
|---|---:|---:|
| Expand | 56,896,642 | 46,754,827 |
| Depthwise | 49,213,055 | 49,213,055 |
| Project | 47,981,278 | 36,484,711 |
| Residual ADD | 8,767,869 | 8,767,869 |
| FC | 9,907,914 | 7,154,649 |
| **ROI 合計** | **172,766,758** | **148,375,111** |

B0/B1 均為 -O2，B1 對 pointwise/FC 做四路 scalar loop unrolling 與四個 accumulator。總指令減少 **14.12%**，指令數比 **1.1644×**，不是 cycle speedup 或完整模型加速比。目前尚未達到 ≥2× 指令減少門檻。

所有層應顯示 `mismatches=0`；seed=2026 的 checksum：expand=2998823028、depthwise=4184350541、project=1727378119、residual=612828347、fc=1427406882。不同輸入／工具版本可能改變動態指令數。

ROI 是算子前後 minstret 差值，包含少量呼叫／取樣開銷。Kernel histogram 僅計 pointwise、depthwise、residual、requant、qmul 函式內指令，排除驗證與列印；whole-program 包含全部測試開銷。三種範圍不可混用。Spike 不提供這個 workload 的 cache miss、stall、CPI 或 CV-Wally cycles。

## 瓶頸與第 3 項提案

- Scalar MAC：14,098,944 MAC 仍逐項 multiply/add，另有 zero-point／迴圈操作。
- Load/store 與迴圈：B0 kernel 約 36.85M memory instructions，約 2.6134 memory instructions/MAC；展開沒有減少 byte loads。
- Requantization：qmul+requant 約 29.89M 指令，含目前 noinline 呼叫／stack 開銷；必須補 inline 軟體比較後再解讀 ISA 效益。

[ISA_PROPOSAL.md](docs/ISA_PROPOSAL.md) 已提出 `Xqmac8`（8 組 signed INT8 MAC）與 `Xrequant8`（per-channel 整數 rescaling/clamp）的 encoding、rounding、overflow、zero-point folding 與驗證計畫。優先加速 pointwise/FC；depthwise 的 gather／邊界處理獨立量測。custom 指令尚未實作，不能報告其加速比。

## 檔案與期中繳交狀態

| 繳交項目 | 狀態／檔案 |
|---|---|
| C/C++ bare-metal workload | 完成目前 block/FC 範圍：src/kernels.c、start.S、link.ld、platform.c |
| Quantized model / Python conversion | scripts/export_model.py、models/manifest.json；setup 下載固定模型 |
| Spike/custom ISA source | 上游 Spike 建置完成；新增指令尚未實作，本次提供設計提案 |
| Added-instruction tests | 待實作指令後完成；目前 tests/ 為 baseline/量化驗證 |
| Reproducible workload benchmark | scripts/run_all.sh、benchmark.sh、profile.py；範圍為完整 block+FC |
| 5–6 分鐘 slides | 尚未製作 |
| GitHub README / expected measurements | 本文件與 results/；遠端 repository 上傳狀態以 GitHub 為準 |

`tools/`、`build/`、模型二進位由 .gitignore 排除。GitHub 可提交原始碼、文件、manifest、結果，以 setup 重建模型與工具。上游權重遵守原始授權。AI 協作紀錄見 [AI_USAGE.md](AI_USAGE.md)。
