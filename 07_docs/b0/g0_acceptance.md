# B0 G0 场景与验收矩阵

**状态：提议中，等待维护者批准；本矩阵不是性能结论。**

机器权威来源是
[b0_g0_contract.v1.json](../../05_integration/b0/configs/b0_g0_contract.v1.json)。
全部数值、种子、事件窗口和候选界值仍为待批准、未执行的工程候选。本文不能被用来
宣称 SIL、HIL、实机、CTL-REQ 或闭环性能符合性。

## 结果分类与无效数据

| 分类 | 含义 |
|---|---|
| performance_pass | 已批准的包线内场景，独立指标满足所有适用准则 |
| performance_fail | 已批准的包线内场景，独立指标违反至少一项准则，含截止时仍未稳定 |
| limitation_characterized | 已知限制按预定信号、窗口与状态记录，不等同于性能通过 |
| invalid_input_rejected | 非法输入按合同拒绝或 reset；不是动态性能证据 |
| execution_error_inconclusive | 构建、运行、数据、时间戳或指标器错误；不得计为通过 |

所有指标定义的缺数据行为都是 execution_error_inconclusive。零 command delta 的超调
是 not_applicable，而不是 0% 或通过。

## 指标口径

| 指标族 | 已固定的计算口径 | 必需原始信号 |
|---|---|---|
| 姿态误差 | 2*acos(clamp(abs(dot(q_reference,q_candidate)),0,1))，处理 q/-q 等价 | q_nb_truth、q_nb_command 或 q_nb_estimate |
| 初始偏差稳定 | 从 scenario tick 0 起；进入 band 后完整 dwell 才计入 | q_nb_truth、q_nb_command |
| command step 跟踪稳定 | 从该 step 的开始 tick 起；每个 event 单独窗口、目标和 deadline | q_nb_truth、q_nb_command |
| 扰动/撤回恢复 | 从该 disturbance 或 command withdrawal 的结束 tick 起 | q_nb_truth、q_nb_command |
| 超调 | 按事件前 command 到目标的有符号增量投影；分母为该增量绝对值 | q_nb_truth、q_nb_command |
| 跨轴误差 | 相对于当前 command step 轴的未命令轴误差最大值 | q_nb_truth、q_nb_command |
| 饱和持续时间 | request 超界且 limited 为组件 clamp 的 dt 总和 | requested_torque_Nm、limited_torque_Nm |
| 估计误差与偏航漂移 | truth 与 estimate 相对误差；偏航仅是初始参考下的相对漂移 | q_nb_truth、q_nb_estimate |
| 积分器 | 逐轴 integral torque contribution，不做全轴掩盖 | controller_integral_Nm |
| 加速度污染限制 | event 内 specific-force、limitation status 与 truth/estimate 均须记录 | imu_specific_force_m_s2、limitation_status、q_nb_truth、q_nb_estimate |
| 无效输入/reset | 显式拒绝原因计数；相同 seed 和显式初态下的 post-reset trace 比较 | sample_validity、rejection_reason、reset_epoch、q_nb_estimate |

稳定窗口必须容纳候选时间界加 dwell。若先达到窗口截止仍未连续驻留完整 dwell，结果是
performance_fail；不允许返回一个虚构的有限稳定时间。

## 八类场景

| 场景 | 类别 | 事件与观察规则 | 候选准则与未来责任 |
|---|---|---|---|
| stationary_zero_command | 包线内性能 | 无事件；记录 truth、estimate、command、角速度和 actual torque | 姿态误差、角速度误差、四元数范数；G1/G2/G3 |
| initial_attitude_offset | 包线内性能 | 偏差只施加到 plant truth；estimate 从显式自身初态 reset | tick 0 起的稳定时间和峰值姿态误差；G1/G2/G3 |
| tri_axis_signed_steps | 包线内性能 | 六个有 ID 的 x/y/z 正负 step，各自半开区间、结束后该轴归零 | 每个 event 单独有稳定、超调和跨轴准则；G2 控制器/G3 |
| external_torque_disturbance | 包线内性能 | 有界机体系外力矩 event；恢复从 event end 起算 | 峰值误差、独立恢复、饱和持续时间；G1/G2/G3 |
| imu_noise_and_bias | 包线内性能 | 每样本噪声、替换式偏置 event 和固定 seed | 横滚/俯仰 RMS、相对偏航漂移；G1/G2 估计器/G3 |
| saturation_withdrawal | 包线内性能 | 非零 command event、逐轴 request/limited/actual 记录，撤回后恢复 | 必须出现正饱和持续时间、积分界、恢复和总饱和上界；G1/G2 控制器/G3 |
| acceleration_contamination | 限制刻画 | additive specific-force event；不引入平移动力学 | event 内限制记录与完整信号依赖；G1/G2 估计器/G3 |
| invalid_input_and_reset | 无效输入 | negative dt、stale timestamp、all-components reset | 明确拒绝计数与确定性 reset replay；G1/G2/G3 |

artifact_path 仅约定未来证据位置。本 PR 不提交 CSV、图表、仿真输出或伪造结果。

## 三轴阶跃与观察窗口核算

候选 base tick 是 0.0025 s，dwell 是 0.25 s，即 100 tick。每个阶跃的候选
稳定界为 1.2 s，即 480 tick，故一个合格观察窗口至少需要 580 tick。当前每一段
保持 700 tick（1.75 s），并有 100 tick（0.25 s）间隔；场景长度调整为 14 s，
使每一个正/负轴事件都有自己的可观测窗口，而不是共享公共窗口。

每个 command event 的 acceptance 项必须显式引用 event_id。校验器拒绝：

- 同一轴事件重叠、乱序或不在场景范围内；
- 删除任一 event 的稳定、超调或跨轴指标；
- 用 sample_validity 等无关 observation 替代所需原始信号；
- 窗口短于时间界加 dwell；
- 把 recovery 窗口的起点放在 event end 之外。

## 饱和撤回的独立证据

饱和撤回不是“非零 command 即认为会饱和”。它需要：

1. event 内的 actuator_saturation_time_s 使用大于零的下界，作为未来 G3 的实际
   触发证据；
2. 同时保留上界，防止持续饱和被当作通过；
3. 将恢复稳定时间绑定到 command event 的结束 tick；
4. 记录逐轴 integral torque contribution、request、limited 与 actual。

因此，未来动态运行若从未触发饱和，必须按合同得到失败或 inconclusive，而不能借由
上界为零而通过。

## CTL-REQ 适用性审查

原有编号和阈值保持不变；本轮未修改需求，也没有产生符合性证据。

| 需求 | 原始阈值 | 当前结论 | 维护者待决事项 |
|---|---|---|---|
| CTL-REQ-001 | Attitude settling time — 10 degree step input，< 0.8 s，Test | 条件化适用，未批准、未执行 | 是否在相同对象、command、band、dwell 与指标口径下采纳旧阈值 |
| CTL-REQ-002 | Attitude overshoot，< 15%，Test | 条件化适用、候选阈值冲突，未执行 | 是否采纳旧阈值，或正式记录不适用并批准 B0 工程阈值 |

候选 B0 阈值不能替换、重编号或暗中放宽这些旧阈值。批准记录须连同新的配置版本保存。

## 未来 G3/G4 执行规则

1. 加载 validate_config.py 接受的批准配置，不允许隐式默认或未知字段；
2. 使用保留验收 seed；调参 seed 与验收 seed 分离；
3. 每项指标由独立于估计器/控制器的指标器计算；
4. 按 timing/sequence 执行并保留 request、limited、actual 三种 torque；
5. 每次运行保留 revision、配置 hash、seed、时钟策略、原始信号、指标器版本和终止状态；
6. 不将 replay、板端、实时闭环 HIL 和实机飞行混为同一级证据；
7. 已批准字段变更时必须版本化、说明原因并重跑受影响场景。

维护者尚未批准前，这些规则只是候选执行合同；G0 校验通过不等于 G0 冻结或 B0 完成。
批准不得把本 v1 原地改成 approved：必须新增版本化的 v2 配置、校验器合同和维护者决定
记录，再重新验证受影响场景。
