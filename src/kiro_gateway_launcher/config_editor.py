"""Interactive configuration editor for kiro-gateway-launcher.

Presents all configurable variables as a numbered list grouped by category.
The user selects a variable by number, enters a new value, and the change
is written to ~/.config/kiro-gateway/.env immediately.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from kiro_gateway_launcher.config_loader import USER_ENV
from kiro_gateway_launcher.setup_wizard import WizardIO, ConsoleIO


# ---------------------------------------------------------------------------
# ANSI color codes
# ---------------------------------------------------------------------------

_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_WHITE = "\033[97m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ConfigVar:
    """A single configurable environment variable.

    Attributes:
        key: Environment variable name.
        description: Short human-readable description shown in the list.
        default: Default value used when the variable is not set.
        sensitive: If True, the value is partially masked in list view.
        allowed_values: Optional list of valid values shown as hint.
    """

    key: str
    description: str
    default: str = ""
    sensitive: bool = False
    allowed_values: list[str] = field(default_factory=list)


@dataclass
class ConfigGroup:
    """A named group of related ConfigVar entries.

    Attributes:
        name: Display name for the group header.
        vars: Ordered list of variables in this group.
    """

    name: str
    vars: list[ConfigVar]


# ---------------------------------------------------------------------------
# Variable definitions (all configurable variables, grouped)
# ---------------------------------------------------------------------------

CONFIG_GROUPS: list[ConfigGroup] = [
    ConfigGroup(
        name="Credentials",
        vars=[
            ConfigVar(
                key="REFRESH_TOKEN",
                description="Kiro refresh token (from IDE network traffic)",
                sensitive=True,
            ),
            ConfigVar(
                key="KIRO_CREDS_FILE",
                description="Path to Kiro credentials JSON file",
            ),
            ConfigVar(
                key="KIRO_CLI_DB_FILE",
                description="Path to kiro-cli SQLite database (AWS SSO)",
            ),
        ],
    ),
    ConfigGroup(
        name="Server",
        vars=[
            ConfigVar(
                key="PROXY_API_KEY",
                description="Client auth key (clients pass this as Bearer token)",
                default="my-super-secret-password-123",
                sensitive=True,
            ),
            ConfigVar(
                key="SERVER_HOST",
                description="Bind address",
                default="0.0.0.0",
            ),
            ConfigVar(
                key="SERVER_PORT",
                description="Server port",
                default="8001",
            ),
        ],
    ),
    ConfigGroup(
        name="Network",
        vars=[
            ConfigVar(
                key="VPN_PROXY_URL",
                description="Proxy for Kiro API (GFW / corporate networks)",
            ),
            ConfigVar(
                key="KIRO_REGION",
                description="AWS region",
                default="us-east-1",
            ),
            ConfigVar(
                key="KIRO_API_REGION",
                description="Kiro API region (if different from AWS region)",
            ),
            ConfigVar(
                key="PROFILE_ARN",
                description="AWS Profile ARN for per-account override",
            ),
        ],
    ),
    ConfigGroup(
        name="Advanced",
        vars=[
            ConfigVar(
                key="LOG_LEVEL",
                description="Log verbosity",
                default="INFO",
                allowed_values=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            ),
            ConfigVar(
                key="FIRST_TOKEN_TIMEOUT",
                description="Seconds to wait for first token before retry",
                default="15",
            ),
            ConfigVar(
                key="STREAMING_READ_TIMEOUT",
                description="Seconds to wait between chunks during streaming",
                default="300",
            ),
            ConfigVar(
                key="FIRST_TOKEN_MAX_RETRIES",
                description="Max retry attempts on first token timeout",
                default="3",
            ),
            ConfigVar(
                key="TRUNCATION_RECOVERY",
                description="Inject synthetic messages on API truncation",
                default="true",
                allowed_values=["true", "false"],
            ),
            ConfigVar(
                key="TOOL_DESCRIPTION_MAX_LENGTH",
                description="Max chars for tool descriptions (0 = disabled)",
                default="10000",
            ),
            ConfigVar(
                key="DEBUG_MODE",
                description="Save debug logs (off / errors / all)",
                default="off",
                allowed_values=["off", "errors", "all"],
            ),
            ConfigVar(
                key="DEBUG_DIR",
                description="Directory for debug log files",
                default="debug_logs",
            ),
            ConfigVar(
                key="FAKE_REASONING",
                description="Enable extended thinking via tag injection",
                default="true",
                allowed_values=["true", "false"],
            ),
            ConfigVar(
                key="FAKE_REASONING_MAX_TOKENS",
                description="Max thinking tokens",
                default="4000",
            ),
            ConfigVar(
                key="FAKE_REASONING_HANDLING",
                description="How to handle thinking blocks in responses",
                default="as_reasoning_content",
                allowed_values=["as_reasoning_content", "remove", "pass", "strip_tags"],
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Config file I/O helpers
# ---------------------------------------------------------------------------


def read_config_file(path: Path) -> dict[str, str]:
    """Read a .env file and return its key-value pairs.

    Handles KEY=value, KEY="value", and KEY='value' formats.
    Comments and blank lines are ignored.

    Args:
        path: Path to the .env file.

    Returns:
        Dict of variable names to raw string values.
        Empty dict if the file does not exist.
    """
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    pattern = r'^([A-Za-z_][A-Za-z0-9_]*)=(["\']?)(.+?)\2\s*$'

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(pattern, line)
        if match:
            result[match.group(1)] = match.group(3)

    return result


def write_config_file(path: Path, data: dict[str, str]) -> None:
    """Write key-value pairs to a .env file.

    Creates parent directories if needed. Writes KEY=value lines without
    quoting to avoid escape-sequence issues on Windows paths.

    Args:
        path: Destination .env file path.
        data: Mapping of variable names to values.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}\n" for k, v in data.items() if v]
    path.write_text("".join(lines), encoding="utf-8")


def update_config_value(path: Path, key: str, value: str) -> None:
    """Set a single variable in the .env file and update os.environ.

    Reads the existing file, updates or inserts the key, then writes back.
    If value is empty, the key is removed from the file.

    Args:
        path: Path to the .env file.
        key: Environment variable name.
        value: New value. Empty string removes the key.
    """
    data = read_config_file(path)
    if value:
        data[key] = value
        os.environ[key] = value
    else:
        data.pop(key, None)
        os.environ.pop(key, None)
    write_config_file(path, data)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _mask(value: str, sensitive: bool) -> str:
    """Return a display-safe version of a value.

    Args:
        value: The raw value string.
        sensitive: If True and value is long enough, mask most characters.

    Returns:
        Masked string like ``eyJhbGci****`` or the original value.
    """
    if sensitive and len(value) > 8:
        return value[:8] + "****"
    return value


def _effective_value(key: str, file_data: dict[str, str], default: str) -> str:
    """Return the currently active value for a variable.

    Priority: os.environ > config file > default.

    Args:
        key: Environment variable name.
        file_data: Values loaded from the config file.
        default: Fallback default value.

    Returns:
        The active value string, or empty string if not set anywhere.
    """
    return os.environ.get(key) or file_data.get(key) or default


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------


class ConfigEditor:
    """Interactive numbered-list configuration editor.

    Displays all configurable variables grouped by category. The user
    selects a variable by number, enters a new value, and the change is
    written to the config file immediately.

    Also provides show_path() and reset() for CLI subcommand dispatch.
    """

    def __init__(self, io: WizardIO | None = None) -> None:
        """Initialise the editor with an optional IO interface.

        Args:
            io: IO interface for prompts and output. Defaults to ConsoleIO.
        """
        self._io = io or ConsoleIO()
        # Build a flat index: display number → ConfigVar
        self._index: dict[int, ConfigVar] = {}
        n = 1
        for group in CONFIG_GROUPS:
            for var in group.vars:
                self._index[n] = var
                n += 1

    def show(self) -> None:
        """Run the interactive configuration editor loop.

        Displays the variable list, prompts for a selection, opens an
        inline edit prompt, writes the change, and repeats until the
        user quits.
        """
        while True:
            file_data = read_config_file(USER_ENV)
            self._print_list(file_data)

            raw = self._io.prompt(
                f"\n  {_CYAN}Enter number to edit, or q to quit{_RESET}"
            ).strip().lower()

            if raw in ("q", "quit", "exit", ""):
                self._io.print("")
                break

            if not raw.isdigit() or int(raw) not in self._index:
                self._io.print(f"  {_YELLOW}Invalid choice.{_RESET}")
                continue

            var = self._index[int(raw)]
            self._edit_var(var, file_data)

    def show_path(self) -> None:
        """Print the absolute path to the user configuration file."""
        self._io.print(str(USER_ENV.resolve()))

    def reset(self) -> None:
        """Delete the user configuration file after confirmation.

        Prompts the user to confirm before deleting. Does nothing if the
        user declines or the file does not exist.
        """
        if not USER_ENV.exists():
            self._io.print("No configuration file to reset.")
            return

        if self._io.confirm(f"Delete {USER_ENV}?"):
            USER_ENV.unlink()
            self._io.print("Configuration reset.")
        else:
            self._io.print("Reset cancelled.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _print_list(self, file_data: dict[str, str]) -> None:
        """Print the full variable list grouped by category.

        Args:
            file_data: Current values from the config file.
        """
        self._io.print("")
        self._io.print(f"  {_BOLD}{_WHITE}Kiro Gateway — Configuration{_RESET}")
        self._io.print(f"  {_DIM}{'─' * 50}{_RESET}")
        if USER_ENV.exists():
            self._io.print(f"  {_DIM}Config: {USER_ENV}{_RESET}")
        else:
            self._io.print(f"  {_YELLOW}Config file not yet created: {USER_ENV}{_RESET}")
        self._io.print("")

        n = 1
        for group in CONFIG_GROUPS:
            self._io.print(f"  {_WHITE}{_BOLD}{group.name}{_RESET}")
            for var in group.vars:
                val = _effective_value(var.key, file_data, var.default)
                display = _mask(val, var.sensitive) if val else f"{_DIM}(not set){_RESET}"
                hint = f"  {_DIM}{var.description}{_RESET}"
                self._io.print(f"  {_DIM}[{n:2d}]{_RESET} {_CYAN}{var.key:<32}{_RESET} {display}")
                self._io.print(f"        {hint}")
                n += 1
            self._io.print("")

    def _edit_var(self, var: ConfigVar, file_data: dict[str, str]) -> None:
        """Prompt the user to enter a new value for a variable.

        Shows the current value, allowed values (if any), and writes the
        new value to the config file immediately on confirmation.

        Args:
            var: The ConfigVar to edit.
            file_data: Current values from the config file.
        """
        current = _effective_value(var.key, file_data, var.default)

        self._io.print("")
        self._io.print(f"  {_BOLD}{_WHITE}{var.key}{_RESET}  {_DIM}— {var.description}{_RESET}")
        if current:
            display = _mask(current, var.sensitive)
            self._io.print(f"  Current: {_GREEN}{display}{_RESET}")
        else:
            self._io.print(f"  Current: {_DIM}(not set){_RESET}")

        if var.allowed_values:
            opts = " / ".join(var.allowed_values)
            self._io.print(f"  Allowed: {_DIM}{opts}{_RESET}")

        if var.default:
            self._io.print(f"  Default: {_DIM}{var.default}{_RESET}")

        self._io.print(f"  {_DIM}(Enter to keep current, '-' to clear){_RESET}")

        new_val = self._io.prompt(f"  {_CYAN}New value{_RESET}").strip()

        if new_val == "":
            self._io.print(f"  {_DIM}Unchanged.{_RESET}")
            return

        if new_val == "-":
            update_config_value(USER_ENV, var.key, "")
            self._io.print(f"  {_GREEN}Cleared.{_RESET}")
            return

        if var.allowed_values and new_val not in var.allowed_values:
            self._io.print(
                f"  {_YELLOW}Invalid value. Allowed: {', '.join(var.allowed_values)}{_RESET}"
            )
            return

        update_config_value(USER_ENV, var.key, new_val)
        self._io.print(f"  {_GREEN}Saved.{_RESET}")
