# 日志编号：2026-11-24 / edge_inference / 桥梁巡检数据集版本解析与边缘AI任务格式对照

## 1. 目标
厘清公开数据集 CODEBRIM（CVPR 2019）多个压缩包版本的区别，明确无人机边缘 AI 桥梁巡检项目中不同感知任务与数据集标注格式的对应关系，为 Day 1 基线模型选型与数据管线搭建提供依据。

## 2. 核心概念与技术拆解

### 2.1 CODEBRIM 数据集四版本演进逻辑
CODEBRIM 原始论文聚焦于混凝土桥梁缺陷的**多目标分类（Multi-target Classification）**，其 Zenodo 仓库提供的 4 个压缩包对应数据预处理的 4 个递进阶段：
- **`CODEBRIM_original_images.zip` (8.3 GB) [本项目选用]**：原始高分辨率全图 + Pascal VOC 风格 XML 边界框标注。保留了缺陷空间坐标，是训练端到端目标检测器（YOLOv8n）的唯一必要数据源。
- **`CODEBRIM_cropped_dataset.zip` (7.9 GB)**：按 BBox 裁剪出的局部缺陷图块 + 多标签类别。丢弃了空间坐标，仅适用于图像分类任务。
- **`CODEBRIM_classification_dataset.zip` (7.9 GB)**：对裁剪图块按原始图像维度划分好 `train/val/test`，防止同一桥梁图像切片跨集合造成数据泄露。
- **`CODEBRIM_classification_balanced_dataset.zip` (12.2 GB)**：通过物理复制稀有类别训练集图块强制平衡样本分布，仅用于严格复现原论文的元学习分类实验。

### 2.2 边缘 AI 感知任务与数据格式映射
1. **图像分类（Classification）**：文件夹分类 / CSV 标签；无空间定位与 NMS 环节，无法直接满足无人机全画面实时巡检。
2. **目标检测（Object Detection，当前主线）**：XML / COCO JSON / YOLO TXT；输出 `(bbox, class, conf)`，完整包含 `Preprocess → Inference → NMS` 端到端延迟链路，适合作为模型剪枝与 INT8 量化的核心基准。
3. **语义/实例分割（Segmentation，后续扩展）**：Mask PNG / Polygon TXT；可支撑土木工程中的裂缝宽度与面积量化，但掩码分支计算开销高、量化敏感度更高。
4. **视觉惯性 SLAM（按需扩展）**：时间戳对齐的图像 + IMU CSV / ROS Bag（如 EuRoC 格式）；服务于桥下 GPS 拒止环境的自主定位与 3D 缺陷建图。

## 3. 决策对照表

| 维度         | 最终选定方案                      | 选型理由                                                     |
| :----------- | :-------------------------------- | :----------------------------------------------------------- |
| 数据集与版本 | `CODEBRIM_original_images.zip`    | 具备 CVPR 2019 与欧盟 AEROBI 无人机桥梁巡检项目学术背书；保留完整 BBox 坐标 |
| 核心任务类型 | Object Detection（目标检测）      | 契合机载摄像头全帧实时推理场景，可完整评估端到端延迟与压缩帕累托边界 |
| 目标格式转换 | XML → 标准 YOLO TXT（8:1:1 划分） | 适配 Ultralytics YOLOv8n 训练与 ONNX 导出流水线，按原图维度划分避免数据泄露 |

## 4. 问题与思考
- **工程启示**：真实无人机边缘部署面对的是高分辨率、大背景、小目标的原始航拍帧，而非预先裁好的缺陷切片。因此模型压缩评估必须基于端到端检测流水线（包含图像缩放预处理和 NMS 后处理），而非仅测分类网络的前向推理耗时。
- **多标签框（Multi-target BBox）处理待定项**：CODEBRIM 的单个 XML 边界框可能同时标注多种共现缺陷（如剥落伴随露筋），在转为标准 YOLO 单标签检测框时，需要明确转换策略（如将多标签框拆分为同坐标多行 YOLO 标注，或聚焦主缺陷类）。
- **下一步计划**：待 `CODEBRIM_original_images.zip` 解压至 `edge_inference/data/codebrim_raw/` 后，编写确定性划分脚本（固定随机种子，按图像级 8:1:1 划分）将其转为标准 YOLO 格式并启动 Day 1 基线训练。

## 5. 可复用资产
- **笔记路径**：`edge_inference/logs/2026-11-24_concept_dataset_tasks_formats.md`
- **可直接用于 Technical Note / PPT 的表述句**：
  > "Rather than evaluating isolated patch classifiers on pre-cropped defects, we formulate onboard UAV bridge inspection as an end-to-end object detection task using the full-resolution CODEBRIM benchmark (Mundt et al., CVPR 2019), capturing full pipeline latency across preprocessing, neural inference, and NMS post-processing."