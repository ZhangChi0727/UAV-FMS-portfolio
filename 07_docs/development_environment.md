# B0 开发环境（Windows 编辑、WSL 20.04 执行）

本说明建立 B0 的开发前提，不实现姿态估计、控制器、仿真或任何 B0
验收结果。现有 Windows 文献环境和 `literature/` 数据保持独立。

## 工作区边界

| 用途 | 位置 | 规则 |
|---|---|---|
| Windows 文献工作 | `<Windows checkout>/.venv` | 仅用于既有文献、notebook 与审计；不安装 B0 依赖。 |
| Linux B0 开发 | `~/src/uav-fms-portfolio` | 此路径是唯一的 Linux 活跃 checkout；通过 Git 同步，而不是复制 Windows 文件夹。 |
| Windows 兼容查看 | `/mnt/<drive>/<project-root>` | 可只读查看或临时诊断；不要与 Linux checkout 同时修改同一分支。 |

WSL 在 Linux 文件系统中使用源码和 build 目录的性能及权限语义更可靠；不要
将 Linux build 或 venv 写入 `/mnt/e` 的 Windows checkout。Microsoft 也建议在
从 Linux 命令行使用 Linux 工具时将文件保存在 WSL 文件系统中。

## Ubuntu 20.04 兼容策略

项目保留现有 Ubuntu 20.04，不原地升级、不新增发行版。其发行版仓库的
Python 为 3.8、CMake 为 3.16，低于本项目 Python 3.11+ 与 CMake 3.20 基线。
因此 B0 使用独立、可删除的用户态 CPython 3.11.17 和 venv；系统 Python
保持不变。CPython 3.11.17 的源码来自 Python.org，压缩包 SHA-256 为
`53cdee63ac4bf12387b7b33a53d3b1f8f4941cad73807a7b4fe91bb001ef004a`。

首次准备时，在 Ubuntu 20.04 终端运行以下命令。`sudo` 会要求你自己的 Linux
密码；不要把密码写入脚本、聊天或仓库。

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential ca-certificates curl gdb git libbz2-dev libffi-dev \
  libgdbm-dev liblzma-dev libncursesw5-dev libreadline-dev libsqlite3-dev \
  libssl-dev tk-dev uuid-dev xz-utils zlib1g-dev

mkdir -p "$HOME/src" "$HOME/.local/src"
cd "$HOME/.local/src"
curl --fail --location --remote-name \
  https://www.python.org/ftp/python/3.11.17/Python-3.11.17.tgz
echo '53cdee63ac4bf12387b7b33a53d3b1f8f4941cad73807a7b4fe91bb001ef004a  Python-3.11.17.tgz' | sha256sum --check
tar -xzf Python-3.11.17.tgz
cd Python-3.11.17
./configure --prefix="$HOME/.local/opt/cpython-3.11.17" --with-ensurepip=install
make -j"$(nproc)"
make altinstall
```

`make altinstall` 不会替换 `/usr/bin/python3`。完成后，使用此解释器创建 B0
环境；其中的 CMake/Ninja 覆盖 Ubuntu 20.04 较旧的系统 CMake，而不更改系统
包：

```bash
git clone https://github.com/ZhangChi0727/UAV-FMS-portfolio.git "$HOME/src/uav-fms-portfolio"
cd "$HOME/src/uav-fms-portfolio"
git switch codex/development-readiness
"$HOME/.local/opt/cpython-3.11.17/bin/python3.11" -m venv .venv-b0
. .venv-b0/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/b0-dev.txt
python --version
cmake --version
ninja --version
```

应仅在需要此开发环境的 Linux checkout 中执行 clone/switch，并按经核实的提交
SHA 或分支同步。Windows `.venv`、Linux `.venv-b0` 与各自 `build/` 都不进入 Git。

## 可复现的工具链探针

下列命令只构建 `tools/development_readiness/`。预设关闭遗留导航 EKF，避免
它的 Eigen 或导航实现状态影响 B0 环境判断。Catch2 v3.5.4 在系统无可用 v3
包时由 CMake 从固定提交 `b5373dadca40b7edc8570cf9470b9b1cb1934d40` 获取。

```bash
. .venv-b0/bin/activate
cmake --preset development-readiness-debug
cmake --build --preset development-readiness-debug
ctest --preset development-readiness-debug

cmake --preset development-readiness-release
cmake --build --preset development-readiness-release
ctest --preset development-readiness-release

cmake --build --preset development-readiness-debug --target clean
cmake --build --preset development-readiness-debug
ctest --preset development-readiness-debug
```

该探针有两个 CTest：一个 Catch2 C++17 测试，另一个由 pytest 加载同一构建目录
的 pybind11 扩展。它们只能证明工具链和 ABI 边界，不能作为 B0 控制或飞行验证
证据。预设不含个人绝对路径，也不使用 `-march=native`。

## IDE 手工验收

个人 `.idea/` 配置不提交。Ubuntu 工具链和 venv 准备完成后，按以下步骤完成
一次真实断点验证，并将实际结果补入就绪报告：

1. 在 CLion 2023.3.4 的 **Settings → Build, Execution, Deployment → Toolchains**
   新建/选择 WSL toolchain，发行版为 Ubuntu，工具使用 Linux 的 GCC、GDB、
   `.venv-b0/bin/cmake`（或其解析到的 CMake）和 Ninja。选择
   `development-readiness-debug` CMake Profile。
2. 在 `tools/development_readiness/src/probe.cpp` 的
   `return left + right;` 这一行设断点，启动 `development_readiness_cpp_tests` 的
   Debug。该行位于函数序言之后，确认停在 WSL 二进制、源码路径正确，并能观察
   `left` 和 `right`。
3. 在 PyCharm Professional 2023.3.3 添加 WSL interpreter，路径选择 Linux checkout
   的 `.venv-b0/bin/python`。以 pytest 运行
   `tools/development_readiness/python/test_binding.py`，在断言行设断点，确认能停止
   并显示 `probe`。

CLion 的 WSL toolchain 包含编译器、CMake、构建工具和调试器；PyCharm Pro 支持
WSL 解释器。IDE 可打开并不等于上述调试验收已经通过。

## MCP

本阶段不启用 IDE MCP server：终端、Git、CMake、CTest、pytest 与 `gh` 足以覆盖
本工作单；避免增加个人客户端配置、端口或权限面。将来若确实需要 IDE 符号分析，
先核实对应 IDE 版本支持，再限定为本项目的只读/确认执行访问。

## 参考

- [Microsoft：WSL 开发环境与 Linux 文件系统建议](https://learn.microsoft.com/windows/wsl/setup/environment)
- [JetBrains：CLion WSL2 toolchain](https://www.jetbrains.com/help/clion/how-to-use-wsl-development-environment-in-product.html)
- [JetBrains：PyCharm WSL interpreter](https://www.jetbrains.com/help/pycharm/using-wsl-as-a-remote-interpreter.html)
- [Python 3.11.17 发布与校验和](https://www.python.org/downloads/release/python-31117/)
