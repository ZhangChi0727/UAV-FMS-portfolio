# B0 G1.5-A 系统工程结构与模型视图实施工作单

日期：2026-10-11。PA 结论：本工作单技术内容已具备派发条件，无待用户决定的 A 阶段
实质设计事项。本文件不是实施完成、代码评审批准或派发成功记录。
总纲：[G1.5 工作单](B0_G1_5_work_order.md)。本轮仅执行 A，总纲的 B/C 保持未启动。

## 基点与角色

- 仓库：`ZhangChi0727/UAV-FMS-portfolio`。
- 已核实远程 main 与 Windows HEAD：`de0006392a4ac6017c4be0b6befa35f1d6cefe0e`。
- PR #12 已合并，Issue #4 已 CLOSED；核验时无开放 PR。
- TC：既有会话 `019fa435-f674-71e3-85ba-10e28ad94470`。
- PA：既有会话 `019f9ef3-4a0c-79f1-99d4-c8415f62bd29`。
- 实施分支：`codex/b0-g15-docs-governance`；一个 A 阶段实施 PR，base 为 main。

开始时重新读取远程 main、双工作区 status/HEAD 和适用 AGENTS.md。若基点变化，先比较
新增差异并向 PA 报告；若影响模型、迁移或验证依据，暂停相关部分，不能套用旧基点结论。
保留一个活跃实现副本，推荐现有 Ubuntu 仓库；Windows 用于工作单保护和同步。

## 目标和允许变更

建立一级 `systems_engineering/` 的真实可读工程入口、首批 B0 模型及工程报告导航；
将 `07_docs/` 按职责拆分迁移至该目录与不编号的 `docs/`，保持 G0 冻结资产和 G1 数值行为。

允许修改文档、图源、链接、README/AGENTS/路线图，以及迁移必需的路径解析兼容、
相关回归测试和轻量链接/渲染检查。每项非文档变更必须说明为什么迁移需要它。
禁止修改 G0 v1/v2 配置字节、性能阈值、组件算法及现有 NAV/CTL/FDI 标识。
禁止需求工具安装/全面导入、需求新编号/冻结、B/C 实施、G2/G3、研究扩展或外部仓库写入。
不得批量删除历史记录、强推、清理无关分支或直接提交 main。

## 先保护本地输入

Windows 已有未跟踪 `07_docs/work_orders/B0_G1_5_work_order.md`；本次新增本 A 工作单，
均属于 PA 交接输入，不得 git clean、覆盖、重建或遗漏。

1. 读取并校验两文件内容，记录 SHA256；检查除此之外是否还有用户修改。
2. 在核实分支不存在或适合复用后建立实施分支，只暂存这两份工作单，形成首个保护提交。
   不使用不加审查的 `git add -A`。后续迁移保留 Git 历史和原文档实质内容。
3. 通过 Git 将保护提交安全快进到 Ubuntu；先检查 Ubuntu 是否干净和有分歧。
   不用文件复制覆盖仓库，不强制 reset。冲突先保护并协调。
4. 将两个工作单最终迁至 `docs/work_orders/`，总纲和本单相互引用保持有效。

## 内容迁移的确定落点

从下表形成完整逐文件清单，不限于搜索到的几个链接；如出现表外文件，按相同职责分配并说明。

| 原内容 | A 阶段目标 |
|---|---|
| project_charter.md、development_baseline.md | systems_engineering/ 同名文件 |
| architecture.md | systems_engineering/models/architecture.md；保留 EXT-NAV 历史部分的适用范围 |
| requirements.md | systems_engineering/requirements/legacy_requirements.md；仅更新适用性摘要，不发明 B0 需求条目 |
| verification/verification_plan.md | systems_engineering/verification/verification_plan.md；只迁移及纠正失效链接，不提前扩展 C |
| v_and_v_report.md、development_readiness_report.md | systems_engineering/reports/ 同名文件 |
| b0/g0_contract.md | systems_engineering/models/g0_contract.md |
| b0/g0_acceptance.md | systems_engineering/verification/g0_acceptance.md |
| b0/g0_approval.md、g0_approval_decision.md、g0_review_resolution.md、pr11_review_report.md | systems_engineering/reports/b0/ 同名文件，保留历史事实 |
| roadmap.md | docs/roadmap.md，保持唯一范围/依赖说明 |
| development_environment.md | docs/development_environment.md |
| work_orders/ 全部文件 | docs/work_orders/，保留历史轮次 |

以 Git move 等可恢复方式迁移，先核对绝对源/目标位于仓库内且无目标冲突。
根 README 同时链接系统工程入口、开发文档和结果摘要；更新 AGENTS 的必读路径。
RESULTS.md 仍为已验证结果摘要，链接系统工程报告，不复制实时 Issue 状态。
保存 `docs/migration_g15a.md`，记录完整旧新路径、当前引用修复和可保留的历史引用理由。

## 冻结合同路径兼容

G0 v2 内的原始批准来源字符串保持不动：`07_docs/b0/g0_approval_decision.md`。
唯一 G0 校验入口将这个精确历史路径解析到
`systems_engineering/reports/b0/g0_approval_decision.md`，以模块位置推导仓库根，不依赖 cwd。
这里只允许位置兼容，不能把任意尾部相似路径或越界路径认作有效批准来源。
不要维护两份决定正文；旧路径可以作为记录/映射键存在，不要求物理副本。

必须测试：合法历史引用、准确新目标存在、缺失新目标拒绝、越界/伪装引用拒绝、不同 cwd、
G1 经权威 G0 校验器加载。保留原有严格日期、版本、审批字段和技术规则。
迁移前后记录 v1/v2 配置 SHA256 并精确比较；不改变历史配置或伪造原批准 hash。

## 首批模型与读者入口

使用 Markdown 内 Mermaid 或相邻可编辑文本图源，不强制安装大型建模平台。
复用已有合同，以图和简短分配表表达以下视角；可合并文件，不按图的数量验收：

1. 系统上下文：使用者、实验平台边界、输入输出、外部依赖与 B0 排除项。
2. 功能/逻辑架构：Plant、IMU、估计、控制、执行器、集成和独立验证职责。
3. 接口流：真值允许/禁止路径、关键消息方向、单位/坐标、配对时间和状态所有权。
4. 行为：启动、正常更新、输入拒绝、运行时 reset；区分 G0 约定与 G1 实现、G3 未来调度。
5. 部署与扩展：当前 Python 组件、计划 C++ 核心、执行环境及 EXT 的依赖边界。

每个视图标出适用基线、来源定位、已验收/待实现/未激活图例。不得把计划的闭环或硬件
画成已有能力。模型元素可用清晰的局部稳定名称，正式需求编号和联合冻结留给 B。
涉及数值时链接批准配置字段，不建立第二套参数源。

`systems_engineering/README.md` 提供“用途→模型→需求现状→开发状态→验证报告→证据”
阅读路线。在 reports 复用已有报告并增加简短入口，标明 G1 已验收、B0 尚未整体完成。
A 只整理现有报告和事实，不宣称已完成 B 的完整需求或 C 的完整验证治理。

图源需实际渲染检查，记录方法/版本或受检 PR head；检查箭头、长标签、图例、断行和
链接是否可读。若渲染依赖不可用，报告具体限制，不用“源码看起来正确”替代视觉核验。
仅需文档/PR 可读展示，不建设网站或应用。

## 检查和证据门槛

在同一待评审 SHA 上分别执行，不在仓库根收集 pytest：

| 工作目录 | 命令或检查 |
|---|---|
| 05_integration/b0 | 既有 venv 的 python validate_config.py，及 --config configs/b0_g0_contract.v1.json、v2.json |
| 05_integration/b0 | python -m pytest -q；python -m ruff check . |
| 01_simulation/b0 | python -m pytest -q tests；python -m ruff check .；python evidence.py |
| 新增迁移检查的独立测试目录 | 正反例测试、链接与锚点检查，PR 写明真实路径和命令 |
| 仓库内 | git diff --check；核实 PR base SHA 后的完整 base..HEAD diff --check |

Ubuntu 解释器复用 `/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python`，先检测可用性。
权限拒绝按工具机制申请，不直接当作 WSL 损坏，不重装环境。

要求：

- 原 G0/G1 测试不得减少、skip/xfail 或弱化断言；新增迁移反例必须实际执行。
- 最新 head 的 G0、G1、导航和 development-readiness 必需 CI 全成功，新增迁移检查也进入 CI。
- 导航既有预期失败单列，不作为 B0 完成证据；本机未执行 C++ 不记为本机通过。
- 配置 hash 不变；迁移前后 G1 evidence 的数值、门槛与判定一致。代码 SHA 等出处字段
  可以合理变化，逐项说明；不能要求整个 JSON hash 恒定，也不能忽略数值变化。
- 链接检查覆盖当前 Markdown/目录/锚点和运行时引用；隔离反例证明失效链接确实失败。
  扫描剩余 07_docs 引用并按历史/兼容例外列明，不盲目清零。
- 保留 CI artifact 和图示可读性核验记录，不提交凭据、完整私有对话或大型生成导出物。

## 交付与确切 head 评审门禁

TC 提交一个真实 A 实施 PR，关联真实创建/复用的执行 Issue，附加 PR 到原 TC 会话。
PR 描述必须含基点、保护提交、迁移清单、冻结配置比较、模型来源、渲染核验、各命令结果、
CI/artifact、未决项与明确 scope。返回双工作区 SHA/状态，不谎称带未提交修改的副本为 clean。

PA 对准确 PR/head 独立给出 `APPROVE` 或 `REWORK`。REWORK 必须有发现、复现和验收要求，
TC 在同一 PR 修复后提交新 SHA 复审；CI 成功或 TC 自评不能替代 PA APPROVE。
任何 head 变化都应标明变更范围并重新取得对应 head 的批准，不沿用旧结论。

只有针对最新确切 head 的 PA APPROVE、全部要求 CI 成功，以及用户合并授权同时成立，
TC 才可按项目方式合并。合并前再次核对远程 head，不能合并未经审阅的额外提交。
随后 TC 提供 merge SHA、双工作区安全同步及合并后回归证据；PA 独立验收。
PA 验收后编写 G1.5-B 工作单并停止，本轮不执行 B/C，不开启下一 PR。

## A 阶段退出清单

- [ ] 两份 PA 本地工作单已原样保护后安全迁移，无用户修改丢失。
- [ ] 一级系统工程入口和必要模型可读、有来源、有成熟度边界。
- [ ] 所有原文件均有唯一职责落点，历史事实保留，当前引用有效。
- [ ] 冻结配置未变，精确历史路径映射及安全拒绝回归通过。
- [ ] G0/G1 数值与既有必需 CI 无回归，所有要求证据可定位。
- [ ] PA 对最新确切 head 明确 APPROVE，TC 按授权合并，PA 完成合并后验收。
- [ ] 产出下一阶段工作单后停止，B/C 仍未实施。
