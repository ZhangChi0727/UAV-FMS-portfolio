# B0 G2 估计器与控制器开发工作单

日期：2026-10-14（Australia/Perth）。执行：Task Carrier（TC）。设计与独立评审：原 PA。

## 1 目标与授权

交付可独立验证的六轴姿态估计器和 C++17 级联姿态/角速度控制器，使 G3 能直接使用
明确的接口、数值行为、构建命令和保留证据。G2 是组件开发门，不以完整闭环性能作为出口。

用户直接要求：“那么我们启动G2开发，请你编写G2详细工作单并交TC执行。”
允许本单范围内设计、代码、测试、绑定、CI、证据和文档实现，创建分支/Draft PR，
更新 Issue #5/#6，并向原 PA 交接评审和修复。允许复用既有工具及隔离环境；
需要系统权限、付费资源、硬件操作或冻结规范变更时，说明具体需求再请求对应权限。
用户无需为本单中普通实现步骤反复授权。

实施分成两个顺序 PR，均由本单约束，每个 PR 对应一个子工作包：

| 子工作包 | 执行 Issue | PR 目标 | 出口 |
| --- | --- | --- | --- |
| G2-A | #5 | Python 姿态估计器、接口、模块验证与证据 | 估计组件验收通过 |
| G2-B | #6 | C++17 控制核心、最小 pybind11 绑定、模块验证与证据 | 控制组件验收通过，G2 完成/G3-ready |

先 G2-A 后 G2-B，每次只有一个主实施 PR。可以提前只读分析后者，不能同时启动另一个主增量。
合并前的具体操作仍需获得对应授权；本单不授权自动合并、关闭 Issue #18/#19、删除分支或启动 G3。
G2-A 合并并经 PA 验收后，TC 可按本单继续 G2-B，无需再次取得 G2 派发授权。

## 2 开工基点与安全要求

G1.5-C 合并提交：`731f1adde0676733474e2038734cc4e2cc70c67b`（PR #20）。
已验收候选：`1663480ed06a446f9fa7ad02a32f40c27c3da19a`，两者树相同。
main CI `38408583717` 六项成功，治理 track 79 passed；原 PA 已给出 POST_MERGE_ACCEPT，
确认 G1.5-C 完成、G2-ready。此前原 PA 使用 sysmlpy 隔离环境实际运行完整 track 79 passed。
这些是开工依据，不能当作 G2 实现已通过的结果。

编单时远端 main 仍是上述 merge；本地仍在旧 C 功能分支，HEAD 是上述候选。
TC 开工重新读取远端 main、当前分支、工作树及其他 checkout。如 main 前进，先分析新增差异。
建议分支：`codex/b0-g2a-attitude-estimator`、`codex/b0-g2b-cascaded-controller`。
PR 编号以 GitHub 实际分配为准，不抢号、不复用已合并 PR #20。

本地受保护文件 `docs/work_orders/B0_G1_5_work_order.md` 尚有用户未提交修改，SHA-256：
`96d45d4215c2215bb50ea0c7b863b627fa2e7d8d64ada3bb456950a2aa0d44a5`。
保留其全部字节，不暂存、提交、恢复或清理。哈希如变化，应保护新修改而非还原旧版本。
本单由 PA 新建，可纳入 G2-A PR。仅精确暂存本轮文件，不用 `git add -A`。
不强推，不破坏性 reset，不自动删除分支，不混入无关工作。

开工必须读取 AGENTS、README、章程、开发基线、架构、roadmap、G0 v2 和 validator、
G1 contract/实现/测试、正式需求/验证目录、G1.5-B S/M/A、G1.5-C 工具及评审记录、本单。
Issue #5/#6 已存在，应更新其旧 `07_docs` 路径及依赖，不创建重复执行 Issue。
Issue #18/#19 的行政状态不阻塞 G2，但不得擅自关闭它们。

## 3 需求与配置权威

- 产品边界：B0 v0.2 开发基线与章程。
- 数值与运行合同：`05_integration/b0/configs/b0_g0_contract.v2.json` 及其 validator。
- 需求：`systems_engineering/requirements/b0_requirements.json`，模型：`systems_engineering/models/b0_system.sysml`。
- 验证设计：`systems_engineering/verification/b0_verification_specifications.json`。
- 执行/证据：G1.5-C 独立账本/schema/检查器，保留冻结目录的 planned/not_run 历史字节。

不得复制一套 G0 默认值；加载批准配置并记录版本、Git blob 和内容哈希。
冻结文件内的 future/candidate 历史状态由审批及当前状态层解释，不能为了“已实现”回写历史源。
不修改 G0 v1/v2、G1 行为、冻结需求/模型语义/验证判据，不重编号 NAV/CTL/FDI/B0 身份。
实现路径、测试与执行结果放当前实现/证据层。确需规范变更时提出版本化变更请求及影响链。

## 4 包含与排除

包含：Python quaternion gyro propagation 与基本加速度计倾斜互补修正；
C++17 attitude P + body-rate PID；唯一力矩限幅、条件积分与反算抗饱和；
reset、时间戳、无效输入、paired command/feedback；最小 Python 绑定和测试夹具；
组件证据、CI、接口说明及 G3 接入交接。

排除：G3 完整调度器/闭环 runner/八类场景性能验收、G4 发布包、导航/EKF/UKF、
geometric/LQR/MPC、学习算法、偏置估计研究、硬件/PX4/HIL/飞行、论文及外部验证套件集成。
组件测试可生成解析 IMU/估计状态/反馈序列，但不能把夹具命名成已完成真实闭环。
模块级抗饱和撤除试验属于本轮；完整系统的恢复时间/超调结论留给 G3。

## 5 S0 设计与验证合同评审

每个 PR 首先提交小型设计记录与逐项验证矩阵，向原 PA 申请 DESIGN_ACCEPT，再实现数值核心。
此前出现过内部同名代理误签门禁；只有 PA 会话 `019f9ef3-4a0c-79f1-99d4-c8415f62bd29`
的明确结论有效。记录精确提交、批准来源和真实时间，不倒填既有批准。
等待设计评审期间可搭建构建/类型/无算法测试夹具，不提前实现被阻塞的算法决定。

本次检查发现 G0 没有规定互补修正增益、加速度模长门限、最大修正步长；
controller 也未固定外环误差向量映射、导数低通离散化及首步历史值。
TC 必须在 S0 列出这些未决项、可选解释、建议公式、单位、稳定性与独立测试依据。
新增小型版本化 G2 实现配置（落在各组件 b0/configs 内），标为实现设计参数，
明确哪些来自 G0、哪些是本轮设计选择；不得声称新值已经冻结在 G0 或由文献直接给出。

PA 可批准与现有规范一致的有界实现选择和组件数值容差。若选择实质改变运行包线、
需求条件、既有判据或时间合同，须先提交规范变更请求给用户决定。
尤其不得声称现有 G0 已定义完整加速度门控；先把缺口解释清楚再选择门控实现。
门控仅用实际 IMU/估计状态，不用场景事件标签或 truth。记录模长门限无法检测所有横向加速度的局限。

每项测试在实现前定义输入、独立 oracle、判据、容差来源及浮点比较方法。
复用历史已定位文献时保留具体定位；需新方法论依据先核对原始来源，不让全面文献综述成为实施前置。
G0 控制增益使用 initial 值；本轮不以调参达成 G3 性能目标。

## 6 G2-A 估计器实施

推荐目录 `02_estimation/b0/`，与 `02_estimation/python` 的 EXT-NAV 隔离。
提供真实 `estimator.py`、消息/参数适配、测试、README 和必要的配置，不建立空算法占位。
已有 `01_simulation/b0/contract.py` 的 IMUSample 可通过显式路径/薄适配复用；
不能反向让 G1 依赖 G2，也不能移动或修改 G1 冻结文件来共享类型。

公开接口遵循 G0：

```text
reset(EstimatorInitialState, reset_epoch, rng_seed) -> StateEstimate
step(imu_sample) -> StateEstimate
```

初始姿态/角速度使用明确估计器初态。`scenario.initial_q_nb` 与 offset 是 plant 所有，
不得自动当作估计器初态。运行时输入只有 IMU，不接受 PlantState、SensorTruth、真实偏置或误差。
无随机内部行为时保留 seed 接口并解释其不影响确定性；不得创建伪噪声估计。

数值与行为要求：

- 以 float64、scalar-first Hamilton `q_nb`（body→NED）传播；有效 gyro 与时间增量由输入推导，
  正确处理零角速度与小角度，传播/修正后归一化并遵循 G0 sign policy。
- 第一次有效样本的 dt 来自 reset boundary；默认 period 为 2×0.0025 s，
  并从批准配置读取而非写死。后续 due/缺样/重复规则按 G0 定义，不能插入未声明更新。
- 加速度计静止 FRD 测得 `[0,0,-g]`；修正符号与 q 方向一致，修正限于重力可观察倾斜。
- 六轴 IMU 无绝对 yaw 观测，不使用真实 yaw 拉回；以不同初始化 yaw 的重力等价实验说明局限。
- 输出 StateEstimate 包含批准字段、timestamp、validity；门控/拒绝/归一化等诊断用独立调试输出，
  不擅自改造冻结消息。诊断可用于独立验证，不能由被测实现自行宣布验收通过。
- 输入校验失败时状态、上次时间戳、缓存和计数的所有权明确。先完整校验再原子更新，
  不出现“抛错但已改变 quaternion/时间”的部分执行。返回/异常语义遵循批准接口。

必须覆盖：静止、各轴正负恒定率解析传播、小角度、q/-q、模长与有限值；
各轴正负初始倾斜纠正、yaw 等价与相对漂移局限；门限内外、零specific force、
非有限观测、横向加速度导致不可判别的限制；negative/zero/nonfinite dt、stale/duplicate timestamp、
wrong shape、valid=false；启动与非零全局时刻 reset、首步 dt、重复reset/replay与输入数组隔离。
使用闭式 quaternion exponential、手算静止重力/旋转结果等独立 oracle，不能全由生产 quaternion helper 自证。

## 7 G2-B 控制器实施

推荐 `03_control/b0/` 下 CMake/include/src/tests/python。核心为平台无关 C++17 double，
Python 只负责输入适配和调用，不重复实现另一套生产 PID。pybind11 使用已验证固定版本，
Catch2 延续固定提交及正确 `Catch::Approx` 用法。Eigen 只有确实需要时引入，不能让 legacy EKF 成为依赖。

公开接口遵循 G0：

```text
reset(ControllerInitialState, reset_epoch) -> TorqueCommand
step(attitude_command, state_estimate, actuator_feedback, dt_s) -> TorqueCommand
```

核心参数通过显式结构注入，适配层从批准 JSON 加载；核心不读取文件、场景或 truth。
以 G0 已定义 `conj(q_est) ⊗ q_cmd` 形成姿态误差，scalar<0 取反，half-turn 用首个非零向量分量正号破除歧义。
外环误差向量、目标角速度限幅及近零/π 行为在 S0 决定；保持与冻结姿态误差定义一致。
角速度 PID 使用测量微分及已声明低通，避免 command step 引入未规定 derivative kick。
导数历史、积分状态、同 tick request 与 next integral 的更新顺序逐步列公式，不用循环定义解当前 request。

控制器是力矩唯一限幅所有者。每次发布同时形成 requested、limited、saturated、同一个 timestamp。
恰好在限幅边界、正负越界与未越界必须分别测试。Actuator 仅消耗 limited target，绑定不能二次 clamp。

抗饱和按 G0 `/actuator_contract/antiwindup`：

```text
I_next = clamp(I + dt * (conditional_ki_rate_error
            + kaw_limit * (current_limited - current_requested)
            + kaw_lag * (feedback_actual - feedback_limited)), -I_limit, I_limit)
```

`current_limited-requested` 来自本控制 tick；lag 项来自反馈所标识的 held command。
禁止拿新 request 配旧 actual，禁止用 `actual-current_limited` 替代反馈配对差值。
requested-minus-limited 与 rate error 同号时阻止继续推向饱和的积分，减小饱和方向应允许积分。
逐轴 I_limit、两组 kaw、导数时间常数与 torque/rate limits 都从 G0 读取。
不能只用积分硬限幅代替完整反算规则。

reset 清除积分、滤波器、上一测量和 held-feedback 历史，并发布 epoch boundary 的零 TorqueCommand。
第一次正常 step 使用 reset command 配对反馈；后续检验反馈 command timestamp 与真实持有命令一致。
无效估计、命令、反馈、错误 dt 或时间戳必须拒绝并保留全部上一有效控制状态。
当前估计来自当前 due IMU；command 是时刻采样的命令，G3 的持有/采样责任要在接口说明中写清。

必须覆盖：三轴正负小误差、零误差、q/-q、π tie-break、body轴/单位；
外环和内环分开手算、rate target limit、力矩边界与paired publication；
P/I/D 各项、低通离散化、首步微分、setpoint step、纯测量变化；
unsaturated、clamp saturated、lag only、组合反馈、积分允许/阻止、撤除后模块级恢复及每轴限值；
错配/未来/陈旧反馈、首次 reset-feedback、valid=false/NaN/Inf/shape/dt；
reset/replay、绑定输入内存隔离、C++与Python入口同输入同输出。
选定反馈符号反转、anti-windup 符号/旁路错误，在隔离测试变体上证明检测，不改生产源码制造缺陷。

## 8 构建、环境与 CI

沿用 CLion/CMake 和 PyCharm；命令行是可复现执行依据，IDE 断点证明不是模块正确性证据。
不要求新 MCP 或新账户。TC 先探测实际工具和权限，复用已有开发就绪探针。

环境区分：

- Windows 系统工程：`build/venv-systems-engineering/Scripts/python.exe`，已有 Python 3.11.5、
  sysmlpy 0.33.2、pytest 8.3.5、jsonschema 4.23.0；该环境不保证含 NumPy/编译/StrictDoc。
- B0 开发依赖沿用 `requirements/b0-dev.txt` 的独立 venv。
- WSL 的 `/home/chi/src/uav-fms-portfolio` 与 Windows checkout 是不同源码树。
  WSL 如可用，按开发环境文档同步准确提交后构建，记录其真实 HEAD；不把旧 checkout 的测试当本轮结果。
  Wsl/E_ACCESSDENIED 是宿主限制，可用已探测 Windows 编译器和 Linux CI推进，不能虚报本地通过。

根 CMake 默认 legacy navigation，新增明确 B0 target/option 与 Debug/Release preset，
这些 preset 关闭 legacy、开启 B0/test，保留原选项兼容性。复用 readiness 的 Catch2/pybind11 固定来源，
但 B0 CI 必须构建真实控制器。禁止 optional-bindings 静默跳过本轮必需绑定。
新增配置不含个人路径；多配置/单配置生成器按实际工具记录。Debug/Release 各跑 CTest，至少一次 clean rebuild。

Python pytest 每个 track 内运行；新 estimator、binding、系统工程、G0/G1 各有明确 cwd。
CTest 测试入口可显式传文件但需设置对应 track 的 working directory。
保留现有六项 CI 及完整覆盖，增加 G2 模块门禁。G2-A 不假装已有控制 job；G2-B 必须构建、
测试并导出绑定路径，检查无 skips/xfails。warnings/异常/工具失败如实记录，不设 continue-on-error 放行。

## 9 原子追溯与证据交付

| 需求 | 验证规定 | G2 验收范围 |
| --- | --- | --- |
| B0-REQ-0012 | B0-VER-ESTIMATOR-PROPAGATION | A 完整模块检查 |
| B0-REQ-0013 | B0-VER-ESTIMATOR-FUSION | A 完整模块检查，前提是 S0 门控决定已接受 |
| B0-REQ-0014/0015 | B0-VER-YAW-LIMITATION / B0-VER-ACCEL-CONTAMINATION | A 模块分析/注入部分；G3 场景部分待执行 |
| B0-REQ-0007 | B0-VER-PAIRED-COMMAND | B 同 tick 发布与限幅 |
| B0-REQ-0016/0017/0018 | B0-VER-CONTROLLER-SIGN / B0-VER-CONTROLLER-SATURATION / B0-VER-ANTI-WINDUP | B 完整模块检查及规定的缺陷检测 |
| B0-REQ-0019/0020/0029 | B0-VER-INVALID-INPUT / B0-VER-RESET / B0-VER-INVALID-MEASUREMENT | A/B 各自模块证据；全组件reset及集成部分留G3 |
| B0-REQ-0003/0004/0009/0026 | B0-VER-TRUTH-BOUNDARY / B0-VER-CONVENTIONS / B0-VER-PAIRED-FEEDBACK / B0-VER-LANGUAGE-BOUNDARY | A/B 接口、单位、绑定与配对检查；运行时全链集成留G3 |

矩阵为本轮范围，不改冻结关系，也不把未列需求从总视图删除。TC S0 补充逐测试定位、
原始信号、oracle、判据、责任和本轮/后续缺口。多阶段规定仅部分执行时保持 partial，
例如 RESET 的“all stateful components integrated”前提在 G2 不能据模块 reset 宣称全部满足。

复用 G1.5-C 四维状态：结果、证据可用性、版本适用性、独立审核。测试通过不能自动 accepted。
原始产物生成在 build/临时目录/CI artifact；只提交受控索引/schema/代码/人工审核记录，
不提交日志、HTML、截图、全文或输出 notebook。记录精确被测提交、实现闭包、配置、seed、
时间语义、命令、环境、原始判据输出、文件/归档哈希、artifact身份、到期时间及review来源。

若新增组件需要 C 检查器的scope→依赖profile，做最小扩展与正负测试，
不靠执行record ID硬编码，不删旧规则，不弱化已有G1闭包。配置与binding也计入相关闭包。
verified证据通过显式cache校验bytes及expiry；默认离线unknown保留unverified，不冒称满足。
报告须呈现新/未执行/被取代/partial/accepted记录的真实状态和逐需求缺口。
生产代码不能提供自己的 pass/satisfaction verdict；独立测试/评估层生成结论。

## 10 交付顺序与评审出口

每个子工作包按顺序：

1. S0：准确基点/环境/保护文件盘点，当前状态入口同步；提交设计、参数与测试矩阵，交 PA DESIGN_ACCEPT。
2. S1：组件实现与单元测试；提交明确、可单独审查的改动，完成所有范围内正负例。
3. S2：构建/绑定（B）、必需 CI、证据链、追溯、读者说明、复现与限制；保持现有回归通过。
4. S3：Draft PR 达到 ready_for_review，交 PA 对准确 head 独立评审；REWORK 时修复并重跑受影响检查。
5. S4：具体合并授权后合并；核对 main 树、CI、证据引用、保护文件，交 PA POST_MERGE_ACCEPT。

G2-A 出口：估计器真实实现，所有规定模块测试通过，门控/限制可解释，接口可供控制器和G3使用。
G2-B 出口：控制器核心/绑定真实实现，Debug/Release/单元/负例/配对与reset检查完成，证据可审计。
两者合并并逐项验收后才宣布 G2 完成、G3-ready；不把 G2-A 单独通过写成 G2完成。

每次评审包至少包含：PR/Issue与head/base；逐条本单验收矩阵；S0决定及审批源；
实现与测试定位；实际命令/结果/失败处置；CI与保留artifact；配置/源闭包；
当前报告与未执行缺口；保护文件哈希；G3接口、安装/构建/最小调用说明。
参数不全、oracle自证、静默跳过、truth泄露、错配反馈、部分执行冒称满足均是阻塞项。
不预填测试数量或数值性能；只记录真实执行结果。

## 11 当前状态与交接

本单仅派发 G2；main 的部分入口仍显示 C active，TC 在 G2-A 中新增当前状态事件并更新入口，
引用 PR #20 merge/main CI/原PA验收和本次启动授权。保留历史冻结与顺序偏差，不改旧候选快照。
RESULTS.md 只更新已验证结果；Issue #5/#6 管 live state，roadmap 管范围，避免多处手工复制实时状态。

TC 向原 PA 会话 `019f9ef3-4a0c-79f1-99d4-c8415f62bd29` 提交 S0、可评审候选、
修复与合并后包；用户授权本单的执行和评审交接。不能用内部同名代理代替原PA门禁。
收到通过即继续下一已授权步骤；等待时说明准确对象、正在等谁及所需结论。
真实阻塞才暂停依赖工作，能独立完成的检查继续推进。不得停在“已规划”而不实现，
也不得越过具体合并、规范变更或后续阶段授权门。
