# Implementation Plan — kiro-gateway-launcher

## Project Structure

```
kiro-gateway-launcher/
├── pyproject.toml                  # package metadata, entry point, kiro's runtime deps
├── .python-version
├── src/
│   └── kiro_gateway_launcher/
│       ├── __init__.py
│       ├── cli.py                  # entry point, argument parsing, command dispatch
│       ├── config_loader.py        # load .env files and inject into os.environ BEFORE kiro imports
│       ├── repo_manager.py         # git clone / git pull for jwadow/kiro-gateway source
│       ├── setup_wizard.py         # interactive first-run credential wizard
│       ├── config_editor.py        # interactive config viewer/editor
│       └── updater.py              # GitHub latest-commit check and git pull
└── tests/
    ├── __init__.py
    ├── test_config_loader.py
    ├── test_repo_manager.py
    ├── test_setup_wizard.py
    ├── test_config_editor.py
    └── test_updater.py
```

## Technology Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | matches upstream kiro-gateway requirement |
| Package manager | uv | enables `uv tool install git+<url>` workflow |
| kiro-gateway 分发方式 | 运行时 git clone（方案 B1） | 上游无 pyproject.toml，不能作为 Python 包安装；clone 后 sys.path 注入 |
| kiro 运行时依赖 | 在 launcher pyproject.toml 中预先声明 | uv tool install 时一次性安装，无需事后修改 venv |
| CLI parsing | `argparse` (stdlib) | no extra deps; sufficient for the command surface |
| HTTP (update check) | `urllib.request` (stdlib) | no extra deps; single GET to GitHub API |
| .env parsing | custom (stdlib only) | avoid `python-dotenv` dep; simple KEY=VALUE format |
| Interactive IO | `input()` (stdlib) | no extra deps; sufficient for wizard/editor |
| Server runner | `uvicorn` (declared dep) | installed via pyproject.toml, shared with kiro |

## Implementation Path

Steps are ordered by dependency. Each step is independently testable before the next begins.

1. **`pyproject.toml`** — 声明包元数据、kiro 的运行时依赖（fastapi/uvicorn/httpx/loguru/python-dotenv/tiktoken）、入口点 `kiro-gateway-launcher = kiro_gateway_launcher.cli:main`
2. **`config_loader.py`** — `ConfigLoader` 类：按优先级定位 `.env` 文件，解析 KEY=VALUE，注入 `os.environ`（不覆盖已有 key）；同时提供 `REPO_DIR` / `CONFIG_DIR` 路径常量
3. **`repo_manager.py`** — `RepoManager` 类：检查 `~/.local/share/kiro-gateway-launcher/repo/` 是否存在；不存在则 `git clone`；提供 `pull()` 方法用于更新；提供 `ensure_on_sys_path()` 将 repo 目录注入 `sys.path`
4. **`setup_wizard.py`** — `SetupWizard` 类：检测缺失凭证，运行交互式引导，写入 `~/.config/kiro-gateway/.env`；依赖 `ConfigLoader` 的路径常量
5. **`config_editor.py`** — `ConfigEditor` 类：只读显示当前配置（敏感值遮蔽）；`--edit` 触发重新运行 `SetupWizard`；`--reset` 删除配置文件；`--show-path` 打印路径
6. **`updater.py`** — `Updater` 类：通过 GitHub API 获取上游最新 commit SHA，与本地 repo 的 HEAD SHA 对比，若有更新则调用 `RepoManager.pull()`
7. **`cli.py`** — `main()` 入口：① `ConfigLoader.load()` 注入 env；② `RepoManager.ensure_on_sys_path()` 注入 kiro 源码路径；③ 解析参数；④ 分发到 wizard / server / config / update

## 功能流程图

### 1. 安装关系

```
用户执行：
uv tool install git+https://github.com/FightingLee97/kiro-gateway-launcher
                              │
                              ▼
         ~/.local/share/uv/tools/kiro-gateway-launcher/
         ├── bin/
         │   └── kiro-gateway-launcher          ← 命令入口
         └── lib/python3.12/site-packages/
             ├── kiro_gateway_launcher/          ← 我们的代码（已安装）
             ├── fastapi/                        ← kiro 运行时依赖（已安装）
             ├── uvicorn/
             ├── httpx/
             ├── loguru/
             └── ...

         注意：kiro/ 源码此时不存在，首次运行时才 clone
```

---

### 2. 启动流程（`kiro-gateway-launcher`）

```
用户输入命令
     │
     ▼
cli.py: main()
     │
     ├─ ① ConfigLoader.load()
     │       读取优先级（从低到高）：
     │       ~/.config/kiro-gateway/.env  →  ./.env  →  os.environ（已有不覆盖）
     │       → 写入 os.environ
     │
     ├─ ② RepoManager.ensure()
     │       REPO_DIR = ~/.local/share/kiro-gateway-launcher/repo/
     │       ┌─ 不存在 ──► git clone jwadow/kiro-gateway → REPO_DIR
     │       └─ 已存在 ──► 跳过 clone
     │       → sys.path.insert(0, REPO_DIR)   ← 此后 import kiro 可用
     │
     ├─ ③ 解析命令行参数
     │
     └─ ④ 分发命令
           │
           ├── config ──────────────────────────────────────────────────────┐
           │                                                                 │
           ├── update ──────────────────────────────────────────────────────┤
           │                                                                 │
           └── start（默认）                                                 │
                 │                                                           │
                 ▼                                                           │
           SetupWizard.needs_setup()?                                        │
           ┌─ True ──► SetupWizard.run()  ← 交互式引导，写 .env             │
           └─ False ──► 继续                                                 │
                 │                                                           │
                 ▼                                                           │
           延迟导入（此时 os.environ 和 sys.path 均已就绪）                  │
           import uvicorn                                                    │
           from kiro.app import app   ← kiro/config.py 在此读取 env         │
                 │                                                           │
                 ▼                                                           │
           uvicorn.run(app, host, port)                                      │
                 │                                                           │
                 ▼                                                           │
           kiro-gateway 服务运行                                             │
                 │                                                           │
                 ▼                                                           │
           Kiro / AWS CodeWhisperer ◄───────────────────────────────────────┘
```

---

### 3. 首次运行 Setup Wizard 流程

```
SetupWizard.run()
     │
     ▼
欢迎信息
     │
     ▼
自动检测已安装的凭证文件
  ├─ ~/.local/share/kiro-cli/data.sqlite3 存在？→ 提示可用
  └─ ~/kiro-credentials.json 存在？→ 提示可用
     │
     ▼
选择凭证类型（CredentialType）
  ├─ [1] JSON 文件      → JsonFileHandler.prompt()   → {KIRO_CREDS_FILE: path}
  ├─ [2] Refresh Token  → RefreshTokenHandler.prompt() → {REFRESH_TOKEN: token}
  └─ [3] SQLite DB      → SqliteDbHandler.prompt()   → {KIRO_CLI_DB_FILE: path}
     │
     ▼
设置 PROXY_API_KEY（显示默认值，回车跳过）
     │
     ▼
写入 ~/.config/kiro-gateway/.env
     │
     ▼
继续启动服务器
```

---

### 4. `update` 命令流程

```
kiro-gateway-launcher update
     │
     ▼
RepoManager.ensure()
  ├─ repo 不存在 ──► git clone（首次）
  └─ repo 已存在 ──► 跳过
     │
     ▼
Updater.run()
     │
     ├─ ① urllib.request → GitHub API
     │       GET /repos/jwadow/kiro-gateway/commits/main
     │       → remote_sha = "b9d1e44..."
     │
     ├─ ② RepoManager.head_sha()
     │       读取 REPO_DIR/.git/HEAD → ref → SHA
     │       → local_sha = "a3f8c21..."
     │
     └─ ③ 对比
           ┌─ 相同 ──► 打印 "已是最新版本 (a3f8c21)"，退出
           └─ 不同 ──► RepoManager.pull()
                           git pull（在 REPO_DIR 里）
                           → 打印 "更新完成：a3f8c21 → b9d1e44"
```

---

### 5. `config` 命令流程

```
kiro-gateway-launcher config [选项]
     │
     ├── （无选项）──► ConfigEditor.show()
     │                   读取 ~/.config/kiro-gateway/.env
     │                   打印所有 KEY=VALUE（敏感值遮蔽为 ****）
     │                   文件不存在时提示"尚未配置，运行 config --edit 开始配置"
     │
     ├── --edit ──────► SetupWizard.run()
     │                   重新运行完整 wizard 引导流程
     │                   覆盖写入 ~/.config/kiro-gateway/.env
     │
     ├── --show-path ──► ConfigEditor.show_path()
     │                   打印 ~/.config/kiro-gateway/.env
     │
     └── --reset ──► ConfigEditor.reset()
                         "确认删除配置？[y/N]"
                         ├─ y ──► 删除 .env
                         └─ N ──► 取消
```

---

### 6. 模块依赖关系

```
cli.py
  ├── ConfigLoader        （无外部依赖）
  ├── RepoManager         （依赖 subprocess/git，依赖 ConfigLoader 的路径常量）
  ├── SetupWizard         （依赖 WizardIO Protocol，依赖 ConfigLoader 路径常量）
  ├── ConfigEditor        （依赖 WizardIO Protocol，依赖 ConfigLoader 路径常量）
  └── Updater             （依赖 RepoManager，依赖 urllib.request）

WizardIO (Protocol)
  ├── ConsoleIO           （生产环境：input() + print()）
  └── MockIO              （测试环境：脚本化输入）

CredentialHandler (ABC)
  ├── JsonFileHandler
  ├── RefreshTokenHandler
  └── SqliteDbHandler
```

---

## Key Technical Points

### Config injection timing (critical)

`kiro-gateway`'s `config.py` binds environment variables at **module import time**. Therefore `ConfigLoader.load()` must be called and must have written all values into `os.environ` **before** any `import kiro.*` statement executes. In `cli.py`, the import of kiro modules is deferred inside the `start_server()` function body, never at the top of the file.

```python
# cli.py — correct pattern
from kiro_gateway_launcher.config_loader import ConfigLoader
from kiro_gateway_launcher.repo_manager import RepoManager

def main() -> None:
    ConfigLoader().load()          # ① 注入 env vars
    RepoManager().ensure()         # ② clone（首次）+ sys.path 注入
    args = _parse_args()
    if args.command == "start":
        _start_server(args)        # kiro 在此处才被 import

def _start_server(args: argparse.Namespace) -> None:
    import uvicorn                 # deferred import
    from kiro.app import app       # deferred import — env 和 sys.path 均已就绪
    uvicorn.run(app, host=args.host, port=args.port)
```

### ConfigLoader — priority chain

```
os.environ (already set)  →  highest priority, never overwrite
./.env (cwd)              →  second
~/.config/kiro-gateway/.env  →  lowest (user config)
```

Only keys **not already present** in `os.environ` are written. This preserves Docker/CI environment variables.

### SetupWizard — credential type dispatch (OCP)

Credential types are modelled as a `StrEnum`. Each type maps to a `CredentialHandler` abstract class. Adding a new credential type requires only a new subclass — no edits to wizard flow logic.

```python
class CredentialType(StrEnum):
    JSON_FILE = "json_file"
    REFRESH_TOKEN = "refresh_token"
    SQLITE_DB = "sqlite_db"

class CredentialHandler(ABC):
    @abstractmethod
    def prompt(self, io: WizardIO) -> dict[str, str]: ...

class JsonFileHandler(CredentialHandler): ...
class RefreshTokenHandler(CredentialHandler): ...
class SqliteDbHandler(CredentialHandler): ...
```

### WizardIO Protocol (DIP / testability)

Both `SetupWizard` and `ConfigEditor` accept a `WizardIO` protocol object for all user interaction. Tests inject a `MockIO` that replays scripted inputs without touching stdin/stdout.

```python
class WizardIO(Protocol):
    def prompt(self, message: str) -> str: ...
    def print(self, message: str) -> None: ...
```

### RepoManager — 运行时 clone 与 sys.path 注入

kiro-gateway 上游无 `pyproject.toml`，不能作为 Python 包安装。launcher 在首次运行时 clone 源码，之后通过 `sys.path` 注入使 `import kiro` 可用。

```
repo 存放位置：~/.local/share/kiro-gateway-launcher/repo/
```

```python
class RepoManager:
    UPSTREAM = "https://github.com/jwadow/kiro-gateway"
    REPO_DIR = Path.home() / ".local/share/kiro-gateway-launcher/repo"

    def ensure(self) -> None:
        """Clone if not present, then inject into sys.path."""
        if not self.REPO_DIR.exists():
            self._clone()
        self._inject_sys_path()

    def pull(self) -> str:
        """git pull, return new HEAD SHA."""
        ...

    def head_sha(self) -> str:
        """Read .git/refs/heads/main (or HEAD) for current SHA."""
        ...
```

`ensure()` 在 `cli.py` 的 `main()` 中、`ConfigLoader.load()` 之后、任何 `import kiro.*` 之前调用。

### Updater — git pull 更新

`update` 命令不再重装 launcher，而是直接 `git pull` 上游源码：

```python
class Updater:
    UPSTREAM_API = "https://api.github.com/repos/jwadow/kiro-gateway/commits/main"

    def run(self) -> None:
        remote_sha = self._fetch_remote_sha()   # GitHub API
        local_sha  = self._repo.head_sha()
        if remote_sha == local_sha:
            print("已是最新版本")
            return
        self._repo.pull()
        print(f"更新完成：{local_sha[:7]} → {remote_sha[:7]}")
```

若 repo 目录不存在（首次 update），先 clone 再报告。

### Error handling strategy

- `ConfigLoader`：静默跳过不存在的 `.env` 文件；文件存在但不可读时打印警告
- `RepoManager`：git 不在 PATH 时打印明确错误并 exit 1；clone 失败时打印错误并 exit 1；网络不通时给出可操作提示
- `SetupWizard`：`KeyboardInterrupt` 时打印友好中止信息并 exit 0
- `Updater`：网络失败时打印明确错误并 exit 1；不静默成功
- `cli.py`：捕获 `ImportError`（kiro import 失败）并打印提示（"请先运行 kiro-gateway-launcher update"）
- **F4 — 凭证无效提示**：`.env` 存在但无有效凭证时，打印明确错误并指向 `~/.config/kiro-gateway/.env`，不再提示 `cp .env.example .env`（对工具安装场景无意义）；提示用户运行 `kiro-gateway-launcher config --edit` 重新配置

## Out of Scope

- Modifying any file in `jwadow/kiro-gateway`
- Supporting Windows (path conventions follow XDG / POSIX)
- GUI or web-based configuration
- Multi-profile / workspace config management
- Automatic background update checks on server start
- Packaging to PyPI (distribution is via `uv tool install git+<url>` only)

---

## Design Compliance Review

**SOLID Principles:**
- [x] **SRP** — `ConfigLoader` loads env; `SetupWizard` guides first run; `ConfigEditor` edits config; `Updater` checks/applies updates; `cli.py` dispatches only
- [x] **OCP** — credential types extended via new `CredentialHandler` subclasses, no edits to wizard flow
- [x] **LSP** — `CredentialHandler` subclasses are fully substitutable; `WizardIO` implementors are fully substitutable
- [x] **ISP** — `WizardIO` protocol has only two methods (`prompt`, `print`); no unused methods forced on implementors
- [x] **DIP** — `SetupWizard` and `ConfigEditor` depend on `WizardIO` protocol, not on `input()`/`print()` directly

**Constitution:**
- [x] All design decisions comply with `init.md § Constitution`
- [x] No hardcoded secrets or environment-specific values
- [x] No duplication of kiro-gateway logic — we wrap, not copy
- [x] No `if/elif` chains for credential types — replaced with polymorphism
