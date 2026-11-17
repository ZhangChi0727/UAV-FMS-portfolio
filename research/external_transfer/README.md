# 跨来源复核 · 入口与复现

2026-11-04。研究方案限定为一个独立飞行来源、一个新的 Linux 代理部署、一条未经重新训练的门控规则。先看[合同](protocol.md)、[来源与许可证](source.md)、[部署](deployment.md)和[研究结论](../../literature/external_transfer_20261104.md)。在源码 release 时刻上重放消息，不能将这些时刻视作原飞行订阅者的到达时刻。

**只复核已有数据。** 从仓库根目录运行以下命令。计分不启动代理，不读取板卡设备。

~~~powershell
New-Item -ItemType Directory -Force build/external-transfer | Out-Null
.\.venv\Scripts\python.exe -B research/external_transfer/score.py research/external_transfer/evidence --output build/external-transfer/rescore.json
~~~

**独立重复采集。** 先按部署说明安装已固定、校验过的 NATS 服务端。使用新的结果目录，避免覆盖原始记录。采集器每批启动并退出自己的 NATS 实例，主体均在 Ubuntu WSL2 内以独立进程运行，只绑定回环地址。主机、代理时延和系统负载影响重复运行的结果。

~~~powershell
$trialDir = 'build/external-transfer-repeat'
.\.venv\Scripts\python.exe -B research/external_transfer/plan.py research/external_transfer/source.csv $trialDir --pub vehicle_attitude --read actuator_outputs --alt vehicle_rates_setpoint
wsl.exe -d Ubuntu --cd /mnt/e/Project/uav-fms-portfolio -- python3 -B research/external_transfer/deployment.py "$trialDir/plan1.jsonl" "$trialDir/raw1.jsonl"
wsl.exe -d Ubuntu --cd /mnt/e/Project/uav-fms-portfolio -- python3 -B research/external_transfer/deployment.py "$trialDir/plan2.jsonl" "$trialDir/raw2.jsonl"
~~~

评分器从给定 evidence 目录读取原始计划和结果，校验 freeze.json 中相对研究包目录的源文件与原留存计划。对于按上述方式重建的完全相同的计划，可将原 `evidence/freeze.json` 复制到新结果目录后评分；评分器另外验证实际所评计划与 plan_meta 哈希一致。板端测量的单独交接见 [Linux 板端实验说明](board_measurement.md)。主机或仿真结果不满足板端证据条件。

[周期服务正对照](service_protocol.md)仅使用主代理下、事先按名义远相位筛选的 latest 窗口，`service/` 单独保留两个计划、原始数据及审计。从根目录执行下列命令即可复核。重新采集时将 deployment_service.py 替换部署命令中的 deployment.py，使用 service/ 下对应的同名计划，输出写到新目录，不覆盖原件。服务包装器保留原实现。

~~~powershell
.\.venv\Scripts\python.exe -B research/external_transfer/service_report.py
~~~

针对现有 STM32F103C8T6 的 STM32/FatFs 测量见[板端操作说明](board_stm32.md)。不同板子的 SD 驱动、卡与同步策略是被测条件，需要保留其版本与时钟。若另购并希望直接使用集成卡槽，STM32F746G-DISCO 自带 microSD 和 ST-LINK/V2-1，对应 STM32CubeF7 有同板 FatFs_uSD 读写示例。建议备一张可清空的专用 microSDHC 卡和连接 CN14 的 USB Mini-B 数据线。ST 示例 main.c 包含格式化步骤；测量内核仅需一个已挂载的试验目录，接入时应跳过该步骤。这一建议针对可复现的介质实验，F7 的结果不能直接作为 F103 或具体飞控的成本。[ST 产品页](https://www.st.com/en/evaluation-tools/32f746gdiscovery.html) · [ST 用户手册](https://www.st.com/resource/en/user_manual/dm00190424.pdf) · [官方同板示例](https://github.com/STMicroelectronics/STM32CubeF7/blob/v1.17.2/Projects/STM32746G-Discovery/Applications/FatFs/FatFs_uSD/Src/main.c#L75-L121)

在没有板端介质的情况下，本包另有已经实际运行的[真实 FatFs + 内存块设备仿真](board_sim_note.md)。它报告增写四字节导致的逻辑扇区写入量，不能替代板端配对时延。
