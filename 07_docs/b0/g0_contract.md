# B0 G0 合同与接口设计

**状态：提议中，等待维护者集中批准；不得称为冻结。**
**范围：B0 v0.2 的合同、版本化配置、校验和验收设计；不实现 G1/G2/G3。**

本文件与 [G0 子工作单](../work_orders/B0_G0_work_order.md) 配套。机器可读配置
[`b0_g0_contract.v1.json`](../../05_integration/b0/configs/b0_g0_contract.v1.json) 是所有参数、
场景、种子和通过值的唯一权威来源；本文件仅引用 JSON Pointer，避免文档与配置漂移。
[`validate_config.py`](../../05_integration/b0/validate_config.py) 对结构、单位、物理约束、
事件、种子和跨字段语义作强制检查。

## G0 边界

G0 交付的是后续实现所必须遵守的合同，不是对象、传感器、估计器、PID、闭环或性能
结果。尤其是：

- 没有本阶段仿真结果、SIL、HIL、板端执行或飞行结论；
- 所有数值均是明确标注为 `synthetic_assumption` 的工程候选，等待维护者批准；
- 配置中的 `proposed_not_executed` 只表示将来的判据，不表示已经达到判据；
- 通过本 track 的配置测试，不能替代任何未来 G1/G2/G3 算法与闭环证据。

## 资产审计与处置

| 路径或资产 | 实际状态和已见证证据 | G0 决定 |
|---|---|---|
| `01_simulation/scenario_generator/generator.py`、`fault_injector.py` 及其测试 | 明示为 Phase 4A placeholder，面向遗留批量场景生成 | 仅作历史参考；不复用为 B0 对象或传感器 |
| `02_estimation/python/ekf.py`、`ukf.py` | EXT-NAV 路径，核心方法抛出 `NotImplementedError` | 不适配为 B0 姿态估计器 |
| `03_control/python/geometric_control.py`、`lqr_baseline.py` | Phase 3B 占位；相关测试以 `pytest.skip` 退出 | 不复用为 G2 控制器或完成证据 |
| `05_integration/integrated_sim.py`、`monte_carlo/`、`fault_scenarios/` | 集成 README 明确标注为保留兼容性的 legacy scaffold | G0 只建立隔离的 `05_integration/b0/` 配置校验 track |
| 根 `CMakeLists.txt` | 根目标为遗留 EXT-NAV EKF；另有 development-readiness probe | G0 采用独立 Python 配置校验入口，不把遗留导航构建当作 B0 证据 |
| `tools/development_readiness/` | 已有开发就绪报告记录工具链、绑定和调试探针 | 仅复用环境证据，不作为 B0 算法或验收证据 |

历史文献记录亦已审计：`literature/evidence_matrix.xlsx` 与
`literature/screening.csv` 可以作为发现与筛选历史，但当前没有可被本阶段核验的、
带原文定位符的数值参数提取。因此配置中没有把候选摘要、筛选记录或未抽取的全文
当成参数依据；将来若采用文献数值，必须先按 `literature/protocol.md` 记录原文
定位和适用边界。

## 参数来源与提议包线

| 合同域 | 配置权威字段 | 来源记录 | G0 状态 |
|---|---|---|---|
| 坐标、单位、四元数 | `/conventions` | `ARCH-COORD-001` | 继承 B0 基线 |
| 单一基础 tick 与多速率 | `/timing` | `SYNTH-TIME-001` | 待批准合成假设 |
| 刚体惯量和积分检查 | `/plant_contract` | `SYNTH-PLANT-001` | G1 输入，未实现 |
| 执行器滞后、限幅、抗饱和反馈 | `/actuator_contract` | `SYNTH-ACTUATOR-001` | G1/G2 输入，未实现 |
| IMU 采样、重力、噪声和偏置 | `/imu_contract` | `SYNTH-IMU-001` | G1 输入，未实现 |
| 姿态/角速度环增益范围及积分限制 | `/controller_contract` | `SYNTH-CONTROL-001` | G2 控制器输入，未实现 |
| 有效包线及排除项 | `/operating_envelope` | `SYNTH-SCENARIO-001` | 待批准；不是实机包线 |
| 指标定义、稳定带与驻留时间 | `/acceptance_policy` | `SYNTH-SCENARIO-001` | 待批准；未执行 |
| 场景、事件、种子、阈值 | `/scenarios` | `SYNTH-SCENARIO-001` | 待批准；未执行 |

配置校验器要求每一个 `source_ref` 都引用已声明记录；历史文献记录
`LIT-STATUS-001` 必须保持为“没有复用可定位数值参数”的审计状态。这样可阻止
无来源数字被静默加入候选包线。

## 坐标、状态和所有权

- 世界坐标系为 **NED**，机体系为 **FRD**，所有量使用 **SI**；
- 姿态为标量在前的 Hamilton 四元数 `q_nb`，旋转方向为机体系到 NED；
- 角速度为 `omega_b`，在机体系 FRD 中表示，单位为 `rad/s`；
- `q` 与 `-q` 物理等价。实现和指标使用配置的规范符号规则；半周情形按首个
  非零向量分量的正号作确定性 tie-break；
- 真实对象状态只能供对象、传感器和独立指标评估器使用，不能进入估计器或控制器。

## 接口账本

| 接口所有者（后续阶段） | 输入 | 输出 | 时间、有效性与 reset 合同 |
|---|---|---|---|
| G1 对象 | 实际机体系力矩 `actual_torque_body_Nm` | 真实 `q_nb`、`omega_b_rad_s` | 每个基础 tick 积分；惯量为 SPD；reset 后只从显式初值开始 |
| G1 执行器 | 请求力矩 `requested_torque_body_Nm` | 限幅目标与实际力矩 | 区分 request、limited target 和 actual；一阶有界响应；抗饱和反馈是 `actual - limited_target` |
| G1 IMU | 对象真值和采样调度 | 带 timestamp/validity 的 IMU 样本 | 在积分区间末采样；重力在 NED；specific force 采用配置公式 |
| G2 估计器 | IMU 样本 | 估计 `q_nb`、估计 `omega_b` | 每次传播/修正后归一化；非正 dt 或陈旧 timestamp 拒绝；reset 仅可显式初始化 |
| G2 控制器 | 指令和**估计**姿态/角速度 | 请求机体系力矩 | 不接收 truth；误差四元数、最短路径和半周规则见 `/controller_contract/attitude_error` |
| G3 调度与指标 | 已实现组件的明确 I/O | 原始记录和独立指标 | 按固定 tick 顺序执行；指标评估器可读 truth，但不能回馈估计器/控制器 |

接口字段的精确名称、帧和单位由配置给出；实现不得用隐式坐标变换、隐式单位换算或
缺省 timestamp 代替它们。

## 确定性时序

`/timing/sequence` 的顺序是每个基础 tick 的唯一合同：

1. 对象在本积分区间消费上一个 `actual_torque`；
2. 执行器向上一个 `limited_target` 推进；
3. 到期时，IMU 在区间末采样；
4. 到期时，估计器消费当前 IMU；
5. 到期时，控制器消费当前估计；
6. 控制器发布下一个 `limited_target`。

所有多速率周期必须是基础 tick 的正整数倍。场景时长、事件窗口和稳定驻留时间也必须
整除基础 tick，校验器不允许静默四舍五入。

## 异常、reset 与真值隔离

非正 `dt` 必须被拒绝；陈旧 timestamp 必须被拒绝并保持最后一个有效状态；reset 必须
清除内部状态并要求显式初始化。校验配置包含 `invalid_input_and_reset`，但不声称
尚未实现组件已经具备该行为。

G3 必须新增独立的真值隔离检查：向估计器和控制器接口注入可审计的拒绝 truth 字段，
并在运行路径中验证这些字段无法被接受；只有 reset 显式初始化可按已批准合同使用
初始真值。该未来测试不能由 G0 的 schema 测试替代。

## 复现入口

在 Linux B0 虚拟环境中，从本 track 运行：

```bash
cd 05_integration/b0
python validate_config.py --config configs/b0_g0_contract.v1.json
python -m pytest -v
```

这些命令验证合同配置及其正反例，不运行闭环。

## 维护者批准清单

在合并或称为冻结前，维护者需要集中决定：

1. `/operating_envelope` 的合成有效范围和明确排除项；
2. `/timing` 的 tick、发布顺序和多速率关系；
3. `/plant_contract`、`/actuator_contract`、`/imu_contract` 的合成候选；
4. `/controller_contract` 的增益范围、初始候选和抗饱和语义；
5. `/acceptance_policy` 与每个 `/scenarios/*/acceptance` 的通过值；
6. `CTL-REQ-001` 与 `CTL-REQ-002` 对 B0 的适用性结论。

未作出这些决定时，状态必须保持 `proposed_pending_maintainer_approval`。

## G1/G2 交接输入

G1 的唯一输入是配置中的对象、执行器、IMU、时序和异常合同；应先为解析角运动和
采样重复性建立独立证据。G2 估计器使用 IMU、归一化、偏航限制和真值隔离合同；G2
控制器使用估计状态、误差四元数、request/limited/actual 力矩界面及已批准增益范围。
后续实现不得改写本配置的已批准字段；确需变化时须说明原因、变更版本并重跑受影响
场景。
