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
| 场景包线与指标 | /operating_envelope、/acceptance_policy、/scenarios | 合成旋转实验；排除平移、气动、导航、硬件，以及无参考的绝对初始航向恢复 |

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
有效性。实现不得隐式变换坐标、单位、时间戳或重复限幅。

| 消息 | 生产者 → 消费者 | 必需字段 |
|---|---|---|
| attitude_command | 场景/命令适配器 → 控制器 | timestamp_s、q_nb_command、valid |
| imu_sample | G1 IMU → G2 估计器 | timestamp_s、gyro_b_rad_s、specific_force_b_m_s2、valid |
| state_estimate | G2 估计器 → G2 控制器/G3 | timestamp_s、q_nb_estimate、omega_b_estimate_rad_s、valid |
| torque_command | G2 控制器 → G1 执行器 | timestamp_s、未限幅 requested_torque_body_Nm、限幅后 limited_torque_body_Nm、逐轴 saturated |
| actuator_feedback | G1 执行器 → G2 控制器/G3 | timestamp_s、command_timestamp_s、配对的 limited_torque_body_Nm、actual_torque_body_Nm、逐轴 saturated |

唯一的限幅责任组件是 controller。它在同一 controller tick 计算未限幅 request、
对 actuator limits 做组件限幅，并在 TorqueCommand 中发布 request、limited 和
saturated；saturated[i] 当且仅当 abs(requested[i]) > limit[i] 且 limited[i] 等于
该组件 clamp。actuator 不重新推断 request 或重复限幅：它只消费配对 TorqueCommand 的
limited 字段，并把同一命令的 limited/saturated 与自身 actual 放入反馈。因此仅持有
limited 的组件从未被要求猜测是否发生 request 饱和。

interface_contract/component_calls 同时固定语言无关的 reset 与 step 签名：

~~~text
Plant.reset(PlantInitialState, reset_epoch) -> PlantState
Plant.step(actual_torque_body_Nm, dt_s) -> PlantState
Actuator.reset(ActuatorInitialState, reset_epoch) -> ActuatorFeedback
Actuator.step(torque_command, dt_s) -> ActuatorFeedback
Estimator.reset(EstimatorInitialState, reset_epoch, rng_seed) -> StateEstimate
Estimator.step(imu_sample) -> StateEstimate
Controller.reset(ControllerInitialState, reset_epoch) -> TorqueCommand
Controller.step(attitude_command, state_estimate, actuator_feedback, dt_s) -> TorqueCommand
~~~

形状不符、非有限值、无效状态、非正 dt 或不允许的时间戳必须产生
ContractValidationError，且不得悄然改变内部状态。估计器 reset 不接收 live
truth；其唯一初值是显式的估计器初态。

## 初始化、tick 0 与 reset

initialization_contract 明确区分：

- 场景中的 initial_q_nb 与 initial_body_rate_rad_s 只属于 plant truth；
- initial_attitude_offset 场景的偏差也只属于 plant truth，按
  q_base ⊗ qx(roll) ⊗ qy(pitch) ⊗ qz(yaw)、FRD 内禀 x→y→z 顺序组合；该场景的
  initial_q_nb 固定为单位四元数，故进入候选包线的姿态偏差只能来自声明的 roll/pitch
  offset，不能由另一个 base attitude 叠加绕过；
- estimator、command、actuator、积分器与微分滤波器从
  initialization_contract/default_component_state 显式初始化；
- tick 0 只完成 reset 与初始化，不积分；首个区间为 [0, base_period_s)；
- pre-tick-0 的 Controller.reset 必须发布 timestamp=0 的全零 C_reset（request、limited
  与 saturated 全部显式）；它保持到 controller 的第一个 due base tick；
- 随机状态在首次噪声抽样前由场景 seed 初始化；reset 产生新的显式 epoch。

初始偏差恢复的候选口径专门处理六轴 IMU 的航向边界。该场景只施加
roll/pitch 偏差 [0.174533, -0.139626, 0] rad 给 plant truth；command 与 estimator
都从各自显式的单位四元数开始。其必达准则不是完整四元数角误差，而是

~~~text
tilt_error_rad =
  acos(clamp(dot(third_column(R_nb_command), third_column(R_nb_truth)), -1, 1))
~~~

即 command 与 truth 的机体 z 轴在 NED 中的夹角。静止或仅六轴惯性量测下，对 NED
竖直轴施加等价的初始航向变换不会改变重力方向量测；零角速度也不提供绝对航向。
因此未知初始 yaw 不被伪装为可达到的绝对姿态恢复性能，而是保留为未来
limitation_characterization 的边界。它既不把 truth 注入 estimator，也不删除正常的
三轴相对 command tracking：六个 command-step 事件仍包括 z 轴并使用各自的相对跟踪
准则。上述是待维护者批准的候选口径，不是已执行结果。

因此，“初始姿态偏差”不会把真值暗中送入估计器；估计器只能读取自身显式初值和随后的
IMU 样本。

## 确定性时序、运行时 reset 与事件语义

`timing/first_due_tick` 固定一个 epoch 内的多速率相位：plant 和 actuator 首次在 epoch-local
tick 1 到期；IMU、estimator 与 controller 首次在 epoch-local tick 2 到期。启动本身是
epoch 0；每个 runtime reset 的事件开始都创建一个新的 epoch-local tick 0。这里选择的是
**重启局部相位**，而不是保留 reset 前的全局偶/奇相位。场景全局时钟、全局 tick 和每个消息的
timestamp 始终不回退。

reset event 必须恰占半开区间 `[R, R+1)`，其中 R 是其全局开始 tick。它在 R 的边界执行以下
唯一动作：丢弃 reset 前 plant/actuator/estimator/controller 状态、held TorqueCommand 和
feedback；以显式初始状态与声明 seed 初始化所有组件；runtime reset 时将 `reset_epoch` 恰增
一次；发布零 `C_reset`。该 reset tick **不**执行 plant、actuator、IMU、estimator 或 controller
step，因而不产生零 dt、虚构的长 dt 或把 reset state 误计为 estimator update。

`C_reset` 的 timestamp 是 `R*base_period_s`（启动时 R=0，故为 0），属于从不回退的
scenario clock，并必须大于此前该 command stream 的已发布 timestamp。它保留为 held command，
直到新 epoch 的首个 controller due tick；首个 controller 用的 feedback 必须仍标记为该
`C_reset` 的原 timestamp。所有后续 normal command 与 IMU/estimate/feedback timestamp 都按
`reset_boundary_s + epoch_local_tick*base_period_s` 映射到全局场景时间。

在一个非 reset 的 epoch-local tick k，唯一顺序仍为：

1. plant 为该 epoch 的相应基础区间消费上一 actuator 更新后保持的 actual torque；
2. actuator 推进严格早于当前全局 tick 发布的最近 TorqueCommand 的 limited 字段一个 base
   interval，并在 feedback 中保留该 command 的原 timestamp；
3. 到期时 IMU 在区间末采样；
4. 到期时 estimator 消费一个新的有效 IMU；
5. 到期时 controller 消费当前 estimate 与标记 feedback；
6. controller 在 actuator step 后发布新的 normal command，timestamp 是同一 scenario-clock
   时刻，供后续 tick 使用。

对候选 `base_period_s=0.0025` 和 2-tick IMU/estimator/controller 周期，以下两个运行时
例子是合同的人工核对表，而不是执行结果。

### runtime reset：R=1000（reset boundary = 2.5000 s）

| 全局 tick | epoch-local tick | 动作与时间戳 | estimator 计数 |
|---:|---:|---|---|
| 1000 | 0 | reset-only；发布 `C_reset`，timestamp 2.5000 s；无 component step | 不计入 |
| 1001 | 1 | plant/actuator 推进 C_reset；无 IMU/estimator/controller due | 0 |
| 1002 | 2 | 新 IMU timestamp 2.5050 s；estimator dt=0.0050 s；controller dt=0.0050 s，使用 C_reset feedback 后发布首个 normal command | 第 1 个有效 update |
| 1004 | 4 | 第二个新 IMU/estimate/controller due，timestamp 2.5100 s | 第 2 个有效 update |

### runtime reset：R=1001（reset boundary = 2.5025 s）

| 全局 tick | epoch-local tick | 动作与时间戳 | estimator 计数 |
|---:|---:|---|---|
| 1001 | 0 | reset-only；发布 `C_reset`，timestamp 2.5025 s；无 component step | 不计入 |
| 1002 | 1 | plant/actuator 推进 C_reset；无 IMU/estimator/controller due | 0 |
| 1003 | 2 | 新 IMU timestamp 2.5075 s；estimator dt=0.0050 s；controller dt=0.0050 s，使用 C_reset feedback 后发布首个 normal command | 第 1 个有效 update |
| 1005 | 4 | 第二个新 IMU/estimate/controller due，timestamp 2.5125 s | 第 2 个有效 update |

因此 reset-replay 的最短合格半开观察窗口是 `[R, R+5)`：R=1000 时为 `[1000,1005)`，
R=1001 时为 `[1001,1006)`。窗口在第二次 due update 的 tick 结束处（例如 `[1001,1005)`）
仍不包含该 update，必须被拒绝。

重放的两次运行必须在同一个 reset boundary 比较：它们拥有相同的 epoch-local schedule、
explicit initial state、输入 reset-relative trace、scenario seed 和 post-reset noise draw index。
比较只使用带有效样本的 matching epoch-local estimator due tick；reset state、本身的 `C_reset`
及其 zero command 不是 estimator update。保留 IMU、attitude command、state estimate、torque
command 和 actuator feedback 的 scenario-clock timestamp，以及 feedback 的 paired-command
timestamp 和 reset_epoch，才能独立重建该比较。

事件使用半开区间 `[start_tick, end_tick)`：开始端包含、结束端不包含。事件按非递减开始 tick
声明；同一信号（含同一指令轴）重叠被拒绝。跨类型重叠仅可由
`timing/event_tick_semantics/allowed_cross_type_overlap_pairs` 逐项批准；默认没有。命令事件
结束后，其受影响轴回到零，其余轴不被隐式修改。

## 限幅与完整抗饱和合同

三个力矩量绝不混同：

~~~text
requested_torque       : controller 在 due tick k 的未限幅输出（TorqueCommand[k]）
limited_target         : 同一 TorqueCommand[k] 内对 request 的逐轴 clamp
feedback_limited_target: Feedback[k] 配对 held command 的 limited 字段与原 timestamp
actual_torque          : actuator 推进该 held command 后发布的有界输出（Feedback[k]）
~~~

控制器采用候选组合策略“条件积分 + 回算”：

~~~text
I_next = clamp(
  I + dt * (
    conditional(ki * rate_error)
    + kaw_limit * (limited_target[k] - requested[k])
    + kaw_lag * (actual[k] - feedback_limited_target[k])
  ),
  -I_limit, I_limit
)
~~~

`feedback_limited_target[k]` 不表示“数值上碰巧等于当前 target 的值”；它是
ActuatorFeedback 明确携带、带原命令时间戳的配对字段。默认多速率下它来自一个 controller
publication 前的 held command；首个 due controller tick 则明确使用 C_reset 的反馈。

actuator_contract/antiwindup 固定每一项的单位、生产者、可用时刻、每轴增益、reset 值和
一 controller-publication delay：

- 当 requested - limited 与 rate_error 同号时，不允许自然积分继续把 request 推向饱和；
- limited_target[k] - requested[k] 在同一 controller tick 的组件限幅后可得，专门处理
  request 超界；
- actual[k] - feedback_limited_target[k] 在 actuator 推进后可得，专门处理动态滞后，且
  不把 held command 错配为当前刚发布的命令；
- 积分状态是 integral_torque_contribution_body_Nm，按轴限于
  controller_contract/rate_pid/integrator_limit_Nm。

手算的合同例子（不是动态性能结果）：x 轴当前 requested=+0.50 Nm、当前
limited_target=+0.35 Nm，而配对反馈中的 actual=feedback_limited_target=+0.35 Nm、正
rate_error 时，条件积分被阻断，限幅反馈为 -0.15 Nm。以候选 kaw_limit=8 1/s 和
controller dt=0.005 s，该项使积分贡献减少 0.006 Nm；lag 项为零。即使执行器已跟上其
held target，当前 request 超界仍由限幅回算记录，不能被误判为“无饱和”。

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
- 初始偏差恢复使用上文定义的 tilt_error，不将未知 yaw 当作可观测的绝对恢复；
- 跟踪稳定时间从 command step 的开始 tick 起算；扰动/撤回恢复从事件结束 tick
  起算；初始倾斜偏差从 tick 0 起算；
- 进入稳定带后必须连续保持完整 dwell；窗口必须同时容纳候选时间界与 dwell；
- 超调和跨轴峰值必须精确覆盖各自 command event 的完整半开区间，不能缩为任意
  一 tick；例如 event [200,900) 内在 tick 899 出现的峰值仍必须被观察；
- 超调基于事件前 command 与目标之间的有符号增量，分母为该增量绝对值；零增量为
  not_applicable；
- 饱和为任一轴 request 超界且 limited 等于 controller clamp。饱和时间是“任意轴
  为真”的 wall-clock 并集，每个 tick 最多累计一次 dt；三轴同时饱和 0.1 s 的候选
  指标值是 0.1 s，不是 0.3 s；
- saturation_withdrawal 必须同时有 event 内正持续时间下界和全场景上界。下界不得
  大于绑定 command event 的物理 wall-clock 时长（相等允许）；二者角色不可相互替代，
  从未饱和或持续过长都不能通过；
- controller_integral_Nm 是按声明轴的最大绝对 integral contribution，x/y/z 的
  限值分别为 0.15/0.15/0.10 Nm；示例 abs(I_z)=0.12 Nm 必须违反 z 轴准则，不能
  被 x/y 的 0.15 Nm 掩盖；
- invalid_input_and_reset 必须恰有一个 negative_dt 和一个 stale_timestamp 注入，
  每个事件以 sample_validity=false 且与 invalid_kind 匹配的 rejection_reason 计
  一次；计数准则覆盖全场景并必须等于这两个事件，随后才允许一个 all-components
  reset；
- reset 仅占其 `[R,R+1)` 的 epoch-local tick 0：它先丢弃 pre-reset held command/feedback，
  发布 timestamp 为 `R*base_period_s` 的 C_reset，并重启局部 schedule；global scenario clock
  不回退。首个 estimator/controller due 在 R+2，以一个新 valid IMU 和 dt=2*base_period_s
  执行；reset state 不计为 update。两次 replay 在同一 reset boundary、相同局部 due tick、
  initial state、input trace、seed/draw index 下比较每个 q_nb_estimate 分量，容差为 1e-12；
  最短窗口 `[R,R+5)` 必须覆盖两次有效 update，不能用空窗口、一次样本或错误的全局偶/奇相位
  伪造确定性；
- 加速度污染必须记录 additive specific-force、limitation status 与 truth/estimate
  信号，不能以任意 true 代替证据。

三轴正负阶跃现在有六个有 ID 的 command event。每个事件拥有自己的目标、完整峰值
窗口、独立稳定时间、超调和跨轴误差准则；候选 1.2 s 稳定界和 0.25 s dwell 被窗口
长度校验。这消除了把撤回后的恢复误判为阶跃跟踪的歧义。

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
