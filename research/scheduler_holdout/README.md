# 间隙规则留出实验 · 复核入口

从[研究记录](../../literature/scheduler_holdout_20261104.md)查看结论，从[预先固定的合同](protocol.md)查看全部条件。evidence/ 保留规则和实现指纹、独立校准、两批正式计划、原始数据及逐组审计。旧规则仍由上一轮文件提供，文本不匹配会停止评价。

## 复核已有数据

仓库根目录、Python 3.11+、标准库。可将输出改成任意新文件。审计会按独立的 MAVLink 线协议字节布局和逐位构造的 CRC 表，重算每批实际编码帧的字节数及摘要。

~~~powershell
.\.venv\Scripts\python.exe -B research/scheduler_holdout/reference.py
.\.venv\Scripts\python.exe -B research/scheduler_holdout/audit.py research/scheduler_holdout/evidence --output build/scheduler-holdout/reanalysis.json
~~~

## 独立重复采集

宿主 Windows x64，MinGW-w64 GCC 13.1、C++17、QPC，未绑定 CPU 或设置实时优先级。下列命令以新目录保留重复实验。每个计划与原始输出仅写一次。两次新运行的逐 ns 时间、实测校准和判定可以因 OS 调度而变化。重新校准使用相同已冻结的方法。

~~~powershell
$out = 'build/holdout-repeat'
New-Item -ItemType Directory -Path $out
$toolchain = '<MINGW_BIN>'
$env:Path = $toolchain + ';' + $env:Path
& "$toolchain\g++.exe" -std=c++17 -O2 -Wall -Wextra -pedantic -static -pthread research/scheduler_holdout/scheduler.cpp -o "$out/scheduler.exe"
& "$out/scheduler.exe" --fixture
.\.venv\Scripts\python.exe -B research/scheduler_holdout/plan.py cal $out
Copy-Item research/scheduler_holdout/evidence/freeze.json "$out/freeze.json"
& "$out/scheduler.exe" "$out/cal_plan.csv" "$out/cal_raw.csv"
.\.venv\Scripts\python.exe -B research/scheduler_holdout/plan.py main $out
& "$out/scheduler.exe" "$out/main1_plan.csv" "$out/main1_raw.csv"
& "$out/scheduler.exe" "$out/main2_plan.csv" "$out/main2_raw.csv"
.\.venv\Scripts\python.exe -B research/scheduler_holdout/audit.py $out --output "$out/audit.json"
~~~

本次源码 SHA-256 为 4F7FF9F5816F2CEF513C7AF4F94BA11412E61BCEDDE15E248226ABA5DDDA35DD，二进制为 AA1BACDE683B8447C414A0AA55FEC1A66AE6FAD421C9CC51FF2ED629BC37C2CB。fixture 输出 `fd0800000001011e0000e80300000000003f1309`。工程负载是写入内存的 unsigned MAVLink 2 ATTITUDE 帧，标量测试值填入 roll，其余五个浮点量置零，序列号逐帧递增，按协议截尾、加入 CRC_EXTRA 39。批量 8 或 256 帧是本实验的负载档，不代表遥测流的发布频率。PX4 的流代码由姿态更新触发发送，而工作队列源码支持同一队列出队后同步执行工作项；台架仅移植这些机制所对应的受限行为。[上游协议](https://mavlink.io/en/guide/serialization.html) · [定义](https://github.com/mavlink/mavlink/blob/bb97687c90d11beb0fcad8f921ca79cecce0453a/message_definitions/v1.0/common.xml#L5733-L5742) · [PX4 姿态流](https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/src/modules/mavlink/streams/ATTITUDE.hpp#L58-L82) · [PX4 工作队列容器](https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/src/include/containers/IntrusiveQueue.hpp#L59-L94)
