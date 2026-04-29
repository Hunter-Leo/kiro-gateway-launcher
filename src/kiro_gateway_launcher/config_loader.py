"""Configuration loader for kiro-gateway-launcher.

Loads .env files in priority order and injects values into os.environ
before any kiro module is imported.

Priority (highest to lowest):
    1. os.environ (already set — never overwritten)
    2. ./.env (current working directory)
    3. ~/.config/kiro-gateway/.env (user config)
"""

import os
from pathlib import Path


CONFIG_DIR: Path = Path.home() / ".config" / "kiro-gateway"
USER_ENV: Path = CONFIG_DIR / ".env"


class ConfigLoader:
    """Loads .env files and injects values into os.environ.

    Values already present in os.environ are never overwritten, which
    preserves Docker/CI environment variables set by the caller.
    """

    def load(self) -> None:
        """Load all .env sources in priority order into os.environ.

        Sources are loaded from lowest to highest priority so that
        higher-priority sources win when the same key appears in multiple files.
        """
        # Load highest priority first; _load_file skips keys already in os.environ,
        # so lower-priority sources cannot overwrite what higher-priority sources set.
        self._load_file(Path.cwd() / ".env")
        self._load_file(USER_ENV)
        # os.environ is already in place — nothing to do for the highest tier

    def _load_file(self, path: Path) -> None:
        """Parse a .env file and inject its values into os.environ.

        Args:
            path: Path to the .env file to load.

        Notes:
            Missing files are silently skipped.
            Unreadable files emit a warning but do not raise.
            Keys already present in os.environ are not overwritten.
        """
        if not path.exists():
            return
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[kiro-gateway-launcher] Warning: cannot read {path}: {exc}")
            return

        for line in text.splitlines():
            line = line.strip()
            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            # Split on the first '=' only so values may contain '='
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            # Never overwrite an existing environment variable
            if key not in os.environ:
                os.environ[key] = value
