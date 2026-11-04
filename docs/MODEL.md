# 模型與工作範圍

選擇 [LiteRT community MobileNet-v3-large](https://huggingface.co/litert-community/MobileNet-v3-large)，固定 revision `9a4fd87358f71befb4de2f5ecdce1a159486b1f2` 的 `mobilenet_v3_large_int8_channelwise.tflite`。SHA256、來源與所選層的 zero-point 紀錄於 ../models/manifest.json；完整所選層 multiplier/shift 由 export script 寫入 build/model_data.h。

這是影像分類 CNN：輸入 [1,3,224,224]，輸出 [1,1000]。從 FlatBuffer 計數，卷積與 FC 權重共有 5,451,272 個元素（不含 bias），理論 dense MAC 為 216,589,760／inference，符合題目規模。網路包含 47 Conv2D、15 depthwise Conv2D、2 FC、21 HardSwish，另有 ADD、MUL、pooling 等；模型中的 batch normalization 相關效果已融合至權重／bias，所選 block 不需要另外執行 normalization。

檔案的邊界圖含 DEQUANTIZE，以及 FP32 的初始卷積與 activation，因此「檔名 INT8」不代表整圖只有整數。**本專案不宣稱完整模型 bare-metal 推論或 ImageNet accuracy**。Python 在 host 使用 LiteRT 執行原圖並擷取真實中間 tensor，RISC-V 僅執行下面的完整整數 block 與一個 FC。輸入是固定 seed 的隨機 INT8 tensor，用於確定性 correctness／profiling，並非自然影像準確率測試。

| 步驟 | 原圖 op | 輸入 → 輸出 | 權重配置 | MAC |
|---|---:|---|---|---:|
| Expand 1×1 Conv + ReLU | 14 | 56×56×24 → 56×56×72 | [72,1,1,24] | 5,419,008 |
| Depthwise 3×3 + ReLU | 15 | 56×56×72 → 同尺寸 | [1,3,3,72]，SAME padding | 2,032,128 |
| Project 1×1 Conv | 16 | 56×56×72 → 56×56×24 | [24,1,1,72] | 5,419,008 |
| Residual ADD | 17 | Project + block input → 56×56×24 | 三次整數 rescaling／元素 | 0 |
| 第一個 FC | 另一獨立算子 | 960 → 1280 | [1280,960] | 1,228,800 |

完整 block 為 12,870,144 MAC，block+FC 為 14,098,944 MAC。MAC 是數學工作量，包含 depthwise padding 位置的零乘法；不包含 requantization 乘法。

權重與 activation 均 INT8，bias／accumulator 為 INT32，requant multiply 使用 INT64。權重 per-channel symmetric（zero-point=0），activation 為 asymmetric，例如 block input zero-point=11；因此乘法前不能忽略輸入 zero-point。浮點 scales 只在 Python export 時轉成 Q31 multiplier 和 shift，C/RISC-V 不計算 float。

`export_model.py` 使用 NumPy INT64 的獨立整數 reference，再逐元素比對 LiteRT BUILTIN_REF kernel。中間 tensor 可能被 runtime buffer alias 覆寫，因此對需要保護的 tensor 另標為 graph output 執行，確保比對的是該層真正輸出。所有選定層須為 0 mismatches；C 的 B0/B1 再與匯出 reference 比對。

所選 block activation 只有 ReLU，可由 requant clamp 實現。全模型其他區塊的 HardSwish、SE pooling/multiply，以及一般 spatial Conv2D 的完整移植，尚未完成；目前完成的是題目允許的 dominant kernels／complete CNN block 路線。

Prepared S/P/X1/XR/X2 共用離線 bias folding 與每 channel 64-bit requant descriptor。
所選層的 shift 必須在 [-31,0]，export 時明確檢查。輸入／權重與中間 buffer
以 8-byte 對齊，通用 kernel 另有未對齊 packing 與 scalar tail。原始 B0/B1
的計算方式與預期指令數保留，便於追溯軟體與 ISA 各自的改善。
