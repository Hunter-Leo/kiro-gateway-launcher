# 项目阶段

```
project_stage: pre-launch
```

# 需求说明

## 背景与动机

`kiro-gateway` 是一个基于 FastAPI 的代理服务，将 OpenAI/Anthropic 兼容的 API 请求转发到 Kiro（AWS CodeWhisperer）。原项目作者拒绝合并 `feat/uv-tool-install` 分支（包含 uv tool 安装支持、setup wizard、config 子命令等功能），因此需要以独立插件包的形式实现这些功能，不修改原项目任何代码。

## 核心问题

1. 原项目无法通过 `uv tool install` 安装为全局 CLI 工具
2. 原项目 `config.py` 在模块导入时即读取环境变量，无法在运行时动态注入用户配置
3. 缺少首次运行引导（setup wizard）和配置管理命令
4. 需要提供 `update` 命令，让用户能一键更新底层 `kiro-gateway` 依赖

## 总体目标

创建独立 Python 包 `kiro-gateway-launcher`，提供 `kiro-gateway-launcher` 命令，作为 `kiro-gateway` 的外层包装：

```bash
# 安装
uv tool install git+https://github.com/FightingLee97/kiro-gatewate-launcher

# 使用
kiro-gateway-launcher                    # 启动服务（首次运行触发 wizard）
kiro-gateway-launcher --port 9000
kiro-gateway-launcher config             # 查看配置
kiro-gateway-launcher config --edit      # 重新配置
kiro-gateway-launcher config --reset     # 重置配置
kiro-gateway-launcher config --show-path # 显示配置文件路径
kiro-gateway-launcher update             # 更新 kiro-gateway 到最新版本
```

## 业务价值

- 无需修改原项目，以插件形式独立维护
- 一条命令安装，一条命令启动，降低使用门槛
- 自动引导首次配置，消除手动创建 `.env` 的门槛
- 提供 `update` 命令，保持与上游同步

---

# 功能需求

## F1 — 包结构与安装

- 包名：`kiro-gateway-launcher`，命令名：`kiro-gateway-launcher`
- 支持 `uv tool install git+<repo-url>` 安装
- 依赖 `kiro-gateway @ git+https://github.com/jwadow/kiro-gateway`

## F2 — 配置加载（在 kiro 模块导入前注入）

- 配置文件路径：`~/.config/kiro-gateway/.env`
- 加载优先级（从高到低）：系统环境变量 > 当前目录 `.env` > `~/.config/kiro-gateway/.env`
- **关键**：必须在 `import kiro.*` 之前将配置写入 `os.environ`，因为 kiro 的 `config.py` 在模块导入时即绑定环境变量

## F3 — 首次运行 Setup Wizard

- 检测到无凭证配置时，启动交互式引导（而非报错退出）
- 引导步骤：
  1. 欢迎信息
  2. 自动检测已安装的 kiro-cli / amazon-q SQLite 数据库
  3. 选择凭证类型：JSON 文件 / Refresh Token / SQLite DB
  4. 输入对应值
  5. 设置 `PROXY_API_KEY`（显示默认值，回车跳过）
  6. 保存到 `~/.config/kiro-gateway/.env`，然后继续启动服务器

## F4 — `config` 子命令

- `kiro-gateway-launcher config`：启动交互式配置编辑器（显示所有变量，按编号修改）
- `kiro-gateway-launcher config --reset`：删除用户配置文件（需确认）
- `kiro-gateway-launcher config --show-path`：显示配置文件路径

## F5 — `update` 子命令

- 检查 `jwadow/kiro-gateway` GitHub 仓库的最新 commit
- 与当前安装版本对比
- 若有更新，提示用户并执行 `uv tool install --reinstall git+<url>` 更新
- 若已是最新，告知用户无需更新

## F6 — 服务器启动

- 支持 `--host` / `-H` 和 `--port` / `-p` 参数
- 启动前打印 banner（与原项目风格一致）
- 委托给 `kiro.app:app` + uvicorn 运行

---

# 技术需求

- Python >= 3.12
- 使用 `uv` 管理依赖
- 不引入额外第三方依赖（交互使用标准库 `input()`，HTTP 检查使用 `urllib`）
- 配置目录遵循 XDG Base Directory 规范：`~/.config/kiro-gateway/`
- 入口点通过 `[project.scripts]` 声明

---

# Action Items

**前置文档**（需要）：

- [X] 已分析 `feat/uv-tool-install` 分支代码（setup_wizard.py、config_editor.py、cli.py、config.py）

> 前置文档已完成，直接进入必需文档。

**必需文档**（按顺序）：

- [ ] `generated/plan.md`             — Phase 04
- [ ] `generated/tasks.md`            — Phase 05
- [ ] `generated/start-and-resume.md` — Phase 06（任务执行前必须存在）

---

# 编码规范

## OOP & SOLID

- **单一职责**：`setup_wizard.py` 只负责交互引导；`config_loader.py` 只负责配置加载；`config_editor.py` 只负责配置编辑；`cli.py` 只负责命令解析与分发；`updater.py` 只负责版本检查与更新
- **开闭原则**：凭证类型使用 `StrEnum`，新增类型只需扩展枚举，不修改现有逻辑
- **依赖倒置**：wizard 和 editor 依赖抽象 IO 接口（`WizardIO` Protocol），便于测试注入 mock

## Python 编码标准

- 所有函数参数和返回值必须有类型注解
- 每个文件、公共类、公共函数必须有 docstring（Google Style）
- 使用 `StrEnum` 表示固定选项（凭证类型）
- 使用 `pathlib.Path` 处理所有路径操作
- 错误处理：明确捕获，给出可操作的错误信息
- 不硬编码 secrets，使用环境变量

## 测试标准

- 测试文件命名：`test_*.py`，放在 `tests/` 目录
- 覆盖：正常流程、边界情况、异常情况
- Wizard / Editor 测试使用 `unittest.mock.patch` mock `input()`
- 核心逻辑覆盖率 ≥ 80%
- 使用 `pytest`
