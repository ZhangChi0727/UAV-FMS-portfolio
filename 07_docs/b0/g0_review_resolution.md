# PR #11 G0 评审修复记录

**状态：修复待复审，仍为 proposed_pending_maintainer_approval。**

本记录保留 Project Administrator 对 PR #11 基线 fd5615f 的首轮发现，并记录第二轮
对 8948769、第三轮对 e0d1e4a 与第四轮对 996cf81 的独立复审收敛工作。“发现 → 合同/代码 → 反例测试”的
对应关系不构成算法、仿真、HIL、飞行或需求符合性证据，也不表示 G0 已冻结。

## 已处理的阻塞发现

| 发现 | 合同与实现改动 | 关键反例测试 |
|---|---|---|
| P1：actual - limited 未覆盖 request 限幅误差 | actuator_contract/antiwindup 明确条件积分、same-tick limited-requested 回算、lag feedback、每轴增益、离散式、reset 与时刻 | test_rejects_incomplete_or_contradictory_antiwindup_contract |
| P1：阶跃稳定时间从 event end 起算且公共窗口掩盖失败 | acceptance_policy 区分 command start、disturbance end、initial tick 0；六个 step event 各有 ID、窗口和三个准则 | test_rejects_event_order_overlap_and_unobservable_settling_windows；test_rejects_silent_weakening_of_step_acceptance |
| P1：reset/step、初态、单位、滤波和速率界仍由未来实现决定 | interface_contract、initialization_contract、estimator/controller 合同固定消息、签名、tick 0、字段所有权、增益单位、微分滤波和角速度界 | test_rejects_incomplete_interfaces_and_initialization；test_rejects_incomplete_or_contradictory_antiwindup_contract |
| P1：验收项、信号或真实饱和可被静默删弱 | metric_definitions 固定信号依赖；required scenario/event metrics 校验；饱和需要 event 内正持续时间触发准则 | test_rejects_silent_weakening_of_step_acceptance；test_saturation_case_requires_excitation_and_positive_trigger |
| P2：事件重叠、驻留窗口和 IMU/estimator 周期缺少跨字段约束 | 半开 event 语义、同信号重叠拒绝、声明式跨类型白名单、dwell 容量、IMU/estimator/controller 同周期消费合同 | test_rejects_incompatible_sampling_and_consumption；test_rejects_event_order_overlap_and_unobservable_settling_windows |
| P2：缺字段产生 KeyError 或其他裸异常 | 每种 event 类型先做 required/allowed/type 校验；criterion/source/observation 也做类型守卫；JSON loader 拒绝重复键 | test_every_event_type_rejects_missing_required_field；test_event_unknown_and_wrong_type_errors_are_contract_errors；test_loader_rejects_nonfinite_and_duplicate_json |

## 第二轮剩余发现的候选修复（待独立复审）

| 第二轮发现 | 本轮合同与实现改动 | 关键正反例测试 |
|---|---|---|
| 成功布尔值、饱和上界和无效事件覆盖仍可删弱 | 真实成功布尔值固定为 true；saturation_withdrawal 同时强制 event 内正下界与全场景上界；negative_dt、stale_timestamp、计数和 reset 一一对应 | test_success_boolean_criteria_cannot_be_weakened；test_saturation_trigger_and_upper_bound_have_distinct_required_roles；test_invalid_input_coverage_and_counter_are_not_weakenable |
| 峰值窗口可缩为一个 tick | step 的超调和跨轴峰值窗口必须精确等于绑定 command event 的完整半开区间 | test_peak_step_metrics_must_cover_the_full_command_event |
| 积分轴限与饱和时间聚合自相矛盾 | controller_integral_Nm 改为逐轴 x/y/z 限值并引用 rate_pid 的 [0.15,0.15,0.10] Nm；saturation duration 改为任意轴 wall-clock 并集 | test_integral_axis_limits_and_saturation_time_aggregation_are_closed；test_per_axis_integral_limit_contract_examples_are_explicit |
| 初始未知 yaw 被作为绝对恢复要求 | 初始恢复改为 roll/pitch tilt 指标；候选配置固定 recovery case 的 yaw=0，并把未知 yaw 记为六轴限制边界；三轴相对 step 跟踪不变 | test_initial_yaw_unobservability_cannot_be_recast_as_recovery |
| request/limited/actual/saturated 的生产消费与时序不闭合 | controller 成为唯一 clamp 和 saturation-flag 责任方；TorqueCommand 明确携带四项，actuator 仅推进上一命令的 limited，feedback 携带配对时间戳 | test_torque_request_limit_pairing_and_feedback_timing_are_closed |
| 三个枚举列表对对象/嵌套列表触发裸 TypeError | 新增逐元素 string type guard，先于 set/成员比较执行 | test_enumeration_collections_reject_nested_and_object_values_as_contract_errors |

本轮仍只定义合同和拒绝性校验；没有实现 G1/G2/G3 指标器、对象或性能判定。上述数学和
接口候选仍待维护者批准，故不能据此合并、冻结或关闭 Issue #3。

## 第三轮复审发现的候选修复（待独立复审）

| 第三轮发现 | 本轮合同与实现改动 | 关键正反例测试 |
|---|---|---|
| 多速率下的命令保持、原 timestamp 与 feedback 配对仍有 k/k-1 歧义 | timing 新增 first_due_tick 与 torque_command_hold；初始化显式 C_reset；interface/actuator/antiwindup 均改为“严格早于当前 base tick 的最新 held command”，并以 feedback 的 paired limited target 回算 | test_round4_held_command_contract_is_explicit；test_round4_rejects_ambiguous_multirate_command_handoff |
| 饱和触发下界可能长于自身 command event | 校验器将 event tick 宽度换算为 wall-clock 上限，要求 trigger 下界不超过该宽度 | test_round4_saturation_trigger_equal_to_command_window_is_valid；test_round4_rejects_saturation_trigger_longer_than_command_window |
| initial_attitude_offset 可通过另一个 initial_q_nb 叠加越过候选包线 | 该场景固定 identity base attitude，只允许声明的 roll/pitch plant-truth offset | test_round4_rejects_initial_offset_with_nonidentity_base_attitude |
| reset replay 窗口可能没有任何或只有一次有效 estimator update | reset 前置顺序、输入/RNG/draw-index、比对时间基准和 1e-12 分量容差写入合同；窗口至少覆盖两次 post-reset due estimator update | test_round4_reset_replay_window_with_two_due_updates_is_valid；test_round4_rejects_reset_replay_window_without_two_due_updates；test_round4_rejects_reset_replay_tolerance_weaker_than_contract |

## 第四轮复审发现的候选修复（待独立复审）

| 第四轮发现 | 本轮合同与实现改动 | 关键正反例测试 |
|---|---|---|
| runtime reset 仍未说明是保持全局相位还是重启局部相位，且 reset tick、首次 dt、C_reset timestamp 与旧 held command 的处置不完整 | 明确选择新 reset epoch / epoch-local tick 0：reset event 恰一 tick、只 reset、不运行 component step；全局 scenario clock 不回退；C_reset 按 reset boundary 发表并丢弃旧 command/feedback；局部 schedule 在 tick 2 首次产生有效 IMU/estimate/controller，dt 为两个 base tick | test_round5_runtime_reset_restarts_local_due_phase；test_round5_startup_and_runtime_reset_share_epoch_zero_contract；test_round5_rejects_window_ending_on_second_local_due_update；test_round5_rejects_reset_only_window；test_round5_rejects_legacy_global_phase_for_odd_runtime_reset；test_round5_rejects_multi_tick_reset_event；test_round5_rejects_ambiguous_runtime_reset_contract |

本轮仍只定义合同和拒绝性校验；没有实现 G1/G2/G3 指标器、对象或性能判定。上述数学和
接口候选仍待维护者批准，故不能据此合并、冻结或关闭 Issue #3。

## 配套完善

- 所有合成参数继续标记为候选，并在配置和合同中记录简短量纲/数量级依据；
- JSON Schema 明确为顶层文档索引，validate_config.py 是唯一严格校验入口；
- 指标定义补充公式、原始信号、轴聚合、时间原点、无效数据与结果分类；
- CTL-REQ-001/002 原编号及阈值未改变，适用性仍待维护者决定；
- 工作包清单登记在 Issue #3；登记不等于勾选、批准或关闭 Issue。

## 实际本地合同验证

下列记录仅说明配置合同与反例测试的执行状态：

| 命令 | 环境 | 实际结果 |
|---|---|---|
| python validate_config.py --config configs/b0_g0_contract.v1.json | WSL Ubuntu，B0 track | 通过；只证明默认候选合同可加载 |
| python -m ruff check . | WSL Ubuntu，05_integration/b0 | 通过；只检查 G0 Python 合同 track |
| /home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m pytest -q | WSL Ubuntu，05_integration/b0 | 132 passed；包含四轮评审的反例、逐事件结构反例、公式/判定方向篡改反例，以及多速率、饱和窗口、组合初态、reset 重放边界和奇/偶 runtime-reset 局部时序反例 |
| cmake/build/ctest preset development-readiness-debug | WSL Ubuntu，开发就绪 probe | 2/2 CTest 通过；仅为工具链/绑定探针 |
| python -m pytest --tb=short -v | WSL Ubuntu，02_estimation/python | 9 xfailed、1 skipped；已执行但不是 B0 完成证据 |

仍须在提交后观察 PR 强制 CI；远程 CI 的通过不能提前宣称。未执行或 xfail/skip 的项目
不得称为 B0 实现或性能通过。

## 待维护者集中批准

1. 合成包线、惯量、力矩界、IMU 与 gain 候选；
2. 条件积分加回算的离散抗饱和合同；
3. 所有场景阈值、窗口、seed 与指标定义；
4. CTL-REQ-001/002 的适用性和批准后版本策略；
5. 批准后新的 b0-g0-contract/v2 配置、校验器合同与维护者决定记录；
6. 允许的跨类型事件并行组合（当前没有）。

在这些决定完成前，不合并或冻结 G0，不关闭 Issue #3，不启动 G1/G2/G3。
