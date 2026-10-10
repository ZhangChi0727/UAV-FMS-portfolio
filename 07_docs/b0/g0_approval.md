# B0 G0 集中批准包（已批准，v1 保留）

状态：`已批准用于生成 v2`。PA 决定记录见 `07_docs/b0/g0_approval_decision.md`。
本文不代表性能、SIL/HIL、飞行或 G0 完成。

准备基点：PR #11 分支 `codex/b0-g0-contracts`，技术基点
`046674dcb391983345a33d683331bcf2e155dcb1`；本次 G1 工作单保护输入提交为
`d8068ad30dde50d3effdf2b09645f1879f7a6a45`。v1
`05_integration/b0/configs/b0_g0_contract.v1.json` 保留为
`proposed_pending_maintainer_approval` 历史回归；当前批准配置为
`05_integration/b0/configs/b0_g0_contract.v2.json`。不得原地修改 v1。

## 决策格式

PA 已逐项通过三项决定；批准设计与允许合并仍是两个独立决定。

## 集中决策表

| 决策项 | v1 精确字段与当前规则 | TC 推荐 | 依据、局限与批准后影响 |
|---|---|---|---|
| 坐标、单位、四元数 | `conventions.navigation_frame=NED`、`body_frame=FRD`、SI；`q_nb` 为 body→NED，Hamilton 标量在前；接口使用 scenario-clock timestamp | 批准原样保留 | 与 B0 v0.2 architecture 一致；不构成导航或绝对偏航能力声明。v2 仅记录批准引用。 |
| 旋转对象 | `plant_contract.inertia_kg_m2=[[0.022,0,0],[0,0.024,0],[0,0,0.041]]`，`body_frd`，`integrator_contract.method=rk4`，要求 step-halving | 批准为合成旋转对象候选 | 正定、z 轴惯量较大，明确不是实机参数；G1 用解析/收敛测试检验，失败不静默调参。 |
| 力矩与执行器 | `actuator_contract.model=first_order_bounded`，`time_constant_s=0.03`，limits `[0.35,0.35,0.20] Nm`；controller 是唯一逐轴限幅责任方，command 同时携带 requested/limited/saturated | 批准为抽象接口候选 | 只表示有界旋转力矩，不表示电机混控或真实响应；G1 只接受合成 TorqueCommand 夹具。 |
| 抗饱和 | `conditional_integration_plus_back_calculation`；`I_next=clamp(...)`；limit feedback gain `[8,8,8] 1/s`、lag gain `[2,2,2] 1/s`、lag delay 1 controller update；积分限 `[0.15,0.15,0.10] Nm` | 批准原样；允许 G2 在不改合同下记录调参 | 覆盖 request 限幅与 actual/limited 滞后；当前无动态性能证据。任何离散规则/信号变更须版本化。 |
| IMU | `sample_period_ticks=2`、质心、`timestamp=end_of_interval`、`f_b=a_b-R_bn*g_n`、`g=[0,0,9.80665]`；gyro noise `[.003,.003,.003]`、bias `[.004,-.003,.002]`；acc noise `[.03,.03,.03]`、bias `[.06,-.04,.03]`，均为每样本独立 Gaussian 标准差/恒定 body bias | 批准为合成 sensor 候选 | 不是实测传感器参数；G1 验证符号、旋转变换、seed/reset 重复性。 |
| 真值隔离与初态 | 真值只给 sensor/evaluator；`estimator/controller` 禁止 live truth；初态字段所有权和初始 offset 规则保持 v1 | 批准原样保留 | 保护后续估计器/控制器输入边界；G1 不实现估计器或控制器。 |
| 采样、held command、reset | `first_due_tick`: plant/actuator=1，IMU/estimator/controller=2；runtime reset 建立 local tick 0，reset tick 只 reset；scenario clock 不回退；R=1000→updates 1002/1004，R=1001→1003/1005；C_reset 与旧 held command/feedback 清除规则已固定 | 批准原样保留 | 由 046674d 的四轮修复及独立复审支持；G1 仅覆盖对象/IMU侧状态和采样，不提前实现 G2/G3 调度。 |
| 八类场景与 seeds | v1 八类场景完整保留；acceptance seeds `[2026100901..2026100908]`，tuning seed `2026100900`，禁止复用 | 批准场景集合与 seed 分离规则 | 各场景仍是待执行候选；限制刻画与 invalid/reset 不等同性能通过。 |
| 场景阈值 A | stationary：姿态峰值 `<=0.0174533 rad`、rate `<=0.05 rad/s`、q norm `<=1e-6`；initial offset：tilt settling `<=3 s`、peak `<=0.4 rad`；三轴 step：settling `<=1.2 s`、overshoot `<=20%`、cross-axis `<=0.0523599 rad` | 批准为 B0 工程候选，或逐字段修改 | 这些阈值不是 CTL 合规证明；step 窗口、dwell=0.25 s、事件原点已在 v1 校验。 |
| 场景阈值 B | disturbance：peak `<=0.35 rad`、recovery `<=2.5 s`、saturation `<=1 s`；noise/bias：roll-pitch RMS `<=0.0872665 rad`、yaw drift `<=0.05 rad/s`；saturation withdrawal：I limits `[.15,.15,.10]`、recovery `<=2 s`、sat duration `[0.05,2] s` | 批准为 B0 工程候选，或逐字段修改 | 仍未执行；饱和下界要求实际触发，上界防止持续饱和伪通过。 |
| 限制与无效输入 | acceleration contamination 只要求 limitation evidence；invalid/reset 要求 negative_dt、stale_timestamp 各一次，reset replay 至少两个 valid local estimator updates，q 分量 tol `1e-12` | 批准原样保留 | 这是限制刻画/输入拒绝，不是闭环性能；v1 反例校验已覆盖删弱、奇偶 reset、窗口边界。 |
| CTL-REQ-001 | 原要求：10° attitude settling `<0.8 s`，Test；B0 candidate step settling `<=1.2 s`，且场景/对象/带宽/dwell 不同 | **建议对 B0 标记“不适用”，保留原需求，不宣称符合** | B0 候选不能替换旧编号或阈值；若维护者选择条件化适用，必须给出适用场景和是否另设独立 0.8 s 验收。 |
| CTL-REQ-002 | 原要求：attitude overshoot `<15%`；B0 candidate overshoot `<=20%` | **建议对 B0 标记“不适用”，保留原需求，不宣称符合** | 20% 候选不能声称满足 `<15%`；若维护者选择条件化适用，必须明确另行保留 `<15%` 判据。 |
| 版本治理 | v1 历史保留；新增 v2，v2 显式记录人工决定引用；v1/v2 分开校验与回归，默认入口转 v2 | 批准该迁移策略 | approved 只来自维护者决定记录，不来自字符串或 CI；后续技术改动必须新版本/新决定。 |
| 跨类型事件 | `allowed_cross_type_overlap_pairs=[]` | 批准保持空集 | 避免未审查的并行语义；如需放开，必须列出具体事件对、执行顺序和新反例测试。 |

## 预计批准后动作

收到逐项决定后，TC 将：

1. 保存含批准人、日期、消息/PR 定位、基点 SHA 和条件的决定记录；
2. 保留 v1，生成 v2，不原地改写历史配置；
3. 让校验器区分 v1 proposed 与 v2 approved，并保留 v1/v2 正反例回归；
4. 更新 schema 索引、CLI/CI、G0 文档和交接记录；
5. 在 Linux B0 track 实际运行 v1/v2 CLI、Ruff、pytest 和 `git diff --check`，再请求独立复核；
6. 只有收到单独的明确合并授权、远程 CI 全绿且独立复核无阻塞后，才合并 PR #11。

已执行 v2 生成与校验器迁移；Issue #3/#4 状态变更和 PR 合并仍需独立授权与验证。
