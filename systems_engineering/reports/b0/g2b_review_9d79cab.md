# G2-B 首轮实现评审与修复工作单

日期：2026-10-14（Australia/Perth）。评审：原 PA。执行：Task Carrier。

## 1 评审对象与结论

- PR #22：<https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/22>。
- base：`5f817ec1fb2405aa269dcf6a701a33cff846c748`。
- 精确 head：`9d79caba593ac9383c5f3db7bf884f76ea6d595c`。
- 结论：`REWORK`，不能合并，G2-B 未完成，不能据此宣布 G3 就绪。
- 已批准 S0：`7084584ef9e69995b88201164fa8659e4ef57c79`，其设计批准不等于实现验收。

本单是 `docs/work_orders/B0_G2_B_work_order.md` 的评审补充，不替代其完整交付要求。
继续同一 PR，按先修复、后补齐组件检查、最后补齐证据的顺序执行。
仍是开发期组件检查和受控验收，不新建独立验证阶段或验证平台。

## 2 已核实证据与限制

精确 head 的 Actions run `38512834016` 为 success，九个 job 成功。
本地 PA 在 WSL 实际执行 TC 已构建的 Debug/Release C++ 测试二进制：
两者各为 4 test cases、14 assertions，通过。Debug Python track 为 4 passed。
这些不是 PA 重新 clean build 的结果，也不能代替工作单尚未覆盖的用例。
PA 在隔离系统工程环境、`tools/systems_engineering` 内执行 `python -m pytest -q tests`，
结果为 80 passed（64.86 s）；历史 hash 反例仍证明现有套件有漏检。

PA 通过 Debug 扩展模块执行额外反例，模块路径为：
`build/b0-controller/debug/03_control/b0/b0_controller.cpython-311-x86_64-linux-gnu.so`。
Python 为现有 B0 WSL 环境的 3.11.17。复现事实如下：

| 反例 | 观测结果 |
| --- | --- |
| reset=0；零误差；每步输入时间 `tick * 0.005`；反馈严格使用前一步输出 | 第 3070 步、15.35 s 被 `unexpected_tick` 拒绝 |
| reset time=`1e16`；下一步同 timestamp | step 成功，输出 timestamp 仍为 `1e16`，与 reset publication 重复 |
| 适配器收到冻结字段 `q_nb_command`、timestamp、valid | `AttributeError`：缺少 `q_nb` |
| 为绕过上述字段错误额外提供 `q_nb`；command.valid=False；estimate.valid 为字符串 `false` | step 成功，而非拒绝 |
| 上述适配输出与 G1 `contract.TorqueCommand` 比较 | `isinstance` 为 False；G1 actuator 的入口要求该类型 |
| adapter reset epoch id=1.5 | 被静默截断为 1 |
| 在内存账本副本中，把被 supersede 的 G2-A 记录首个 source hash 改为 64 个 `a` | 默认 `validate_ledger(repo, ledger)` 仍接受 |

最后一项没有改写受控账本。数值反例只证明组件缺陷，不是闭环/SIL/HIL/飞行结果。
这些关键反例必须转化为永久受控回归测试，不能只保留聊天执行记录。

## 3 必须修复的问题

### R1 — P1：冻结指令与有效性合同没有贯通

定位：`03_control/b0/python/controller.py:108`、`:115`；
`03_control/b0/include/b0_controller/controller.hpp:38`；`src/controller.cpp:93`。

适配器读取 `q_nb`，但 G0 指令字段是 `q_nb_command`。C++ AttitudeCommand 缺少
显式 valid，核心只检查 estimate.valid。适配器的 `bool(...)` 会把字符串等非法值变成 True。
`int(reset_epoch.id)` 同样在检查前丢失了非法原始值。

修复：逐字段遵循冻结消息合同；贯通并检查 command/estimate 显式有效性；
拒绝错误布尔类型、非整数/bool epoch、越界整数及非法标量，不能隐式截断或真值化。
绑定与适配器都不得成为绕过核心输入合同的路径。任何拒绝应保留完整状态。
测试覆盖 false、错误类型、缺字段、整数边界、拒绝后同 tick 重试及 clean twin 对照。

### R2 — P1：浮点累加时钟误拒绝合法 tick，并允许不可推进时间

定位：`03_control/b0/src/controller.cpp:73`、`:141`。

`expected_timestamp += period` 与调用者的 epoch+integer_tick*period 网格逐渐偏离，
超过已批准 1e-12 s 容差；复现无需噪声或非零控制输入。
巨大有限 epoch 又会使 `epoch+period == epoch`，当前代码仍提交 reset/step。

修复：保存 epoch origin 和整数 tick，从整数网格推导 due time，避免递推累加；
在状态提交前验证计算有限、时间严格推进、tick 增量/转换无整数溢出。
不可表示合法下一 tick 时原子拒绝，不通过放宽容差掩盖时钟错误。
至少保留覆盖已复现失败点的确定性长序列、非零 epoch、巨大 epoch、duplicate/off-grid/
retry/missed-tick 回归，并与 G0/G1 调度时间定义一致。

### R3 — P1：适配器输出不能交付已有 G1 执行器

定位：`03_control/b0/python/controller.py:124`；
`01_simulation/b0/actuator.py:119`；`01_simulation/b0/contract.py:129`。

适配器直接返回扩展模块 TorqueCommand，但 G1 显式检查自己的 TorqueCommand 类型。
S0 B-BIND-02 已承诺构造 G1 TorqueCommand 并实际消费，目前未实现。

修复：用控制器已计算的 request/limited/status/time 构造 G1 消息，不重算限幅，
不改变 G1 类型检查、不新增竞争字段。reset 输出也需明确同一映射策略。
使用真实 G2-A StateEstimate、真实 G1 feedback 和 G1 actuator 入口完成接口夹具；
夹具保持正确时序，不伪造未来反馈、不宣称 G3 完整闭环验证。

### R4 — P2：supersession 不应关闭历史来源完整性检查

定位：`tools/systems_engineering/g15c_traceability.py:193`。

把整个文件验证块都放在 `record_id not in superseded` 之下，连历史 source/target hash、
implementation revision 和来源字节一致性也不再检查。历史记录排除当前满足计数是正确的，
但并不授权篡改其来源身份。

修复：分离历史来源完整性与当前 HEAD 适用性。历史记录仍校验其被声明的 revision/hash/
路径及当时适用关系；被 supersede 的记录不要求继续匹配当前 HEAD，不参与当前满足计数。
如果历史路径已迁移，验证其历史 revision，而非强求当前路径存在。
加入被 supersede 记录损坏 source hash、target hash、未知 revision 的拒绝测试，
以及正常 supersession 后当前 HEAD 已变更仍合法的正例。

### R5 — P2：测试名称、数值判据及绑定可观测性不足

定位：`03_control/b0/tests/test_controller.cpp`、`python/tests/`、`python/controller_bindings.cpp`。

当前四个 C++ 用例不能覆盖已批准 S0 矩阵；例如名称包含 axes/half turn 的用例只检查
x 轴 .1 rad 与其反号，不含三轴或 half-turn。原子性多只比较诊断 tick，而非完整状态。
`Catch::Approx(...).margin(1e-12)` 仍保留默认相对容差，不等于已批准 rtol=0。
Python 未暴露完整 snapshot/D/filter/conditional-Ki 等，不能完成承诺的逐字段绑定核对。

修复：把 S0 每一行落到实际可执行 node，逐行登记输入、oracle、容差和证据；
使用真正的绝对误差判据；暴露所需只读复制快照和完整诊断，明确稳定错误 reason 接口，
验证 C++/Python 输出与拒绝语义一致、调用者/输出数组修改不污染内部状态。
补齐三轴/非 identity/π、rate/torque float 边界、独立 P/I/D 与 AW 分量、清零/replay、
无效数值/类型/shape/overflow、配置 loader 正负例与真实接口用例，不以改名代替覆盖。

四种缺陷检测必须实际改变隔离的 subject core：姿态反馈反号、AW 反号、取消 AW、
lag 项错用 current limited。正确 oracle 保持不变；每个变体编译成功后，被预指定数值
测试检测；编译失败不计成功；最后恢复未修改生产源码并通过 clean build/tests。

### R6 — P2：构建与受控证据交付尚未完成

完成总工作单第 9–11 节：CTest 设置 Python track working directory；
锁定/核实实际 Catch2、pybind11 来源版本；Debug/Release 都运行核心及绑定，至少一次 clean rebuild。
当前 CMake 找到任意系统 Catch2 3/pybind11 时不能无条件绕过已规定版本身份。

新增 G2-B 证据生成/CI artifact 上传和 controller scope→强制依赖闭包，包含 core/header、
绑定/adapter/loader、tests/oracle、配置/审批、实际 validator、CMake/presets/CI 及相关接口依赖。
保留逐用例输入/独立期望/输出、P/I/D/AW、时间配对、拒绝前后快照、构建/ABI/module 身份、
source run/commit、artifact ID/文件/归档 hash/expiry，更新账本及报告。
新 CI 工作流若再次改变 G2-A 闭包，应重跑并受控 supersede，不能弱化检查。
多阶段规格仍保持 partial；未经实际 bytes/expiry/review 核验，不能冒称 verified/accepted。

## 4 执行顺序、再提审条件与权限

1. 在 PR #22 修复 R1–R4，同时纳入对应永久回归；保持已批准算法/冻结文件不变。
2. 完成 R5 的全部 S0 矩阵、绑定对照及四个 subject mutation 检测。
3. 完成 R6 的 Debug/Release/clean/CI、artifact、闭包、账本与入口状态同步。
4. 自检总工作单和本单所有条目，按每条给出 changed file、test node、实际结果及证据定位。
5. 提交完整 head/base、CI run、构建及 module 身份、artifact hash、矩阵关闭情况、限制、
   git status 和保护文件 hash 给原 PA；不要再把明确未完成的 S1/S2 候选标成可最终验收。

允许 TC 将本人工评审记录精确纳入同一 PR，不暂存用户保护文件。
受保护文件 `docs/work_orders/B0_G1_5_work_order.md` 评审时 hash 仍为
`96d45d4215c2215bb50ea0c7b863b627fa2e7d8d64ada3bb456950a2aa0d44a5`。
没有新增合并、Issue 关闭、分支删除或 G3 开发授权。修复后由原 PA 再评审精确候选。
