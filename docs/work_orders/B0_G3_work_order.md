# B0 G3 闭环集成与验收详细工作单

日期：2026-10-15（Australia/Perth）。编制与评审：原 Project Administrator（PA）。
拟执行：Task Carrier（TC）。执行主 Issue：[#7](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/7)。

## 1 当前状态与授权边界

**状态：已由原 PA 派发给 TC；G3-A S0 候选编制中，算法实施尚未启动。**

本单最初按用户 2026-10-15 的要求“请你编写G3详细工作单，包含收口工作，编写完暂不交TC执行”
作为本地待审草案编制；该历史边界保留。随后用户明确要求“工作单交TC执行”，原 PA 在同一控制
会话派发 G3，并限定先执行 G3-A、先提交 S0 精确 head 取得 `DESIGN_ACCEPT`。用户又在 TC 会话
要求“继续按工作单执行”。因此当前允许建立 G3-A 分支/Draft PR、整理前序收口、Issue #7 和
非算法 S0 资产；在 `DESIGN_ACCEPT` 前仍不得实现调度、事件或指标决策。

G3 的目标是把已验收组件连接成估计状态反馈的确定性姿态闭环，用独立指标执行批准场景，
形成可审查的集成证据。G3-ready 表示前置组件与治理门满足，不表示闭环性能已经通过。

G3 启动和本单三个顺序 PR 的边界已获授权；每个 PR 的合并、Issue #7 的关闭、分支删除和
G4 启动仍分别遵守后续明确授权。设计与实施可由 TC 提案，但原 PA 的门禁不得由同名内部代理代签。
原 PA 会话：`019f9ef3-4a0c-79f1-99d4-c8415f62bd29`。

## 2 基点与已完成前置条件

| 对象 | 已核实基点与结论 |
| --- | --- |
| G0、G1、G1.5-A/B/C | 已依次验收；批准合同、组件和联合需求模型基线继续有效 |
| G2-A | PR #21 合并 `5f817ec1fb2405aa269dcf6a701a33cff846c748`，原 PA 已合并后验收；Issue #5 completed |
| G2-B 实施候选 | `89148b4e38bcd267e4d9c8eca3f6b12216fc9f76`，原 PA `IMPLEMENTATION_ACCEPT` |
| G2-B 合并后基点 | PR #22 merge `5ff4435bd1f231fc3b5292edfe6dad22f109f1e1`，原 PA `POST_MERGE_ACCEPT`；Issue #6 completed |
| 合并树 | `ed775db203fcc1e6071c82e399442ebefe9130b5`，与已接受候选树一致 |
| main CI | [38561983495](https://github.com/ZhangChi0727/UAV-FMS-portfolio/actions/runs/38561983495)，九项成功；控制器 Debug/Release 各 25 CTest 节点、79 Python 用例，含 clean Debug 重建 |
| 当前证据层 | 已验收实施与账本审计状态分开管理；合并时为 20/29 规格已执行、5 条当前生产记录、0 accepted evidence、0/30 satisfied |

上述计数是已有记录，不是 G3 的预计测试数量或完成目标。不得为了显示进度把所有需求直接标为满足。
开工时重新核对远端 main、已有 PR、Issue #7 和工作树；main 如前进，应审查差异后确定新基点。

### 工作区保护

用户文件 `docs/work_orders/B0_G1_5_work_order.md` 有未提交修改，编单基点的 SHA-256 为：
`96d45d4215c2215bb50ea0c7b863b627fa2e7d8d64ada3bb456950a2aa0d44a5`。

不得暂存、提交、还原或删除该文件；若用户后来继续修改，保护新的内容，不能恢复旧哈希。
使用精确文件清单暂存，不用 `git add -A`；不强推、不破坏性 reset、不自动清理分支。
切换分支若有覆盖风险，先停下说明。编单完成只增加本工作单，不改写此前工作单。

## 3 权威来源与变更规则

执行前完整读取 AGENTS、README、章程、开发基线、架构、roadmap、G2 总单、G2-B 工作单、
本单，以及以下资产和对应 G1/G2 公共接口、S0 设计、批准 overlay、测试及证据生成器：

- 数值与时序合同：`05_integration/b0/configs/b0_g0_contract.v2.json`、权威 `validate_config.py`。
- G0 批准：`systems_engineering/reports/b0/g0_approval_decision.md`。
- 需求：`systems_engineering/requirements/b0_requirements.json`。
- 模型：`systems_engineering/models/b0_system.sysml`、`architecture.md` 和已批准模型审查。
- 联合基线与冻结清单：`systems_engineering/reports/b0/g15b_joint_baseline_manifest.json`。
- 验证设计：`systems_engineering/verification/b0_verification_specifications.json`、`g0_acceptance.md`。
- 执行层：`systems_engineering/verification/b0_execution_evidence.json`、schema、G1.5-C 检查器。
- 环境：`requirements/b0-dev.txt`、现有 CMake presets 和开发就绪记录。

G0 v2 Git blob 为 `1beff6e6a9a81d0ab92b2059a93207ffed9d291d`，canonical LF SHA-256 为
`5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`。
执行时验证实际加载字节，仅规范化 CRLF/CR→LF 后核对身份，并调用权威 validator。
不能只验证 Git HEAD 后加载另一份本地配置。

G0 和冻结需求、模型、验证规格中的 candidate/planned/not_run 字段是历史版本语境，
由批准记录和当前执行层解释，不原地改成 approved/pass。保留全部已有身份，不创造或重编号
NAV/CTL/FDI/B0 需求。下文 G3 测试组标签仅是工作单标签。

普通集成实现选择由 S0 说明并交 PA 批准。修改包线、性能阈值、场景/种子、已有数值算法或
冻结模型语义时，先提出受控变更及影响链，获得对应批准后才能实施。

## 4 包含与排除

包含：G2 收口记录与当前入口整理；Python 确定性调度器、命令/事件适配和闭环运行入口；
真实 G1 plant/actuator/IMU、G2-A estimator、G2-B C++17 binding 的调用；八类批准场景；
独立指标器、调度/复位/真值隔离检查、集成原始信号、证据 manifest、CI 和追溯收口。

生产控制计算继续由 C++ 核心完成。Python 不另写生产 PID，也不以理想姿态或角速度绕过估计器。
使用已验收组件，保留其模块路径；不在集成文件内复制 plant、IMU、estimator 或 actuator 算法。

排除：平移/位置/导航、电机混控、真实机体气动、PX4、板端、实时闭环 HIL、飞行、研究扩展、
论文、通用验证平台以及 G4 发布验收。正常 Python 闭环数值仿真在本单记为 integration simulation，
不自动升级为板端、HIL、飞行或未经定义的 SIL 证据等级。

本阶段仍是开发期集成检查及 PA 验收。测试代码与集成实现相邻，系统工程 verification 管计划、
执行索引和审核关系；不另建一级验证目录，不迁移全仓库，也不启动独立验证研究包。

## 5 顺序 PR 分解

本单拟采用三个顺序 PR；编号由创建时分配，不预占 PR #23 等编号。Issue #7 用任务列表承载
三个子包，保持一个主工程增量。每个子包完成自己的验证和评审，不用最后一个 PR 掩盖前项缺口。

| 子包 | 单个 PR 的交付边界 | 出口 |
| --- | --- | --- |
| G3-A 收口与确定性闭环 | 第 6 节收口、S0 设计、最小真实闭环、时序/事件/复位/接口与真值隔离检查 | PA 接受调度和组件接入；不宣称八场景性能通过 |
| G3-B 独立评估与场景验证 | 独立指标器及人工信号 oracle、八场景执行、逐准则结果、失败定位与范围内修复 | 全部必需准则与结果分类可审查，未解决性能失败不冒称通过 |
| G3-C 集成证据与验收收口 | 完整回归、Debug/Release 集成、原始产物/manifest/强制闭包、账本报告、合并后验收包 | 原 PA 最终验收后确认 G3 完成，按授权关闭 Issue #7；G4 未启动 |

先在 G3-A 的 Draft PR 提交 S0，取得 `DESIGN_ACCEPT` 才实现调度/事件语义。
G3-B 的指标计算选择也必须在实现前有明确设计批准，可以与 G3-A S0 一次审查，避免重复等待。
G3-C 的证据格式先在 S0 确定；A/B 就保留原始检查结果，不到 C 才首次建立证据。
每个 PR 经候选评审、具体合并授权、main 验收后再推进下一个，不能并行启动三个主 PR。

## 6 前序收口与管理状态整理

以下工作现纳入已派发的 G3-A；在 S0 `DESIGN_ACCEPT` 前只执行收口、设计、矩阵、schema 和
管理状态更新，不提前实现后续算法：

1. 新增简洁人工收口记录，例如 `systems_engineering/reports/b0/g2_closeout_and_g3_readiness.md`，
   记录 G2-A/B 候选接受、main 验收、Issue #5/#6 completed、精确 SHA/CI 和范围边界。
   审核来源使用真实 PA 决定和 Issue 收口评论，不编造签字、时间或证据 URL。
2. 更新 README、roadmap、systems_engineering/README 中“PR #22 active / G2-B 未接受”等过期入口，
   指向收口记录和本单；RESULTS 只登记已验证结果。正式执行前不能提前写 G3 active/complete。
3. `systems_engineering/reports/current_status.md` 是明确标记的 G1 历史快照，不能把旧计数冒充
   现况。保留历史语境，通过当前入口链接新的日期化收口记录；不要静默改写旧验收事实。
4. Issue #7 修正 `07_docs` 旧路径、依赖、owner/阶段、三个子包和验收条件。Issue 管执行状态，
   roadmap 管范围，不在大量 README 中复制完整实时进度。
5. 逐条清点 G2 仍为 partial 的规格，列出哪些集成部分由本单补齐、哪些留 G4；
   实施接受、证据是否可审计、规格覆盖、需求满足分别记录。
6. 核查遗留未关闭 PR/Issue 与分支。仅报告相关性；本单不授权关闭其他 Issue/PR 或删分支。
7. 盘点 artifact 到期时间和可获取性。可以下载到临时/build cache 做哈希校验，但不能把
   过期或不可获取产物继续标为 remote_verified，也不能提交生成输出或凭据。

收口通过条件：当前入口不再把 G2 写成未接受，历史证据原样保留，冻结资产无漂移，
Issue #7 的计划和本单一致，用户工作区未被混入提交。

## 7 S0 设计与可达性审查

提交 `g3_s0_integration_design.md`、逐测试/场景矩阵及最小证据 schema 草案，至少关闭以下事项：

| 设计事项 | 必须确定的内容 |
| --- | --- |
| 调度 | scenario/global tick 与 epoch-local tick、六阶段顺序、due 判断、起止端点和 hold 身份 |
| 初态与复位 | plant offset 所有权、各组件显式初态、epoch ID/时间映射、RNG draw index、首两次有效更新 |
| 事件适配 | external torque、bias replace、specific-force add、非法调用的目标/阶段/恢复，不修改 G1/G2 数值实现 |
| 评估定义 | G0 文字公式对应的可执行坐标映射、符号/分支、采样对齐、每轴 RMS、yaw unwrap、持续时间权重 |
| 可达性 | 批准初始增益与包线下的跟踪/恢复及真实饱和触发是否具备实现条件；发现冲突如何处置 |
| 运行接口 | CLI、模块路径、配置/版本身份、run/epoch/scenario ID 和明确的成功/失败退出语义 |
| 证据 | 原始字段映射、stream 更新标记、完整案例及准则记录、manifest/hash/expiry、依赖闭包 |

先使用 G0 初始值和已接受 G2 参数，不承诺它们必然满足全部动态准则。特别检查
`saturation_withdrawal` 的实际请求力矩是否能越过限幅并满足冻结的正饱和持续时间下界；
非零命令不等于已经发生饱和。不得通过放大命令、改限幅、删下界或伪造 saturated 达标。

若设计分析或开发运行发现参数/合同不相容，先区分时序/符号/模型缺陷与真实性能不足。
范围内实现缺陷先修复；需要调参时单独提出版本化 G3 参数提案、来源/允许范围、组件回归及
判据影响，未经批准不改 G2 配置或已冻结 G0。开发调参只使用 `tuning_seed`，不得用保留验收
seed 反复挑选参数。验收 seed/场景已用于诊断时如实记录，不再宣称其为未接触的独立留出集。

G0 未细化的轴误差投影、unwrap/差分端点等实现解释需 PA 在 S0 审查；若解释实质改变冻结
指标含义，转为规范变更，不能藏在 metrics helper 内。数值容差按量与比较目的声明，不通用放宽。

系统模型按既有 SysML 方法和已批准模型语义使用。需要集成时序、接口、活动和追溯视图时，
从已有模型身份生成/维护有用视图，放 systems_engineering，标明版本、来源及阅读边界；
不为凑图类新增模型，不以 Mermaid 等示意图冒充正式 SysML 语义。冻结模型变更走受控版本。

## 8 确定性调度与初始化

基准周期从 G0 加载：0.0025 s。plant/actuator 每个 base tick 更新，IMU/estimator/controller
每两个 base tick 更新。时间由 `reset_boundary + local_tick * base_period` 推导，不累加浮点 dt，
不按操作系统 wall clock 调度，不跳过真实计算以追求运行速度。

初始化和每次 reset boundary 为 local tick 0，只 reset，不执行任何 component step。
controller 发布零 request/limited/saturated 的 reset command，时间为该全局边界；
actuator reset 保持对应 held 身份。IMU 与 estimator/controller 首个正常 due 为 local tick 2。

每个普通 base tick 的顺序必须直接落实 `/timing/sequence`：

```text
plant.step_base(previous held actual torque + permitted external torque)
actuator.step_base(latest torque command published strictly before this tick)
if IMU due: sample interval-end truth at the sensor boundary and apply declared measurement events
if estimator due: consume exactly that new IMU sample
if controller due: consume current-due estimate, sampled command and current paired actuator feedback
if controller accepted: publish the new torque command for subsequent actuator ticks
```

这是阶段顺序，不是允许复写现有组件算法。plant 不能消费本 tick 刚计算出的 controller 输出，
也不能消费本 tick 刚推进的 actuator actual；actuator 不得提前消费本 tick 新发布命令。
hold 期间重用同一 command 及其原始 timestamp，不制造“值相同但新时间”的假发布。

场景初始偏差只施加给 plant truth，按 G0 右乘 `qx* qy* qz` 构造；estimator 和 command
使用各自显式默认初态。不能把 plant 的未知初始偏差/航向自动复制给 estimator。

场景持续时间对应 N 个 base interval：S0 说明保留 tick 0、1…N 的原始边界记录及终止规则；
所有准则窗口仍严格使用 `[start_tick, end_tick)`。最后的边界记录不能被重复算成额外时间。
reset 的 base tick 是 reset-only 的特殊边界，必须显式记录，不能为填满点数执行隐藏 step。

日志分别标识 source/publication timestamp、当前 base tick、epoch-local tick、due/held/valid。
需要 base-grid 视图时保留 hold 的原 timestamp 和更新标记，不把未更新 estimate 重新标成新采样。

## 9 事件和错误恢复适配

事件区间、优先级、重叠限制、结束动作直接读取 G0。默认是 start inclusive、end exclusive，
按 start tick 与声明顺序处理；禁止为方便实现改变重叠政策或把 event end 当最后有效 sample。

- command step：按声明轴与符号生成单位 quaternion，事件结束后该轴归零；controller 输入
  仍用冻结的 `q_nb_command`、timestamp、显式 valid，不接收 scenario/truth 对象。
- external torque：仅在 plant 的机体系合力矩输入处与 actuator actual 相加；记录两者，
  不能把外扰写成 actuator 实际输出或反馈中的已执行控制力矩，也不对外扰偷偷做控制器 clamp。
- IMU bias：复用 G1 正常采样与噪声抽样，在显式测量事件层做 replace-nominal-bias；
  不把替换写成追加第二份 bias，不重置 RNG，不修改 G1 私有参数或在事件边界重建 IMU。
- specific-force contamination：在声明的 body specific-force 测量上 additive，保持原噪声和时间；
  这是外生测量污染，不为此增加平移动力学。限制事件标签只到日志/评估端，不能成为融合门控输入。
- invalid input：在 S0 指定真实公共入口与阶段，例如 due controller 的负 dt 调用、due estimator
  的 stale sample 调用；每个声明事件只计一次真实、匹配原因的拒绝，不由 runner 自填成功状态。

非法调用检查比较被拒绝组件的全部相关状态、时间和 held 身份；拒绝后可以在同 due tick 使用
原有正确输入重试，避免制造 controller 漏 tick。IMU 样本只抽取一次，不能重试时再抽一次噪声。
如果采用跳过更新，必须先证明符合 G0 与 G2 恢复合同；controller 已错过 expected due 时不能
静默长 dt 恢复，需明确 reset 路径。已经正常推进的 plant/actuator 不假装被自动回滚。

runtime reset 清除全部组件状态、旧反馈/命令和调度相位，递增 epoch ID；scenario clock 不倒退。
各 G1 接口的 reset 参数是边界时间，G2 接口含 ID/time，薄适配保持各自合同，不强行统一 wire 类型。
重放保存真实 IMU/command trace、初态、seed 和抽样索引，只比较 matching、valid 的 reset-local
estimator due ticks；reset 输出不能冒充正常更新，至少两次有效更新，q 分量绝对容差 1e-12。

## 10 必需集成测试矩阵

S0 为每组确定实际输入、独立期望、单位/容差、执行 node 和来源；实现后保留运行结果。

| 工作单测试组 | 最低检查与判据 |
| --- | --- |
| G3-TIME | 独立重算整数 schedule；首 tick、due/非 due、长序列、非零 origin、重复/遗漏/顺序错误 |
| G3-HOLD | reset command、连续三次控制发布、两次发布之间的 hold、request/limited/status 与反馈身份 |
| G3-EVENT | 每类事件起止两侧、六个正负 step、bias replacement、body additive force、扰动与 actuator 分离 |
| G3-INIT | plant-only 初始偏差、显式 estimator 初态、禁止隐式 truth 初始化、无 tick-zero integration |
| G3-RESET | 偶数/奇数 reset boundary 夹具、R+2/R+4 首两次更新、旧 epoch replay 拒绝、全组件/RNG 清理 |
| G3-INVALID | 两种批准非法事件真实拒绝且各计一次、完整快照、同 tick 修正重试、missed-tick 恢复边界 |
| G3-TRUTH | 静态允许路径检查；固定 IMU/command/初态，仅变评估端 truth 副本不改变估计/控制输出 |
| G3-TRUTH-NEGATIVE | 隔离地向 estimator/controller 引入禁止的 truth 依赖，预声明的边界检查必须检出 |
| G3-BIND | 实际加载模块路径/哈希/ABI，冻结字段和 G1 类型消费，Debug/Release 真实闭环接口一致 |
| G3-METRIC | 人工信号独立算全部指标族：正负/零 step、q/-q、dwell 边界、晚峰值、yaw 分支、重叠饱和 |
| G3-DATA | 缺字段、缺 due tick、错误帧/单位、NaN/Inf、假 pairing、窗口截断、重复事件计数不得通过 |
| G3-SCENARIO | 批准八场景和所有 criterion ID 一一有结果、原始输入/数值及事件/窗口定位，不只给总通过数 |
| G3-REPLAY | 同版本/配置/seed 两次真实运行与 reset trace replay；比较信号、更新时间和终止分类 |
| G3-EVIDENCE | schema/哈希/配置/源提交/模块身份/闭包/expiry；删行、改数值或错配 source 能被拒绝 |

边界夹具或故障变体不新增正式场景需求，不篡改批准八场景。被测调度器不能自行生成唯一期望
schedule；指标测试不能从 metrics helper 得出自己的期望；算法不能返回自己的 pass verdict。
少量集成缺陷检测服务上述合同，不扩张为通用 mutation 平台；G4 完整缺陷演示仍单独验收。

## 11 八场景与逐准则验收

从 G0 v2 的 `/scenarios` 直接加载 ID、class、seed、初态、事件、时长、observations、artifact_path
和 acceptance。下面是责任定位，不是复制出来的第二份可编辑配置；所有数值以 G0 为准。

| 场景 ID | 必需检查与结果边界 |
| --- | --- |
| stationary_zero_command | 姿态/角速度误差及 estimate quaternion 范数；不能以“输出接近零”替代全部准则 |
| initial_attitude_offset | plant-only roll/pitch 偏差，tick 0 起 tilt 恢复与峰值；不要求未知绝对 yaw 恢复 |
| tri_axis_signed_steps | x/y/z 各正负六事件，每个独立算 settling、signed overshoot、cross-axis，保留完整窗口 |
| external_torque_disturbance | 峰值、event end 起恢复、饱和时间；真实 body 外扰与控制力矩分列 |
| imu_noise_and_bias | 固定 seed/噪声抽样与替换 bias；每轴 roll/pitch RMS、相对 yaw drift，不能用跟踪误差代替估计误差 |
| saturation_withdrawal | 正饱和触发下界、总饱和上界、x/y/z I 界、撤回后恢复；未触发饱和不能凭上界通过 |
| acceleration_contamination | additive specific force 与限制状态及 truth/estimate 全记录；结果是 limitation_characterized，不冒充性能恢复通过 |
| invalid_input_and_reset | negative dt、stale timestamp 各一次真实匹配拒绝，随后一次全组件 reset，匹配有效 due ticks 重放 |

六个包线内性能场景须满足全部适用准则；限制刻画和非法输入场景按各自规则验收。
八场景名称正确但漏了某 event 的 acceptance 项仍不合格。未通过准则须保留数值、定位及原因，
不能只保存成功场景、以 skip/xfail 承接未完成行为或反复随机运行挑选通过样本。

## 12 独立指标器与结果分类

指标器放 `05_integration/b0/` 的独立模块，只读取已封存原始信号与批准配置，不读取 controller/
estimator 私有状态做期望、不导入生产算法 helper 作为唯一 oracle；诊断可以作为被测观察量。
允许 evaluator 读取 truth，但不能把 evaluator 的结果/事件标签回馈运行闭环。

必须逐项实现 `/acceptance_policy/metric_definitions`，并记录 source signals、采样时刻与轴聚合：

1. 姿态误差处理 q/-q 等价；初始偏差用两个 R_nb 第三列夹角的 tilt 指标，不用绝对 yaw 补偿。
2. settling 记录进入误差带并完整保持 dwell 的首个 sample；time origin 分别是 step start、
   disturbance/withdrawal end、initial-offset tick 0。G0 band=0.0174533 rad、dwell=0.25 s。
   窗口不足以检查准则是数据/执行错误；合法完整窗口内未稳定是 performance_fail，不能输出假有限时间。
3. signed overshoot 按实际事件前 command 到目标的 signed delta；负阶跃也按方向投影。
   零 delta 是 not_applicable，不填 0% 或 pass。晚至 event 最后一个有效 tick 的峰值必须参与。
4. cross-axis 使用 G0 声明的未命令轴口径，轴误差映射经 S0 批准；不以总角误差代替轴耦合。
5. 饱和时间按任意轴饱和的时间并集，不把三轴同时饱和算成三倍。明确 publication/hold 到
   base interval 的时间权重，不能直接对稀疏 controller samples 乘错误 dt。
6. roll/pitch 估计 RMS 分轴报告；yaw drift 基于相对初始参考并处理角度分支和有效样本间隔，
   不把 ±π 跳变当真实漂移，不宣称六轴 IMU 提供绝对航向。
7. I_before/I_after 与 applied request 的时序明确；三个轴限值分别评估，不把统一 0.15 Nm
   用于 z 轴。reject count 按声明事件去重，reset match 只计正常有效更新。

每条 criterion 保留原始 metric、reducer、operator、limit、unit、window、event_id/axis、
计算值、比较表达式、状态和原始 trace locator；综合结论不能替代逐项结果。

只使用 G0 已有五类运行结果：`performance_pass`、`performance_fail`、
`limitation_characterized`、`invalid_input_rejected`、`execution_error_inconclusive`。
构建/配置/输入数据/时间对齐/指标异常不能伪装为性能失败，更不能计入通过。
单条不适用指标另有 not_applicable 状态与原因，不能让它自动满足某必需数值准则。

指标正负测试至少包含：恰在阈值及相邻浮点两侧、dwell 少一个 tick/刚好足够、半开 end tick、
故意漏晚峰值、负/零阶跃、多轴并发饱和、缺数/重复数、无匹配 event、未达到最少 reset 更新数。

## 13 文件布局与工具环境

建议沿用已有 track，在 `05_integration/b0/` 增加 `runner.py`、`scheduler.py`、`events.py`、
`metrics.py`、`evidence.py`、`tests/`、`README.md`，必要的 schema 放该 track 的 schema 目录。
按实际职责合并小文件，避免为每个事件建一个框架或复制 G0。G3-only 实施选择需要版本化配置
和审批 overlay 时，放该 track 的 configs 中，不把它当成另一个系统需求源。

人工设计/评审/验收报告放 `systems_engineering/reports/b0/`；已有 verification 账本管理执行索引。
不改 numbered module paths，不新建带编号 docs，也不要求九类或某个固定数量的系统模型图。

沿用 Python 3.11+、C++17、CMake/Ninja、pybind11 2.13.6、既有固定 Catch2，复用 CLion/PyCharm。
依赖从 `requirements/b0-dev.txt` 加载，B0 venv 与 Windows research 环境隔离。
本单不要求新 MCP、账户、API key、MATLAB、GPU 或付费服务；新增依赖/权限须单独说明必要性。

探测实际工具与 checkout；WSL 的 Linux clone 和 `/mnt/e` 共享源树不能混报 HEAD。
Windows 系统工程 venv 不保证含完整 B0 编译依赖；可用现有 Linux CI 验证构建，但本地未执行
就不能写本地通过。IDE 操作必须有等价命令行复现，不以截图代替数值检查。

### 拟定运行接口

以下是 S0 需要落实的接口建议，**目前尚不存在，不能把它们写成已经可运行的命令**：

```text
# cwd: 05_integration/b0，使用 B0 venv；模块路径指向本次真实构建
python runner.py --config configs/b0_g0_contract.v2.json --all-scenarios \
  --module-dir <absolute-built-module-directory> --output-root <temporary-run-root>
python metrics.py --run-dir <one-sealed-run-directory> --output <temporary-evaluation-json>
python evidence.py --runs-root <temporary-run-root> --output <temporary-evidence-manifest>
python -m pytest -q tests
```

配置缺失、模块不匹配、零测试收集或必需准则失败时必须有明确非成功语义。
G3-A 的短闭环 smoke 输出只能标为开发检查，不冒充全八场景验收结果。

## 14 需求与验证分配

本表是当前阶段责任，不更改冻结 stage、关系或历史 execution_status。

| 现有需求与规格 | G3 应交付 | 后续边界 |
| --- | --- | --- |
| B0-REQ-0021 / B0-VER-SCHEDULING | 全多速率调度、实际 consume/publish trace、独立 tick 比较 | 本阶段主要完成项 |
| B0-REQ-0002 / B0-VER-REPLAY | 双运行与 runtime reset replay，版本、输入及容差一致 | G4 发布环境复现仍独立 |
| B0-REQ-0003 / B0-VER-TRUTH-BOUNDARY | 静态/runtime 路径审查及禁止 truth 依赖的负变体检出 | 不以 API 签名无 truth 一项替代完整检查 |
| B0-REQ-0009 / B0-VER-PAIRED-FEEDBACK | 真实多速率 held-command 配对 trace | 复用 G2 组件检查并补集成部分 |
| B0-REQ-0020 / B0-VER-RESET | all stateful components 的 reset、调度相位、RNG 和有效更新重放 | 不再仅凭单组件清零证明 |
| B0-REQ-0019、B0-REQ-0029 / B0-VER-INVALID-INPUT、B0-VER-INVALID-MEASUREMENT | 真实非法注入、拒绝、状态保持及恢复 | 既有 G1/G2 模块证据保持来源 |
| B0-REQ-0014、B0-REQ-0015 / B0-VER-YAW-LIMITATION、B0-VER-ACCEL-CONTAMINATION | 闭环中 yaw 局限与污染场景证据 | limitation 不等于性能通过 |
| B0-REQ-0016、B0-REQ-0017、B0-REQ-0018 / B0-VER-CONTROLLER-SIGN、B0-VER-CONTROLLER-SATURATION、B0-VER-ANTI-WINDUP | 三轴跟踪、真实限幅与撤回恢复的集成补充 | 不覆盖或否定已有组件证据 |
| B0-REQ-0022 / B0-VER-SCENARIO-CATALOGUE | 八场景与每个 G0 criterion 的执行映射，复用既有 catalogue 审查 | 不把历史 inspection 改成伪造的性能 test |
| B0-REQ-0023、B0-REQ-0024 / B0-VER-EVALUATOR-INDEPENDENCE、B0-VER-EVIDENCE-PROVENANCE | 指标器实现独立性、原始信号与 manifest 审查 | G4 发布级义务未完成则保持 partial |
| B0-REQ-0004、B0-REQ-0026 / B0-VER-CONVENTIONS、B0-VER-LANGUAGE-BOUNDARY | 全链单位/帧及实际 Python/C++ 构建接口 | 模块检查加集成证据，不能重复计为新需求 |
| B0-REQ-0025、B0-REQ-0027 / B0-VER-DEFECT-DETECTION、B0-VER-CLEAN-CHECKOUT | 可保留本阶段真实局部检测与 CI 重建记录 | G4 完整发布演示不能提前标 complete |
| B0-REQ-0001、B0-REQ-0030、B0-REQ-0028 / B0-VER-SCOPE-INSPECTION、B0-VER-LEGACY-DISPOSITION | 复用边界审查，核实本轮未扩展范围 | legacy CTL-REQ-001/002 仍按批准处置 not_applicable |

以下已验收组件项通过原 G1/G2 证据引用，不复制 test 结果或把它们硬改成新的 G3 实现：

| 需求 | 复用规格 | G3 责任 |
| --- | --- | --- |
| B0-REQ-0005 | B0-VER-PLANT-DYNAMICS | 实际调用已验收 plant；外扰与执行器输出分开记录 |
| B0-REQ-0006 | B0-VER-PLANT-QUATERNION | 保持单位 quaternion 与帧约定，记录集成中的范数检查 |
| B0-REQ-0007 | B0-VER-PAIRED-COMMAND | 原样传递 controller 同 tick 的 request/limited/status/time，不拆分重建身份 |
| B0-REQ-0008 | B0-VER-ACTUATOR-DYNAMICS | 调用 step_base，不二次限幅，不混用 oracle substep |
| B0-REQ-0010 | B0-VER-IMU-GYRO | 保持固定噪声抽样、时间与替换 bias 语义 |
| B0-REQ-0011 | B0-VER-IMU-SPECIFIC-FORCE | 在批准 sensor truth 边界采样，显式记录污染适配 |
| B0-REQ-0012 | B0-VER-ESTIMATOR-PROPAGATION | 只消费当前 due IMU，继承已批准归一化与时间规则 |
| B0-REQ-0013 | B0-VER-ESTIMATOR-FUSION | 不用场景标签或真值改变融合门控；记录现有诊断 |

最终矩阵覆盖全部 30 需求/29 规格的当前状态与缺口，未执行项也要可见。

## 15 证据与版本适用性

原始输出放 build、临时 run root 或 CI artifact，仓库只收代码、schema、索引和人工审核记录。
尊重 G0 artifact_path 的场景目录语义，用统一 run root 承载；不提交 CSV/NPZ/JSON 运行输出、
日志、HTML、图像或 notebook outputs。G3 只需支持审查所需的有界产物，完整发布图表包留 G4。

每个 run 至少保留：

- 实际 checkout SHA、artifact source SHA、PR/main SHA 与 Actions 事件元数据的区别；工具/ABI、
  build type、module 路径与二进制 hash、G0/G2/G3 配置和审批身份、源码依赖闭包。
- scenario/seed、所有显式初态、event 表、global/local tick/epoch、RNG 抽样策略和版本。
- truth/estimate/command quaternion、真实/估计角速度、IMU、有效性/reason、request/limited/actual
  torque、外扰、I/P/D/AW 诊断、source/publication/feedback-command timestamps 及更新标记。
- 原始更新流与事件/拒绝/reset trace，独立 metric、逐 criterion 和逐集成测试组的输入/期望/实际/
  单位/容差/比较/结果/原始文件定位，完整矩阵、JUnit 和日志，不只保留通过摘要。
- 每个文件及 archive hash、真实 run/job/artifact ID、有效期、重放比较、审核来源与限制。

manifest 检查必须拒绝：缺场景/准则/原始字段、假模块身份、错 source、数值与比较不符、
空/截断/错配 JUnit、删除失败记录、错误模型单位、过期 cache 冒充 verified、被替代历史 hash 损坏。
指标支持离线从封存原始信号重算，不能靠 runner 自报 verdict。

为集成 scope 增加最小强制闭包 profile，包括实际 runner/scheduler/events/metrics/evidence、
schemas、oracle/tests、G0 与权威 validator、G1/G2 源码/绑定/入口/配置/审批、CMake/presets/依赖锁、
实际 CI 和有关证据检查器。按行为依赖制定规则，不用某个 execution record ID 绕过检查。

修改整个 CI workflow 会改变既有 G2-A 和 G2-B 闭包，不能继续将旧记录假称精确适用。
在新 workflow/source 上实际重跑相关 evidence jobs，新增记录 supersede 旧记录；
历史来源完整性始终验证，当前记录还需验证 source/target/HEAD 的相关字节。
不得通过删 workflow 依赖、缩闭包或免检 superseded 历史规避收口。

采用已验证的非递归两阶段收口：先固定完整代码/测试/schema/矩阵/CI 的证据源 S，取得真实
产物；再提交只含账本、生成投影和人工收口记录的候选 C，验证闭包 S→C 未变，并让 C 完整 CI
通过。预收口 source run 如治理门未通过，应明确失败原因，不冒充完整全绿；最终候选必须全绿。
如果 C 又改了闭包内代码、配置或 workflow，则重新生成受影响证据，不能沿用旧 hash。

账本的 result、availability、applicability、review 与 coverage 独立管理。只在缓存字节/expiry
核验和明确 review 具备时升级 verified/accepted；partial 或未满足前提的规格不能被候选接受
自动标成 complete/satisfied。模型/StrictDoc 当前视图与账本保持一致，冻结 planned/not_run 不回写。

## 16 CI 回归与候选评审包

保持既有九项 CI 及真实覆盖；新增 G3 integration checks，必要时使用 Debug/Release matrix，
两个 build 都加载自己的真实绑定路径，不能 import 到另一 build 或历史模块。
controller 仍保留 Debug/Release 与 clean Debug；至少在干净 CI 环境真实构建并运行完整八场景。

各 track 的 pytest 在各自目录运行：G0 `05_integration/b0`、G1 `01_simulation/b0`、
G2-A `02_estimation/b0`、controller binding `03_control/b0/python`（或现有明确 track 入口）、
系统工程 `tools/systems_engineering`。G3 tests 与 G0 合同 tests 同 track 可分文件/标记，
不能通过新入口减少原 G0 回归，禁止根目录 collection。

数值 test、真实场景和证据验证均为必需检查，不使用 continue-on-error、零收集、skip/xfail
解释实施完成；条件矩阵中仅运行适用 build 的重建步骤，不算跳过组件义务。
失败场景也保留诊断产物；失败不能因 artifact 上传步骤成功变成通过。

每个 PR 交原 PA 的包至少含：base/head/Issue/PR；S0 决定及精确批准 SHA；本单逐项关闭表；
actual commands/cwd/environment、collected nodes/结果、scenario/criterion 覆盖；CI、raw artifact/hash/
source/expiry、闭包与重放；未通过项/局限；保护文件 hash/git status。核心缺陷、oracle 自证、
truth 泄露、错配反馈、改冻结判据、无效数据放行、伪造/缺失证据均为阻塞项。

## 17 最终收口与完成判定

G3-C 具备以下全部条件后，才交最终候选验收：

1. 收口入口与 Issue #7 的状态准确，G2 已完成来源清晰；冻结资产和用户修改完整保留。
2. 真实估计状态闭环按 G0 时序运行，plant/sensor 真值与 estimator/controller 运行输入隔离。
3. 八场景及全部准则实际执行；六个包线内性能场景所有必需准则通过，限制/非法输入场景按其
   既定类别通过，不把未触发饱和、未收敛或缺数算作成功。
4. 指标器有独立人工信号正负测试；调度、事件边界、全组件 reset/RNG、重放、配对和禁止 truth
   负变体均有受控且可定位结果；Debug/Release 的比较口径和容差有批准依据。
5. 原始产物、逐案例结果、manifest、JUnit、文件/归档 hash、source/run/expiry 和闭包能重算。
6. 既有回归与最终 head CI 全绿；版本适用性、账本/报告/系统模型阅读视图一致，未完成 G4 义务可见。

原 PA 给出候选 `ACCEPT/REWORK`；REWORK 关闭后重新提审精确 head。获得具体合并授权后合并，
再核对 main 树、main CI、证据引用和工作区，原 PA 给出 `POST_MERGE_ACCEPT` 才确认 G3 完成。

最终人工收口记录登记候选/合并 SHA、审查来源、实际结果与范围；RESULTS 只登记可追溯事实。
取得相应授权后关闭 Issue #7，并记录 G4-ready 的前提与仍待发布验证的内容；不自动启动 G4、
发布 release、删除分支或宣称全部 B0 完成。未通过性能合同则保留失败证据和具体阻塞，
不能用“程序能跑”或“已提交报告”代替 G3 出口。

## 18 执行前确认清单

- [x] 用户批准 G3 启动以及本单的三个顺序 PR 边界。
- [x] 基点/现有 PR/Issue 与用户工作区重新核对，无另一主工程增量冲突。
- [x] 收口文件和当前入口清单明确，历史快照与冻结资产保护规则明确。
- [x] S0 设计、指标解释、事件拒绝/重试策略和可达性检查随本候选交原 PA。
- [x] 环境与绑定可复现，无未说明的新权限/账户/依赖前提。
- [x] 完整测试/场景/criterion 矩阵和证据 schema 先于对应实现固定。
- [x] 合并、Issue 关闭和后续阶段授权边界没有被默认扩大。

本单的 2026-10-15 草案历史保留；当前派发只推进 G3-A S0 候选。原 PA 接受精确 S0 head 后才可
执行调度/事件语义；每个候选的合并及后续 G3-B/G3-C 仍按本单门禁另行决定。
