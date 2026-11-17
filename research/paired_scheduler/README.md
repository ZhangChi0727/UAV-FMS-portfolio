# 配对调度实验的运行与核查

本包是[闭环故障取证方案](../closed_loop_fault_evidence_proposal_20261104.md)下的独立研究实现。建议先看[测量合同](protocol.md)和[结果解释](../../literature/paired_scheduler_20261104.md)。观测原件在 evidence/ 下。两个 main 进程分别产生一个原始 CSV，生成终审 JSON 的 Python 分析不依赖任何原生程序内部函数。

## 重做保留数据的分析

从仓库根目录执行。CSV 每行是一个完整时窗，时间为相对于各自运行起点的 ns。每个 pair 的 A 是公共测量开启的 off 臂，B 是探针臂或 off/off 对照的第二次 off。单位 ns 与动力学的模型时间单位通过 unit_ns 对应。

~~~powershell
.\.venv\Scripts\python.exe -B research/paired_scheduler/reference.py
.\.venv\Scripts\python.exe -B research/paired_scheduler/analyze.py research/paired_scheduler/evidence --output build/paired-scheduler/reanalysis.json
~~~

## 重新采集

环境为 Windows x64，Windows 构建 26200，Python 3.11.5、MinGW-w64 GCC 13.1、C++17。宿主报告 24 个逻辑处理器。未固定线程亲和性或电源策略。采用 QPC（本次频率 10 MHz），两个线程使用同一时钟；比较跨线程顺序采用一刻度加 ns 转换保护量（101 ns）。[Windows 计时说明](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)

下面重建一次完整测量，out 选择未使用的目录，原始输出不可覆盖。每次测量包含真实 OS 调度，逐 ns 数据可随系统改变。Python 仅用标准库。

~~~powershell
$out = 'build/paired-scheduler-reproduction'
New-Item -ItemType Directory -Path $out
$compilerBin = '<MINGW_BIN>'
$env:Path = $compilerBin + ';' + $env:Path
& "$compilerBin\g++.exe" -std=c++17 -O2 -Wall -Wextra -pedantic -static -pthread research/paired_scheduler/scheduler.cpp -o "$out/scheduler.exe"
& .\.venv\Scripts\python.exe -B research/paired_scheduler/plan.py calibration $out
& "$out/scheduler.exe" "$out/calibration_plan.csv" "$out/calibration_raw.csv"
& .\.venv\Scripts\python.exe -B research/paired_scheduler/plan.py main $out
& "$out/scheduler.exe" "$out/main1_plan.csv" "$out/main1_raw.csv"
& "$out/scheduler.exe" "$out/main2_plan.csv" "$out/main2_raw.csv"
& .\.venv\Scripts\python.exe -B research/paired_scheduler/analyze.py $out --output "$out/audit.json"
~~~

本次采集源 scheduler.cpp 的 SHA-256 为 CA6D4FC5A56C82600FD4574082CCC9A2FC2F29EBD3E94CD4E7AED3260281B254；可执行文件的 SHA-256 为 CB7A0252981F1513D34EB4892D963FC70ED7450C7F3671604F4A0F5B7EC18CFD。实验在工作树 HEAD 6271219b2e4f68f9574542688a839c8c37381e44 上执行，新增实验文件属于工作树。正式 CSV 与计划的哈希在 [audit.json](evidence/audit.json) 中。校准独立保留，正式数值不含冒烟测试。
