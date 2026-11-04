# 驗證紀錄

- `scripts/run_all.sh` 完整執行成功：LiteRT reference／NumPy integer reference／C B0／C B1／Spike B0/B1/micro 全部 PASS。
- 模型 seed=2026：所有輸出逐元素相同，manifest 內 LiteRT mismatches 均為零。
- 額外 seed=17：重新匯出模型及 host B0/B1 全部 PASS；詳見 seed17-tests.txt。最後已還原 seed=2026。
- qmul：144 組 directed 與 10,000 組 randomized C/Python 交叉比對通過；指令分類器測試通過。詳見 host-tests.txt。
- GCC AddressSanitizer + UndefinedBehaviorSanitizer 執行 B1 成功，詳見 sanitizer.txt。環境受 ptrace 影響，LeakSanitizer 關閉（ASAN_OPTIONS=detect_leaks=0）；此 workload 不做動態配置。
- `bash -n scripts/*.sh` 通過；setup.sh 在已具快取環境的 hash 驗證、套件檢查與 export 流程成功，詳見 setup-validation.txt。未做刪除全部快取後的獨立 clean-room 安裝。
- 最後檢查固定 seed、零 mismatches、ROI 指令數及各測試 PASS 與 README 一致。

未執行：custom ISA tests（指令尚未實作）、完整模型 bare-metal inference、資料集分類 accuracy、CV-Wally／PPA。
