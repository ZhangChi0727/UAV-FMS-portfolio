# B0 G0 决定记录

日期：2026-10-10
决定人：Project Administrator（经用户授权交付 PA 评审）
范围：G0 合同候选冻结与 CTL 适用性；不构成性能合规证明。

授权与主体定位：用户在本任务中明确授权“将 1–3 交 Project Administrator 讨论，PA
通过则授权执行”；实际作出三项设计决定的评审主体是本任务的 Project Administrator
评审任务 `/root/project_administrator`。当前主会话 Project Administrator
`019f9ef3-4a0c-79f1-99d4-c8415f62bd29` 负责本轮收尾复核，不将最终复审子代理
`01a125e9-a0be-7d60-8209-89a15a66b3d4` 冒充为设计批准人。

## 用户追认（不倒签）

2026-10-10（Australia/Perth），用户在主会话
`019f9ef3-4a0c-79f1-99d4-c8415f62bd29` 明确回复“同意上述范围”，追认以下三项
设计决定：冻结当前 G0 v2 作为开发合同但不构成性能达标声明；CTL-REQ-001 对当前
B0 为 `not_applicable`；CTL-REQ-002 对当前 B0 为 `not_applicable`。两项原始要求和
历史记录保留，未来扩展时重新评估适用性。本段是当前追认，不改变历史决定日期或基点，
也不授权合并、启动 G1 或宣告 G1 ready。

基线提交：`046674dcb391983345a33d683331bcf2e155dcb1`
批准包提交：`ab2e6b05b2d51d851b1c3dfada5b69a66f47b9b0`

## 决定

1. 通过当前 G0 技术候选原样进入 `b0-g0-contract/v2`。v1 保持不变；v2 仅冻结已记录的合成候选和接口/验收合同，不是性能结果。不得新增未讨论的参数或验收承诺。
2. `CTL-REQ-001` 对当前 B0 记为 `not_applicable`。保留原要求和历史适用范围，不声称 B0 满足 `<0.8 s`。
3. `CTL-REQ-002` 对当前 B0 记为 `not_applicable`。保留原要求和历史适用范围，不声称 B0 满足 `<15%`。

后续实现仍须独立校验和测试；不得提前实现 G1/G2/G3。
