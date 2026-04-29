"""Configuration editor for kiro-gateway-launcher.

Provides read-only display of the current configuration, path display,
and configuration reset. Editing is handled by re-running SetupWizard
via the --edit flag in cli.py.
"""

from pathlib import Path

from kiro_gateway_launcher.config_loader import USER_ENV
from kiro_gateway_launcher.setup_wizard import WizardIO, ConsoleIO


# Keys whose values are masked in display output
_SENSITIVE_PATTERNS: tuple[str, ...] = ("TOKEN", "KEY", "SECRET", "PASSWORD")


def _is_sensitive(key: str) -> bool:
    """Return True if the key name suggests a sensitive value.

    Args:
        key: The environment variable name to check.

    Returns:
        True when the key contains a known sensitive pattern.
    """
    upper = key.upper()
    return any(pattern in upper for pattern in _SENSITIVE_PATTERNS)


class ConfigEditor:
    """Read-only viewer and manager for the user configuration file.

    Responsibilities:
    - Display current config with sensitive values masked
    - Show the config file path
    - Reset (delete) the config file after confirmation

    Note: The --edit flow (re-running the wizard) is handled by cli.py
    calling SetupWizard.run() directly.
    """

    def __init__(self, io: WizardIO | None = None) -> None:
        """Initialise the editor with an optional IO interface.

        Args:
            io: IO interface for prompts and output. Defaults to ConsoleIO.
        """
        self._io = io or ConsoleIO()

    def show(self) -> None:
        """Display the current configuration with sensitive values masked.

        Reads USER_ENV and prints each KEY=VALUE pair. Values for keys
        containing TOKEN, KEY, SECRET, or PASSWORD are replaced with ****.
        Prints a friendly message if the file does not exist.
        """
        if not USER_ENV.exists():
            self._io.print(
                "No configuration found.\n"
                f"  Run 'kiro-gateway-launcher config --edit' to set up."
            )
            return

        try:
            text = USER_ENV.read_text(encoding="utf-8")
        except OSError as exc:
            self._io.print(f"[kiro-gateway-launcher] Warning: cannot read {USER_ENV}: {exc}")
            return

        self._io.print(f"Configuration ({USER_ENV}):\n")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            display_value = "****" if _is_sensitive(key) else value.strip()
            self._io.print(f"  {key}={display_value}")

    def show_path(self) -> None:
        """Print the absolute path to the user configuration file.

        Always prints the path regardless of whether the file exists.
        """
        self._io.print(str(USER_ENV.resolve()))

    def reset(self) -> None:
        """Delete the user configuration file after confirmation.

        Prompts the user to confirm before deleting. Does nothing if the
        user declines or the file does not exist.
        """
        if not USER_ENV.exists():
            self._io.print("No configuration file to reset.")
            return

        answer = self._io.prompt(f"Delete {USER_ENV}? [y/N]: ")
        if answer.strip().lower() == "y":
            USER_ENV.unlink()
            self._io.print("Configuration reset.")
        else:
            self._io.print("Reset cancelled.")
