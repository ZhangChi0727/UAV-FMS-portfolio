# B0 开发就绪报告

状态日期：2026-10-09。此报告只记录开发环境与工具链证据；不实现或宣称完成 B0
姿态估计、级联控制、SIL/HIL 或飞行验证。

## 已验证通过

| 项目 | 证据 | 状态 |
|---|---|---|
| 工作现场保护 | 原有 `roadmap.md` 修改与 `work_orders/` 未跟踪输入保留在 `codex/development-readiness` | 通过 |
| Windows 研究环境 | 既有 Windows Python 3.11.5、JupyterLab 4.2.5 与 `literature/` 未被此工作单修改 | 通过 |
| Ubuntu 20.04 工具链 | Ubuntu 20.04.6；GCC 9.4.0、GDB 9.2、Git 2.25.1 已安装。保留既有发行版，未新增或升级 Ubuntu | 通过 |
| 用户态 Python | `/home/chi/.local/opt/cpython-3.11.17/bin/python3.11` 为 CPython 3.11.17；源码 SHA-256 与说明中的 Python.org 校验值一致 | 通过 |
| Linux B0 venv | `/home/chi/src/uav-fms-portfolio/.venv-b0` 已安装 `requirements/b0-dev.txt`；CMake 3.30.5、Ninja 1.11.1、pytest 8.3.5、pybind11 2.13.6；`pip check` 无损坏依赖 | 通过 |
| WSL 网络与 Git | `github.com` DNS 可解析、HTTPS 返回 HTTP 200；APT 与 GitHub clone/push 已实际成功 | 通过 |
| Linux 工作区策略 | 主开发 checkout 与 venv 位于 `/home/chi/src/uav-fms-portfolio`；正常 Linux build/venv 不写入 `/mnt/e`。仅为验证 Windows IDE↔WSL 而保留一个已忽略的兼容性 build 目录 | 通过 |
| C++17 / CTest | 最终源码修订 `92f2c117cc93ab7a3177972e96d1d7b3f13eb607` 上，Debug clean-rebuild 与 Release 均为 2/2 CTest 通过；结束前复验的 Debug/Release 也均为 2/2 通过，含 Catch2 C++17 测试 | 通过 |
| pybind11 / pytest | 同一构建目录中的 pybind11 扩展由 pytest 成功加载；`add_for_probe(20, 22) == 42`，CTest Python binding 测试通过 | 通过 |
| GDB CLI 断点 | 在 `probe.cpp` 的 `return left + right;` 停止时，GDB 显示 `left = 20`、`right = 22`，并与寄存器参数一致 | 通过 |
| CLion 2023.3.4 WSL UI 调试 | `development_readiness_cpp_tests` 的真实 Debug 会话停在 `development_readiness::add_for_probe`；IDE Variables 显示 `left = 20`、`right = 22`，调用栈包含 Catch2 测试帧 | 通过 |
| PyCharm Professional 2023.3.3 WSL pytest UI 调试 | `development_readiness_pytest_wsl` 的真实 pytest Debug 会话停在 `test_python_calls_the_linux_or_native_cxx_extension`；Variables 中可见从已构建 Linux pybind11 扩展加载的 `probe`，调用栈包含 pytest 帧 | 通过 |
| 配置静态检查 | Windows CMake 3.27.8 可列出两个就绪 presets；`CMakePresets.json`、CI YAML、Python 探针语法已解析，Ruff 通过 | 通过 |
| 结束时清洁审计 | Windows checkout 与 WSL 活跃 checkout 的 `git status --short` 均为空，Windows 无未跟踪的非忽略文件；可再生的 pytest/Ruff/`__pycache__` 已清除，`.idea/`、venv 与本地 CMake 构建目录由 `.gitignore` 隔离，未删除刚验收所需的本机工具产物 | 通过 |
| MCP | 未启用；终端、Git、CMake、CTest、pytest 与 `gh` 覆盖本工作单需求 | 通过（不需要） |

原先的 localhost-proxy 启动警告会干扰 PyCharm 2023.3 的 WSL 文件夹检查。经用户授权，
在用户全局 `.wslconfig` 的 `[wsl2]` 段设置 `autoProxy=false` 并重启 WSL 后，该警告消失，
CPython 3.11.17 仍可启动。这是未提交、可逆的本机 WSL 设置，不属于仓库配置。

## 已执行的构建矩阵

探针只构建 `tools/development_readiness/`，并关闭遗留导航 EKF；它不能作为任何 B0
算法或飞行证据。最终修订上的实测结果如下：

| 配置 | CTest 结果 | 覆盖范围 |
|---|---|---|
| `development-readiness-debug`（clean-rebuild；结束前复验） | 2/2 通过，0.22 s | Catch2 C++17 与 pytest/pybind11 |
| `development-readiness-release`（结束前复验） | 2/2 通过，0.20 s | Catch2 C++17 与 pytest/pybind11 |

遗留 `02_estimation/python` 的现状为 9 个 xfailed、1 个 skipped、0 个 passed；这些
跳过/预期失败不构成实现或环境验收证据，未将其计入通过项。

## IDE 人工验收范围说明

CLion 与 PyCharm 的 UI 测试均从 Windows checkout 启动，因此 WSL 的生成目录是
`/mnt/e/Project/uav-fms-portfolio/cmake-build-debug-wsl`。它们证明 CLion/PyCharm↔WSL
的构建、C++ GDB 和 pytest/pybind11 调试链路可用，但不替代“Linux 活跃 checkout 的 build/
venv 不写入 `/mnt/e`”这一工作区策略；该生成目录是未提交的本地兼容性产物。两项 IDE
图形界面验收均已实际完成；个人 `.idea/` 配置不提交。

## 构建配置交付

`CMakePresets.json` 提供 Debug 与 Release 的独立目录。它们启用
`tools/development_readiness/` 而关闭遗留导航构建；探针包含 Catch2 C++17 和
pybind11/pytest 两项测试。根构建不再默认使用 `-march=native`，以免把开发机 CPU
特征写入可复现构建配置。

## 旧分支清理审计（删除前）

在 `2026-10-09` 对 `origin` 执行 `fetch --prune` 后，默认分支为
`origin/main`，其完整 SHA 为 `c9cf452f0a5f6e3e8ebbee553d083de79176877c`。
没有开放 PR，且 `git worktree list` 仅显示当前
`codex/development-readiness` 工作树。以下候选均为 `origin/main` 祖先、没有
`origin/main..candidate` 独有提交；当前工作树没有检出它们：

| 候选 | 删除前完整 tip SHA | 关联 PR | 远程状态 |
|---|---|---|---|
| `codex/development-baseline-v0.1` | `4c6bbf46394035fb05eeb09c960a767da9c350e2` | #2，已合并 | 本地与 `origin/` 均存在 |
| `codex/modular-platform-baseline` | `174623a8331685c985ca31756a8d5c0a023603d2` | #9，已合并 | 本地与 `origin/` 均存在 |
| `codex/research-environment` | `4c6bbf46394035fb05eeb09c960a767da9c350e2` | 无 | 仅本地存在 |

实际删除前必须再次读取远程 SHA，并对远程分支使用带上述 SHA 的
`--force-with-lease` 删除；本地只用 `git branch -d`。如需恢复，可运行
`git branch <name> <tip-sha>`，并在确认后推送该明确分支。删除结果会在执行后
追加到本报告；不删除 `main`、标签或当前就绪分支。

### 删除结果

重新读取的两个远程 tip SHA 与上表完全一致后，已删除远程
`codex/development-baseline-v0.1` 和
`codex/modular-platform-baseline`，并以 `git branch -d` 删除三个对应的本地候选。
随后 `git fetch --prune origin` 的结果只保留 `origin/main`；当前本地只保留
`main` 与活跃的 `codex/development-readiness`。没有删除 `main`、标签、工作树或
运行中的就绪分支。上表的 SHA 仍可用于恢复明确的本地分支。

## 非目标

- 不证明 B0 姿态估计、级联控制、SIL/HIL 或飞行结果。
- 不关闭 GitHub Issues #3–#8。
- 不迁移、重建或覆盖 `literature/screening.csv`、既有检索记录或 Windows 文献环境。
