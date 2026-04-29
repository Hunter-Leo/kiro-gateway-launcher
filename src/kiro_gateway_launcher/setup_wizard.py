"""Setup wizard for kiro-gateway-launcher.

Guides the user through first-run credential configuration and writes
the result to ~/.config/kiro-gateway/.env.

Design uses the Open/Closed Principle: adding a new credential type
requires only a new CredentialHandler subclass — the wizard flow itself
is never modified.
"""

import os
import sys
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from kiro_gateway_launcher.config_loader import CONFIG_DIR, USER_ENV


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

_DEFAULT_PROXY_API_KEY = "my-super-secret-password-123"

# Known SQLite database paths to probe during auto-detection.
_CLI_DB_CANDIDATES: list[tuple[Path, str]] = [
    (
        Path.home() / ".local" / "share" / "kiro-cli" / "data.sqlite3",
        "kiro-cli (Linux/macOS)",
    ),
    (
        Path.home() / ".local" / "share" / "amazon-q" / "data.sqlite3",
        "amazon-q-developer-cli (Linux/macOS)",
    ),
    (
        Path.home() / "Library" / "Application Support" / "kiro-cli" / "data.sqlite3",
        "kiro-cli (macOS)",
    ),
]


class WizardIO(Protocol):
    """Abstract IO interface for the setup wizard and config editor.

    Injecting this protocol enables tests to replay scripted inputs
    without touching stdin or stdout.
    """

    def prompt(self, message: str, default: str = "") -> str:
        """Display a prompt and return the user's input.

        Args:
            message: The prompt text to display.
            default: Value returned when the user presses Enter without input.

        Returns:
            The string entered by the user, or default if empty.
        """
        ...

    def confirm(self, message: str) -> bool:
        """Ask a yes/no question and return the boolean answer.

        Args:
            message: The question text shown to the user.

        Returns:
            True if the user confirms, False otherwise.
        """
        ...

    def print(self, message: str) -> None:
        """Display a message to the user.

        Args:
            message: The text to display.
        """
        ...


class ConsoleIO:
    """Production WizardIO implementation using stdin/stdout."""

    def prompt(self, message: str, default: str = "") -> str:
        """Prompt the user via input().

        Args:
            message: The prompt text.
            default: Value returned when the user presses Enter without input.

        Returns:
            The stripped user input, or default if empty.
        """
        hint = f" [{default}]" if default else ""
        raw = input(f"{message}{hint}: ").strip()
        return raw if raw else default

    def confirm(self, message: str) -> bool:
        """Ask a yes/no question.

        Args:
            message: The question text.

        Returns:
            True if the user answers 'y' or 'yes'.
        """
        raw = input(f"{message} [y/N]: ").strip().lower()
        return raw in ("y", "yes")

    def print(self, message: str) -> None:
        """Print a message to stdout.

        Args:
            message: The text to display.
        """
        print(message)


class CredentialType(StrEnum):
    """Supported credential types for kiro-gateway authentication."""

    JSON_FILE = "json_file"
    REFRESH_TOKEN = "refresh_token"
    SQLITE_DB = "sqlite_db"


class CredentialHandler(ABC):
    """Abstract base for credential-type-specific prompt logic.

    Each subclass handles one CredentialType. Adding a new type requires
    only a new subclass — the wizard dispatch loop is unchanged.
    """

    @abstractmethod
    def prompt(self, io: WizardIO) -> dict[str, str]:
        """Prompt the user for credential values.

        Args:
            io: The IO interface to use for prompts and output.

        Returns:
            A dict of environment variable name → value pairs to write
            into the .env file.
        """
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-readable label shown in the credential type menu.

        Returns:
            A short descriptive string.
        """
        ...


class JsonFileHandler(CredentialHandler):
    """Handles JSON credentials file path input."""

    @property
    def label(self) -> str:
        """Return the menu label for this handler."""
        return "JSON credentials file (KIRO_CREDS_FILE)"

    def prompt(self, io: WizardIO) -> dict[str, str]:
        """Prompt for the path to a Kiro JSON credentials file.

        Args:
            io: The IO interface.

        Returns:
            Dict with KIRO_CREDS_FILE set to the provided path.
        """
        path = io.prompt(f"{_CYAN}  Path to JSON credentials file{_RESET}")
        return {"KIRO_CREDS_FILE": path}


class RefreshTokenHandler(CredentialHandler):
    """Handles refresh token input."""

    @property
    def label(self) -> str:
        """Return the menu label for this handler."""
        return "Refresh token (REFRESH_TOKEN)"

    def prompt(self, io: WizardIO) -> dict[str, str]:
        """Prompt for a Kiro refresh token.

        Args:
            io: The IO interface.

        Returns:
            Dict with REFRESH_TOKEN set to the provided value.
        """
        token = io.prompt(f"{_CYAN}  Refresh token (from Kiro IDE network traffic){_RESET}")
        return {"REFRESH_TOKEN": token}


class SqliteDbHandler(CredentialHandler):
    """Handles kiro-cli SQLite database path input."""

    _DEFAULT_PATH: str = "~/.local/share/kiro-cli/data.sqlite3"

    @property
    def label(self) -> str:
        """Return the menu label for this handler."""
        return "kiro-cli SQLite database (KIRO_CLI_DB_FILE)"

    def prompt(self, io: WizardIO) -> dict[str, str]:
        """Prompt for the kiro-cli SQLite database path.

        Args:
            io: The IO interface.

        Returns:
            Dict with KIRO_CLI_DB_FILE set to the provided or default path.
        """
        path = io.prompt(
            f"{_CYAN}  Path to kiro-cli SQLite database{_RESET}",
            default=self._DEFAULT_PATH,
        )
        return {"KIRO_CLI_DB_FILE": path or self._DEFAULT_PATH}


# Registry maps CredentialType to its handler — extend here for new types
_HANDLERS: dict[CredentialType, CredentialHandler] = {
    CredentialType.JSON_FILE: JsonFileHandler(),
    CredentialType.REFRESH_TOKEN: RefreshTokenHandler(),
    CredentialType.SQLITE_DB: SqliteDbHandler(),
}

_CREDENTIAL_KEYS: frozenset[str] = frozenset(
    {"REFRESH_TOKEN", "KIRO_CREDS_FILE", "KIRO_CLI_DB_FILE"}
)


def detect_credentials() -> list[tuple[Path, str]]:
    """Scan well-known paths for installed Kiro credential sources.

    Checks each candidate path in _CLI_DB_CANDIDATES and returns
    a list of (path, label) tuples for those that exist on disk.

    Returns:
        List of (path, label) tuples for each found source.
        Empty list if nothing is found.
    """
    return [(path, label) for path, label in _CLI_DB_CANDIDATES if path.exists()]


class SetupWizard:
    """Interactive first-run configuration wizard.

    Guides the user through selecting a credential type, entering values,
    and optionally setting PROXY_API_KEY. Writes the result to USER_ENV.

    Auto-detects installed kiro-cli / amazon-q SQLite databases and offers
    to use them before falling back to manual credential selection.
    """

    def __init__(self, io: WizardIO | None = None) -> None:
        """Initialise the wizard with an optional IO interface.

        Args:
            io: IO interface for prompts and output. Defaults to ConsoleIO.
        """
        self._io = io or ConsoleIO()

    def needs_setup(self) -> bool:
        """Return True if no credential configuration is present.

        Checks USER_ENV for any of the known credential keys. If none are
        found, the wizard should be run before starting the server.

        Returns:
            True when setup is required, False when credentials exist.
        """
        if not USER_ENV.exists():
            return True
        try:
            text = USER_ENV.read_text(encoding="utf-8")
        except OSError:
            return True
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key in _CREDENTIAL_KEYS:
                return False
        return True

    def run(self) -> None:
        """Run the interactive setup wizard.

        Guides the user through credential selection, prompts for values,
        optionally sets PROXY_API_KEY, and writes ~/.config/kiro-gateway/.env.

        Raises:
            SystemExit: With code 0 if the user presses Ctrl-C.
        """
        try:
            self._run_wizard()
        except KeyboardInterrupt:
            self._io.print("\n\n[kiro-gateway-launcher] Setup cancelled. Run again to configure.")
            sys.exit(0)

    def _run_wizard(self) -> None:
        """Internal wizard flow (separated to allow KeyboardInterrupt wrapping)."""
        self._io.print(f"\n  {_BOLD}{_WHITE}👻 Kiro Gateway — First-time Setup{_RESET}")
        self._io.print(f"  {_DIM}{'─' * 44}{_RESET}")
        self._io.print(f"  {_YELLOW}No credentials found. Let's set them up.{_RESET}\n")

        config: dict[str, str] = {}

        # Try auto-detection first
        detected = detect_credentials()
        if detected:
            chosen = self._ask_use_detected(detected)
            if chosen is not None:
                config["KIRO_CLI_DB_FILE"] = str(chosen[0])
                proxy_key = self._io.prompt(
                    f"{_CYAN}  Proxy API key (clients use this to authenticate){_RESET}",
                    default=_DEFAULT_PROXY_API_KEY,
                )
                config["PROXY_API_KEY"] = proxy_key
                self._write_env(config)
                self._io.print(f"\n{_GREEN}  Configuration saved to {USER_ENV}{_RESET}")
                self._io.print("  Starting server...\n")
                return

        # Manual credential selection
        env_vars = self._ask_credential_type_and_prompt()
        proxy_key = self._io.prompt(
            f"{_CYAN}  Proxy API key (clients use this to authenticate){_RESET}",
            default=_DEFAULT_PROXY_API_KEY,
        )
        env_vars["PROXY_API_KEY"] = proxy_key
        self._write_env(env_vars)
        self._io.print(f"\n{_GREEN}  Configuration saved to {USER_ENV}{_RESET}")
        self._io.print("  Starting server...\n")

    def _ask_use_detected(
        self, detected: list[tuple[Path, str]]
    ) -> tuple[Path, str] | None:
        """Prompt the user to use an auto-detected credential source.

        Args:
            detected: Non-empty list of (path, label) tuples.

        Returns:
            The chosen (path, label) tuple, or None if the user declined.
        """
        if len(detected) == 1:
            path, label = detected[0]
            self._io.print(f"  {_GREEN}Found:{_RESET} {label}")
            self._io.print(f"  {_DIM}{path}{_RESET}\n")
            if self._io.confirm(f"  {_CYAN}Use this credential source?{_RESET}"):
                return detected[0]
            return None

        self._io.print(f"  {_GREEN}Found {len(detected)} credential sources:{_RESET}")
        for i, (path, label) in enumerate(detected, start=1):
            self._io.print(f"  {_DIM}{i}){_RESET} {label}")
            self._io.print(f"     {_DIM}{path}{_RESET}")
        self._io.print(f"  {_DIM}0){_RESET} Enter manually\n")

        while True:
            raw = self._io.prompt(
                f"  {_CYAN}Select (0-{len(detected)}){_RESET}"
            ).strip()
            if raw == "0":
                return None
            if raw.isdigit() and 1 <= int(raw) <= len(detected):
                return detected[int(raw) - 1]
            self._io.print(f"  {_YELLOW}Invalid choice. Enter 0–{len(detected)}.{_RESET}")

    def _ask_credential_type_and_prompt(self) -> dict[str, str]:
        """Show credential type menu and prompt for the chosen type's values.

        Returns:
            Dict of env var name → value for the selected credential type.
        """
        self._io.print(f"  {_WHITE}Choose your credential source:{_RESET}")
        types = list(CredentialType)
        for i, ctype in enumerate(types, start=1):
            self._io.print(f"  {_DIM}{i}){_RESET} {_HANDLERS[ctype].label}")
        self._io.print("")

        while True:
            raw = self._io.prompt(
                f"  {_CYAN}Enter choice (1-{len(types)}){_RESET}"
            ).strip()
            if raw.isdigit() and 1 <= int(raw) <= len(types):
                selected = types[int(raw) - 1]
                return _HANDLERS[selected].prompt(self._io)
            self._io.print(f"  {_YELLOW}Invalid choice. Enter 1–{len(types)}.{_RESET}")

    def _write_env(self, env_vars: dict[str, str]) -> None:
        """Write env_vars to USER_ENV, creating the directory if needed.

        Also updates os.environ so the current process can use the new
        values immediately without a restart.

        Args:
            env_vars: Mapping of KEY → value to write.
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={v}\n" for k, v in env_vars.items()]
        USER_ENV.write_text("".join(lines), encoding="utf-8")
        for k, v in env_vars.items():
            os.environ[k] = v
