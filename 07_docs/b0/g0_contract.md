# B0 G0 合同与接口设计

**状态：提议中，等待维护者集中批准；不得称为冻结。**
**范围：B0 v0.2 的合同、版本化配置、校验和验收设计；不实现 G1/G2/G3。**

机器可读配置
[b0_g0_contract.v1.json](../../05_integration/b0/configs/b0_g0_contract.v1.json)
是参数、场景、种子、接口和候选通过值的唯一权威来源。
[validate_config.py](../../05_integration/b0/validate_config.py) 是唯一可执行的
合同校验入口；JSON Schema 仅为顶层结构索引，不能单独用于接受配置。

本文件记录合同语义与交接边界。配置校验和其测试通过，只证明候选合同可被一致加载、
非法合同会被拒绝；不证明任何 G1 对象、G2 组件、G3 调度、SIL、HIL、板端、飞行或
性能结果。

## G0 边界与资产审计

G0 固定后续实现必须遵守的输入、输出、时序、初值、验收和错误语义。所有数值保持
synthetic_assumption、proposed_pending_maintainer_approval 或
proposed_not_executed 状态，直到维护者批准。

| 路径或资产 | 实际状态和已见证证据 | G0 决定 |
|---|---|---|
| 01_simulation/scenario_generator/ | 遗留批量场景 placeholder | 仅作历史参考，不复用为 B0 对象或传感器 |
| 02_estimation/python/ekf.py、ukf.py | EXT-NAV 路径；核心实现未完成 | 不适配为 B0 姿态估计器 |
| 03_control/python/geometric_control.py、lqr_baseline.py | 遗留控制脚手架 | 不复用为 G2 控制器或完成证据 |
| 05_integration/integrated_sim.py 及旧 Monte Carlo 路径 | 兼容性保留的 legacy scaffold | G0 只维护隔离的 05_integration/b0/ 合同 track |
| 根 CMakeLists.txt | EXT-NAV 根目标与开发就绪探针 | 不作为 B0 算法或验收证据 |
| tools/development_readiness/ | Linux 工具链、绑定和调试探针已记录 | 只复用环境证据 |

literature/evidence_matrix.xlsx 和 literature/screening.csv 仍只用于历史发现和筛选
审计。没有带原文定位的数值被复用；若将来采用文献参数，必须先按
literature/protocol.md 记录原文位置与适用边界。

## 参数、包线与工程依据

| 合同域 | 权威配置位置 | 当前依据和状态 |
|---|---|---|
| 坐标、单位、四元数 | /conventions | 继承 ARCH-COORD-001；NED、FRD、SI、标量在前 Hamilton q_nb |
| 基础 tick、事件端点、多速率 | /timing | 合成候选；所有周期为基础 tick 整数倍 |
| 初始化、reset、随机状态 | /initialization_contract | 显式 tick 0、默认状态和场景字段所有权 |
| 刚体惯量与积分 | /plant_contract | 合成 SPD 对角惯量；量纲为 kg*m^2，z 轴惯量最大，不代表真实机型 |
| 执行器与抗饱和 | /actuator_contract | 合成力矩界和 0.03 s 滞后；用于限定抽象力矩接口 |
| IMU | /imu_contract | 噪声为每样本独立高斯标准差，偏置为机体系常值；不代表真实传感器 |
| 控制候选 | /controller_contract | 有量纲的候选增益、角速度目标限值和滤波；不是已调参或性能结论 |
| 场景包线与指标 | /operating_envelope、/acceptance_policy、/scenarios | 合成旋转实验；排除平移、气动、导航和硬件 |

配置中的简短 parameter_rationale 说明各个量级之间的工程关系。它们不是文献、实测
或适航依据，不能被表述为真实机型参数。

## 坐标、真值与所有权

- 世界坐标系为 **NED**，机体系为 **FRD**，全部量使用 **SI**；
- 姿态为标量在前的 Hamilton 四元数 q_nb，将机体系向量旋转到 NED；
- 角速度 omega_b 位于 FRD 机体系，单位 rad/s；
- q 与 -q 等价；符号和半周 tie-break 由 conventions/quaternion 与
  controller_contract/attitude_error 固定；
- plant truth 仅可被对象、传感器和独立指标器读取，不能进入估计器或控制器；
- G3 仍须用固定 IMU/指令/初始化、仅改变评估端 truth 副本的测试证明运行时隔离。

## 语言无关接口账本

interface_contract/messages 固定每一个跨组件消息的字段、类型、形状、单位、帧和
有效性。实现不得隐式变换坐标、单位或时间戳。

| 消息 | 生产者 → 消费者 | 必需字段 |
|---|---|---|
| attitude_command | 场景/命令适配器 → 控制器 | timestamp_s、q_nb_command、valid |
| imu_sample | G1 IMU → G2 估计器 | timestamp_s、gyro_b_rad_s、specific_force_b_m_s2、valid |
| state_estimate | G2 估计器 → G2 控制器/G3 | timestamp_s、q_nb_estimate、omega_b_estimate_rad_s、valid |
| torque_request | G2 控制器 → G1 执行器 | timestamp_s、未限幅 requested_torque_body_Nm |
| actuator_feedback | G1 执行器 → G2 控制器/G3 | timestamp_s、limited_torque_body_Nm、actual_torque_body_Nm、逐轴 saturated |

interface_contract/component_calls 同时固定语言无关的 reset 与 step 签名：

~~~text
Plant.reset(PlantInitialState, reset_epoch) -> PlantState
Plant.step(actual_torque_body_Nm, dt_s) -> PlantState
Actuator.reset(ActuatorInitialState, reset_epoch) -> ActuatorFeedback
Actuator.step(limited_torque_body_Nm, dt_s) -> ActuatorFeedback
Estimator.reset(EstimatorInitialState, reset_epoch, rng_seed) -> StateEstimate
Estimator.step(imu_sample) -> StateEstimate
Controller.reset(ControllerInitialState, reset_epoch) -> TorqueRequest
Controller.step(attitude_command, state_estimate, actuator_feedback, dt_s) -> TorqueRequest
~~~

形状不符、非有限值、无效状态、非正 dt 或不允许的时间戳必须产生
ContractValidationError，且不得悄然改变内部状态。估计器 reset 不接收 live
truth；其唯一初值是显式的估计器初态。

## 初始化、tick 0 与 reset

initialization_contract 明确区分：

- 场景中的 initial_q_nb 与 initial_body_rate_rad_s 只属于 plant truth；
- initial_attitude_offset 场景的偏差也只属于 plant truth，按
  q_base ⊗ qx(roll) ⊗ qy(pitch) ⊗ qz(yaw)、FRD 内禀 x→y→z 顺序组合；
- estimator、command、actuator、积分器与微分滤波器从
  initialization_contract/default_component_state 显式初始化；
- tick 0 只完成 reset 与初始化，不积分；首个区间为 [0, base_period_s)；
- 随机状态在首次噪声抽样前由场景 seed 初始化；reset 产生新的显式 epoch。

因此，“初始姿态偏差”不会把真值暗中送入估计器；估计器只能读取自身显式初值和随后的
IMU 样本。

## 确定性时序与事件语义

每个基础 tick 唯一执行以下顺序：

1. plant 在当前积分区间消费上一个 actual_torque；
2. actuator 向上一个 limited_target 推进；
3. 到期时 IMU 在区间末采样；
4. 到期时 estimator 消费该新 IMU；
5. 到期时 controller 消费当前 estimate；
6. controller 计算 request、限幅并发布下一 limited_target。

当前候选要求 estimator 与 IMU 同周期，controller 与 estimator 同周期；因此不存在
“无新 IMU 仍重复消费”的隐含分支，no_new_imu_action 明确为 not_scheduled。
controller 读取的 estimate 年龄为零个基础 tick。

事件使用半开区间 [start_tick, end_tick)：开始端包含、结束端不包含。事件按非递减
开始 tick 声明；同一信号（含同一指令轴）重叠被拒绝。跨类型重叠仅可由
timing/event_tick_semantics/allowed_cross_type_overlap_pairs 逐项批准；默认没有。
命令事件结束后，其受影响轴回到零，其余轴不被隐式修改。

## 限幅与完整抗饱和合同

三个力矩量绝不混同：

~~~text
requested_torque : 控制器未限幅输出
limited_target   : 同 tick 对 request 逐轴限幅后的目标
actual_torque    : actuator 在本 tick 推进后的有界实际输出
~~~

控制器采用候选组合策略“条件积分 + 回算”：

~~~text
I_next = clamp(
  I + dt * (
    conditional(ki * rate_error)
    + kaw_limit * (limited_target - requested)
    + kaw_lag * (actual - limited_target)
  ),
  -I_limit, I_limit
)
~~~

actuator_contract/antiwindup 固定每一项的单位、生产者、时刻、增益、reset 值和一
tick actuator 发布延迟：

- 当 requested - limited 与 rate_error 同号时，不允许自然积分继续把 request
  推向饱和；
- limited_target - requested 在同一 controller tick 的组件限幅后可得，专门处理
  request 超界；
- actual - limited_target 在 actuator 推进后可得，专门处理动态滞后；
- 积分状态是 integral_torque_contribution_body_Nm，按轴限于
  controller_contract/rate_pid/integrator_limit_Nm。

手算的合同例子（不是动态性能结果）：x 轴 requested=+0.50 Nm、
limited_target=actual=+0.35 Nm、正 rate_error 时，条件积分被阻断，限幅反馈为
-0.15 Nm。以候选 kaw_limit=8 1/s 和 controller dt=0.005 s，该项使积分贡献减少
0.006 Nm；lag 项为零。未饱和时限幅反馈为零，反向误差则允许正常积分并协助恢复。
此例说明 request 超界不会因 actual=limited_target 而被误判为无饱和。

## 控制、估计与 IMU 的未实现合同

| 域 | 已固定、供后续实现遵循的项目 |
|---|---|
| G1 plant | SPD 惯量、RK4、步长减半检查、质心 IMU、抽象力矩输入 |
| G1 actuator | 一阶有界响应、三种 torque、反馈时刻与饱和状态 |
| G1 IMU | NED 重力、specific force 定义、每样本噪声标准差、偏置替换事件 |
| G2 estimator | reset/step、有效样本、归一化、拒绝与保持状态、六轴无绝对偏航 |
| G2 controller | 仅 command/estimate/actuator feedback、四元数误差、目标角速度界、增益单位、测量角速度微分及一阶滤波 |

rate_pid 的候选单位为 kp: Nm*s/rad、ki: Nm/rad、kd: Nm*s2/rad；姿态环 kp 的单位为
1/s。这些是合同字段，不是已调好的参数。后续 G2 可以在批准的合同内调参，但不得
重定义离散积分、微分或抗饱和语义。

## 指标、事件绑定与失败语义

acceptance_policy/metric_definitions 为每项指标固定原始信号、公式、轴聚合和无效数据
处理；所有缺数据、运行中断或指标器错误均为 execution_error_inconclusive，不得
伪装为有限稳定时间或性能通过。

- 四元数误差使用 2*acos(clamp(abs(dot(q_reference,q_candidate)),0,1))；
- 跟踪稳定时间从 command step 的开始 tick 起算；扰动/撤回恢复从事件结束 tick
  起算；初始偏差从 tick 0 起算；
- 进入稳定带后必须连续保持完整 dwell；窗口必须同时容纳候选时间界与 dwell；
- 超调基于事件前 command 与目标之间的有符号增量，分母为该增量绝对值；零增量为
  not_applicable；
- 饱和为任一轴 request 超界且 limited 等于组件 clamp；饱和撤回场景必须记录事件
  内的正持续时间和独立恢复准则；
- 加速度污染必须记录 additive specific-force、limitation status 与 truth/estimate
  信号，不能以任意 true 代替证据。

三轴正负阶跃现在有六个有 ID 的 command event。每个事件拥有自己的目标、独立窗口、
稳定时间、超调和跨轴误差准则；候选 1.2 s 稳定界和 0.25 s dwell 被窗口长度校验。
这消除了把撤回后的恢复误判为阶跃跟踪的歧义。

## 复现与批准

在 Linux B0 环境中运行：

~~~bash
cd 05_integration/b0
python validate_config.py --config configs/b0_g0_contract.v1.json
python -m pytest -v
~~~

详见 [g0_review_resolution.md](g0_review_resolution.md) 中的评审发现到测试映射。

维护者仍须集中批准：合成包线、惯量/限幅/IMU/增益候选、离散抗饱和设计、指标和阈值、
CTL-REQ-001/002 适用性，以及批准后版本策略。当前 v1 校验器故意只接受 proposed
状态；一经批准，必须提交新的 b0-g0-contract/v2 配置和对应校验器合同，连同维护者对
参数、包线、指标与 CTL 适用性的决定记录。不得原地把已审查的 v1 改写成 approved。
未批准前所有状态必须保持 proposed_pending_maintainer_approval，不得关闭 Issue #3 或
启动 G1/G2/G3。
