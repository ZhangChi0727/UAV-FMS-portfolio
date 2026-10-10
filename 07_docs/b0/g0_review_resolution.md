# PR #11 G0 评审修复记录

**状态：修复待复审，仍为 proposed_pending_maintainer_approval。**

本记录处理 Project Administrator 对 PR #11 基线 fd5615f 的合同评审发现。它记录
“发现 → 合同/代码 → 反例测试”的对应关系；不构成算法、仿真、HIL、飞行或需求符合性
证据，也不表示 G0 已冻结。

## 已处理的阻塞发现

| 发现 | 合同与实现改动 | 关键反例测试 |
|---|---|---|
| P1：actual - limited 未覆盖 request 限幅误差 | actuator_contract/antiwindup 明确条件积分、same-tick limited-requested 回算、lag feedback、每轴增益、离散式、reset 与时刻 | test_rejects_incomplete_or_contradictory_antiwindup_contract |
| P1：阶跃稳定时间从 event end 起算且公共窗口掩盖失败 | acceptance_policy 区分 command start、disturbance end、initial tick 0；六个 step event 各有 ID、窗口和三个准则 | test_rejects_event_order_overlap_and_unobservable_settling_windows；test_rejects_silent_weakening_of_step_acceptance |
| P1：reset/step、初态、单位、滤波和速率界仍由未来实现决定 | interface_contract、initialization_contract、estimator/controller 合同固定消息、签名、tick 0、字段所有权、增益单位、微分滤波和角速度界 | test_rejects_incomplete_interfaces_and_initialization；test_rejects_incomplete_or_contradictory_antiwindup_contract |
| P1：验收项、信号或真实饱和可被静默删弱 | metric_definitions 固定信号依赖；required scenario/event metrics 校验；饱和需要 event 内正持续时间触发准则 | test_rejects_silent_weakening_of_step_acceptance；test_saturation_case_requires_excitation_and_positive_trigger |
| P2：事件重叠、驻留窗口和 IMU/estimator 周期缺少跨字段约束 | 半开 event 语义、同信号重叠拒绝、声明式跨类型白名单、dwell 容量、IMU/estimator/controller 同周期消费合同 | test_rejects_incompatible_sampling_and_consumption；test_rejects_event_order_overlap_and_unobservable_settling_windows |
| P2：缺字段产生 KeyError 或其他裸异常 | 每种 event 类型先做 required/allowed/type 校验；criterion/source/observation 也做类型守卫；JSON loader 拒绝重复键 | test_every_event_type_rejects_missing_required_field；test_event_unknown_and_wrong_type_errors_are_contract_errors；test_loader_rejects_nonfinite_and_duplicate_json |

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
| /home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m pytest -q | WSL Ubuntu，05_integration/b0 | 79 passed；包含评审列出的反例、逐事件结构反例，以及公式和判定方向篡改反例 |
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
