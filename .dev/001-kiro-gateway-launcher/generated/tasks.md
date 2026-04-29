# 任务列表 — kiro-gateway-launcher

## 状态表

| ID    | 任务名称                        | 状态        | 备注 |
|-------|---------------------------------|-------------|------|
| T-001 | 配置 pyproject.toml             | not-started |      |
| T-002 | 实现 config_loader.py           | not-started |      |
| T-003 | config_loader 单元测试          | not-started |      |
| T-004 | 实现 repo_manager.py            | not-started |      |
| T-005 | repo_manager 单元测试           | not-started |      |
| T-006 | 实现 setup_wizard.py            | not-started |      |
| T-007 | setup_wizard 单元测试           | not-started |      |
| T-008 | 实现 config_editor.py           | not-started |      |
| T-009 | config_editor 单元测试          | not-started |      |
| T-010 | 实现 updater.py                 | not-started |      |
| T-011 | updater 单元测试                | not-started |      |
| T-012 | 实现 cli.py                     | not-started |      |
| T-013 | 端到端冒烟测试                  | not-started |      |

---

## 任务详情

#### T-001 — 配置 pyproject.toml

**目标：** 建立可安装的包结构，声明 kiro 的运行时依赖和命令入口点。

**需求：**
- 包名 `kiro-gateway-launcher`，命令名 `kiro-gateway-launcher`
- 入口点：`kiro-gateway-launcher = kiro_gateway_launcher.cli:main`
- 声明 kiro 运行时依赖：`fastapi`、`uvicorn[standard]`、`httpx`、`loguru`、`python-dotenv`、`tiktoken`
- `requires-python = ">=3.12"`
- 创建 `src/kiro_gateway_launcher/__init__.py`（空文件）
- 创建 `tests/__init__.py`（空文件）

**验收标准：**
- `uv build` 无报错
- `uv run kiro-gateway-launcher --help` 可执行（即使 cli.py 只是占位符）

**参考：** `plan.md § Technology Decisions`

**实现摘要：** *(任务完成后填写)*

---

#### T-002 — 实现 config_loader.py

**目标：** 在任何 kiro 模块导入前，将配置注入 `os.environ`。

**需求：**
- `ConfigLoader` 类，提供 `load() -> None` 方法
- 路径常量：`CONFIG_DIR = ~/.config/kiro-gateway/`，`USER_ENV = CONFIG_DIR / ".env"`
- 加载优先级（从低到高）：`USER_ENV` → `./.env`（cwd）→ `os.environ`（已有的不覆盖）
- 自定义解析 KEY=VALUE（不依赖 python-dotenv），跳过注释行和空行
- 文件不存在时静默跳过；文件存在但不可读时打印警告

**验收标准：**
- 单元测试通过（T-003）
- 不引入任何新依赖

**参考：** `plan.md § ConfigLoader — priority chain`

**实现摘要：** *(任务完成后填写)*

---

#### T-003 — config_loader 单元测试

**目标：** 验证 ConfigLoader 的优先级逻辑和边界情况。

**需求：**
- 正常：USER_ENV 中的值被加载到 os.environ
- 优先级：cwd `.env` 覆盖 USER_ENV；os.environ 已有的值不被覆盖
- 边界：文件不存在时不报错
- 边界：注释行（`#`）和空行被跳过
- 边界：`KEY=VALUE=WITH=EQUALS` 正确解析（只按第一个 `=` 分割）

**验收标准：**
- `pytest tests/test_config_loader.py` 全部通过
- 覆盖率 ≥ 80%

**参考：** `src/kiro_gateway_launcher/config_loader.py`

**实现摘要：** *(任务完成后填写)*

---

#### T-004 — 实现 repo_manager.py

**目标：** 管理 kiro-gateway 源码的 clone / pull，并注入 sys.path。

**需求：**
- `RepoManager` 类
- 常量：`UPSTREAM = "https://github.com/jwadow/kiro-gateway"`，`REPO_DIR = ~/.local/share/kiro-gateway-launcher/repo/`
- `ensure() -> None`：若 REPO_DIR 不存在则 clone，然后调用 `_inject_sys_path()`
- `pull() -> str`：执行 `git pull`，返回新的 HEAD SHA
- `head_sha() -> str`：读取本地 repo 的当前 commit SHA（读 `.git/HEAD` + ref 文件）
- `_inject_sys_path() -> None`：将 REPO_DIR 插入 `sys.path[0]`（幂等，已存在则跳过）
- git 不在 PATH 时打印明确错误并 `sys.exit(1)`
- clone / pull 失败时打印错误并 `sys.exit(1)`

**验收标准：**
- 单元测试通过（T-005）
- `ensure()` 在 REPO_DIR 已存在时不重复 clone

**参考：** `plan.md § RepoManager — 运行时 clone 与 sys.path 注入`

**实现摘要：** *(任务完成后填写)*

---

#### T-005 — repo_manager 单元测试

**目标：** 验证 RepoManager 的 clone/pull/sys.path 逻辑。

**需求：**
- 正常：REPO_DIR 不存在时触发 clone
- 正常：REPO_DIR 已存在时跳过 clone，直接注入 sys.path
- 正常：`_inject_sys_path()` 幂等（多次调用不重复添加）
- 正常：`head_sha()` 正确读取 SHA
- 边界：git 不在 PATH 时 exit 1
- 使用 `unittest.mock.patch` mock `subprocess.run` 和文件系统操作

**验收标准：**
- `pytest tests/test_repo_manager.py` 全部通过

**参考：** `src/kiro_gateway_launcher/repo_manager.py`

**实现摘要：** *(任务完成后填写)*

---

#### T-006 — 实现 setup_wizard.py

**目标：** 首次运行时交互式引导用户完成凭证配置。

**需求：**
- `SetupWizard` 类，接受 `WizardIO` protocol 参数（DIP）
- `WizardIO` Protocol：`prompt(message: str) -> str`，`print(message: str) -> None`
- `CredentialType(StrEnum)`：`JSON_FILE`、`REFRESH_TOKEN`、`SQLITE_DB`
- `CredentialHandler(ABC)`：`prompt(io: WizardIO) -> dict[str, str]`
- 三个具体 handler：`JsonFileHandler`、`RefreshTokenHandler`、`SqliteDbHandler`
- `SetupWizard.needs_setup() -> bool`：检查 USER_ENV 中是否缺少凭证
- `SetupWizard.run() -> None`：引导流程，写入 `~/.config/kiro-gateway/.env`
- `KeyboardInterrupt` 时打印友好信息并 `sys.exit(0)`

**验收标准：**
- 单元测试通过（T-007）
- 新增凭证类型只需添加新 handler 子类，不修改 wizard 流程

**参考：** `plan.md § SetupWizard — credential type dispatch (OCP)`，`init.md § F3`

**实现摘要：** *(任务完成后填写)*

---

#### T-007 — setup_wizard 单元测试

**目标：** 验证 wizard 流程和各凭证类型的处理。

**需求：**
- 正常：`needs_setup()` 在无凭证时返回 True，有凭证时返回 False
- 正常：完整 wizard 流程写入正确的 .env 内容（mock WizardIO）
- 正常：三种凭证类型各自的 prompt 流程
- 边界：`KeyboardInterrupt` 时 exit 0 不抛异常
- 使用 `MockIO` 注入脚本化输入

**验收标准：**
- `pytest tests/test_setup_wizard.py` 全部通过

**参考：** `src/kiro_gateway_launcher/setup_wizard.py`

**实现摘要：** *(任务完成后填写)*

---

#### T-008 — 实现 config_editor.py

**目标：** 提供只读配置查看、路径显示和配置重置功能。

**需求：**
- `ConfigEditor` 类，接受 `WizardIO` protocol 参数
- `show() -> None`：读取 USER_ENV，打印所有 KEY=VALUE（敏感值部分遮蔽为 `****`）；文件不存在时打印提示"尚未配置，运行 `config --edit` 开始配置"
- `show_path() -> None`：打印 USER_ENV 的绝对路径
- `reset(io: WizardIO) -> None`：二次确认后删除 USER_ENV
- **注意**：`--edit` 功能由 `cli.py` 直接调用 `SetupWizard.run()` 实现，不在 ConfigEditor 中

**验收标准：**
- 单元测试通过（T-009）
- 敏感 key（含 TOKEN、KEY、SECRET、PASSWORD）的值显示为 `****`
- 文件不存在时 `show()` 不报错，打印友好提示

**参考：** `init.md § F4`，`plan.md § config 命令流程`

**实现摘要：** *(任务完成后填写)*

---

#### T-009 — config_editor 单元测试

**目标：** 验证 ConfigEditor 的显示、遮蔽和重置逻辑。

**需求：**
- 正常：`show()` 正确遮蔽敏感 key（TOKEN、KEY、SECRET、PASSWORD）
- 正常：`show()` 在文件不存在时打印友好提示，不抛异常
- 正常：`show_path()` 返回正确路径
- 正常：`reset()` 在确认后删除文件
- 边界：`reset()` 未确认时不删除文件

**验收标准：**
- `pytest tests/test_config_editor.py` 全部通过

**参考：** `src/kiro_gateway_launcher/config_editor.py`

**实现摘要：** *(任务完成后填写)*

---

#### T-010 — 实现 updater.py

**目标：** 检查上游最新 commit，通过 git pull 更新本地 repo。

**需求：**
- `Updater` 类，依赖注入 `RepoManager`
- `UPSTREAM_API = "https://api.github.com/repos/jwadow/kiro-gateway/commits/main"`
- `run() -> None`：获取远端 SHA → 对比本地 SHA → 若不同则 pull → 打印结果
- 若 repo 不存在，先调用 `RepoManager.ensure()` 再更新
- 网络失败时打印明确错误并 `sys.exit(1)`
- 使用 `urllib.request`（stdlib），不引入新依赖

**验收标准：**
- 单元测试通过（T-011）
- 已是最新时打印提示，不执行 pull

**参考：** `plan.md § Updater — git pull 更新`

**实现摘要：** *(任务完成后填写)*

---

#### T-011 — updater 单元测试

**目标：** 验证 Updater 的版本对比和更新逻辑。

**需求：**
- 正常：远端 SHA 与本地相同时不执行 pull
- 正常：远端 SHA 不同时执行 pull 并打印新旧 SHA
- 边界：网络失败时 exit 1
- 边界：repo 不存在时先 clone 再更新
- mock `urllib.request.urlopen` 和 `RepoManager`

**验收标准：**
- `pytest tests/test_updater.py` 全部通过

**参考：** `src/kiro_gateway_launcher/updater.py`

**实现摘要：** *(任务完成后填写)*

---

#### T-012 — 实现 cli.py

**目标：** 命令入口，按正确顺序初始化并分发命令。

**需求：**
- `main()` 函数：① `ConfigLoader().load()` → ② `RepoManager().ensure()` → ③ 解析参数 → ④ 分发
- 子命令及行为：
  - `config`（无参数）→ `ConfigEditor.show()`：只读显示当前配置（敏感值遮蔽）
  - `config --edit` → `SetupWizard.run()`：重新运行完整 wizard
  - `config --reset` → `ConfigEditor.reset()`：删除配置文件（需确认）
  - `config --show-path` → `ConfigEditor.show_path()`：打印配置文件路径
  - `update` → `Updater.run()`
  - 默认（无子命令）→ 检查凭证 → 若缺失则 `SetupWizard.run()` → 启动 uvicorn
- `--host` / `-H`，`--port` / `-p` 参数
- **F4 错误提示**：凭证无效时打印明确错误，指向 `~/.config/kiro-gateway/.env`，提示运行 `config --edit` 重新配置；不再提示 `cp .env.example .env`
- 捕获 `ImportError`（kiro import 失败）并打印可操作提示
- 所有 `import kiro.*` 必须在函数体内（延迟导入）

**验收标准：**
- `kiro-gateway-launcher --help` 显示正确帮助信息
- `kiro-gateway-launcher config` 显示当前配置（或友好提示）
- `kiro-gateway-launcher config --show-path` 正确输出路径
- `kiro-gateway-launcher update` 可执行

**参考：** `plan.md § Config injection timing (critical)`，`plan.md § config 命令流程`，`init.md § F4`

**实现摘要：** *(任务完成后填写)*

---

#### T-013 — 端到端冒烟测试

**目标：** 验证完整安装和启动流程。

**需求：**
- `uv build` 成功
- `uv tool install dist/*.whl` 成功
- `kiro-gateway-launcher --help` 输出正确
- `kiro-gateway-launcher config --show-path` 输出正确路径
- `kiro-gateway-launcher update` 在有网络时成功执行（或打印"已是最新"）
- 手动验证：配置凭证后 `kiro-gateway-launcher` 能启动服务

**验收标准：**
- 以上所有步骤无报错

**参考：** 全部源文件

**实现摘要：** *(任务完成后填写)*
