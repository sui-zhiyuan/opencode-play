# PyCharm "Run with uv run" 导致 Ray 重建 worker 环境

## 症状

PyCharm 运行 Ray 脚本时，每次都有 `(raylet)` warning：

```
VIRTUAL_ENV=/home/.../.venv does not match the project environment path .venv
Creating virtual environment at: .venv
Building daft-demo @ file:///tmp/ray/...
Installed 19 packages in 530ms
```

worker 请求时需要重建整个环境。

## 根因

PyCharm 默认勾选 **"Run with uv run"**，实际命令变成：

```
uv run .venv/bin/python -m daft_demo
```

Ray 的 `uv_runtime_env_hook.py` 检测到父进程命令行中有 `uv run`，自动接管 runtime env：

1. 强制设置 `working_dir = os.getcwd()`（打包本地代码发给 worker）
2. 将 worker 的 `py_executable` 设为 `uv run` 命令
3. worker 启动时进入 uv 项目上下文，检测到 `VIRTUAL_ENV`（绝对路径）不等于 `.venv`（相对路径），触发 `uv pip install` 重建环境

与 `runtime_env={"env_vars": {}}` 无关——hook 第 404 行直接写 `working_dir`，用户配置无效。

## 修复

取消 PyCharm 的 "Run with uv run"：

`Run → Edit Configurations` → 取消勾选 **"Run with uv run"** → 命令变为：

```
.venv/bin/python -m daft_demo
```

没有 `uv run` → hook 不触发 → worker 直接复用已有 venv → 任务投喂到常驻 `ray::IDLE` 池进程。
