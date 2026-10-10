# B0 G1 对象与传感器实施子工作单（草案）

状态：`草案，依赖 G0 维护者批准与 PR #11 合并`。本文件仅为 Issue #4 的实施交接规划，
不表示 G1 已开始、对象/IMU 已实现或任何性能通过。对应未来一个独立 G1 实施 PR；建议分支
`codex/b0-g1-plant-imu`，以 G0 合并后的 `main` 为起点。

## 输入与可追溯性

- 批准配置：`05_integration/b0/configs/b0_g0_contract.v2.json`（当前尚不存在；由维护者
  决定后生成）。不得复制另一套参数默认值。
- 当前候选参考：v1 `05_integration/b0/configs/b0_g0_contract.v1.json`，基点
  `046674dcb391983345a33d683331bcf2e155dcb1`；该 SHA 不是批准 v2 的依据。
- schema 只作顶层文档索引；`05_integration/b0/validate_config.py` 的字段/跨字段规则和
  v2 决定记录是实施前必须核对的合同入口。
- 依赖：G0 v2 合并后的准确 merge SHA、批准包、`requirements/b0-dev.txt`、WSL venv
  `/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python`。禁止实现者自行重填或静默修改参数。

## 范围与边界

范围限定为 Python 旋转刚体、有限一阶执行器响应、IMU 生成及组件级测试；默认落点为
`01_simulation/b0/`，与遗留生成器隔离。可以建立真实模块和测试所需的最小目录，不创建
空算法占位。

不得实现：姿态估计器、PID/C++ 控制核心、pybind 控制绑定、闭环 runner、G3 指标器，或
平移/导航/硬件/HIL/论文范围。不得把 estimator/controller 真值输入接入 G1。G1 可使用
明确构造的 TorqueCommand fixture 测 actuator，不为 fixture 提前实现控制器。

## 接口与状态所有权

1. `Plant.reset(PlantInitialState, reset_epoch) -> PlantState`；
   `Plant.step(actual_torque_body_Nm, dt_s) -> PlantState`。
2. `Actuator.reset(ActuatorInitialState, reset_epoch) -> ActuatorFeedback`；
   `Actuator.step(torque_command, dt_s) -> ActuatorFeedback`。actuator 只推进 paired
   `limited_target_torque_body_Nm`，不重新计算 clamp；controller 的唯一限幅责任在 G2。
3. `IMU.reset(IMUInitialState, reset_epoch, rng_seed) -> IMUState`；
   `IMU.sample(truth_state, sample_timestamp_s) -> IMUSample`。truth 只在 sensor boundary
   使用，不外泄给 estimator/controller。
4. 所有公开输入先检查形状、有限值、单位和 timestamp；错误输入抛出明确的
   `ContractValidationError`/组件异常并保持上一有效状态。`dt_s` 必须有限且严格为正。
5. 保留 NED/FRD、SI、scalar-first Hamilton `q_nb`（body→NED）；所有消息含 scenario-clock
   timestamp、validity，必要时含 `reset_epoch`。

## 动力学验收设计

模型实现绕质心旋转：`I*dot(omega_b) + omega_b × (I*omega_b) = tau_b`，四元数按 G0
`q_nb` 方向传播并归一化。候选参数只能从批准 v2 读取。

- 零力矩/静止：identity q、zero rate、zero torque 在无噪声 fixture 下保持；specific force
  不在 plant 内计算。
- 主惯量定轴解析用例：选定单一 body 轴、零初始 rate，比较角速度与姿态的解析趋势/符号；
  正负力矩各一例，验证 `tau` 符号、NED/FRD 映射和 q/-q 等价。
- 四元数：每个有效 step 后 `|norm(q)-1| <= 1e-12`（候选 G1 gate）；比较姿态时接受
  q 与 -q。
- RK4 步长减半：同一输入在 `dt` 与 `dt/2` 下比较终点姿态/角速度；初始候选为
  `abs(angle_error) <= 1e-8 rad`、`abs(rate_error) <= 1e-8 rad/s`，正式开工前以批准
  v2 和解析量级复核，不得看结果后放宽。

## 执行器验收设计

- 对一阶 bounded 响应使用解析参考 `y(t)=target+(y0-target)exp(-t/tau)`；边界值、正负
  轴、零 target 和限值内外输入均测试。当前候选 tau/limits 只从 v2 读取。
- 初始候选数值误差为 torque absolute `1e-10 Nm`（double、固定 tick）并记录解析参考、
  dt、误差和终止状态；若批准包另有数值约束，以 v2 为准并更新本工作单。
- 用合成 TorqueCommand 夹具验证 limited target 的配对、held command 原 timestamp、
  feedback paired-command timestamp、reset 清除旧缓存，以及 R=1000/R=1001 的局部相位；
  不测试 controller 的首次 dt 实现，那属于 G2/G3。
- saturation flag 只能被夹具提供/核对，不把 actuator 变成第二个限幅器。

## IMU 验收设计

- 质心静止、zero bias/noise 必须生成 `[0,0,-9.80665] m/s²` specific force 和 zero gyro。
- 对已知 q_nb 的解析旋转，验证 `f_b = R_bn(a_n-g_n)` 和 body-frame angular rate；正负
  轴各测试，明确不引入平移动力学或杆臂效应。
- 噪声/偏置按 v2 的“每样本独立 Gaussian 标准差 + 恒定 body bias”语义生成；固定 seed
  的同一 reset trace 必须逐样本可重复，改变 seed 不得误称为统计性能结果。
- IMU 每 2 base ticks 在区间末采样；无新样本时不调用 estimator（由 G0 schedule 约束），
  但 G1 只验证 sample timestamp、validity、seed/reset 和输入缓存清除。

## 时序与 reset 验收

以 G0 v2 为唯一时序来源，至少保留以下人工构造测试：

| 边界 | 预期 |
|---|---|
| 启动 epoch local tick 0 | reset-only；无 plant/actuator/IMU step；C_reset timestamp 0 |
| R=1000 | local due estimator/IMU/controller 在 global 1002、1004；首个有效 dt=0.005 s |
| R=1001 | local due estimator/IMU/controller 在 global 1003、1005；首个有效 dt=0.005 s |
| 任一 reset tick | 清除旧 held command/feedback；global timestamp 不回退；reset state 不计 estimator update |

G1 只实现并测试 plant/actuator/IMU 自身所需 reset state；估计器/controller 首次 dt 的运行时
验证交给 G2，完整 replay/调度和场景执行交给 G3。

## 数值 oracle、容差与证据

上述 `1e-12` quaternion norm、`1e-8` step-halving 候选和 `1e-10 Nm` actuator 候选必须
在 G1 开工前由批准 v2、解析参考量级和维护者审阅共同确定。实施者不得看到结果后修改
阈值以制造通过；若对象误差不满足，保留失败 artifact、分析原因并提出变更决定。

每项测试保留：配置版本/hash、代码 SHA、seed、dt/tick、解析参考、实际输出、绝对/相对
误差、单位、容差和终止状态。不要提交 notebook 输出、私有路径、完整文献或 credentials。

## 文件、命令、CI 与交付

建议文件落点：`01_simulation/b0/plant.py`、`01_simulation/b0/actuator.py`、
`01_simulation/b0/imu.py`，以及同目录 `tests/`；若资产审计发现更合适的现有路径，须在
G1 PR 记录映射理由，不搬迁遗留导航代码。

在 Linux 活跃 checkout、B0 track 内运行：

```text
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m pytest -q 01_simulation/b0/tests
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m ruff check 01_simulation/b0
git diff --check
```

必要时补充独立解析 oracle 命令，但不得从根目录收集 pytest。新增测试进入 CI 的 G1 track；
G0 CTest/development-readiness probe 继续单独报告。G1 PR 更新 PR 描述、实际命令、
RESULTS.md 的已验证结果（仅在有保留 artifact 时）和 Issue #4，不改写 G0 历史记录。

## 完成定义与停止点

G1 实施 PR 完成需有批准 v2 输入、上述组件实现、无 skip/xfail 的强制组件测试、解析误差
和收敛记录、CI 结果、独立评审及清洁工作区。它不得宣称 G2/G3 或 B0 完成。

本草案在 G0 v2 合并、G1 数值 oracle 确认和 Issue #4 进入 `ready` 前保持草案；当前不创建
实施分支、空 PR 或算法代码。
