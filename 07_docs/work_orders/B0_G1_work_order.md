# B0 G1 对象与传感器实施子工作单（条件定稿）

状态：`条件定稿，待历史 G0 授权来源确认；依赖 PR #11 合并后启动`。本文件仅为 Issue #4 的实施交接规划，
不表示 G1 已开始、对象/IMU 已实现或任何性能通过。对应未来一个独立 G1 实施 PR；建议分支
`codex/b0-g1-plant-imu`，以 G0 合并后的 `main` 为起点。

## 输入与可追溯性

- 批准配置：`05_integration/b0/configs/b0_g0_contract.v2.json`，技术批准提交
  `1fd66551c0143a93f7b0f1e0bff19df32b1bb5b0`，决定记录
  `07_docs/b0/g0_approval_decision.md`。不得复制另一套参数默认值。
- v1 `05_integration/b0/configs/b0_g0_contract.v1.json` 仅作历史回归；其基点
  `046674dcb391983345a33d683331bcf2e155dcb1` 不是批准 v2 的依据。
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
   `Actuator.step(torque_command, dt_s) -> ActuatorFeedback`。G1 输入字段严格使用批准消息
   `limited_torque_body_Nm`，不建立 `limited_target_torque_body_Nm` 别名；actuator 不重新
   计算 clamp，controller 的唯一限幅责任在 G2。
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
- 主惯量定轴解析用例：初始 `q_nb=[1,0,0,0]`、`omega_b=[0,0,0]`，分别对 x/y/z 轴施加 `+/-0.01 Nm`，
  `dt=0.00025 s`、总时域 `0.01 s`；以 `omega_i(t)=tau_i t/I_i` 和小角度
  `theta_i(t)=0.5 tau_i t^2/I_i` 为参考，逐轴比较符号和绝对误差 `1e-10`。
- 四元数：每个有效 step 后 `|norm(q)-1| <= 1e-12`（候选 G1 gate）；比较姿态时接受
  q 与 -q。
- RK4 步长减半：初始 `q_nb=[1,0,0,0]`、`omega_b=[0,0,0]`，恒定 `tau=[0.01,-0.01,0.005] Nm`、总时域 `0.05 s`，
  以 `dt=0.0025 s` 与 `dt/2=0.00125 s` 的结果分别对高精度参考（连续方程用
  `dt/16` RK4）比较；步长差只能作为收敛证据，不能替代参考解。姿态使用
  对 `q_delta=normalize(q_ref^{-1}⊗q)` 使用 `2*atan2(norm(q_delta[1:4]), abs(q_delta[0]))`，
  输入为 scalar-first `[w,x,y,z]`，零范数输入非法；容差 `1e-8 rad`，角速度误差
  `1e-8 rad/s`。纯数学回归例：identity 对 identity 得 `0`；`q` 与 `-q` 得相同距离；
  `q_delta=[cos(ε/2),sin(ε/2),0,0]` 得 `abs(ε)`，其中 `0<=ε<=π`（极小 ε 用 `atan2` 保持稳定）；
  `q_delta=[√2/2,0,0,√2/2]` 得 `π/2`。

## 执行器验收设计

- 对一阶 bounded 响应使用解析参考 `y(t)=target+(y0-target)exp(-t/tau)`；`target` 在一个步长内保持恒定；fixture 明确 `y0=0`，各轴分别测试正/负限值和 `target=0`，限值与 tau 只从 v2 读取；非法超限输入另测，不改变 G0 的限幅责任。
- 执行器采用批准一阶模型的零阶保持精确离散更新
  `y_next=target+(y-target)*exp(-dt/tau)`；初始候选数值误差为 torque absolute
  `1e-10 Nm`（double、`dt=0.0025 s`、时域 `0.05 s`、固定 tick）。该容差依据为
  解析指数参考与 double 舍入量级，须由维护者在 G1 开工前确认；未确认前标记为候选，
  不得称为已批准门槛。
- 用合成 TorqueCommand 夹具验证 limited target 的配对、held command 原 timestamp、
  feedback paired-command timestamp、reset 清除旧缓存，以及 R=1000/R=1001 的局部相位；
  不测试 controller 的首次 dt 实现，那属于 G2/G3。
- saturation flag 只能被夹具提供/核对，不把 actuator 变成第二个限幅器。

## IMU 验收设计

- 质心静止、zero bias/noise 必须生成 `[0,0,-9.80665] m/s²` specific force 和 zero gyro。
- 对已知 q_nb 的解析旋转，验证 `f_b = R_bn(a_n-g_n)` 和 body-frame angular rate；正负
  轴各测试，明确不引入平移动力学或杆臂效应。
- 噪声/偏置按 v2 的“每样本独立 Gaussian 标准差 + 恒定 body bias”语义生成；固定 seed
  的同一 reset trace 必须逐样本可重复，改变 seed 只验证随机流改变，不宣称统计性能。另以
  zero-noise/zero-bias fixture、单独 bias fixture 和单独 noise fixture 分离验证三种来源。
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

上述 `1e-12` quaternion norm、`1e-8` 姿态/角速度收敛、`1e-10 Nm` actuator 候选已作为
本工作单的待执行 oracle；它们不因测试结果自动放宽。姿态范数、姿态角误差、角速度误差、
执行器误差分别记录，不能互相替代。若对象误差不满足，保留失败 artifact、分析原因并提出
新决定。

每项测试保留：配置版本/hash、代码 SHA、seed、dt/tick、解析参考、实际输出、绝对/相对
误差、单位、容差和终止状态。不要提交 notebook 输出、私有路径、完整文献或 credentials。

### 待主会话审阅的数值决策表

| 项目 | 候选定义 | 依据 | 状态 |
|---|---|---|---|
| 四元数范数 | 每个有效 step 后 `abs(norm(q)-1) <= 1e-12` | double 归一化后的直接范数误差 | 待主会话审阅 |
| 主惯量解析 | x/y/z 各 `+/-0.01 Nm`，`omega0=0`，`dt=0.00025 s`，`T=0.01 s`；分别比较 `omega` (rad/s) 与 `theta` (rad)，绝对误差 `1e-10` | `omega=tau*t/I`、`theta=0.5*tau*t^2/I` 独立解析解 | 待主会话审阅 |
| RK4 收敛 | `tau=[.01,-.01,.005] Nm`，`T=.05 s`；`dt=.0025` 与 `.00125 s`，参考为同一 RK4 方法 `dt/16`；姿态 `1e-8 rad`、角速率 `1e-8 rad/s` | 参考解用于误差量级，步长差只作收敛证据，不等同独立真值 | 待主会话审阅 |
| 执行器 | 精确一阶零阶保持 `y_next=target+(y-target)exp(-dt/tau)`，`dt=.0025 s`，`T=.05 s`，误差 `1e-10 Nm` | 与常值输入解析指数完全匹配；容差仍需维护者确认 | 待主会话审阅 |

## 文件、命令、CI 与交付

建议文件落点：`01_simulation/b0/plant.py`、`01_simulation/b0/actuator.py`、
`01_simulation/b0/imu.py`，以及同目录 `tests/`；若资产审计发现更合适的现有路径，须在
G1 PR 记录映射理由，不搬迁遗留导航代码。

G1 开始后在 Linux 活跃 checkout 中明确进入 `01_simulation/b0`，以下命令的相对路径均
相对于该目录；未实现阶段不运行这些未来入口：

```text
cd /home/chi/src/uav-fms-portfolio/01_simulation/b0
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m pytest -q tests
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m ruff check .
git diff --check
```

必要时补充独立解析 oracle 命令，但不得从根目录收集 pytest。新增测试进入 CI 的 G1 track；
G0 CTest/development-readiness probe 继续单独报告。G1 PR 更新 PR 描述、实际命令、
RESULTS.md 的已验证结果（仅在有保留 artifact 时）和 Issue #4，不改写 G0 历史记录。

## 完成定义与停止点

G1 实施 PR 完成需有批准 v2 输入、上述组件实现、无 skip/xfail 的强制组件测试、解析误差
和收敛记录、CI 结果、独立评审及清洁工作区。它不得宣称 G2/G3 或 B0 完成。

本条件定稿在历史 G0 授权来源确认、PR #11 合并、G1 数值 oracle 执行确认和 Issue #4 进入 `ready` 前不表示 G1
已实现；当前不创建实施分支、空 PR 或算法代码。
