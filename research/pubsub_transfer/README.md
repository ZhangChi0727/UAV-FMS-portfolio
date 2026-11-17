# 可复核的第二套发布／订阅实验

2026-11-04，Windows 宿主。使用 PyZMQ 27.1.0、libzmq 4.3.5 和 Python 3.11.5，实际执行 XPUB/SUB TCP 回环通信。先读[实验合同](protocol.md)、[来源与提取说明](trace_provenance.md)和[结果报告](../../literature/pubsub_transfer_20261104.md)。

## 复核保存的运行

原始计划和采集在 evidence/，freeze.json 保存采集前固定的预测规则、台架、计划及成本基准指纹。下列命令只做本地分析。独立参考复用 [上一台架的精确轨迹计算](../scheduler_holdout/reference.py)，接口只传递控制、时间和状态检查点。compare by `pair_id`，按相同窗口、相同策略匹配两个字段臂。

~~~powershell
New-Item -ItemType Directory -Force build/pubsub-transfer | Out-Null
.\.venv\Scripts\python.exe -B research/pubsub_transfer/reference.py
.\.venv\Scripts\python.exe -B research/pubsub_transfer/audit.py research/pubsub_transfer/evidence --output build/pubsub-transfer/reanalysis.json
~~~

## 重新采集

要启动本机回环连接，沙箱环境可能要求仅限 loopback 的联网许可。每个 socket 只由一个线程操作。每次运行使用新的订阅前缀，XPUB 收到订阅通知并确认暖机消息后才开始；容量上限 65,536，检查原始计划、发送与接收内容、顺序及事后排空。名义上到期不等于该消息已在订阅端可读。特别是 latest 在实际轮询时处理消息，直至当时队列为空；这与基线用一个固定读取时刻计算释放顺序有差别。[ZeroMQ 套接字语义](https://libzmq.readthedocs.io/en/latest/zmq_socket.html)

以下各次输出使用一个新的目录。为重做冻结的主实验，保留原微基准文件和合同指纹；新一轮 CPU/内存基准若需测量，用独立文件存储。

~~~powershell
$out = 'build/pubsub-transfer-repeat'
New-Item -ItemType Directory -Path $out
.\.venv\Scripts\python.exe -B research/pubsub_transfer/design.py research/pubsub_transfer/trace.csv $out
Copy-Item research/pubsub_transfer/evidence/freeze.json $out
Copy-Item research/pubsub_transfer/evidence/field_cost.json $out
.\.venv\Scripts\python.exe -B research/pubsub_transfer/transport.py "$out/plan1.jsonl" "$out/raw1.jsonl"
.\.venv\Scripts\python.exe -B research/pubsub_transfer/transport.py "$out/plan2.jsonl" "$out/raw2.jsonl"
.\.venv\Scripts\python.exe -B research/pubsub_transfer/audit.py $out --output "$out/audit.json"
~~~

两批进程重放相同的 48 个源窗口。时间戳以 1:1 时间尺度回放；发送实际开始时间、排队、线程唤醒和窗口最低状态随主机变化。跨窗重置清空订阅队列，评价的是有界片段。原 ULog 与本机含定位信息的全量文件不属于该研究包。

后续 30 秒使用独立的[时间段留出合同](holdback_protocol.md)。从仓库根目录可用下列命令重复测量，或仅对保留的 holdback/ 运行 score。后者不启动网络。附加网络基准使用预编码帧，输出文件应当尚不存在。

~~~powershell
$later = 'build/pubsub-later-repeat'
.\.venv\Scripts\python.exe -B research/pubsub_transfer/holdback.py prepare $later --ulog build/reference-logs/sample.ulg
.\.venv\Scripts\python.exe -B research/pubsub_transfer/transport.py "$later/plan.jsonl" "$later/raw.jsonl"
.\.venv\Scripts\python.exe -B research/pubsub_transfer/holdback.py score $later
.\.venv\Scripts\python.exe -B research/pubsub_transfer/network_cost.py build/pubsub-transfer/net-cost-repeat.json
~~~
