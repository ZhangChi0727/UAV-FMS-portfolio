# PR 11 批准版校验与 G1 就绪收尾工作单

日期：2026-10-10。执行者：Task Carrier（TC）。维护者：Chi Zhang。
关联：[PR #11](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/11)、
[Issue #3](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/3)、
[Issue #4](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/4)。

本单补充 [G1 开发就绪总单](B0_G1_development_readiness.md)，针对最新迁移与交接缺口收尾。
继续使用原 PR、原分支并追加提交；不重新设计 G0，不开始 G1 实现，不另开规划 PR。
范围为校验器、配置治理元数据、测试、CI、审批/评审记录及 G1 工作单定稿。

## 基点和事实

复审基点为 `1fd66551c0143a93f7b0f1e0bff19df32b1bb5b0`。
PA 主会话已独立核验 v1/v2 默认配置可通过，除 schema_version 和 contract_status 外
两版配置无差异；使用既有 WSL Python 对 Windows 最新源码做只读诊断得到 135 passed、
Ruff 通过，最新远程三项 CI 通过。这不消除下列额外反例，也不是 G1 实现证据。

WSL 经权限允许后的只读检查可运行，Python 为 3.11.17，但 Linux checkout 仍在
`ab2e6b05b2d51d851b1c3dfada5b69a66f47b9b0`。不得据旧的 E_ACCESSDENIED 直接判定
环境损坏，也不能把 Windows 最新提交的结果说成 Linux 活跃 checkout 已同步。

实施前重查远程 HEAD、双工作区状态和本单是否已被其他任务处理；保护用户修改。
本单是 Windows 新增交接输入，先可恢复地提交保护，再经 Git 同步至 Linux 活跃副本。
禁止强推、破坏性清理、覆盖式同步或顺带删分支；只保留一个活跃实施副本。

## 一 修复版本类型检查回归

证据：在基点把配置 schema_version 改为 `{}`，validate_config.py 的集合成员检查产生
`TypeError: unhashable type: 'dict'`，而不是 ContractValidationError。

要求：

1. 在集合比较前验证版本为非空字符串，再检查支持版本；沿用现有类型守卫。
2. v1/v2 都保留正确状态校验，不以通用 except Exception 掩盖错误。
3. 添加对象、数组、null、布尔、数字、空白字符串、未知版本的拒绝测试。
   非法版本必须得到 ContractValidationError，错误路径含 schema_version。
4. 对对象/数组反例增加 CLI 测试：非零退出、可读路径和原因，无裸 traceback。
   v1、v2 及默认 CLI 正例继续通过。

关闭证据：具名测试、实际命令与新 SHA；不能只展示默认配置成功。

## 二 批准记录的内容校验与真实来源

证据：基点中把 approval_record 的 decision_source、decision_date、baseline_commit、
approval_package_commit、scope 全改为空字符串，v2 仍被接受。现有 Schema 描述比唯一
执行入口更严格，但 Schema 自身不是运行时校验入口。

要求：

1. date 是真实有效的 YYYY-MM-DD 日期；SHA 为非空 40 位十六进制字符串；source 和
   scope 为非空字符串。先检查类型，拒绝空白、对象、数组、布尔等错误值。
2. 批准引用明确指向仓库的 g0_approval_decision.md 或等价决定文件。按项目根而非调用
   cwd 定位，限制在预定文档范围，拒绝缺失、越界或无效引用。若用固定路径而非配置字段，
   明确该约定并为缺失文件提供可测试入口；不为此建立签名、数据库或通用审批平台。
3. 记录实际授权链：用户授予何种决策权限、哪个会话/子代理作出何种决定、对应基点及条件。
   source 不能仍只有“PA review communicated in task conversation”。公开文档只保留
   必要的技术授权摘要及可定位标识，不导出整段私有对话或凭据。
4. 不伪称所有 PA 名称指向同一个主体。已有主会话 Project Administrator 的 ID 是
   `019f9ef3-4a0c-79f1-99d4-c8415f62bd29`；TC 的最终复审子代理为
   `01a125e9-a0be-7d60-8209-89a15a66b3d4`，路径 project_administrator_final_review。
   该子代理对 1fd6655 的条件性合并建议，不是主会话此前对 046674d 的结论。
   技术候选批准本身的来源须另行核验，不得把这个最终复审子代理 ID 当成设计批准证据。
5. 不自动撤销或重做真实、有效的用户决定。若用户要求的指定评审主体与实际执行主体不同，
   或授权链不能支持当前批准记录，准确说明并请求用户确认/追认；在此之前不补写虚假批准。
6. 配置、决定记录、Schema 描述和实际校验保持一致；人工核验授权真实性，程序校验结构
   和引用一致性。不得声称字符串或文件存在即证明审批身份真实。

正例：完整合法记录、日期/哈希合法、从不同 cwd 校验均正确定位。
反例：逐字段缺失、空/空白、错误类型、非法日期、短/非十六进制哈希、失效或越界引用、
v1/v2 状态错配。测试必须断言合同错误及字段路径，不能捕获 Exception 就算通过。

## 三 状态文档与 CI 统一

1. 保留 v1 历史配置及历史测试。按版本区分历史 proposed 与当前 v2 的批准状态；
   同步 g0_contract.md、g0_acceptance.md、g0_approval.md、g0_approval_decision.md 和
   g0_review_resolution.md 的当前摘要，不批量改写历史发现和结果。
2. 检查 v2 内 operating_envelope、acceptance_policy 和 sources 等治理状态。顶层批准
   与子项仍称“等待批准”应有明确一致的解释或版本感知修正；不能因此改变技术数值。
   approved 是设计批准，proposed_not_executed 等性能证据状态仍须保留未执行含义。
3. CI 显式运行 v1 CLI、v2 CLI、默认入口及测试；当前只写 v1 的步骤不得仍命名为默认
   v2 校验。新增回归覆盖 v2，不仅在 v1 上检验共用规则。检查默认路径确实指向 v2。
4. 增加可执行迁移对比，列出允许变化的治理元数据；技术参数、场景、指标、窗口和 seed
   必须保持此前已审内容。若有技术差异，单列原因和审批，不夹带在状态整理中。
5. 修复批准文档三处行尾空白。区分“工作树干净时 git diff --check 无输出”和“完整
   PR 差异通过检查”；最终需对 base..HEAD 检查，不只检查尚未提交的差异。

### 保存真正可追溯的复审报告

新增或复用 07_docs/b0/pr11_review_report.md，按轮次保留：评审主体与会话标识、准确 SHA、
范围、发现、复现、关闭证据、实跑命令与环境、未执行项、合并结论及条件。
TC 可以整理已有原始结论，必须标为转录并准确归属；不得自行替独立评审者写“已通过”。

将本轮修复提交后，请求已有 PA 主会话复核；不要新建同名子代理冒充该会话。
若消息权限要求额外用户授权，说明并请求，不绕过。最终报告引用实际返回结论。
报告入库导致新 SHA 时，明确代码评审基点与仅记录报告的提交，补跑对应检查；不假称
评审覆盖尚不存在的提交。已有报告里“三项 Schema 阻塞”必须对应 Schema 修复，
不能用前几轮抗饱和/稳定时间的关闭描述替代。

## 四 定稿 G1 实施子工作单

修改现有 B0_G1_work_order.md，不再新建一份重复的 G1 规划。

1. 移除“v2 当前尚不存在”等过时描述，引用实际配置、决定记录和批准技术提交；
   合并 SHA 在合并后记入 Issue #4/交接摘要，避免要求工作单预写自身 merge SHA。
2. 定稿每个解析用例的初态、输入幅值/方向、作用时间、步长、比较量、公式、
   绝对/相对容差及依据。不能只写“趋势/符号”或孤立的 1e-8，没有测试时域和量级。
3. 将四元数范数、姿态角误差、角速度误差、执行器误差分开；选择在目标精度下数值稳定的
   姿态比较方式，不能仅靠低精度 acos(dot) 计算极小角误差。
4. RK4 步长减半说明参考解与收敛判断，不能把两个步长的解接近当作正确性的唯一证据。
   执行器容差应与所选离散方式及解析参考相匹配。只确定验收设计，不提前实现对象来调容差。
5. 明确 IMU 理想值/偏置/噪声/seed/reset 的独立测试口径；不以一次随机样本统计或两个
   seed 恰好不同冒充噪声模型的全面验证。不得借此引入大规模 Monte Carlo。
6. 对齐 G0 字段名称：当前 actuator 段的 limited_target_torque_body_Nm 与消息中的
   limited_torque_body_Nm 不一致，应明确使用批准消息字段，不建立隐式别名。
   新增的 IMU 接口若属于 G1 细化，明确其输入来源及与 G0 的映射，不冒充 G0 已固定字段。
7. 数值候选提出依据后集中提交审阅，记录最终决定；关键验收仍待决定时不能标 ready。
   已批准 G0 参数及阈值不重新开放讨论，除非确实发现冲突。
8. 明确命令执行目录。未来 G1 测试从 01_simulation/b0 内执行 pytest、Ruff，
   不在该目录内再拼接 01_simulation/b0/tests，也不做根目录测试收集。
   未实现阶段的命令标为未来入口，不运行空测试或把不存在的目标当作已验证。
9. 保持 G1 为一个独立实施 PR：只做 plant/actuator/IMU 与组件测试；输入由合成夹具提供。
   G2 首次 estimator/controller dt、G3 完整调度/replay/闭环仍属于后续阶段。

## 五 验证与安全同步

实施前读取双工作区 git status、HEAD、分支。保护 Windows 最新提交及本单后，通过 Git
将 Linux 活跃副本安全快进至待测提交；如有分歧/未提交修改，先保护和协调，不能强制覆盖。
记录“在哪个工作区、哪个 SHA”运行，避免用旧 Linux HEAD 证明新 Windows 提交。

在 Linux 的 05_integration/b0 目录中使用已核实的绝对解释器运行：

```text
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python validate_config.py --config configs/b0_g0_contract.v1.json
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python validate_config.py --config configs/b0_g0_contract.v2.json
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python validate_config.py
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m pytest -q
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m ruff check .
```

另执行本轮两个原始反例和新增边界；预期均为带字段路径的合同错误。
在仓库内执行 git diff --check，并以核实的 PR base SHA 执行 base..HEAD 完整差异检查。
最新 SHA 必需 CI 全部通过。G0 测试不得 skip/xfail；导航历史预期失败单独记录。
工具链/依赖未改变则复用既有 probe 证据，最新 CI 仍需保留其强制执行。

不要把一次沙箱权限拒绝解释为必须重装 WSL。按工具权限机制重试必要只读检查；
若真正不可用，准确记录阻塞和替代验证的边界，不修改系统配置或重新安装环境。

## 六 合并门槛与 G1 就绪门槛

两个结论分开报告，不将 GitHub MERGEABLE 等同于开发就绪。

合并前必须满足：版本/批准记录反例关闭，授权来源清晰，当前状态与 CI 入口一致，
完整差异检查通过，新提交 CI 全绿，独立复核无阻塞，并有覆盖合并动作的明确用户授权。
可引用已获得的有效授权，不重复索取；存在歧义时只问缺失的授权，不自行推断。

满足门槛并执行获授权合并后：

- 核验 GitHub merged 与实际 merge SHA；确认批准资产进入 main。
- 安全同步 Windows 与 Linux 到相同 main 基点，验证解释器和新配置可运行。
- 按真实证据完成 Issue #3；Issue #4 登记依赖、工作单、验收、执行责任及 ready 状态。
  无仓库账号的 TC 作为执行责任写在任务说明即可，不随意指派其他 GitHub 用户。
- G1 数值验收和接口细化已确定，工作单没有关键 TBD，环境和权限无阻塞，才宣告 ready。
- 到 ready 即停止；不创建空 G1 PR，不写算法，不宣称 G1/B0 完成，不引入 B1 名称。

## 最终交付清单

- [ ] 原始两个反例及新增边界均有具名正反例测试和新提交实跑证据。
- [ ] 批准主体、用户授权、决定来源和技术基点可追溯，无身份混称。
- [ ] v1 历史保留，v2 元数据/文档/Schema/实际校验/CLI/CI 一致，技术差异可解释。
- [ ] 本轮独立评审报告已保存，准确区分主会话、子代理及各自评审范围。
- [ ] G1 工作单定稿，容差/oracle/时域/接口/目录与命令明确，关键决定已记录。
- [ ] 合并仅在门槛与授权满足后执行；merge SHA 与双工作区同步可核验。
- [ ] Issue #3/#4 按实际状态更新，G1 ready 与实现完成明确区分。

交付时给用户报告：逐项关闭证据、配置/报告/工作单链接、最新 SHA 和 CI、批准来源、
是否可合并、是否已合并、是否 G1 ready。任何一项未完成，直接列出缺口和下一责任方。
本单只规定收尾任务，不预先给出通过或批准结论。

## 追加轮次（基点 9ea9e22；执行中）

本轮由既有 Project Administrator 主会话追加派单，继续沿用本单范围。已修复 R1 的
`origin/main` 不可用问题（B0 CI checkout 使用完整历史）、R2 的四元数误差公式和批准
决定文档行尾空白；最新提交为 `468743e`。本轮新增要求：R3 使用严格
`YYYY-MM-DD` 正则加真实日期校验，并将批准来源解析为受限的仓库相对固定路径；R4 补齐
v1→v2 仅治理元数据迁移测试和状态摘要；R5 记录 WSL 权限边界、双工作区状态及本轮
验证命令。主会话 PA 复核尚未返回，本轮不得写成通过、可合并或 G1 ready。
