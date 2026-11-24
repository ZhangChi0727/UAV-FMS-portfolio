# 日志编号：2026-11-24 / edge_inference / 边缘AI核心工程考量与标准化性能评估框架

## 1. 目标
系统梳理边缘 AI 与云端 AI 的本质边界、研究前沿及模型压缩工程考量，并确立一套**可跨模型版本反复复用的标准化性能评估协议（Evaluation Protocol）**，确保后续 `FP32` 基线、通道剪枝、静态 `INT8` PTQ 及未来更深层压缩模型均在同一基准标尺下公平对比。

## 2. 核心原理与工程考量拆解

### 2.1 边缘 AI vs. 云端 AI 的本质差异
- **物理资源硬约束**：算力（TOPS/GFLOPs）、内存/显存上限、机载电池功耗与被动散热限制，额外载荷与功耗直接压缩无人机续航。
- **确定性实时性要求**：云端追求高吞吐（Throughput）与均值响应；无人机巡检与闭环感知追求单帧低延迟与**尾延迟稳定性（P95/P99）**，并消除无线通信抖动与断连风险。
- **软硬件异构强耦合**：模型实际推理速度高度依赖硬件架构（GPU / ARM CPU / NPU）及推理引擎的算子融合与内存对齐策略，理论 FLOPs 下降并不自动等价于端到端加速。

### 2.2 研究前沿脉络（2025–2026）
1. **紧凑型端侧多模态/小模型（SLM / Edge-VLM）与端边云协同卸载**。
2. **硬件感知的模型压缩与编译优化（Hardware-Aware Compression & Compilation）**。
3. **动态与自适应推理（Dynamic / Adaptive Inference）**：按帧复杂度或剩余电量动态调整计算分支（Early-Exit / 动态采样）。
4. **具身智能与无人机闭环的感知-控制协同与实时资源调度（RTOS / 线程抢占隔离）**。

### 2.3 裁剪、量化与部署的关键工程陷阱
- **裁剪（Pruning）**：优先采用**结构化通道/滤波器剪枝**（直接缩小张量维度），避免非结构化稀疏在通用硬件上无加速反增开销；剪枝后需配合短周期微调恢复特征提取能力，并注意检测头与残差连接处的通道维度对齐。
- **量化（Quantization）**：`INT8` PTQ 依赖代表性校准集统计激活值动态范围；针对桥梁细微裂缝等低对比度小目标，量化误差易导致召回率骤降，必要时需保留输入/输出敏感层为 `FP16/FP32`（混合精度）。
- **部署（Deployment）**：严禁只测网络前向传播（Forward）；必须测量包含**图像缩放归一化（Preprocess）→ 神经网络推理（Inference）→ NMS 后处理（Postprocess）**的完整端到端链路。

---

## 3. 标准化边缘 AI 性能评估协议（后续所有实验统一执行）

后续每一轮模型变体（如 `YOLOv8n-FP32`、`YOLOv8n-Pruned`、`YOLOv8n-INT8`、`YOLOv8n-Pruned-INT8`）均须严格按以下 **4 个维度、12 项核心指标**输出 JSON 结果并生成对照表：

| 评估维度 | 具体指标 | 单位 / 统计口径 | 工程意义与分析重点 |
| :--- | :--- | :--- | :--- |
| **1. 任务精度**<br>(Task Accuracy) | `mAP@50`, `mAP@50:95`<br>`Precision`, `Recall`<br>分缺陷类别 `AP / Recall` | `%`（在统一验证/测试集上评测） | 重点监控细长低对比度目标（如 `crack`）在剪枝与 INT8 量化后的 Recall 退化幅度 |
| **2. 分阶段时延**<br>(Stage Latency) | `preprocess_ms`<br>`inference_ms`<br>`postprocess_ms`<br>`total_ms`（Mean / **P95** / **P99**）<br>有效吞吐 `FPS` | `ms` / `Hz`（固定预热 `20` 次 + 正式采样 `100` 次） | 识别系统瓶颈（推理受限 vs. 预处理/NMS 受限）；用 P95/P99 衡量实时系统尾延迟抖动 |
| **3. 资源占用**<br>(Resource Footprint) | 模型磁盘体积（Serialized Size）<br>参数量（Params） & 计算量（GFLOPs）<br>运行期**峰值 RSS 内存** | `MB` / `M` / `GFLOPs` | 验证压缩率与内存驻留开销；检查多轮连续推理是否存在内存持续增长 |
| **4. 权衡与定性分析**<br>(Trade-off & Failure) | **精度–延迟 / 精度–体积帕累托曲线**<br>典型失败案例视觉对比图（FP32 vs. 压缩后） | 图表 + 典型帧标注对比 | 量化“每降低 1 ms 延迟付出的 mAP 代价”；定位压缩模型失效的物理成因（阴影、细裂纹、背景纹理） |

### 双配置测速基准环境规范
- **Profile A（开发机 GPU 参考基准）**：Windows + NVIDIA RTX 4060 (8GB)，ONNX Runtime `CUDAExecutionProvider`，记录桌面级 GPU 算力上限。
- **Profile B（受限机载算力模拟基准）**：同机限制 ONNX Runtime `CPUExecutionProvider` 线程数（`intra_op_num_threads=4`），模拟资源受限机载计算单元（须在报告中明确标注为“线程受限 CPU 模拟”，不冒充真实 Jetson ARM 实测）。

---

## 4. 问题与思考
- **方法论沉淀**：将上述评估表固化进 `edge_inference/src/benchmark.py` 的输出 Schema 后，未来新增任何模型（如 YOLO11n、QAT 量化版或蒸馏模型）都无需修改评估逻辑，只需传入 `.onnx` 路径即可自动生成可横向对比的 JSON 与帕累托图表。
- **下一步计划**：待 `CODEBRIM_original_images.zip` 下载解压完毕，立即执行 Day 1 任务：完成 XML → YOLO 格式转换，训练并导出 `yolov8n_bridge_fp32.onnx`，跑通 Profile A 与 Profile B 的首版基线数据。

## 5. 可复用资产
- **笔记路径**：`edge_inference/logs/2026-11-24_concept_edge_ai_evaluation_framework.md`
- **可直接用于 Technical Note 的评估方法学描述**：
  > "To ensure rigorous, apples-to-apples comparisons across compression stages, all model variants are evaluated under a unified four-dimensional profiling protocol tracking task accuracy (overall and per-class mAP/Recall), end-to-end stage latency (mean, P95, and P99 across preprocessing, inference, and NMS), resource footprint (serialized size and peak RSS memory), and Pareto efficiency under both GPU and thread-constrained CPU execution profiles."