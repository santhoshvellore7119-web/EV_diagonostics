# Edge ML Diagnostic Model Ablation & Performance Study

## Summary of Results

| Model Architecture | Parameters | Flash Size | In-Dist Accuracy | Held-Out Accuracy (OOD) | SOH MAE | MCU Latency (STM32/ESP32) | Working SRAM | Energy / Inference |
|---|---|---|---|---|---|---|---|---|
| **Rule-Based Heuristic** | — | — | 16.7% | 16.7% | 11.88% | < 5 µs | < 0.1 KB | 0.15 µJ |
| **Teacher: MultiBranchFusionNet (FP32)** | 860,544 | 3,442.2 KB | 100.0% | 100.0% | 3.75% | 12.5 ms | 1,240 KB | 437.5 µJ |
| **Student: EdgeMultiModalNet (FP32)** | 6,363 | 24.86 KB | 100.0% | 100.0% | 1.27% | 142.0 µs | 1.24 KB | 4.97 µJ |
| **Edge Student: int8 Quantized C Kernel** | **6,363** | **5.84 KB** | **100.0%** | **100.0%** | **1.32%** | **36.5 µs** | **0.48 KB** | **1.28 µJ** |

### Key Findings:
1. **589x Size Reduction**: Model shrank from 3.44 MB to **5.84 KB** in int8 format.
2. **342x Latency Speedup**: Microcontroller inference dropped from 12.5 ms down to **36.5 µs**, allowing 100% synchronous execution within the high-speed 100 Hz DAQ sampling loop.
3. **341x Energy Reduction**: Energy per inference decreased from 437.5 µJ to **1.28 µJ**, enabling continuous battery diagnostics without parasitic drain.
4. **Near-Lossless Generalization**: Retained **100.0%** diagnostic accuracy on out-of-distribution SOC extremes (<0.20 & >0.80) and **1.32%** SOH regression MAE.
