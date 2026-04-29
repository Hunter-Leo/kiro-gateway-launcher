# Start and Resume Guide — 001-kiro-gateway-launcher

## Quick Start
1. Read `init.md` — requirement scope
2. Read `plan.md` — technical approach
3. Read `tasks.md` — find the next `not-started` task
4. Review the standards sections below before writing any code

## Resuming After Interruption
1. Open `tasks.md` and find the first task not in `done`
2. If a task is `in-progress`, read its Notes for context before continuing
3. If a task is `blocked`, read the Notes and address the blocker first
4. Review the standards sections below before continuing

## Key Documents
- Requirement: `.dev/001-kiro-gateway-launcher/init.md`
- Plan: `.dev/001-kiro-gateway-launcher/generated/plan.md`
- Tasks: `.dev/001-kiro-gateway-launcher/generated/tasks.md`

---

## Constitution

### OOP & SOLID

- **单一职责**：`setup_wizard.py` 只负责交互引导；`config_loader.py` 只负责配置加载；`config_editor.py` 只负责配置编辑；`cli.py` 只负责命令解析与分发；`updater.py` 只负责版本检查与更新；`repo_manager.py` 只负责 clone/pull/sys.path 注入
- **开闭原则**：凭证类型使用 `StrEnum`，新增类型只需扩展枚举和添加新 `CredentialHandler` 子类，不修改现有逻辑
- **依赖倒置**：wizard 和 editor 依赖抽象 `WizardIO` Protocol，便于测试注入 mock

### Python 编码标准

- 所有函数参数和返回值必须有类型注解
- 每个文件、公共类、公共函数必须有 docstring（Google Style）
- 使用 `StrEnum` 表示固定选项（凭证类型）
- 使用 `pathlib.Path` 处理所有路径操作
- 错误处理：明确捕获，给出可操作的错误信息
- 不硬编码 secrets，使用环境变量

### 测试标准

- 测试文件命名：`test_*.py`，放在 `tests/` 目录
- 覆盖：正常流程、边界情况、异常情况
- Wizard / Editor 测试使用 `unittest.mock.patch` mock `input()`
- 核心逻辑覆盖率 ≥ 80%
- 使用 `pytest`

---

## OOP & SOLID Principles (applicable rules)

### Single Responsibility Principle
Each module has exactly one reason to change. If you need "and" to describe what a module does, split it.

### Open/Closed Principle ⭐
Credential types are extended by adding a new `CredentialHandler` subclass — never by editing the wizard flow. No `if/elif` chains for credential type dispatch.

```python
# Bad: must edit this for every new credential type
def handle_credential(type: str) -> dict:
    if type == "json_file": ...
    elif type == "refresh_token": ...

# Good: extend by adding a new subclass
class CredentialHandler(ABC):
    @abstractmethod
    def prompt(self, io: WizardIO) -> dict[str, str]: ...

class JsonFileHandler(CredentialHandler): ...
class RefreshTokenHandler(CredentialHandler): ...
```

### Dependency Inversion Principle
`SetupWizard` and `ConfigEditor` depend on the `WizardIO` Protocol, not on `input()`/`print()` directly. This enables test injection without touching stdin/stdout.

```python
class WizardIO(Protocol):
    def prompt(self, message: str) -> str: ...
    def print(self, message: str) -> None: ...
```

---

## Coding Standards (Python)

### Type Annotations
All function parameters and return values must be annotated. No untyped signatures.

### Documentation (Google Style)
Every file must have a module-level docstring. Every class must have a class-level docstring. Every public function must have a full docstring with `Args`, `Returns`, and `Raises`.

### Paths
Use `pathlib.Path` for all path operations. Never use string concatenation for paths.

### Error Handling
- Handle errors explicitly — never silently swallow exceptions
- Error messages must be actionable (tell the user what to do next)
- `sys.exit(1)` for unrecoverable errors; `sys.exit(0)` for user-initiated abort

### Critical: Deferred Imports
All `import kiro.*` statements must be inside function bodies, never at module top-level. `ConfigLoader.load()` and `RepoManager.ensure()` must complete before any kiro import executes.

```python
# Bad
import kiro.app  # top-level — config.py runs before env is set

# Good
def _start_server(args: argparse.Namespace) -> None:
    import kiro.app  # deferred — env and sys.path already set
```

### No New Dependencies
Use only stdlib for: HTTP requests (`urllib.request`), .env parsing (custom), interactive IO (`input()`). Do not add packages beyond what is declared in `pyproject.toml`.

### Testing
- Test file naming: `test_*.py` in `tests/`
- Cover: normal cases, edge cases, error/exception cases
- Mock `subprocess.run` for git operations; mock `urllib.request.urlopen` for network calls
- Mock `input()` via `WizardIO` protocol injection (not `unittest.mock.patch('builtins.input')`)
- Minimum coverage for core logic: 80%

---

## Git Workflow

Branch: `feat/001-kiro-gateway-launcher`

Commit format:
```
[001] T-XXX <type>: <imperative summary ≤ 72 chars>
```

Types: `feat` · `fix` · `refactor` · `test` · `docs` · `chore`

Examples:
```
[001] T-001 chore: configure pyproject.toml with kiro runtime deps
[001] T-002 feat: implement ConfigLoader with priority env injection
[001] T-003 test: add unit tests for ConfigLoader
```

One commit per task. Commit only after the task's tests pass.
