# B0 G1 对象与传感器实施工作单

状态：`2026-10-11 已核验开发就绪，授权 TC 执行至可评审状态`。本文件为 Issue #4 的实施工作单，
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
- 依赖：G0 v2 merge SHA `3741cb1cef9353b64021aeeeb058e9917f3596cd`、批准包、`requirements/b0-dev.txt`、WSL venv
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
- 四元数：每个有效 step 后 `|norm(q)-1| <= 1e-12`（G1 工程验收）；比较姿态时接受
  q 与 -q。
- RK4 步长减半：初始 `q_nb=[1,0,0,0]`、`omega_b=[0,0,0]`，恒定 `tau=[0.01,-0.01,0.005] Nm`、总时域 `T=0.05 s`，
  以 `dt=0.0025 s` 与 `dt/2=0.00125 s` 的终点分别对同一个 `dt/16=0.00015625 s`
  RK4 参考比较；两种步长均须满足姿态误差 `<=1e-8 rad`、角速度误差 `<=1e-8 rad/s`。
  必须报告两种步长的误差；只有有实际下降证据才可宣称误差下降，若接近舍入噪声而无法
  分辨下降，则如实记录，不宣称测得四阶或其他收敛阶数。步长差只能作为收敛证据，不能替代参考解。姿态使用
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
  解析指数参考与 double 舍入量级，已作为工程验收设计审阅通过，不构成实测结果。
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

### 已审阅的数值决策表

| 项目 | 候选定义 | 依据 | 状态 |
|---|---|---|---|
| 四元数范数 | 每个有效 step 后 `abs(norm(q)-1) <= 1e-12` | double 归一化后的直接范数误差 | 已审阅工程设计，待实现验证 |
| 主惯量解析 | x/y/z 各 `+/-0.01 Nm`，`q0=identity`、`omega0=0`，`dt=0.00025 s`，`T=0.01 s`；分别比较 `omega` (rad/s) 与 `theta` (rad)，绝对误差 `1e-10` | `omega=tau*t/I`、`theta=0.5*tau*t^2/I` 独立解析解 | 已审阅工程设计，待实现验证 |
| RK4 收敛 | `q0=identity`、`omega0=0`、`tau=[.01,-.01,.005] Nm`、`T=.05 s`；比较终点 `dt=.0025` 与 `.00125 s` 相对同一 `dt/16=.00015625 s` RK4 参考；两者姿态 `<=1e-8 rad`、角速率 `<=1e-8 rad/s`，报告误差下降或不可分辨 | 同方法细步长参考只用于误差量级；定轴解析用例是独立正确性证据；不宣称阶数测试 | 已审阅工程设计，待实现验证 |
| 执行器 | `y0=0`，target 每步恒定，精确 ZOH `y_next=target+(y-target)exp(-dt/tau)`，`dt=.0025 s`、`T=.05 s`，误差 `1e-10 Nm` | 与常值输入解析指数匹配；正/负限值和零 target fixture，非法超限另测 | 已审阅工程设计，待实现验证 |

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

G0 授权追认和 PR #11 合并已完成，Issue #4 已完成 ready 交接。用户于 2026-10-11
授权本轮 G1 实施及评审流程。TC 可创建实施分支、编写组件和提交真实实现 PR；完成下列
交付后交回既有 PA 主会话评审，不自行宣布 G1 验收通过或继续 G2/G3。

## 本轮就绪核验与责任

PA 已核验 Windows 与 Ubuntu 同为 `016a259aecd1d00812686a8009678272e9b1b5df`、
工作区干净，包含 G0 merge SHA。Ubuntu Python 3.11.17 的既有 venv 实跑 G0 默认
v2 校验、162 项测试及 Ruff 通过。Issue #4 已明确依赖、执行责任和验收交接。
本地 CMake 可用性不作为 Python G1 开工门槛；保留远程 development-readiness 检查，
不得把其成功说成本地 C++ 构建成功。

执行者：Task Carrier；独立评审：既有 Project Administrator 主会话
`019f9ef3-4a0c-79f1-99d4-c8415f62bd29`。每个下列步骤是同一个 G1 PR 内的提交单元，
不是新增阶段 PR。执行状态只在 Issue #4 维护为 in progress、review、done 等。

## 实施顺序与交付

### 第一步 保护工作单与建立实施分支

先检查两侧 HEAD、分支和未提交内容；将本工作单修改纳入 G1 分支首个提交，通过 Git
同步到 Ubuntu，再以 Ubuntu 为唯一活跃实现副本。已有同名分支先核验是否可复用，
禁止覆盖、强推、复制覆盖式同步或无关分支删除。保留 Windows 作为同步副本。
读取 AGENTS.md 和项目治理文档，复用 requirements/b0-dev.txt 与既有 venv，不安装
本阶段不需要的 MATLAB、PX4、PyTorch 或新 MCP。

### 第二步 最小类型与合同适配

在 `01_simulation/b0` 实现最小消息/状态类型、配置读取及四元数工具；可将共用工具放入
同目录独立文件，避免相互导入循环，不搭建通用框架。先通过 G0 校验再提取配置，
不得复制一套隐式默认参数。列出每个本地字段到 v2 字段的映射，特别说明 IMU 输入
中 truth、外生 a_n、采样时间的来源；a_n 由合成夹具明确提供，不引入平移动力学。
若 IMU.sample 的 truth_state 不含 a_n，显式细化接口并记录映射，不能静默假定任意运动
都满足 a_n=0。传出数组不得让调用者意外修改组件内部状态。

四元数辅助函数测试使用独立解析期望值，不能用被测乘法/旋转函数生成自身预期答案。
拒绝零范数及非有限输入；固定 NED/FRD、Hamilton、scalar-first 和 body-to-NED 方向。

### 第三步 Plant

实现旋转刚体 RK4、状态归一化和 reset。惯量检查与 v2 合同一致；输入无效时不得
部分推进状态或时间。定轴解析比较须由解析角构造精确 sin/cos 四元数，不用小角度
近似四元数冒充 `1e-10 rad` 的参考。覆盖 x/y/z 正负方向、静止、q/-q 等价、
错误形状、NaN/Inf、非正 dt、非法初态和重复 reset；落实上表的数值门槛。

### 第四步 Actuator

实现精确一阶零阶保持响应，不重新计算 controller clamp。合成消息分别覆盖正负限值、
零输入、held command 的原时间戳、配对反馈、非法超限和 reset 后旧缓存失效。
按 G0 合同验证时间及消息一致性；拒绝非法输入而不静默修正。解析夹具独立计算终点，
同时检查反馈字段，不仅检查 torque 数值。

### 第五步 IMU 与局部时间测试

实现理想量、恒定 body bias 和独立每样本 Gaussian 噪声。用可注入的可控随机源测试
噪声缩放、各轴/各传感器取样和调用顺序；以真实种子生成器验证 reset 重放。
不依赖一次样本均值恰好接近零来判定模型正确。非法采样不得消耗随机流或改变有效状态。
以静止、解析正负轴旋转和显式外生加速度夹具检查 specific-force 符号与坐标方向。
样本时间用整数 tick 派生。R=1000/R=1001 测试由有限合成调用序列驱动组件，
不建立完整 scheduler、estimator/controller 或闭环 runner。

### 第六步 CI 与证据

新增 G1 Python CI job，工作目录为 `01_simulation/b0`，使用既有固定依赖；执行
Ruff、组件 pytest 和可复现数值证据入口。G1 不得 skip/xfail，不能以零测试收集成功
作为验证；保留 G0、导航历史和 development-readiness jobs，分别报告结果。

提交一个可重复运行的轻量数值证据入口及小型审阅证据：解析用例每轴误差、两种步长
相对共享参考的姿态/角速度误差、执行器解析误差、判定与局限。证据记录生成命令、
实现提交 SHA、配置文件 hash、依赖版本、seed、单位和容差。允许证据提交晚于实现
提交，但不得将记录提交 SHA 冒充已测实现 SHA。不提交大型生成导出物或 notebook 输出；
遵循仓库既有 artifact 存储规则，RESULTS.md 只链接真实保留的结果。

在各 track 内分别复跑 G1 和 G0；G0 执行 v1/v2/default CLI、pytest、Ruff。
检查工作树差异和 PR 完整 base..HEAD 差异。最新 head 的必需 CI 全绿后才交评审。
局部解析/组件结果不得称为闭环 SIL、HIL 或飞行验证。

## 可评审门槛与交回方式

- [ ] 单一 G1 实施 PR 关联 Issue #4，范围无 G2/G3 实现或 G0 参数变更。
- [ ] Plant、Actuator、IMU 及合同映射完整，无占位实现。
- [ ] 正例、边界、非法输入、状态不变性和 reset/seed 重放均有强制测试。
- [ ] 已审阅数值门槛有实际证据，不为通过测试而放宽；无法判定的收敛阶数如实报告。
- [ ] G1/G0 本地检查、最新远程 CI 和完整差异检查通过，历史导航预期失败单列。
- [ ] 双工作区提交一致或明确说明同步边界，未提交修改已保护。
- [ ] PR 描述包含变更清单、工作单逐项证据、准确 SHA、命令、结果和未决风险。

TC 获授权提交、推送、创建并附加 PR、更新 Issue #4 为执行/评审状态，以及向既有 PA
主会话发送评审请求。发现缺陷可在本范围内修复并重新验证；遇到必须改变 G0 合同、
新增范围、凭据或破坏性操作时先交 PA/用户决定。不要新建同名 PA 代替独立评审。
达到可评审状态后停止实现，发送 PR URL、head SHA、工作单关闭矩阵、证据路径和 CI 链接；
由 PA 独立评审。不得在评审前合并、自行关闭 Issue #4 或开始下一阶段。
