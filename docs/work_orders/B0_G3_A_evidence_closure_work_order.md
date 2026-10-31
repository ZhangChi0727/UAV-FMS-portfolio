# B0 G3-A 真实集成补证与关闭工作单

版本：v0.1-owner-review。日期：2026-10-22（Australia/Perth）。
编制、阶段放行与最终验收：原 Project Administrator（PA）。实施：Task Carrier（TC）。
执行对象：[PR #23](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/23)，主 Issue：[#7](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/7)。

**当前状态：仅提交 Owner 审阅；未派发、未取得任何新增运行、Git 写入或合并权限。**

## 1 目标、出口与不变边界

本单不是再开一轮研究，而是补齐原 G3-A 已定义、尚缺真实证据的集成义务，形成从实施、
环境/F0、真实执行、独立复核，到候选评审、具体合并授权和 main 验收的完整关闭路径。

最终出口为原 PA 对实际合并对象给出 `POST_MERGE_ACCEPT / G3_A_CLOSED`。
仅写完测试、静态接受、CI 绿色或 `IMPLEMENTATION_ACCEPT`，均不单独等于 G3-A 关闭。
如 Owner 暂不批准合并，可停在“技术接受、候选就绪、G3-A 尚未关闭”。

保持模型 A：姿态刚体旋转子系统、机体力矩级执行器、IMU、姿态估计与级联控制；保持
NED/body、SI、scalar-first Hamilton quaternion。生产控制仍由既有真实 C++17 核心承担。
不复制 plant、IMU、估计器或 PID 作为生产替身，不把 truth 接入估计器/控制器，显式批准初始化除外。

以下不属于本单：

- 冻结 G0/需求/SysML/验证规格变更，数值算法、生产参数、包线、判据、容差或正式 seed 修改。
- G3-B 八场景/37 criterion 性能验收、50 ms 饱和覆盖、重新调参、旧研究重跑或补写历史来源。
- P1/SR6 challenge 包的运行；其环境/F0 `NOT_READY` 不成为 G3-A 的新增前置门。
- G3-C 全面收口、G4、B1、精细模型、实机、板端、实时闭环 HIL、飞行或论文包。
- 关闭整个 Issue #7、删除分支、release、强推、本地安装/升级工具或依赖、新增依赖/MCP、付费或共享文献库写入。
  CI安装既有锁定依赖仅在A3明确批准的bootstrap内允许，不隐含本地安装许可。

本单中的真实闭环是开发用 integration simulation；不得升级称为 HIL/flight 或未经定义的 SIL。
50 ms 是后续 B/总体出口的问题，不自动阻塞 A 的实施接受；本单不降低其未来义务。

## 2 输入身份、既有工作与实际缺口

### 2.1 编单快照

本地 HEAD：`6271219b2e4f68f9574542688a839c8c37381e44`；分支：
`codex/b0-g3a-deterministic-loop`。这不是本轮已核实的远端 PR/main 状态；V0 必须另行只读核实。
S0 `DESIGN_ACCEPT` 对象：`e3a5df2c7b21b4f4a4c7c6f296e0711222ac2569`。

编单时读取的关键原字节 SHA-256 如下；它们是输入定位，不是完整执行闭包：

| 文件（仓库相对路径） | SHA-256 |
| --- | --- |
| `docs/work_orders/B0_G3_work_order.md` | `E87F0D565697BD0581145856630EB87F1B1D3B3226DD4406233C4D41A847023D` |
| `systems_engineering/reports/b0/g3_s0_integration_design.md` | `AB3730AC97170374CA28ED395C6AE5F126B80C9965737AA9E204A12E2F259443` |
| `systems_engineering/reports/b0/g3a_implementation_review_status.md` | `CAD97DF05B007710C4AEBC41625B2AAEEDBF622F508DBBC1FF826C70281038F3` |
| `systems_engineering/reports/b0/p1_bounded_static_repair_review.md` | `FEEC435B9A9DB318A827E8134FC748C1C4A704DECB427FE669CC4A84CF581051` |
| `05_integration/b0/runner.py` | `7E7BAEC4210E87DA8A799346C8234609EA425D034B7AD96A5B21AE60ADA6D403` |
| `05_integration/b0/scheduler.py` | `5AA6A5B4DB765E28E476098224010CC34F2EFAAAED31BF184C6D280D0742C6C1` |
| `05_integration/b0/events.py` | `833AB6310F51A10BF058B2A882FE092B4946CB1C63A7D49C67D8E18B97260CA1` |
| `03_control/b0/python/controller.py` | `C51A19461ED95FC531F0CD614C489B84CBF63E8E26C300249E370C1C00646790` |
| `CMakePresets.json` | `C26792ACB4434DF9B21E92C4943E4662147BFBAC931815638CBDBA9256FA501F` |
| `03_control/b0/CMakeLists.txt` | `D49BEAF91DCD6E113CC2C5F43256ADF7C4AF2E9D97119F53BB6827E0D24BD4FD` |
| `.github/workflows/g3a.yml` | `6821AF41A56FDD1C11AA33C4FBD162EC4687263FC93F77B07752D8F48EB1C913` |
| `.github/workflows/ci.yml` | `3D07E48D8DF76445F7D752F9E6C6A79EE2C8B567A78F966803AAF293335F3F51` |

G0 当前 raw SHA-256：`CF3BA49791A316E5C5F99B3EB0989633659327B544C95A89A0162828CC72C86A`；
canonical LF SHA-256：`5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`；
Git blob：`1beff6e6a9a81d0ab92b2059a93207ffed9d291d`。
只准 CRLF/CR→LF 规范化；执行时必须验证**实际消费的同一份字节**并调用权威 validator。

### 2.2 已有成果不能丢失，也不能扩大解释

| 已有成果 | 可复用范围 | 仍不能声称 |
| --- | --- | --- |
| 接受的 S0、整数 scheduler、events、12-tick 真组件 smoke | 设计与局部接口基础 | 运行中 reset、旧 epoch、非法恢复已验收 |
| controller-first reset 事务 | reset 输出与 actuator 初态配对方式 | 全组件/RNG/奇偶 reset 已有真实证明 |
| 有界参数研究的有限负结论 | 保留原生产参数和研究历史 | 新参数获批、历史研究正式证据完整 |
| 旧 33-path 来源清单、filter fail-closed | 新闭包盘点起点 | 新 harness/checker、运行环境、执行时身份已完整 |
| R/D/N 文献与设计包、P1/SR6 静态接受 | 边界、机制、原始字节保全原则 | 参数数值充分、真实检出、构建/运行已经通过 |

`formal_study_evidence_complete=false` 和 `2026100906` 永久暴露记录保持，不恢复 holdout，
不倒填历史 run 的执行时来源。本单只生成新的、明确标为开发补证的证据。

### 2.3 原 A 六类缺口

1. 全组件运行中 reset、奇偶相位、RNG 清理及前两次有效更新。
2. 所有 runner-held 角色的旧 epoch 拒绝且状态不污染。
3. 真实非法 controller/estimator 调用、完整快照不变、合法恢复及 missed-tick 边界。
4. 固定输入的 truth 不变性，加受控禁止边负测与静态允许路径审查。
5. 多次真实 publication、间隔 hold、request/limited/status/反馈与时间配对。
6. 本次实际执行时的完整 source/config/environment/build/module 身份及非作者独立复核。

## 3 审批方式与分工

### 3.1 拟申请的权限分组

Owner 审阅后可分组批准；**本稿本身不授予下列任何权限**。技术权限不包含合并。
每个阶段只有在相应批准和 PA 阶段记录同时成立后才能启动。

| 权限组 | 拟允许 | 尚需的精确对象/条件 |
| --- | --- | --- |
| A0 静态实施与本地来源冻结 | V0–V2，按精确文件清单写实现、规格、测试与静态复核；只读 PR/CI；在受审隔离 checkout/worktree 内按精确 allowlist 作本地 commit 冻结 Si，不 push | Owner 批准本组（含本地 Git 写入）；单写入分工/保护表、隔离路径/分支先登记；不切换共享 dirty 分支 |
| A1 环境盘点 | §6 E1 的有限 WSL/metadata 动作 | PA 先接受精确 launcher、脚本、argv/cwd/env；未知启动代码不得执行 |
| A2 本地资格验证 | §7 的真实 Debug/Release 构建、§8–10 的有限开发运行与离线检查、已列明回归 | V2 静态接受；E2 真实工具子进程清单和完整额度先提交 Owner 批准；PA 核 F0 后释放运行 |
| A3 远端协作与 CI | 精确 allowlist 的候选元数据本地 commit、push 到现有 PR #23、已冻结 workflow 的 CI campaign、必要 artifact 上传下载 | 单独批准精确来源清单、CI 展开清单/网络资源盒；不能由一次 push 隐含获得未知运行许可 |
| A4 具体合并 | 仅已接受的 PR #23 精确候选 head 的合并及已批准 main 验收 | V4 后另取 Owner 明确授权；不得以批准本单替代 |

A1/E2 的目的在于填实当前未知环境，而不是不断要求 Owner 批准同一个已知命令。
在已批准的精确资源盒内由 PA 分阶段放行；新工具、未知可执行家族、预算/范围/判据变更才再申请。
未填实的命令模板、占位路径、未知 helper 上界均不是可执行许可。

### 3.2 单写入与非作者职责

| 角色 | 负责 | 不得自行批准 |
| --- | --- | --- |
| TC | 源码/调用图与环境盘点；薄 session、运行入口、透明观察器、夹具素材化；实现侧测试；获批后的构建/运行、原始记录；诊断并修复范围内缺陷 | 自己代码/日志的独立 oracle、F0 接受、G3-A 接受、扩大运行或合并 |
| PA | 接受 V0/V1；冻结权限/资源盒；组织非作者编写期望与 checker；阶段释放；审精确 source/build/raw；候选及 main 验收；Owner 汇报 | 代 Owner 批准新范围/运行盒/合并；把作者自验当独立复核 |
| PA 指定非作者 | 独立整数时序、快照字段/边界、truth/epoch 预期、raw checker、来源及 F0 复核；不使用 DUT 生成唯一期望 | 自验自己写的 checker；用再次闭环重跑替代读取原始证据 |
| Owner | 审批权限组、E2 未知项、超额/范围/规范变更及最终精确合并 | — |

Researcher 不重启；无定点文献检索任务。PA 若亲自编写某 checker，其独立验收交另一非作者。
TC 不写独立 checker；非作者不改 TC 的运行实现。停写、报精确 hash 后交接；不覆盖活跃编辑。

### 3.3 资格验证与修复预算

提议首次 source `S1`，加至多两次**已诊断、范围内修复后的**重新资格验证 `S2/S3`；最多三轮。
这不是随机重试额度：同源失败不得为挑选结果再跑；启动失败、超时、部分执行都消费本轮相应额度。
每轮有新 attempt、先封存 source/输入、保留全部失败、明确影响项和复验清单。
未变化的已接受静态项目可复用；运行来源闭包改变后不能复用失效的旧 runtime 结论。

上一静态修复阶段“目标未完成则继续”的许可，不解释为本轮无上限运行/构建/CI 许可。
超过三轮、需要第四个来源、任何规范/参数/环境扩展时，停止并交 Owner 原因与新预算。

## 4 V0–V6 阶段、产物与放行

| 阶段 | 工作和交付 | 放行/出口 |
| --- | --- | --- |
| V0 基点与保护 | 只读核 PR/main/head/CI；读取原工作单及批准链；保护清单、旧证据适用性、差异清单、文件归属 | PA `INPUT_ACCEPT`；漂移有解释，不凭旧摘要假定远端状态 |
| V1 补证设计与资源盒 | §8–10 夹具、原 A 逐项映射、调用分母、oracle/tolerance、环境计划、候选文件/node 清单 | PA+非作者 `DESIGN_AND_BUDGET_SPEC_ACCEPT`；这是实施设计，不是运行许可 |
| V2 静态实现/E1/E2 | 按 A0 实施；按 A1 盘点；非作者静态复审；按已批 A0 在隔离来源本地提交冻结 Si；形成精确命令和运行 manifest | `STATIC_IMPLEMENTATION_ACCEPT` 与 `EXECUTION_REQUEST_READY` 分开；Owner 批 A2/E2 后才配置构建；Si 不依赖先 push |
| V3 F0 与真实补证 | 构建前身份门；Debug/Release 真实构建；构建后 F0；各一批开发运行；离线重建、原 A 矩阵、必要选定回归 | 原 PA 对精确 `Si` 给 `IMPLEMENTATION_ACCEPT` 或 `REWORK/INCONCLUSIVE` |
| V4 PR 候选 | 获 A3 后按精确清单提交/推送；CI、原始产物可得性、账本/投影；形成最终候选 `C`；审 `Si→C` 行为闭包 | PA 对精确 PR head 给 `CANDIDATE_ACCEPT`；所有必需检查和证据可审，尚未合并 |
| V5 具体合并 | 把 `C`、CI/artifact/review 标识交 Owner；获 A4 后合并 PR #23，登记实际 merge/main/tree | 不预写 merge SHA，不合并其他 PR |
| V6 main 验收/关闭 | 核合并树、行为相同/差异、main CI 原始补证与独立结果、可得性；最终签署 | `POST_MERGE_ACCEPT / G3_A_CLOSED`；仅更新 Issue #7 的 A 子项，B/C 与 Issue 本体保持未关闭 |

若最终候选的行为依赖不同于已接受 `Si`，必须重新资格验证，不能叫“仅文档变化”。
候选 `C` 只允许真正不参与执行的账本/投影/人工收口记录变化；workflow、测试、checker、配置
也属于行为闭包。main 发生新漂移则停止适用性判定，不把 PR CI 冒充 main 实测。

## 5 文件范围、保护和隔离来源

执行前按以下责任边界固定**实际逐文件 allowlist**，不能把整目录写权限当精确清单：

- TC：`05_integration/b0/runner.py`、必要的 `scheduler.py/events.py` 最小修复；拟新增
  `integration_session.py`、`g3a_evidence_driver.py`、`configs/g3a_evidence_profiles.v1.json`、
  `binding_checks/check_g3a_runtime.py`（调用/记录，不生成独立期望）、必要既有 smoke 接口；
  拟新增 `tests/test_g3a_session.py` 等明确列出的本 track 实施测试。
- 非作者：拟新增 `binding_checks/g3a_independent_checks.py`、固定独立期望/schema 及其审查记录。
  保持最小文件数；期望表与执行夹具分开，禁止复制生产算法作为 oracle。
- TC 提案、PA 审：`.github/workflows/g3a.yml` 必要补证/去重改造；只有实际依赖闭包或证据缓存
  接口需要时才改 `.github/workflows/ci.yml`，不削减原九项检查。默认不改 root/track CMake 和 presets。
- PA：拟新增 `systems_engineering/reports/b0/g3a_evidence_closure_protocol.md`、精确 input/run manifests、
  `g3a_evidence_closure_review.md`；后续更新原 A 状态记录、执行账本及受控投影，不能改冻结权威源。
- 环境 metadata、快照和监督 helper 如确需新增，先在 V1 逐文件登记作者/API/hash；它们也要非作者审查，
  不能作为未申报的“工具小脚本”执行。

代码可重用既有公共接口；若不能在上述集成层修复而必须改 G1/G2 数值实现或公开合同，停下申请。
不得改 G0、生产参数/批准 overlay、StrictDoc/SysML 权威源、原研究 protocol/raw/summary/sidecar。

保护 `docs/work_orders/B0_G1_5_work_order.md` 的用户修改、G4/B1 未派发草案、共享 literature、
R/D/N 全包和旧 attempt、P1/SR6 所有文件。V0 保存当前 dirty/未跟踪逐文件 hash；后续保护当前内容，
不能为了符合旧 hash 还原用户新改动。禁止 `git add -A`、强推、破坏性清理/切分支。

有执行许可后从**精确来源快照/隔离 checkout**执行，只含本次接受文件；不复制凭据/私有笔记。
WSL 路径、Windows 路径、模块目录和原始 source tree 分开记录，不假称目录天然同步。
本单获批后保持原字节；进度放在 protocol，运行 manifest 绑定工作单 hash 和 `Si`，避免自引用提交。
`Si` 必须是在 A0 本地 Git 冻结权限下建立的真实 commit；若本地 Git 写入未获批准，停在静态候选，
不靠允许 dirty provenance、改身份检查器或先 push 绕过。隔离来源纳入实际拟进入 PR #23 的文件，
保护他人 dirty，非本次文件不得夹带提交；不对共享工作树作 reset/checkout 清理。

A0 的 Git-local 冻结也有执行边界：事前只读核有效 Git config、attributes、clean/smudge/process
filters、hooks、签名helper、fsmonitor、worktree/setup启动链；冻结实际 Git 可执行文件与argv。
提议隔离来源创建至多1次，每Si精确暂存/本地commit各1次（Si最多3个）；不自动amend/重试。
默认附加helper额度为0：以受审单次命令设置避免触发未批准helper，不修改用户永久配置；不得运行
自动格式化/测试钩子。若仓库要求某helper/签名/过滤流程，不绕过要求，先取其精确执行批准。
无法静态说明时停在静态候选，不先commit或checkout再由E2追认。A0不是新程序/测试的一般许可。

## 6 环境核验 E0–E2：先盘点，后有界执行

### E0 复用历史资料（仅静态）

历史候选是 WSL Ubuntu20.04、CPython 3.11.17、`.venv-b0`、GCC 9.4、CMake 3.30.5、Ninja、
pybind11 2.13.6；都不是本轮当前事实。旧 cache 的 source 为 `/mnt/e/Project/uav-fms-portfolio`，
环境文档的 Linux 活跃 checkout 为 `/home/chi/src/uav-fms-portfolio`；必须选择一个实际 source，
核实际 HEAD/dirty/路径/配置和依赖字节，不能混用。

优先复用已安装环境，不安装、不升级、不联网。Windows CLion/PyCharm 可作为编辑入口，
不能据此宣称 Windows/WSL ABI 或构建身份相同。仅选一个受审主环境；跨环境验证需另预算。

### E1 有限环境盘点（须 A1）

| 动作 | 提议硬上限 | 前置/输出 |
| --- | --- | --- |
| Windows 只读 WSL 发行版查询 | 1 次，60 s | 精确 `wsl.exe` 路径/argv 先核；无 distro install/update |
| WSL guest 启动及 metadata Python | 最多 2 次 guest 启动、2 个受审 metadata Python 进程，各 60 s | 串行；第一步安全 metadata，第二步经接受后确认正常 venv 身份；不导入 DUT/NumPy/pybind 作探针 |
| 静态读取工具/venv 启动来源 | 预先固定有限路径清单 | `pyvenv.cfg`、包 metadata、`.pth`、sitecustomize/usercustomize、launcher、CMake/工具配置；无递归不受控扫描 |

先静态审查 Python 启动链，第一步采用受审无 site 启动读取必要 metadata；Python 3.11 的
`-S` 结果不冒称正常 venv 运行身份。未知 `.pth`/启动代码、缺 tool/config、路径漂移立即停止，
不得为了“查版本”先执行未知 startup。第二步只在启动链接受后执行，不导入组件或调用配置 loader。
精确 script/argv/cwd/env 在运行前签署；本表不是对任意 `wsl`/shell/Python 命令的通用许可。

### E2 静态冻结真实执行图（必须先于 configure）

TC 根据 E1 的**实际安装文件**读取 CMake/FindPython/pybind/Catch/工具启动链，非作者核查，
PA 提交完整 `execution_manifest` 给 Owner。每个动作至少列：

`permission_id, stage, source/hash, executable/path/hash, argv, cwd, env_allowlist,
parent/child_family, child_limit, timeout, filesystem/network_scope, output,
consumption_counter, on_failure, stop/kill_method, responsible, approving_record`。

必须盘点并定量：compiler-id/ABI/try_compile（含生成的探测程序）、FindPython 和 pybind helpers、
Ninja/compiler/assembler/archiver/linker、Release LTO/strip（如实际存在）、Catch 配置/源准备、
素材化/metadata/快照/F0checker/observer/supervisor、collection/import/module load/validator/checker。
不需要对每次 stat/hash syscall 建额度；必须列所有有独立作用的程序与组件消费。

现在未知的内部进程数不填假数，也不设无限“其他 helper”。**外层两次 configure/build 上限不能
代替内部家族/上限批准**。静态资料仍不能确定时交 Owner 一个限定环境补证请求；不能先 configure 再补账。
被动 process trace 只报告发生过的动作，不能声称阻止首个未知子进程；事前授权和实际观察分开。
监督/超时必须能终止实际 guest 进程组/子树并证明停止；工具返回 session ID/WSL wrapper 超时不等于已停止。

## 7 真实 G3-A F0：生产 binding 的构建前/后两道门

F0 是本次真实 G3-A source/environment/build/module 的适用性核验，不是跑 P1 五个隔离 mutant。
不能要求构建前已有新 binary hash；先接受构建输入，构建后、任何 DUT 导入前接受实际 binary。

### 7.1 每个资格验证 epoch 的本地构建提议

| 动作 | 上限/明确行为 | 不包含 |
| --- | --- | --- |
| driver 顶层 G0 事前身份/权威校验 | 每个 build 批次 1 次，共 2；仅指顶层 gate，不是所有 validator 调用总数 | 生成新合同、改 validator/正式场景；内联 loader 校验另列 |
| 独立 Debug/Release configure | 各 1 次，共 2；每次 120 s；全离线 | 自动下载 Catch、安装/升级、默认 root legacy |
| 生产 target build | 各 1 次，共 2；每次 600 s；`--parallel 1`；显式 `b0_controller` | 默认 ALL、CTest/discovery、P1 targets、额外 G2 mutant 编译/运行 |
| 显式 pybind Python 调用 | 现 CMake 每 configure 2 次，合计 4；版本与 cmakedir | FindPython 等未知隐含 helpers；须在 E2 另列 |
| 既有 G2 mutation 源准备 | 现 CMake 每 configure 4 份，合计 8；仅源码生成 | 编译/运行 mutant；不能误报源准备为零 |
| 生产编译链接 | 每 build 两个 translation units、一次 core archive、一次 binding module link | CMake 探测编译/LTO 子动作；它们在 E2 独立列明 |
| F0 独立核查 | 每 build 1 次，TC 只交事实、非作者核；PA签门 | 导入或构造 DUT、跑 smoke 来“探测能否加载” |

以上 timeout 是资源提议，不是预计完成时间。失败/超时消耗本次动作；不自动重试。
复用现有 B0-only preset 语义：legacy/readiness OFF、B0 ON、C++17；不能裸用 root 默认配置。
Catch2 精确 3.5.4 必须来自受审已安装包/固定本地源，锁定离线 fallback；缺失即停止。
保留并审查实际编译链接/浮点选项。旧 Release 有 pybind LTO，不能静默套用 P1 的 no-IPO/strict-FP。
需要改变 build policy 时明确提案及影响，不以环境修复偷换 G2 已接受构建语义。
G1/G2 loader 和现有 S 还会内部调用权威 validator：单个原 S 路径已有 runner、G1、estimator、
controller loader 等多次校验，不能写成全部仅一次。V1/E2 按真实构造/加载调用图给出内联
validator/config 解析的独立总额度，保留既有校验，不为适配预算删掉或绕过它们。

### 7.2 F0 必交资料

1. 原字节 source/config/批准链、完整依赖闭包、隔离根、无遗漏 dirty、消费字节与 manifest 一致。
2. 实际解释器/venv/ABI、Python headers、NumPy/pybind/Catch 有限依赖与来源字节、工具二进制身份。
   live venv 可用，但非作者先接受依赖集合，再核每份实际字节；版本/RECORD hash 不等于集合完整。
3. root/track CMake、presets、有效 flags、compile/link commands、配置/build 完整日志和进程消费表。
4. 实际 Debug/Release 模块路径、原字节 hash、平台后缀/ABI、对应 source/build，二者分进程/目录加载。
5. 运行闭包扩展覆盖新增 session/profile/driver/checker/schema/tests/workflows/采集与启动 helper。
   旧 33-path 不是固定配额；必要 G1/G2 公共包、quaternion、core/header/binding/配置批准均不可漏。
6. 未知/越界/缺失项显式为 `NOT_READY`；不能用旧模块、旧 smoke 或事后拼的 build 身份放行。

避免调用旧调参/可达性入口取得 provenance。若复用旧 `_authority_identity`，要计其 Git 子进程，
审查 filter/fsmonitor/配置；`git cat-file --filters` 可能执行程序。普通 12-tick smoke 没有完整来源链，
必须在本次真正执行前封存新闭包。任何 checkout filter 只可作为诊断，不替代精确字节/canonical LF 身份。

## 8 真实集成补证矩阵：固定最小开发集合

所有新闭环 profile 使用 tuning seed **`2026100900`**，无候选优化、随机扫描或正式场景选择。
正式 `2026100901–2026100908` 不用于这些 profile；尤其不再运行 0906。
现有组件回归若有自己的固定种子，必须在独立 node 清单登记并批准，不混入本表或隐瞒消费。

以下是拟新增开发 fixtures，不是已存在 CLI，不是正式 G0 场景结果。V1 冻结每个精确数值/初态/
事件/调用/node，来源能追至现有批准值。不能运行时再根据结果选值或放宽比较。

| ID/每 build 次数 | 固定输入与过程 | 必交结果/边界 |
| --- | --- | --- |
| S ×1 | 原 12-tick G3-BIND，实际五组件、原命令、seed0900 | 保留原真实 smoke 义务；一次执行同时保存 raw/JUnit，不再 pytest 后 CLI 重跑 |
| L ×2 | 独立开发 profile；horizon1200；controller negative_dt 在400，estimator stale_timestamp 在800，reset1000；位置/类型/值沿用 S0；只 seed 明确为0900 | 两种拒绝各一次、精确原因/快照/同 tick 单次修正；reset-only1000，1002/1004有效；两次真实运行独立初始化并匹配 |
| O ×2 | horizon13，运行中 reset R7；起始/reset 后相同显式初态及 reset-local 命令；tick6 另施 §9.3 的 missed-tick 故障 | 奇相位9/11/13更新，RNG 清理、真实重复与 missed-tick 只能 reset 恢复 |
| E ×1 | horizon38；六个 ±x/y/z 命令依次 [2,4)、[6,8)、[10,12)、[14,16)、[18,20)、[22,24)；外扰[26,28)、bias replacement[30,32)、additive force[34,36)；幅值/plant-only offset 源自现有批准声明 | 每类前/起/末/结束边界、符号、帧、初始化、三次以上 publication/hold/phase2；压缩时间仅开发声明，不是正常场景复现 |
| T ×2 | 从 L1 的1002/1004封存真实 IMU/command/feedback，按原 epoch/time 显式 reset 新 E/C；各2更新；仅 evaluator-owned truth 副本不同 | 相互及对 L1 同输入输出比较；不调用 plant/actuator/IMU、不采新噪声；测试初始化不能从 truth 派生 |
| N ×2 | 隔离的 evaluator-truth→estimator-input、evaluator-truth→controller-input 两个禁止边 | 同一允许路径检查准确检出具体边；在真实 E/C消费前拒绝；不靠“输出不同”宣称检出 |

L 的 seed0900/development ID 必须显著记录；不能把它写成正式 `invalid_input_and_reset/0908` 已验收。
T 是补充重放而非真实闭环替代；N 是集成边界负夹具而非改变生产实现的通用 mutation 平台。
E/L/O 的实际组件和调度路径须相同；禁止为测试复制一份“正确 session”。

## 9 独立预期与逐项验收

### 9.1 时间、初始化、事件、hold 与反馈

- 非作者从 fixture 整数字面表独立计算期望，不能调用被测 scheduler/events 生成唯一期望。
  base period0.0025 s，reset R 为 local0 且只 reset；R+1 仅 P/A，R+2/R+4 才 I/E/C；
  time 由 epoch origin+local tick×period 推导，scenario global clock 不倒退。
- 按 S0 顺序推进 plant/actuator、采样/事件、估计、控制；plant 消费前一 actual+独立外扰。
  保存每相位实际输入/输出与前后身份；估计/控制不能从新 tick truth 直接取状态。
- 显式零/identity estimator 初态，plant-only offset 按 G0 右乘约定；tick0 不积分。
- reset command 与 actuator held 请求/限幅/状态/时间完全配对；发布2供3/4消费，发布4供5/6消费，
  发布6供7/8消费。hold 不刷新 timestamp，不补发 publication。
- feedback 对应 phase2 的 `[k-1,k)`，不能与 settling/evaluator 的 `[k,k+1)` 混用。
  raw 记录 actual、request、limited、status、command identity/timestamp、interval 和外扰，缺一个不通过。
- 六轴正负命令独立核 quaternion 轴/符号；bias replacement 为 raw−nominal+replacement，
  additive specific force 为独立加法。事件起止是半开区间，非 due 边界也要核不产生额外样本/更新。

### 9.2 全组件 reset、RNG 与旧 epoch

- controller-first reset 一次语义事务，再 actuator、plant、IMU、estimator；部分失败终止 inconclusive，
  不继续半 reset session。清除旧 held/feedback/sample/estimate/command、event/pairing 状态与调度相位。
- 每次 reset 记录 IMU `samples_emitted=0`、`next_sample_tick=2`、last sample 空；首两次样本编号1/2。
  保存 seed、reset epoch/origin、reset-local index、真实 measurement 和比较 trace。
- O 的同初态/同 reset-local 输入比较 reset 前后首两份 raw IMU；L/O twin 再比较对应 trace。
  时间戳按 global/local 映射比较，不要求两个 origin 的绝对 timestamp 相等。
  不虚构私有 RNG scalar draw index；样本计数、源码调用与可观察重放证据分开。
- session-owned envelope 保存真实对象生成时的 epoch，不能在消费时自动贴 current epoch 掩盖旧对象。
  至少 held torque、feedback、IMU、estimate、attitude command 五角色逐个注入 prior-epoch envelope；
  其余 stateful 槽逐项列有/无与原因。每角色每 build 一次拒绝，消费前全 session/组件快照不变、
  组件调用增量0；随后正常消费同一未消费 tick。不得把五个角色合成只测一个字典标签。

### 9.3 非法输入、快照与恢复

- L400 controller 真实非法 dt 必须为 `invalid_dt`；L800 estimator 真实 stale 必须
  `accepted=false` 且精确 reason 匹配接口。每事件只计一次拒绝；保存前/后完整相关状态。
- 快照取在目标调用前后：此前正常完成的 P/A/IMU/estimate（如适用）不伪装回滚。
  纠正同一输入副本、同 tick 重试一次；不重采 IMU、不重复前序 phase、不推进 RNG。
- O6 在 P/A/IMU/E 正常完成后，对真实 controller 传故意超前 timestamp 的副本、dt仍0.005，
  必须为 `unexpected_tick` 且 controller snapshot 不变；不补正确 tick6，session进入 needs-reset。
  ordinary7 在任何组件调用前拒绝，随后显式 reset7；9/11/13正常恢复。
  此为开发 fault，不冒充 G0 两种非法事件，也不允许长 dt 静默续跑。
- controller 用公开完整 snapshot；estimator/G1 未公开字段由版本绑定、只读测试观察器覆盖
  estimate、epoch/last_tick/seed、clock、mode、held request/target、sample 等状态。
  快照字段/序列化先静态接受，不能用 repr/对象地址/仅输出 q 替代状态证明；观察器不得改状态。

### 9.4 truth 隔离与真实绑定

- 静态审查允许边：plant→IMU sensor boundary；truth→sealed evaluator；显式批准初始化。
  禁止 evaluator/event标签/truth 直接进入 E/C 输入或恢复状态。
- T 固定真实 IMU/command/feedback/初态，只改 evaluator 副本；比较两次全部有效 E/C输出与 L1。
  这是限定 fixed-input 不变性，不夸称证明任意隐藏 truth 依赖都不存在。
- N 分别引入两个真实禁止边声明/适配路径，由同一边界检查检出准确 edge；入口和所有消费分支
  必须实际经过该检查，不能仅对人工自报“我有污染”的标签返回失败。
  V1 明确绑定到既有 L/T 的某个具体 profile/tick/phase，在合法消费前以 evaluator-owned truth
  实际派生隔离的候选 IMU 或 estimate/command payload，保留 producer/字段/guard 调用定位；
  guard 拒绝后全快照零 commit，再消费原合法对象。由此不新增 DUT 构造/step；wire payload 构造
  和 guard 调用另记预算。不能只贴 `origin=truth`，也不能向 DUT 真正提交污染后再声称消费前拦截。
- S/L/O/E/T 均加载真实对应 Debug 或 Release C++模块；记录实际 import path/hash/ABI、输入参数对象
  与批准配置绑定。loader 的临时验证构造也计数；无私有 getter 就不冒称 core readback。

### 9.5 比较与缺陷可分辨

离散 tick/phase/epoch、角色、reason、计数、valid/status/调用顺序逐项精确比较。
G0/S0 已规定 quaternion 分量绝对容差1e-12，不通用放宽；同对象未消费的快照必须原字节不变。
其他浮点字段的比较目的、单位、既有依据、预声明绝对/相对界与正分离由 V1 逐字段列出。
不能在看到运行结果后挑 tolerance；不能把所有量统一套1e-12或“若干 ULP”。
Debug/Release matching trace 按字段比较，保留最大差值和定位；跨 build 不要求任意量逐 bit 相同。

非作者先审独立字面期望、错误分支及每个负夹具的 owning signature，执行后只读取封存 raw。
缺失、重复、乱序、错 epoch/phase/pairing、错 source/module/hash、NaN/Inf、错帧/单位/字段必须
不能获通过。新 checker 的有限数据破坏夹具见§10.2；精确字段/node和子调用在 V1/E2 单列，不得藏为“离线免费检查”。

## 10 逐项运行预算与去重

### 10.1 每个 build 一批的组件预算（纸面上限，不是已运行结果）

包含 §8 的 S×1、L×2、O×2、E×1、T×2；N 在真实消费前拒绝。O 包含一次未补的 controller拒绝。

| 调用/对象 | 每 build | Debug+Release/每轮 |
| --- | ---: | ---: |
| 完整五组件闭环 profile | 6 | 12 |
| E/C 固定输入 replay | 2 | 4 |
| truth 禁止边夹具 | 2 | 4 |
| Plant `step_base` | 2472 | 4944 |
| Actuator `step_base` | 2472 | 4944 |
| IMU `sample` | 1235 | 2470 |
| Estimator 顶层处理 | 1241＝1239 accepted+2 rejected | 2482＝2478+4 |
| ControllerAdapter/core `step` | 1241＝1237 accepted+4 rejected | 2482＝2474+8 |
| P/A/IMU reset，各 | 10 | 20 |
| E/C reset，各 | 12 | 24 |
| 新建 P/A/IMU，各 | 6 | 12 |
| 新建 estimator/ControllerAdapter，各 | 8 | 16 |
| C++ core 构造（含 loader 临时验证） | 16 | 32 |
| 旧 epoch 角色拒绝 | 5 | 10 |
| needs-reset 下 ordinary7 拒绝 | 2 | 4 |

分母推导：L每次1199个 P/A、599个 IMU/正常 E/C due，外加各一次 E/C非法调用；
O每次12个 P/A、6个 IMU/E due、6次C尝试（5有效+1拒绝）；E为38/19；S为12/6；
T每次2个E/C。L reset于1000、O reset于7的边界本身均无 component step。
五角色 stale 注入和 N 不新增组件构造/step/reset；在既有 session 边界只做拒绝。
完整成功批次须逐profile达到预声明精确计数/顺序，不是“少于上限就通过”；失败中止的较小消费
如实登记，但不产生完整批次通过结论。上限用于阻止越界，独立精确预期用于检测漏调用。

actuator 内部委托 `step`、estimator 内部委托 `process` 需观察但不重复算一次调度更新。
IMU 源码每 sample 两次长度3 normal 请求，属于上述已批准 sample 的内含行为，不宣称已观察
底层标量 RNG 推进次数。每次 IMU reset 的 RNG创建包含在 reset 分母；不得额外抽随机样本。
素材化/校验必须不调用 loader 的隐藏构造；若真实路径不符合这些分母，静态改设计或申请，不先跑再解释。

### 10.2 每轮辅助动作提议

| 动作 | 上限与隔离要求 |
| --- | --- |
| 输入封存/素材化 | 每 build 1 个受审动作，共2；纯固定数据，不构造 DUT；失败保留 |
| 真实补证 driver | Debug/Release各1进程/1批，合计2；每批120 s；上表全部消费限额，禁止自动补跑 |
| collection/实施侧非运行回归 | 每 build至多1次 collection+1次精确 node 执行；node数和所有潜在组件消费先在E2冻结，未列额度为0 |
| raw schema/完整性与预算审计 | 每 build1次，共2；真实 raw先hash后消费；不导入DUT |
| 独立 raw重建检查 | 每 build2次：TC一次交付检查、非作者一次独立检查，共4；相同封存raw，不新闭环 |
| Debug/Release离线比较 | 1次，matching记录读取；不再次调用runner |
| 来源/模块适用性终审 | 每轮1次；静态hash/文件/日志/身份核对，不借此探测构造或运行 |
| 配置loader/内联权威validator | V1按逐入口实际调用图冻结、E2单独批准总次数；至少覆盖S入口、G1、默认estimator、每个ControllerAdapter；不视为免费导入 |
| 数据负夹具/新checker自检 | 每 build 1 批：1合法对照+12个单缺陷副本；共2批26份record-set；不调用DUT；V1锁字段/node/程序，E2批准 |
| 既有G0/G1/G2必要选定回归 | 单独精确文件/node/seed/CTest发现/构造/step清单，计入E2，不能混入上表 |

这些外层检查次数不代替其真实子调用清单。collector/checker/loader/import及所有 helper 都在
E2统一闭包和资源表。若TC/非作者采用不同检查实现，均先审脚本和输入；PA不为复审重跑闭环。
任何 full pytest/CTest/ruff/语法检查亦是执行，必须在批准 node/工具表中，不能叫静态读文件。

12个数据负夹具固定为：缺due、重复due、相位乱序、旧epoch、错feedback配对、错source、错module、
缺必需字段、NaN、Inf、错frame、错unit；各只破坏一项。使用封存 raw 的隔离副本，不改原产物；
保留父raw hash、唯一diff、新字节hash。每副本的输入完整性外壳按其真实字节登记，使语义负测
不能只靠“副本hash变了”一律拒绝。错source/module仍须与外部已接受身份比较，不能同步篡改权威预期。
合法对照必须通过，各负例以预声明精确诊断拒绝；某类型无真实字段/独立观测时不填造字段，报V1设计缺口。
26份record-set只由每build指定的一次独立负测批消费，正常raw的TC/非作者检查另计；非作者还读取
这两批全部原始诊断/副本/唯一diff作静态复核，不额外运行负测。若需双方各跑一遍，先把申请改为
4批52次record-set消费，不能当免费复核。

新增组件总量最多为上述每轮乘3轮；不是预先必须用满，也不是跨阶段挪用额度。
CI内真实补证另按§11逐 campaign 计量，不冒充本地一次运行已覆盖所有后续CI执行。

## 11 回归、CI、Git 与候选/main 适用性

### 11.1 本地避免误收集与重复

当前 `.github/workflows/g3a.yml` 每build先pytest调用12-tick smoke，再CLI调用同一smoke保存JSON，
实际两次闭环。本提案改为**一次真实执行保存 raw，pytest/独立比较只消费同一raw**。
保留原检查强度和 JUnit，不删 smoke，也不能仍双跑却只计一次。

共享 dirty 的 `tests/test_verification_challenges.py` 属P1未来运行包；宽 `pytest -q tests` 会收集它。
使用隔离来源和显式文件/node；原有 `test_config_validation.py`、`test_g3_events.py`、
`test_g3_s0_assets.py`、`test_g3_scheduler_runner.py` 是盘点起点，读取其真实调用后锁定额度。
仅跑选定清单就写“选定回归”，不能声称共享工作树完整track通过。root pytest不支持，不运行。

修改 workflow/公共入口会改变 G2 证据闭包，必须审既有记录适用性，必要时由当前强制job生成新记录，
旧记录标历史/被替代而非删掉。G3-C的完整回归/clean Debug/八场景不被本单免除。

### 11.2 CI 是独立运行权限，不是 push 的免费副作用

编单时已有 `ci.yml` 展开9个job（readiness、G0、G1、G2A、G2B D/R、navigation、SE治理、G1.5B pilot），
`g3a.yml` 展开3个job（真实D/R、compare）。一次有关联push可能触发两workflow合计12job。
现 `ci.yml` 内存在clean Debug重建、重复CTest和证据生成调用，不能按一个CTest/job计算。

提议 CI campaign 共享硬上限：**最多5轮、按当前结构最多60个展开job**。每个 `Si` 最多1轮
（最多3个来源），候选C基本1轮、至多另1轮行为闭包不变的元数据修正，main最多1轮。
三类总和不得超过5；始终为main预留1轮。无修复的通常路径为S/C/main三轮。
元数据修正不需要虚构新Si，但仍占共享额度；S1–S3已用满时没有额外候选重跑额度。
每轮D/R真实补证各至多§10.1一批；同一raw离线检查，不另重复闭环。重跑job、push、
merge后再次触发均消费额度；未采用C独立提交时不为凑额度额外触发。取消/失败保留，不能免费重试。
main第一次campaign失败或来源漂移即暂停关闭判定，交Owner原因和有限重试申请，不自动挪用剩余额度续跑main。

这只是campaign/job的外层上限，**不授权未知job内部执行**。A3前TC必须交展开的逐step命令、
依赖与版本约束、网络目的地/下载范围、setup/apt/pip/FetchContent、compiler/测试/seed/生成器/
artifact动作及其次数与超时；PA/非作者审核，Owner批准完整CI资源盒后才允许第一次push。
新workflow使job数增加或发现未列程序/场景/seed时先停，不以60job额度吞并新范围。

CI环境不同于本地E1；`ubuntu-latest`/setup-python等下载前不能假称已有实际runner身份/hash。
A3要包含受控bootstrap子阶段：事前锁Actions来源/引用、工具家族、下载目的地、次数/超时和
OS/Python/ABI/依赖版本约束；启动后、任何DUT消费前采集实际身份/字节、核约束并封存，才放行
后续job动作。预批资源盒不要求事前知道尚未下载的binary hash，但不得包含未知家族或不受控更新。
实际超约束/缺依赖即fail-closed；bootstrap本身消耗campaign/下载额度，不能借它放行其余未批步骤。

本地网络0/安装0；CI如需要现有dependency安装/下载，必须在A3单独明确批准，不隐含套用“全离线”。
可固定已有版本/来源，不能借本单升级依赖/引入新服务。保留所有既有mandatory CI；不得为预算通过删检查。

### 11.3 证据账本与最终候选

- 新A证据要检查 RESET/TRUTH/PAIR 等规格所需 G1/G2A/G2B closure并集，不能只复制旧33path。
- schema合格、artifact可得、来源适用、PA接受、requirement satisfied是不同状态。
  当前SE治理入口未配置 `--evidence-cache`，不能无有效缓存/审核链就写 `remote_verified/local_only`。
  如需增加缓存接口，在V1/A3明确实现/权限/额度；否则已上传但未完成该链时使用合法
  `remote_unverified`，未上传/缺失等按schema真实枚举登记，不编造`available`状态。
- G3-A关闭不要求30需求/29规格全部complete；也不能借未完成的B/C遮蔽A本身缺证。
- 账本/投影只登记实测、确切source/build/run/artifact/reviewer；RESULTS只在接受后按精确事实更新，
  不把开发profile登记成八场景/50ms性能通过。
- `Si→C→merge/main` 逐文件审行为闭包及工具环境；元数据提交不改变执行来源，仍记录真实
  commit/tree关系。新行为、不可得raw、CI不匹配、漂移未审，候选或main均不接受。

## 12 原始产物与逐项可审查性

每次attempt唯一目录，先输入后执行：`approved_manifest → immutable_inputs → start →
commands/stdout/stderr/process_counts → raw → derived/JUnit → index/final`。
实际目录在V1确定并核ignored；不覆盖，不把失败/部分结果写成未发生；不上载凭据/全文文献。

至少保留：

1. 工作单/Owner权限/PA放行的hash和时间、`Si`/dirty保护、原字节输入及完整closure。
2. E1/E2/F0、实际命令/工具/env/flags/module、父子进程消费/未知项/超时和终止事实。
3. 每profile全部global/localtick、epoch/origin、phase、seed/sample index、event/invalid/reset日志。
4. truth（只给evaluator）、IMU/估计/command、request/limited/actual/status、held/feedback身份与时间。
5. 每次拒绝前后快照及错误、恢复路径、调用序列和预算；完整失败原文，不只总数。
6. 独立预期、逐字段单位/比较/tol/实际差值/raw定位、负夹具owning signature、D/R匹配。
7. JUnit与node/skip/xfail完整计数、离线checker结果、artifact原字节hash/位置/取回核查、PA决定。

不得把第三方组件自己的pass或driver汇总当独立结论。保留raw后可独立重建结果，不为“验证”再运行seed。
新A必须执行的node不得skip/xfail；不适用内容先在设计中明确移出scope，不运行后改成不适用。

## 13 停止、修复与升级规则

立即停止当前阶段并保全资料：

- 冻结输入/参数/实际source/module不符、truth泄露、旧epoch污染、错配反馈、非法输入被接受。
- 任一实测计数超预算、未知进程/启动代码/网络/依赖、缺失observer或无法证明子树已停止。
- raw/快照缺失、schema/闭包不完整、oracle同源/掩蔽/分离不足、任何mandatory skip/xfail。
- 配置/构建/导入/测试失败、超时、CI不一致或main漂移；不能继续后续profile凑通过率。

确定性DUT缺陷→TC给最小诊断/差异/影响范围，PA评是否可在剩余S2/S3预算内修复；
基础设施失败/缺证→`execution_error_inconclusive`，不冒充DUT通过或失败，但同样消费已启动动作。
部分先行phase不回滚伪造；需要reset时仅走已批准显式路径。
不得通过改参数/激励/阈值、删mandatory node、mock真实组件、复用旧module、选择性忽略失败“修复”。

若缺口不能在有限集成修复内闭合，交Owner：精确阻塞、已耗/剩预算、有限证据、最小新方案及
不继续的影响。原PA可拒绝接受/缩小未声明为关闭的结论，不能降低原A门槛却宣称A关闭。

## 14 验收清单与关闭签署

以下 `GAE-*` 仅本单检查项，不新增/重编号任何需求或验证规格ID。

| 检查项 | 通过标准 | 决策人 |
| --- | --- | --- |
| GAE01 基点/权限 | 实际PR/main/head、输入/保护、权限组、精确allowlist可审，无越权 | PA |
| GAE02 环境/F0 | E1/E2真实事实、已批资源盒、构建前后两道F0、真实D/R闭包完整 | 非作者核，PA接受 |
| GAE03 时间/初始化 | 原G3-TIME/INIT；reset-only、长序列/非零origin、due/非due与错误序列，plant-only offset | 非作者重建 |
| GAE04 发布/配对/事件 | 原G3-HOLD/EVENT；连续三发布、全部hold、phase2真实配对及所有事件边界 | 非作者重建 |
| GAE05 reset/RNG/epoch | 原G3-RESET；奇偶R、R+2/R+4有效、全状态与RNG可观清理、全部held角色旧epoch拒绝 | 非作者重建 |
| GAE06 非法恢复 | 原G3-INVALID；两真实拒绝、全快照不变、同tick一次纠正、missedtick必须reset | 非作者重建 |
| GAE07 truth | 原G3-TRUTH/NEGATIVE；静态允许边+真实固定输入正测+两个禁止边准确检出 | 非作者重建 |
| GAE08 绑定/重放 | 原G3-BIND/REPLAY；S保留，L/O双真运行，T封存重放，D/R独立且匹配 | 非作者核，PA接受 |
| GAE09 数据/证据 | A适用G3-DATA/EVIDENCE；完整raw/来源/预算，破坏夹具拒绝，无新增mandatory skip/xfail | 非作者核 |
| GAE10 实施接受 | GAE01–09及原A全部义务逐项有定位；未把B/C/METRIC/SCENARIO冒充完成 | 原PA精确Si `IMPLEMENTATION_ACCEPT` |
| GAE11 候选接受 | 必需CI/产物、回归影响/账本状态诚实、Si→C行为相同或已复验 | 原PA精确C `CANDIDATE_ACCEPT` |
| GAE12 合并后关闭 | Owner具体合并授权、实际main/tree/CI原始补证与适用性、无未闭A阻塞 | 原PA `POST_MERGE_ACCEPT / G3_A_CLOSED` |

原G3矩阵中的完整METRIC/SCENARIO及B/C专属DATA/EVIDENCE部分明确留后续，不强制塞入本单；
A适用的时序/数据/来源检查不能以“后续验证”推迟。V1逐条列原条款、归属、本单node或后续责任。

最终向Owner交一页结论：精确对象/实际执行与耗额、六类缺口关闭定位、非作者/PA结论、CI/artifact、
是否可具体合并、main验收及A关闭状态、仍未完成的B/C/50ms事项。
关闭A后只登记Issue#7的A子任务；不自动启动B/C、不关闭Issue#7，不发布release或删除分支。

## 15 Owner 审阅时需要决定什么

建议批准顺序：

1. 审本单目标、固定开发矩阵与三轮上限；批准A0和符合§6精确启动条件的A1，启动静态实施/有限环境盘点。
2. 收到E2精确命令/子进程/回归/数据负夹具清单后，审批A2本地运行盒；届时不是重新讨论模型或开新研究。
3. 候选推送前另审A3完整CI/Git资源盒；候选接受后对精确head另审A4合并。

当前交付仅本工作单。没有派发TC，没有运行程序/测试/构建/仿真/seed，没有修改冻结合同或合并PR#23。
