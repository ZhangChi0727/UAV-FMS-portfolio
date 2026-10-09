# B0 开发就绪报告

状态日期：2026-10-09。此报告仅记录环境证据；不实现或宣称完成 B0。

## 已验证通过

| 项目 | 证据 | 状态 |
|---|---|---|
| 工作现场保护 | 原有 `roadmap.md` 修改与 `work_orders/` 未跟踪输入保留在 `codex/development-readiness` | 通过 |
| Windows 研究环境 | 已有 Windows Python 3.11.5、JupyterLab 4.2.5 与 `literature/`；未被此工作单修改 | 通过 |
| WSL 连通性 | Ubuntu 用户 `chi`；`github.com` DNS 可解析，`https://github.com` 返回 HTTP 200 | 通过 |
| WSL 文件系统 | `/mnt/e/Project/uav-fms-portfolio` 可访问；Linux 工作区策略见 `development_environment.md` | 通过 |
| Windows IDE 盘点 | CLion 2023.3.4、PyCharm Professional 2023.3.3、CLion bundled CMake 3.27.8 已发现 | 通过 |
| MCP | 未启用；CLI 覆盖当前工作单需求 | 通过（不需要） |

## 受限可用 / 待执行

| 项目 | 实际发现 | 下一步 |
|---|---|---|
| Ubuntu 20.04 | Python 3.8.10、Git 2.25.1；CMake、Ninja、G++、GDB 当前未安装 | 按 `development_environment.md` 安装最小工具并创建独立 CPython 3.11.17 venv。 |
| Linux C++17/CTest | 未执行；不得以 Windows IDE 的存在替代 Linux 构建证据 | 在 Linux checkout 运行 Debug、Release、clean-rebuild 三组 presets。 |
| pybind11 | 未执行；没有 Linux ABI 通过证据 | 在同一 `.venv-b0` 中运行 CTest 的 Python binding 测试。 |
| CLion | 已核对 WSL toolchain 与 GDB 支持文档；尚未进行 UI 构建/运行/断点 | 完成文档中的 CLion 三步手工验收。 |
| PyCharm | 已确认安装为 Professional 模块；尚未配置 WSL interpreter 或执行断点 | 完成文档中的 PyCharm 三步手工验收。 |

Ubuntu 20.04 发行版按用户决定保留使用，未新增或升级发行版。其系统版本低于
Python 3.11+ 与 CMake 3.20 基线，因此采用用户态、可删除的 CPython 3.11.17 与
`.venv-b0` 兼容路径；该路径尚待实际安装和测试。

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

## 非目标

- 不证明 B0 姿态估计、级联控制、SIL/HIL 或飞行结果。
- 不关闭 GitHub Issues #3–#8。
- 不迁移、重建或覆盖 `literature/screening.csv`、既有检索记录或 Windows 文献环境。
