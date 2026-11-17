# WSL2 / NATS Core 部署记录

Windows 原生 PATH 未发现消息代理；本机已注册的 Ubuntu WSL2 运行 Linux 5.15.167.4、Python 3.8.10。此部署在同一物理计算机上更换了操作系统环境、中间件、进程划分和接收路径。NATS 是独立运行的 Go 消息代理。发布者是独立启动的 Python 子进程，订阅和控制使用父进程，另有一个订阅入队线程。[NATS 2.11.9 发布](https://github.com/nats-io/nats-server/releases/tag/v2.11.9) · [NATS 文本协议](https://docs.nats.io/reference/reference-protocols/nats-protocol) · [Core NATS 消息语义](https://docs.nats.io/nats-concepts/core-nats)

## 配置与复现

下载目录为被忽略的 `build/external-transfer`。已将官方 Linux amd64 压缩包的 SHA-256 对照同一发布的 SHA256SUMS，得到 `3eef83faa048d3879937a6871f59ae5d9c3bbf5900905b7a9ff996a894d755ab`；解压的 broker SHA-256 为 `da17f1e330bcfc9790c7a2fc26ae150700edb1a1fa36fe1cb7a0e95af7595bb0`。可在 PowerShell 中按以下方式重建。

```powershell
$staging = 'build/external-transfer'
New-Item -ItemType Directory -Force $staging | Out-Null
$release = 'https://github.com/nats-io/nats-server/releases/download/v2.11.9'
Invoke-WebRequest "$release/nats-server-v2.11.9-linux-amd64.tar.gz" -OutFile "$staging/nats-server.tar.gz"
Invoke-WebRequest "$release/SHA256SUMS" -OutFile "$staging/SHA256SUMS"
Get-FileHash "$staging/nats-server.tar.gz"
Select-String 'nats-server-v2.11.9-linux-amd64.tar.gz' "$staging/SHA256SUMS"
tar -xzf "$staging/nats-server.tar.gz" -C $staging
wsl.exe -d Ubuntu --cd /mnt/e/Project/uav-fms-portfolio -- python3 -B research/external_transfer/deployment.py PLAN.jsonl NEW_OUTPUT.jsonl
```

每次调用启动一个具独立名字的本地 broker，仅绑定 `127.0.0.1`，通过 INFO 核对其名字、版本，并以 PING/PONG 确认服务。一个计划文件内的试验复用 broker，每条使用独立主题和新客户端。订阅方先订阅并确认 PONG，再确认收到发布者发送的 warm 消息，才设定全体进程共享的 monotonic epoch。结束时核对消息顺序、数量和双方独立计算的流摘要；新输出成功写入后改名。退出只停止该次启动的 broker。Ubuntu 环境仅须有 Python 标准库和该 ELF。脚本运行时不会下载软件。

## 观察与诊断界限

自然窗口内的状态和背景流分属同一连接上的两个 NATS subjects。状态内容来自各自实际采样产生的值；有时间及大小但缺少原载荷的背景记录使用等长确定性字节。订阅线程逐帧解码，背景帧消耗传输与解码资源，只有状态帧进入应用队列。控制器在锁内读取快照；FIFO 取一个，latest 取最后一个并清空。无新值时保持上次选择。消息完整性检查适用于本次有限流；Core NATS 的服务自身为至多一次投递。

仅一个选定读取可写入四字节字段，空字段模式不输出消费编号。独立标注可使用施加的控制量和生效时刻；应从输入投影中剔除控制来源标识、队列诊断及模型预测。单独的 `diagnostics` 是事后定位证据。对每个已知计划序号记录实际 sendall 调用的前后界、订阅线程读完并解析该状态的时间、应用队列加锁入列的前后界。两个读取各记录申请锁之前、持锁观察队列的时刻、完成选择的时刻。所有相对时间单位均为 ns，使用 WSL 同一个单调时钟。附近时间应考虑记录分辨率；相邻时钟读数及 sendall 返回值无法精确定位内核或代理的收包时刻。共用诊断本身会改变执行时序，机制解释只针对带这些诊断的当前部署。

若发布调用始于读取之后，可检出发送者执行延迟。若调用已经返回而入列在读取之后，只能定位为发送者到应用队列之间的剩余路径；该路径包括内核、代理、接收线程调度、解析和入队。若多个状态在持锁读取之前已入列，应按策略重建先前消耗量，区分 FIFO 保留的旧数据与传输迟到。单个时钟边界重叠须保留未知。所有三类都应由对应一次运行的实际记录判断。

四行开发冒烟各运行六条数据消息，三进程 PID、流数量和摘要核查均成功，`none` 写零字节、`one` 写四字节。实际研究结果取决于正式计划与保留产物。[运行实现](deployment.py)
