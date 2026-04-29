"""Setup wizard for kiro-gateway-launcher.

Guides the user through first-run credential configuration and writes
the result to ~/.config/kiro-gateway/.env.

Design uses the Open/Closed Principle: adding a new credential type
requires only a new CredentialHandler subclass — the wizard flow itself
is never modified.
"""

import sys
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from kiro_gateway_launcher.config_loader import CONFIG_DIR, USER_ENV


class WizardIO(Protocol):
    """Abstract IO interface for the setup wizard and config editor.

    Injecting this protocol enables tests to replay scripted inputs
    without touching stdin or stdout.
    """

    def prompt(self, message: str) -> str:
        """Display a prompt and return the user's input.

        Args:
            message: The prompt text to display.

        Returns:
            The string entered by the user.
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

    def prompt(self, message: str) -> str:
        """Prompt the user via input().

        Args:
            message: The prompt text.

        Returns:
            The stripped user input.
        """
        return input(message).strip()

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
        path = io.prompt("  Path to JSON credentials file: ")
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
        token = io.prompt("  Refresh token: ")
        return {"REFRESH_TOKEN": token}


class SqliteDbHandler(CredentialHandler):
    """Handles kiro-cli SQLite database path input."""

    _DEFAULT_PATH: str = "~/.local/share/kiro-cli/data.sqlite3"

    @property
    def label(self) -> str:
        """Return the menu label for this handler."""
        return f"kiro-cli SQLite database (KIRO_CLI_DB_FILE) [default: {self._DEFAULT_PATH}]"

    def prompt(self, io: WizardIO) -> dict[str, str]:
        """Prompt for the kiro-cli SQLite database path.

        Args:
            io: The IO interface.

        Returns:
            Dict with KIRO_CLI_DB_FILE set to the provided or default path.
        """
        path = io.prompt(f"  SQLite DB path [{self._DEFAULT_PATH}]: ")
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


class SetupWizard:
    """Interactive first-run configuration wizard.

    Guides the user through selecting a credential type, entering values,
    and optionally setting PROXY_API_KEY. Writes the result to USER_ENV.
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
        self._io.print("\n=== kiro-gateway-launcher: First-Run Setup ===\n")
        self._io.print("No credentials found. Let's configure kiro-gateway.\n")

        # Show credential type menu
        types = list(CredentialType)
        for i, ctype in enumerate(types, start=1):
            handler = _HANDLERS[ctype]
            self._io.print(f"  [{i}] {handler.label}")

        choice_str = self._io.prompt("\nSelect credential type [1]: ")
        choice = int(choice_str) if choice_str.isdigit() else 1
        if not 1 <= choice <= len(types):
            choice = 1

        selected_type = types[choice - 1]
        handler = _HANDLERS[selected_type]
        env_vars = handler.prompt(self._io)

        # Optional PROXY_API_KEY
        default_key = "change-me-please"
        proxy_key = self._io.prompt(f"\nPROXY_API_KEY [{default_key}]: ")
        env_vars["PROXY_API_KEY"] = proxy_key or default_key

        self._write_env(env_vars)
        self._io.print(f"\n✓ Configuration saved to {USER_ENV}")
        self._io.print("  Starting server...\n")

    def _write_env(self, env_vars: dict[str, str]) -> None:
        """Write env_vars to USER_ENV, creating the directory if needed.

        Args:
            env_vars: Mapping of KEY → value to write.
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={v}\n" for k, v in env_vars.items()]
        USER_ENV.write_text("".join(lines), encoding="utf-8")
