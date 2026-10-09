# B0 开发就绪与工具环境工作单

执行对象：Task Carrier。日期：2026-10-09。
目标：建立可复现的 Linux 编译运行环境、Windows IDE 开发入口及安全的
Git 工作流，使 [B0 工作单](B0_work_order.md) 可以开始 G0。
本任务不实现控制算法，不宣称 B0 已完成，不更换项目技术方向。

## 输入与已知状态

先读取 AGENTS.md、项目章程、架构、开发基线、路线图及 B0 工作单。
以下是交接快照，执行前必须重新核查：

- Windows 工作区为 E 盘 Project 下的 uav-fms-portfolio，远程为
  https://github.com/ZhangChi0727/UAV-FMS-portfolio。
- main 曾与 origin/main 同步在 c9cf452；PR #1、#2、#9 已合并。
- 本地 roadmap.md 有未提交修改，work_orders/ 有未跟踪文件。
  这些是本任务输入，必须保留、阅读并纳入适当提交。
- WSL2 已存在 Ubuntu，版本 20.04.6；无需重新安装 WSL 本身。
- Windows 研究虚拟环境可读取 Python 3.11.5、JupyterLab 4.2.5、
  NumPy 1.26.4、Pandas 2.2.2、Matplotlib 3.8.4、OpenPyXL 3.1.5。
- CLion、PyCharm、本机 CMake 的具体版本、路径、许可证及 WSL 功能待检查。
- 启动 WSL 曾出现 localhost 代理提示；尚未证明下载受影响。

## 权限与人工介入

用户授权本任务配置项目开发环境、维护相关文件和安全清理已合并分支。
按工具实际审批机制申请所需权限，不能把本文件视为绕过系统限制的依据。

| 操作 | 执行方式 | 人工介入 |
|---|---|---|
| 仓库读写、构建和测试 | 优先终端、Git、gh | 沙箱需要时按具体命令审批 |
| 软件安装及用户配置目录写入 | 指定安装目标、来源、变更范围 | 管理员/UAC、sudo 密码由用户输入 |
| 新发行版初始化 | 官方 WSL 发行版 | 用户创建 Linux 用户及密码 |
| IDE 许可证、服务登录 | 原有官方账户流程 | 用户完成登录及许可确认；不自动购买 |
| GitHub 身份验证 | 优先现有 gh/Git 凭据 | 缺失时用户浏览器登录；不索取私钥或 token |
| MCP 或新客户端访问 | 必须说明工具能力、项目及访问范围 | 按当前工具策略确认后启用 |
| 重启、迁移、网络全局修改 | 说明影响后执行 | 必须协调用户，避免中断其他任务 |

不要启用永久管理员、sudo NOPASSWD、全局关闭确认、TLS 校验绕过、
防火墙关闭或对外开放 IDE 服务。不要在日志或仓库保存密钥、代理口令、
登录 cookie、完整个人环境变量或许可证信息。
不要覆盖整个用户配置文件；读取后做最小变更并保存可恢复副本。

## 第一阶段 保护现场与清点工具

1. 记录 git status、当前分支、remote、HEAD、worktree list、开放 PR。
2. 阅读已有未提交文件，区分本工作单输入和其他用户修改。
   不使用 reset --hard、clean -fd、强制 checkout 或全量自动暂存。
3. 新建或复用本任务专用 codex/development-readiness 分支。
   如已有同名分支，先检查所属工作，不重置它。
4. 记录 Windows CMake、CLion、PyCharm 的版本和安装来源；
   PATH 未发现不等于软件未安装。检查 IDE 内置工具，不盲目重装。
5. 检查 WSL 发行版、默认用户、Python、编译器、CMake、Ninja、GDB、Git。
6. 对照官方文档确认当前 IDE 的 WSL 和调试功能是否可用。
   PyCharm WSL 解释器可能涉及 Pro 功能；缺失时不自动购买。

验收：形成工具清单及可用性表，未提交成果均得到保护。

## 第二阶段 Linux 环境

推荐并行配置 Ubuntu 24.04，保留现有 20.04。先检查是否已有适合环境，
若已有则复用；不要原地升级或注销旧发行版。新增发行版需要说明磁盘
影响，并让用户完成首次账号初始化。若无法新增，记录旧环境适配方案。

基础工具包括 GCC/G++、CMake、Ninja、GDB、Git、Python 3、venv 和开发头文件。
从官方软件源安装，记录最终版本。C++ 标准固定为 C++17。
不为追求最新版本升级系统所有软件。

验证 DNS、HTTPS、软件源和 GitHub 连接后再判断代理是否需要处理。
不要把 Windows localhost 代理地址直接照搬给 WSL。
必要变更限定于开发环境，保留原配置；不要披露认证信息。

### 工作区选择

优先考虑 WSL Linux 文件系统内的源码及构建目录，通过 IDE 打开同一份源码。
现有 Windows 工作区保留。若新增 Linux clone，必须先提交并推送需要交接的
工作单，按 Git revision 同步，不用文件夹复制实现双向同步。
明确唯一的活跃开发工作区和各自分支，禁止两个环境同时改写同一个 checkout。

如果选择现有 Windows 路径经 /mnt/e 挂载，须记录性能与文件权限限制，
且 Linux build、venv 不与 Windows build、venv 混用。
在报告中记录实际路径；共享文档和 presets 不写个人绝对路径。

验收：普通用户可运行工具版本检查、编译 C++17 小程序及运行 Python。

## 第三阶段 依赖与研究环境复用

保留 Windows Zotero、Better BibTeX、研究虚拟环境及文献记录。
Linux 创建独立 B0 venv，不复制 Windows .venv，不覆盖 Conda base。

建立独立 B0 依赖文件：数值/绘图、pytest、代码检查及 pybind11 所需工具。
版本经小型探针验证后锁定，并记录 Python 主次版本；旧根 requirements.txt
含 PyTorch、视觉和实验跟踪等扩展依赖，不作为 B0 全量安装入口。

研究 notebook 如需迁至 Linux，单独验证其路径和依赖，注册独立 kernel；
这不是 B0 就绪的先决条件。不得将已有文献工作簿或筛选数据重建覆盖。

验收：解释器路径明确，依赖可从清单重建，Windows 研究环境仍可用。

## 第四阶段 CMake 与 CLion

Windows CLion 选择 WSL toolchain，明确发行版、Linux 编译器、CMake、
构建工具和调试器。本机 Windows CMake 保留，用于独立 Windows 构建时
再启用，不能与 Linux 对象文件共用 build 目录。

先建立小型、独立的环境 smoke target，验证 C++17、CTest/Catch2 和调试。
该探针不能被标为 B0 控制器。不要因旧 EKF 构建缺陷扩展本任务范围。
若修改根构建，保留旧导航目标，通过选项隔离其依赖。

建立可复现的 CMake 配置或 presets，区分 Debug/Release，避免机器专用
路径和默认 -march=native。验证首次配置、构建、测试、清理后重建。
CLion 中设置一次断点，确认停在 WSL 二进制、源码路径正确、可查看变量。

验收：IDE 与终端使用同一配置；CTest 通过；断点实测成功。

## 第五阶段 PyCharm 与跨语言调用

选择同一 WSL 发行版和 B0 venv，工作目录指向实际开发 checkout。
验证运行、pytest、断点及图表输出。若 WSL 解释器功能不可用，报告
许可证/版本限制；以 WSL 终端作为临时执行入口，不把终端成功写成 IDE 验收成功。

建立小型 pybind11 探针，验证 Python 调用 Linux C++ 扩展并检查返回值。
构建使用同一 Python 解释器与开发头文件，避免 Windows/Linux ABI 混用。
探针仅验证工具链，不实现控制算法。

验收：记录 Python 路径、扩展来源路径、测试输出；PyCharm 断点实测。

## 第六阶段 工具与 MCP

终端、Git、gh 足以完成主要工作，MCP 不是就绪前提。
优先复用已有工具；不要为每个 IDE 安装重复服务器。

若需要 IDE 符号分析或运行配置控制，可评估该 IDE 版本的官方 JetBrains
MCP Server。先检查实际支持与暴露工具，再决定是否启用。
只打开本项目，限制工具到需要的读取、分析、构建能力。
修改或执行命令保留确认；不启用无确认执行模式。

连接配置使用 IDE 实际生成的 transport、端口及客户端配置；
禁止猜测端点。限定本机访问，不对公网开放。若 Windows 客户端与 WSL
连接失败，优先调整受限本地路径或使用 CLI，不为连通性扩大网络权限。

任何客户端配置修改都先读取现有文件并保存备份。不要把其他项目的 MCP、
GitHub、代理配置覆盖。若涉及 Codex 客户端设置，按实际版本官方说明操作。
缺少可用 IDE 控制工具时让用户完成具体 UI 步骤，不报告未经验证的成功。

验收：若启用 MCP，实际列出工具并完成一次本项目只读调用；
若不启用，记录“不需要，CLI 覆盖”，不作为阻塞项。

## 第七阶段 安全清理分支

候选范围仅限下列旧分支，不含任务执行期间新建分支：

| 分支 | 快照状态 | 清理条件 |
|---|---|---|
| codex/development-baseline-v0.1 | 本地/远程，旧 PR #2 已合并 | 重新验证所有检查 |
| codex/modular-platform-baseline | 本地/远程，PR #9 已合并 | 重新验证所有检查 |
| codex/research-environment | 仅本地，指向旧基线 | 重新验证无独有提交及未保护文件 |

逐个执行以下检查，失败则保留该分支并报告原因：

1. fetch 更新远程；核实 remote URL 和默认分支为本仓库/main。
2. 将分支名称、完整 tip SHA、关联 PR 状态保存到清理记录。
3. 用 merge-base --is-ancestor 检查候选 tip 是否为最新 origin/main 的祖先；
   同时检查 origin/main..candidate 不含独有提交。
4. 查询开放 PR，确认无依赖该分支的工作；检查 git worktree list，
   候选不得被其他 worktree 使用，也不得属于正在执行的任务。
5. 确认工作单及其他未提交文件已安全保存。本地删除时切到安全分支。
6. 删除远程前再次读取该引用 SHA，必须与记录一致。优先使用指定旧 SHA
   的 force-with-lease 条件删除来防止覆盖并发更新；这仅用于比较并删除
   指定引用，不允许无条件 force push。若引用变化则停止该分支清理。
7. 本地仅使用 git branch -d 加明确名称；失败不改用 -D。
8. fetch --prune 后复查远程、本地、工作树及默认分支。

示例命令仅在替换并核实完整 SHA 后执行：

```text
git merge-base --is-ancestor <candidate-tip-sha> origin/main
git log --oneline origin/main..<candidate>
git push --force-with-lease=refs/heads/<candidate>:<verified-tip-sha> origin :refs/heads/<candidate>
git branch -d <candidate>
```

保留 tip SHA 后可用 git branch <name> <sha> 恢复本地分支；
必要时推送该明确分支恢复远程。全部候选均已被 main 包含才可清理。
禁止删除 main、标签、未合并分支、他人 worktree 或发行版。
不启用全仓库自动删分支设置，除非另有明确授权。

## 第八阶段 交付与验收

提交项目可复用的依赖清单、构建探针、操作说明和已脱敏就绪报告。
IDE 个人设置、用户 presets、venv、build、认证材料不得进入 Git。
检查差异和本地链接，执行现有导航合同测试，记录 xfail/skip 的真实含义。
为新增环境探针配置独立 CI；不要借就绪任务关闭 B0 #3-#8。

创建一个就绪 PR，关联 B0 #3 并注明只完成环境部分，不自动关闭该 Issue。
推送后附上 PR，等待检查并报告；本工作单不要求自动合并就绪 PR。
main 可以与一个活跃就绪分支并存，不应为“只有一个分支”删除活跃工作。

| 验收项 | 需要的证据 |
|---|---|
| 工作保护 | 原有修改去向明确，无意外丢失 |
| Linux 工具链 | 版本清单、C++17 编译及测试 |
| Python 环境 | 独立 venv、依赖重建及 pytest |
| 跨语言 | pybind11 探针通过 |
| CLion | WSL 构建/运行/调试实际验证 |
| PyCharm | WSL 解释器/运行/调试实际验证，或明确受限状态 |
| 研究兼容 | 旧环境及数据保留，路径与用途明确 |
| MCP | 可选启用验证或不需要的理由 |
| 分支清理 | 前后名称、SHA、祖先检查、恢复办法 |
| 远程交付 | PR、CI、提交 SHA、剩余阻塞与人工步骤 |

最终报告区分“已验证通过”“受限可用”“待人工操作”“未执行”。
不得因命令存在、软件安装完成或 IDE 打开就报告全部开发就绪。

## 官方参考

- [CLion WSL 工具链](https://www.jetbrains.com/help/clion/how-to-use-wsl-development-environment-in-product.html)
- [PyCharm WSL 解释器](https://www.jetbrains.com/help/pycharm/using-wsl-as-a-remote-interpreter.html)
- [PyCharm 解释器与功能范围](https://www.jetbrains.com/help/pycharm/configuring-python-interpreter.html)
- [JetBrains MCP 配置参考，实际 IDE 支持另行核实](https://www.jetbrains.com/help/idea/mcp-server.html)
- [Microsoft WSL 开发环境](https://learn.microsoft.com/en-us/windows/wsl/setup/environment)
