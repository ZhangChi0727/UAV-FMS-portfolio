# B0 G0 场景与验收矩阵

**状态：提议中，等待维护者批准；本矩阵不是性能结论。**

本矩阵的机器权威来源是
[`b0_g0_contract.v1.json`](../../05_integration/b0/configs/b0_g0_contract.v1.json)。
每个 JSON Pointer 中的数值、种子、事件窗口和通过值都只是
`proposed_pending_maintainer_approval` / `proposed_not_executed` 候选。
本文件不能被用于宣称 SIL、HIL、实机或需求符合性已经完成。

## 结果分类

未来 G3/G4 必须在记录中区分下列结果，不能把工具错误、限制刻画或无效输入测试
归入性能通过：

| 分类 | 含义 |
|---|---|
| `performance_pass` | 已批准的包线内场景，独立指标满足所有适用准则 |
| `performance_fail` | 已批准的包线内场景，独立指标违反至少一项准则 |
| `limitation_characterized` | 包线外或已知限制场景按预定方式记录，不等同于性能通过 |
| `invalid_input_rejected` | 非法输入按合同拒绝或 reset，不是动态性能证据 |
| `execution_error_inconclusive` | 构建、运行、数据或指标错误；必须保留原因且不得计为通过 |

结果分类的权威字段为
`/acceptance_policy/outcome_classes`。

## 指标口径

| 指标族 | 合同定义 | 配置字段 |
|---|---|---|
| 四元数姿态误差 | 使用 `q` 与 `-q` 等价的夹角公式，避免符号翻转伪误差 | `/acceptance_policy/attitude_error` |
| 稳定时间 | 从命令或扰动事件结束起，进入稳定带并连续保持驻留时间；G3 必须在独立指标器实现这一口径 | `/acceptance_policy/settling` |
| 超调 | 仅针对非零阶跃的首个有符号目标幅值；零指令不定义超调 | `/acceptance_policy/overshoot` |
| 角速度、积分、力矩和饱和 | 单位、窗口、reducer、运算符和界值均在具体 `acceptance` 项中声明 | `/scenarios/*/acceptance/*` |
| 偏航 | 仅评价给定初始参考下的相对跟踪/漂移；六轴 IMU 不提供持续绝对偏航观测 | `/estimator_contract/absolute_yaw_observation` |

G3 还必须明确记录用于计算的原始信号、指标器版本、配置 hash、Git revision、种子、
时间窗口和终止状态。指标器必须独立于被测估计器和控制器。

## 八类场景

| 场景 | 类别 | 配置入口 | 预定事件/覆盖点 | 候选准则与预期证据 | 未来负责阶段 |
|---|---|---|---|---|---|
| `stationary_zero_command` | 包线内性能 | `/scenarios/0` | 零指令、静止、四元数归一化 | 三项候选准则：姿态误差、角速度误差、四元数范数；`artifacts/b0/stationary_zero_command/` | G1、G2、G3 |
| `initial_attitude_offset` | 包线内性能 | `/scenarios/1` | 显式初始姿态偏差 | 稳定时间和峰值姿态误差；`artifacts/b0/initial_attitude_offset/` | G1、G2、G3 |
| `tri_axis_signed_steps` | 包线内性能 | `/scenarios/2` | x/y/z 每轴正、负阶跃 | 稳定时间、超调、交叉轴误差；`artifacts/b0/tri_axis_signed_steps/` | G2 控制器、G3 |
| `external_torque_disturbance` | 包线内性能 | `/scenarios/3` | 有界外部机体系力矩 | 峰值偏差、恢复时间、饱和时间；`artifacts/b0/external_torque_disturbance/` | G1、G2、G3 |
| `imu_noise_and_bias` | 包线内性能 | `/scenarios/4` | 可复现噪声和偏置 | 横滚/俯仰估计 RMS 与偏航漂移；`artifacts/b0/imu_noise_and_bias/` | G1、G2 估计器、G3 |
| `saturation_withdrawal` | 包线内性能 | `/scenarios/5` | 大阶跃、限幅后撤回 | 积分界、恢复时间、饱和持续时间；`artifacts/b0/saturation_withdrawal/` | G1、G2 控制器、G3 |
| `acceleration_contamination` | 限制刻画 | `/scenarios/6` | 非重力 specific-force 污染 | 记录限制事件和状态；不预设任意污染下恢复；`artifacts/b0/acceleration_contamination/` | G1、G2 估计器、G3 |
| `invalid_input_and_reset` | 无效输入 | `/scenarios/7` | 负 dt、陈旧 timestamp、reset | 拒绝计数和确定性 reset replay；`artifacts/b0/invalid_input_and_reset/` | G1、G2、G3 |

所有场景的 `artifact_path` 只是未来证据位置约定。本 PR 不创建生成输出、图表、CSV
或伪造的结果文件。

## CTL-REQ 适用性审查

现有需求 ID 和阈值必须原样保留，但不自动成为 B0 发布准则。

| 需求 | 原始阈值 | G0 适用性结论 | 原因与行动 |
|---|---|---|---|
| `CTL-REQ-001` | Attitude settling time — 10 degree step input，`< 0.8 s`，Test | **条件化适用，未批准、未执行** | B0 含三轴正/负的十度阶跃，但对象、命令定义、稳定带/驻留时间和指标器尚未实现或批准。B0 的候选工程准则见 `/scenarios/2/acceptance`，与旧阈值不同；在维护者裁决前不得报告符合 `CTL-REQ-001`。 |
| `CTL-REQ-002` | Attitude overshoot，`< 15%`，Test | **条件化适用，阈值冲突待裁决，未执行** | B0 候选超调准则位于 `/scenarios/2/acceptance`，并非旧阈值。若维护者保留旧需求，则必须在相同对象、命令、采样和 metric 定义下单独验证；若不保留，必须记录不适用理由并批准 B0 自身门槛。 |

这两个结论保留旧要求的文字和阈值，但不宣称任何符合性。G0 退出前需要维护者对每一项
选择“适用”“条件化适用”或“不适用”，并记录对应理由。

## 场景执行和独立验收规则

未来实现应遵守以下最小规则：

1. 从已批准的配置版本加载，不允许缺字段、未知字段、NaN/Inf、非法惯量或隐式默认；
2. 只使用配置的保留验收种子；调参种子与验收种子分离；
3. 估计器与控制器只能获取合同声明的估计/测量输入，不能读取对象 truth；
4. 执行时以 `/timing/sequence` 指定的顺序调度，并保留 request、limited target 和 actual torque；
5. 对每一项准则由独立指标器计算。算法运行错误或数据缺失只能为
   `execution_error_inconclusive`；
6. 若调整任一已批准参数或阈值，必须增加配置版本、说明理由并重跑受影响场景；
7. 不预设 Monte Carlo 次数或统计显著性。若以后引入随机试验，必须先说明试验目的、
   种子集合和分析方法。

## 待维护者集中批准的决定

| 决定 | 权威位置 | 未批准时的处理 |
|---|---|---|
| 有效旋转包线及排除的飞行能力 | `/operating_envelope` | 仅可称为合成候选，不能称为真实机型包线 |
| 稳定带、驻留时间、超调定义 | `/acceptance_policy` | 不得把任意运行时间计算为需求稳定时间/超调 |
| 八类场景的扰动、窗口、种子和阈值 | `/scenarios` | 只可运行用于开发诊断，不能宣称验收通过 |
| 执行器/IMU/增益候选 | `/actuator_contract`、`/imu_contract`、`/controller_contract` | 后续实现不得把候选写成已验证或最终参数 |
| CTL-REQ-001/002 的适用性 | 本节与 `07_docs/requirements.md` | 不得报告需求符合性 |

G0 的配置校验测试只证明这些候选能够被一致地加载、拒绝非法输入并满足跨字段合同；
它不证明八类场景的动态性能。
