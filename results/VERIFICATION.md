# 驗證紀錄

## 可重現命令

```bash
source scripts/env.sh
bash scripts/run_all.sh
```

本次完整流程通過，詳細輸出保留於 run-all.log、host-tests.txt、isa-tests.log、各 variant 的 stdout/histogram/JSON。

## 新增指令與 kernel tests

- Xqmac8：216 組 directed + 10,000 組 randomized vectors。
- Xrequant8：576 組 directed + 10,000 組 randomized vectors。
- Python oracle 使用任意精度整數，獨立於 Spike/C 實作；預期結果包含完整 64-bit sign extension。
- Bare-metal 指令測試共 **155,800 項斷言**，包含 lane/signed arithmetic、INT32 overflow、high-bit 忽略、來源/目的 alias、x0、rounding、clamp。
- 13 次預期 illegal instruction traps，檢查 mcause／mtval，以及目的暫存器未被修改。6 種非法 descriptor 各測一般 rd 和 rd=x0，另測 reserved encoding。
- **19,008 項 kernel 比對**：K=0..65、offset=0..7、4 種 activation zero-points、tail、未對齊 rows/weights。
- 原版 Spike 確認拒絕兩條 custom 指令；修改版 Spike 的 RV32 執行也確認拒絕這兩條 RV64-only 指令。
- custom-trace-sample.txt 保留 micro-X2 執行的 16 條 Xqmac8 與 1 條 Xrequant8 trace。

## 模型與效能回歸

- seed=2026：LiteRT BUILTIN_REF 與 NumPy 整數 reference 所選層全部 0 mismatches。
- B0/B1/S/P/X1/XR/X2 在 Spike 執行完整 residual block+FC，全部逐元素相同，checksum 與 README 一致。
- micro、micro-S/P/X1/XR/X2 全部 PASS。
- seed=17 額外執行 S 與 X2（seed17-S.stdout、seed17-X2.stdout），全部 0 mismatches；最後已還原 seed=2026。
- 原始 B0/B1 ROI 仍為 172,766,758／148,375,111；X2 為 72,303,636。
- Profiling script 檢查 histogram 指令數守恆、純軟體組態無 custom、custom MAC 次數為 1,508,352、custom requant 次數為 528,128；micro 則為 16／1。

## Host 與建置

- 原 qmul：144 組 directed + 10,000 組 randomized C/Python 比對通過。
- Prepared scalar descriptor：另 10,000 組 Python 任意精度／C 比對通過；instruction classifier tests 通過。
- 最終 packed software prepared path 的 AddressSanitizer + UndefinedBehaviorSanitizer 通過，見 sanitizer-prepared.txt。LeakSanitizer 因環境 ptrace 限制關閉（ASAN_OPTIONS=detect_leaks=0）；本 workload 不做動態配置。硬體 opcode 由 Spike 測試，不在 host emulation 假造結果。
- scripts/*.sh 的 bash 語法檢查通過。Custom Spike 由固定 hash 的原始 tarball、tracked patch 與 instruction headers 建置；原版 Spike 保留。
- setup-validation.txt 為先前 baseline setup 的快取驗證紀錄，不代表本次重新做所有依賴的 clean-room 安裝。

未測完整模型 bare-metal inference、分類 accuracy、CV-Wally、PPA 或 cycles。性能結論以 SUMMARY.md 所列 ISA-level retired instruction 數為限。
