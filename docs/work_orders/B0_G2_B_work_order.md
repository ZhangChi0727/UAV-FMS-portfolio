# G2-B C++ 级联控制器详细工作单

日期：2026-10-14（Australia/Perth）。执行：Task Carrier（TC）。设计、候选及合并后评审：原 PA。
执行 Issue：#6。一个新的 G2-B PR；实际编号由 GitHub 分配。

## 1 目标与本次授权

实现平台无关 C++17 级联姿态/角速度控制核心，完成唯一力矩限幅、完整抗饱和、
reset/无效输入处理、最小 Python 绑定和受控组件测试，使 G3 有可直接调用的控制组件。

用户直接要求：“了解，那么目前尚未到达独立验证阶段，只需要受控管理即可。
请你编写G2-B详细工作单交TC执行，你来评审结果。”本单是
`B0_G2_work_order.md` 的 G2-B 执行细化；共同工程约束继续有效。
允许创建分支/Draft PR、更新 Issue #6、设计和实现、测试与 CI、证据及追溯、范围内修复，
并向原 PA 交接评审。该请求解除此前 G2-A 评审消息中“本次不派发 G2-B”的限制。
G2-A 合并后验收已完成，无需再次等待 G2-B 开工许可。

本轮开展开发期组件检查与评审验收，并受控保留必要用例。暂不另开独立验证阶段，
不创建新的一级验证目录或通用验证平台；已有系统工程验证规定/账本继续管理追溯。
用户未授权自动合并本轮 PR、关闭其他 Issue、删除分支或启动 G3。
普通实现选择由 TC 提案、原 PA 评审；需要改变冻结规范或新增系统权限时再请求对应决定。

## 2 基点、状态和工作区保护

- main/G2-A merge：`5f817ec1fb2405aa269dcf6a701a33cff846c748`（PR #21）。
- 已验收候选：`81979a6d8e5d99e50dfede6cdeac5d68f76baa5e`；合并树与候选完全一致。
- 原 PA 已给 POST_MERGE_ACCEPT；main CI `38502995877` 七项成功，
  estimator 53 passed、systems engineering 80 passed。G2-A 完成，G2-B 尚待本单实施。
- 编单时远端 main 与上述 SHA 一致，没有 open PR；Issue #6 仍显示被 G2-A 阻塞，应更新。
- 本地仍在 G2-A topic branch，HEAD 为上述候选。TC 从核对后的 main 建立
  `codex/b0-g2b-cascaded-controller`，不得把 G2-B 提交追加到已合并 PR #21。

开工核对远端/本地 HEAD、分支及工作树；main 如前进先审查增量。只有一个主工程增量。
读取 AGENTS、README、章程、开发基线、架构、roadmap、G2 总单、本单、G0 v2/validator、
G1 消息/执行器实现、G2-A StateEstimate/诊断及评审、冻结需求/规格和 C 证据工具。

保护 `docs/work_orders/B0_G1_5_work_order.md` 的用户未提交修改，其当前 SHA-256：
`96d45d4215c2215bb50ea0c7b863b627fa2e7d8d64ada3bb456950a2aa0d44a5`。
不得暂存/提交/还原；如字节变动，保护较新的修改。新建的本单可精确暂存到 G2-B PR。
不用 `git add -A`，不强推/reset，不自动清理分支或源码。切换有覆盖风险时先停报。

## 3 范围和资产落点

推荐目录 `03_control/b0/`：CMake、include/src、C++ tests、python binding/adapters/tests、
实施配置、组件证据生成器和 README。文件命名可在 S0 确定，职责必须明确且无空算法占位。
控制计算只在 C++ 核心；Python 负责配置、消息适配、执行和独立测试 oracle，
不能另写一套生产 PID。控制核心不依赖 Python、文件系统、场景 runner 或 truth 类型。

包含：同 tick paired torque command、held-command feedback 校验、reset 和时间规则，
Debug/Release 构建、C++及绑定测试、最小 estimator→controller 和 controller→actuator 接口夹具。
这些夹具只证明接口兼容，不能命名为完整闭环性能验证。

排除：G3 scheduler/全闭环/全部场景、系统恢复时间和超调性能验收、G4 发布、
真实飞行/板端/HIL、PX4、导航/高级控制、论文与研究扩展、完整独立验证工程。
不修改 G0 v1/v2、G1 算法、G2-A 已验收实现/配置、冻结需求/模型语义/验证判据。
确需改动先列问题、影响和版本化变更请求；不能静默通过适配层绕过合同。

## 4 S0 设计门与实施配置

先提交 `g2b_s0_controller_design.md`、逐用例矩阵、G2-only 版本化实施配置和构建/接口方案，
向原 PA 申请 DESIGN_ACCEPT，再实现控制数值核心。允许先建立构建和无算法类型夹具。
批准必须来自原 PA 会话 `019f9ef3-4a0c-79f1-99d4-c8415f62bd29`，
记录准确 SHA、决定来源与真实时间，内部同名代理不具该门禁权。

G0 的数值从 `05_integration/b0/configs/b0_g0_contract.v2.json` 加载；
保留其 Git blob `1beff6e6a9a81d0ab92b2059a93207ffed9d291d` 与 canonical LF SHA-256
`5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`。
验证实际加载文件，仅规范化 CRLF/CR→LF，再验哈希并调用权威 validator，不能只验证 HEAD。
G2 实施配置记录未由 G0 固定的离散公式、首步策略和组件测试容差；
单独审批 overlay 绑定已审配置，不回写历史候选状态。配置字段也需明确类型、单位和范围。

S0 必须逐项确定：外环 quaternion→误差向量；导数低通离散化及首步测量历史；
request 使用哪个积分状态；command/estimate/feedback 时间对齐；拒绝之后重试/下一 tick 的策略；
reset epoch/time 次序；C++/Python 错误类型、状态快照和诊断；绑定输出的 G1 兼容映射。
下面的推荐公式是本单的设计输入，需 S0 明确采用或给出替代方案后评审，不能称作 G0 已冻结公式。

## 5 级联计算与状态顺序

帧：NED/FRD；SI；double；quaternion `[w,x,y,z]`、Hamilton、body→NED。
单位 quaternion 输入按 G0 容差验证，不把任意非单位输入悄悄归一化成有效测量。

G0 已固定：`q_err = conjugate(q_est) ⊗ q_cmd`；scalar<0 取反；
scalar=0 用首个非零向量分量正号消除 half-turn 歧义。
推荐外环选择 `e_att = 2*q_err.vector`，`omega_sp = clamp(K_att*e_att, ±omega_limit)`。
S0 需写明它的小角度含义、π 处行为和作用坐标；若选择旋转向量映射，必须解释同样的边界与测试。

内环推荐使用以下明确的离散顺序：

```text
e_rate       = omega_sp - omega_est
d_raw        = (omega_est - omega_prev) / dt
alpha        = dt / (tau_D + dt)                  # 推荐 backward-Euler 低通
d_filtered   = d_prev + alpha*(d_raw - d_prev)
request      = Kp*e_rate + I_current - Kd*d_filtered
limited      = componentwise_clamp(request, ±torque_limit)
saturated_i  = abs(request_i) > torque_limit_i
I_next       = approved_conditional_and_back_calculation_update(...)
```

首步推荐 `d_raw=0` 并初始化 measurement history，reset D 状态为 G0 指定零值；
S0 如改用显式初始角速度形成首步导数，必须说明输入所有权和独立 oracle。
本 tick 发布由 `I_current` 计算的 request；更新 `I_next` 留给下一 tick，避免隐式代数环。
姿态 setpoint step 不得因微分 setpoint 产生未规定 derivative kick。

G0 初始值为 K_att=[4,4,2.5]，Kp=[.08,.08,.06]、Ki=[.02,.02,.015]、
Kd=[.004,.004,.003]、tau_D=.02 s；以上只是定位提示，生产值仍从批准配置读取。
本轮不以调参证明 G3 性能；测试中拆分 P/I/D 可以使用明确标记的测试参数夹具，
不能据此替换生产 G0 参数或重新宣称运行包线已批准。

控制器独占力矩 clamp，限值=[.35,.35,.2] Nm；rate target limit=[2,2,1.5] rad/s。
等于力矩限值时 saturated=false，严格超过才 true。request、limited、saturated、timestamp
作为一个不可拆分的发布值；适配器可以校验，不再次计算/替换生产限幅结果。

## 6 抗饱和与反馈配对

G0 `/actuator_contract/antiwindup` 的完整规则必须保留：

```text
I_next = clamp(I_current + dt * (
    conditional_Ki_e_rate
    + kaw_limit * (current_limited - current_request)
    + kaw_lag   * (feedback_actual - feedback_limited)
), -I_limit, I_limit)
```

逐轴条件积分：requested-minus-limited 与 rate error 同号时阻止继续推入饱和的项；
未饱和或误差减小饱和时允许。kaw_limit=[8,8,8]/s、kaw_lag=[2,2,2]/s；
I_limit=[.15,.15,.1] Nm，仍从 G0 读取。
反算两项都有独立测试；不能以积分硬限幅或仅条件积分替代完整规则。

limit 项用本 tick request/limited；lag 项用反馈所指 held command 的 limited 与实际 torque。
禁止把旧 actual 与新 limited 混配。控制器保存自己真实发布的命令身份/值，
验证反馈 command timestamp、limited、saturated 与 held command 一致，
而非仅检查时间戳在过去。unknown/跨epoch/未来/值不符反馈应规范拒绝。

S0 必须给至少三个连续 due tick 的手算序列：第一步使用 reset command，
第二步使用第一步发布命令，第三步使用第二步命令；另给一次拒绝后 held command 不变的序列。
记录 current time、feedback time、paired command time、I_before/I_after、两组反算项及 request/limited。
G1 actuator dynamics 未改变；模块试验中用已批准 actuator 生成反馈是允许的接口检查。

## 7 接口、时间、reset 与原子性

公开接口遵循 G0，具体 C++ 类型/namespace 由 S0 提案：

```text
reset(ControllerInitialState, ResetEpoch) -> TorqueCommand
step(AttitudeCommand, StateEstimate, ActuatorFeedback, dt_s) -> TorqueCommand
```

G2-A `StateEstimate` 字段已可用；适配器逐字段复制 q/rate/timestamp/显式 validity，
不把其默认构造行为当作输入有效性证明。Core 不接受 PlantState、SensorTruth 或场景标签。
G2-A 的 gap diagnostics 可在调用侧保留，不能把 truth 填进控制输入来补偿 gap。

默认控制周期为 G0 2×.0025=.005 s，按配置推导。reset tick 不运行 step；
首步必须在该epoch首个 due tick，dt 为批准周期，并使用 reset-command 配对反馈。
Runtime reset 场景时钟不倒退；epoch ID 的规则、同边界重复 reset 与首步缓存初始化在 S0 写清楚。
reset 发布零 request/limited/saturated，清除积分、D滤波器、测量历史、旧反馈及旧命令配对。

每个有效 step 的 estimate/command 必须满足当前 due tick 与 G0 freshness；
feedback 是当前执行器采样、指向严格更早发布的 held command。常值 setpoint 的值可以相同，
但采样 timestamp 与发布 timestamp 不能混为一谈，不为通过测试伪造新的执行器反馈。
保持原始字段名 `limited_torque_body_Nm`，不创造竞争别名。

S0 必须专门定义控制器遇到缺更新后的恢复：采用何种 dt、测量导数历史、
held feedback 和积分推进规则，或者明确必须 reset。不得直接复制估计器的 gap 积分政策。
只要无效调用被拒绝，就不得更新 last accepted tick、I、D、prev rate、held command、epoch或配对历史。
重试同一个合法 tick 应与没有该无效调用的对照轨迹一致；随后的合法 tick 行为符合 S0 恢复决定。

全部输入、参数及派生计算在提交新状态前验证。NaN/Inf、错误长度/类型、
Python 超大整数转换、浮点溢出、C++整数范围与 tick 转换均应明确拒绝，
不得 UB、wraparound、裸数学异常、部分状态写入或输出假 valid。
诊断是数值事实与拒绝原因，不是生产代码自判“验证通过”。

## 8 S0 到测试的必需矩阵

以下是工作单用例编号，不创建新系统需求。每行在 S0 定义具体输入、独立期望、
单位、绝对/相对容差、比较表达式及测试 node；实施后记录命令和证据定位。
建议 ordinary double 组件比较绝对容差1e-12，是否适用由S0逐项论证，不能把 quaternion norm 容差当角误差。

| 用例组 | 最低覆盖 | 独立判据 |
| --- | --- | --- |
| B-ATT | 三轴正负误差、零误差、非identity、多轴、q/-q、极小角、π tie-break | 手写axis-angle/旋转矩阵和独立Hamilton公式，明确反馈符号和axis |
| B-RATE | 外环/内环拆开，rate clamp两侧/恰边界，P/I/D各项，首步及后续滤波 | 手算离散一步与多步，禁止以生产helper求期望 |
| B-DERIV | 常值测量、测量step、setpoint step、reset后第一步 | 预声明filter系数与历史，证明微分作用对象正确 |
| B-LIMIT | 三轴正负torque限值、等于/相邻float/超过、same-tick bundle | 独立component clamp与严格比较，paired字段一致 |
| B-AW | 无饱和、推入/退出饱和、lag only、两项同时、每轴I bound、撤除 | 逐步独立计算条件Ki及两组反算；记录I_before/after，避免只验最终有界 |
| B-PAIR | reset配对、连续三tick、重复held值不同timestamp、假limited/status、未来/未知/旧epoch | 自己发布命令的可定位历史；错误必须原子拒绝 |
| B-TIME | 首tick early/late、nonzero reset、duplicate/stale/off-grid、dt零/负/NaN/Inf、缺样恢复 | G0整数网格及S0明确恢复规则，所有状态快照比较 |
| B-INVALID | valid=false、非单位/零q、NaN/Inf、wrong shape/type、float64不可表示整数、派生overflow | 公共API声明的错误/诊断，无部分更新；有效后续调用与对照一致 |
| B-RESET | 非零I/D/held后reset、时钟/epoch错误、重复reset/replay | 公共序列建立状态；全部清零/历史隔离；deterministic轨迹比较 |
| B-BIND | 核心与绑定相同输入、真实G2-A estimate/G1 feedback适配、caller/output数组突变 | C++与Python入口结果/拒绝语义一致，G1 TorqueCommand可合法消费 |
| B-DETECT | 反馈符号反转、反算符号反转、取消anti-windup、错用current limited的lag | 隔离变体必须被对应预先指定测试检测；恢复生产后通过 |
| B-CONFIG | LF/CRLF/CR等价、G0/实施配置变更/缺失/错版本、非法参数 | 实际loader fail closed，固定已审身份，不以仅hashhelper测试代替loader |

边界测试须确认实际float落在所需一侧。多步测试在S0固定步数和输入轨迹，不先观察结果再调容差。
缺陷检测不要求G4完整mutation平台；少量独立可复现变体足以满足现有G2规格，禁止永久污染生产代码。

## 9 CMake、绑定和环境

使用现有 CLion/CMake/PyCharm，命令行可复现；不新增 MCP 前置条件。
探测实际 compiler/CMake/Ninja/Python/pybind11/Catch2，记录版本、源码目录和build目录。
Windows文献 `.venv` 不安装控制依赖；B0沿用 `requirements/b0-dev.txt` 隔离环境。
系统工程检查可用 `build/venv-systems-engineering/Scripts/python.exe`，其中不保证有完整B0构建依赖。
WSL不同checkout需核对与同步精确head；宿主不可访问时按实际Windows工具+Linux CI验证，不虚报WSL结果。

新增明确 B0 CMake option/真实target及Debug/Release presets，关闭legacy navigation，
保留既有选项兼容性与readiness探针。C++17 required，extensions off，警告级别明确。
Catch2沿用固定提交 `b5373dadca40b7edc8570cf9470b9b1cb1934d40` 或项目已锁定等价来源；
不在无验证情况下使用系统任意版本。pybind11沿用2.13.6，Python3.11+ ABI匹配。
Eigen确需时才引入且固定来源，不能继承legacy EKF依赖问题。

核心静态库/可重用target与pybind11 module分离；本轮绑定是必需target，缺依赖即失败，
不能走legacy optional bindings分支静默跳过。提供显式模块路径与loader说明，
不得因测试import到陈旧pyd/so而误报新构建通过。

Debug/Release分别configure/build/CTest，分别确认实际加载module路径；至少一次clean rebuild。
C++与绑定测试都是必需，零测试收集、disabled/skipped不得计完成。
pytest在各自track内执行，CTest设置对应working directory；构建/测试命令不能收集仓库根目录。
可提交普通可移植presets，个人IDE配置/绝对路径不提交；不以IDE调试替代模块检查。

## 10 CI、用例与证据的受控管理

保留现有七项CI及全部原门禁，增加G2-B Debug/Release C++与绑定检查；不得continue-on-error或减少覆盖。
新检查可合理组合为一个matrix job，但每个构建类型须实际执行对应核心/绑定测试。
回归至少覆盖G0、G1、G2-A、系统工程与原六类检查；按实际依赖隔离安装。

本阶段测试代码与实现相邻，系统工程verification目录管理计划/结果关系，不迁移整个仓库。
TC用例和PA评审反例使用同一受控套件：每个必要发现记录来源、缺陷/需求关系、
永久测试node、适用版本、执行结果与证据。一次性环境探针可以仅留说明；
关键验收不得只留聊天命令。不得为了凑数量把独立评审用例复制成重复测试。

复用冻结规格：B0-VER-CONTROLLER-SIGN、CONTROLLER-SATURATION、ANTI-WINDUP、PAIRED-COMMAND；
INVALID-INPUT、INVALID-MEASUREMENT、RESET、PAIRED-FEEDBACK、CONVENTIONS、TRUTH-BOUNDARY、
LANGUAGE-BOUNDARY按本轮模块/接口范围分配。每条使用完整原ID，S0列出对应B0-REQ及具体判据。
多阶段规格在G3尚有未执行前提时保持partial；不得修改冻结planned/not_run目录。

artifact至少含精确源提交、构建类型/工具/ABI、配置及闭包身份、逐用例原始输入/期望/输出，
I/P/D/两组反算分量、request/limited/status、命令/反馈/epoch时间序列、拒绝前后状态、
独立判据与局限。控制生产核心不输出pass verdict；独立检查层判断。
记录测试日志、文件和归档hash、具体artifact ID、source run、expiry及审核来源。
原始输出/二进制/日志/HTML/截图放临时build或CI artifact，仓库只收代码、受控索引和人工记录。

C证据工具新增controller的scope→强制闭包profile，包含源码、headers、binding/adapter、loader、
测试/oracle、配置/审批、实际validator、CMake/presets/CI及本地相关依赖；不能用record ID绕过规则。
修改实施后重新生成证据，旧记录留历史并正确supersedes，source/target/HEAD引用必须一致或有受控复用依据。
注意既有G2-A闭包包含整个CI工作流：新增G2-B job会改变其相关文件身份，即使估计器源码未改，
也不能继续把旧G2-A记录当作满足当前闭包。优先在新工作流上重跑G2-A并保留新artifact，
新增记录取代旧记录、更新source/target和hash；不得删除workflow依赖或弱化检查绕过此变化。
若采用更细的受控影响分析替代重跑，须先把规则/反例交PA批准。最终head治理门禁必须通过。
证据中的实际执行checkout SHA、PR head SHA与Actions元数据SHA可能不同，分别记录并核对文件身份，
不得把分支SHA直接冒充实际构建revision；合并ref同源字节可由明确的复用分析解释。
offline remote_unverified/pending与0满足允许保留；PA候选验收不自动把全部需求标accepted/satisfied。
如要使用verified接受计数，必须实际cache校验bytes/expiry并具有明确review决定。

## 11 S1 至合并后验收

| 阶段 | TC必须交付 | PA门禁 |
| --- | --- | --- |
| S0 | 设计/实施配置、公式/时间/配对序列、数值与用例矩阵、构建方案 | DESIGN_ACCEPT后数值实施 |
| S1 | 真实核心+绑定、逐行矩阵落到test node、模块正负例 | 完成自检再推进 |
| S2 | Debug/Release/clean、CI、原始证据、依赖闭包、报告和必要入口同步 | ready_for_review，精确head |
| S3 | 关闭PA REWORK、最终全绿及完整评审包 | PA ACCEPT后待具体合并授权 |
| S4 | 授权合并后main树/CI/保护文件检查 | PA POST_MERGE_ACCEPT |

先更新README/roadmap和Issue #6的过期状态：G2-A已合并验收，G2-B当前阶段。
历史设计候选/已批准源保持版本语境，以当前事件层承接，不在多个入口手工复制所有实时状态。
RESULTS.md只记录实际验证结果及产物，不能先写G2完成。

评审包必须含base/head/PR/Issue；本单逐条关闭矩阵；S0批准定位；全部实际命令/结果；
build及module实际路径；关键反例/检测结果；新artifact与hash；完整依赖闭包；
逐需求/规格的complete/partial边界；保护文件hash及git status；G3最小调用和输入/状态责任说明。

当核心、绑定、所有本轮必需模块检查均完成，并合并后由PA验收通过，确认G2-B完成。
结合已完成G2-A，可确认G2完成/G3开发就绪；这不等于G3已启动、B0完成、闭环性能通过或独立验证阶段完成。
TC将S0、候选、修复和合并后包交原PA会话；本次用户明确授权这些评审交接。
通过后继续已授权步骤，真实阻塞时给出准确对象和所缺决定，避免仅写“等待授权”。
