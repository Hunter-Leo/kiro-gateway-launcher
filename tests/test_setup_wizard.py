"""Unit tests for SetupWizard."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import kiro_gateway_launcher.setup_wizard as sw_module
from kiro_gateway_launcher.setup_wizard import (
    CredentialType,
    JsonFileHandler,
    RefreshTokenHandler,
    SetupWizard,
    SqliteDbHandler,
)


class MockIO:
    """Test WizardIO that replays scripted inputs."""

    def __init__(self, inputs: list[str]) -> None:
        self._inputs = list(inputs)
        self.printed: list[str] = []

    def prompt(self, message: str) -> str:
        return self._inputs.pop(0) if self._inputs else ""

    def print(self, message: str) -> None:
        self.printed.append(message)


class TestNeedsSetup:
    """Tests for SetupWizard.needs_setup()."""

    def test_returns_true_when_no_user_env(self, tmp_path: Path) -> None:
        """needs_setup() is True when USER_ENV does not exist."""
        missing = tmp_path / ".env"
        with patch.object(sw_module, "USER_ENV", missing):
            assert SetupWizard().needs_setup() is True

    def test_returns_false_when_refresh_token_present(self, tmp_path: Path) -> None:
        """needs_setup() is False when REFRESH_TOKEN is in USER_ENV."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=abc123\n")
        with patch.object(sw_module, "USER_ENV", env_file):
            assert SetupWizard().needs_setup() is False

    def test_returns_false_when_kiro_creds_file_present(self, tmp_path: Path) -> None:
        """needs_setup() is False when KIRO_CREDS_FILE is in USER_ENV."""
        env_file = tmp_path / ".env"
        env_file.write_text("KIRO_CREDS_FILE=/path/to/creds.json\n")
        with patch.object(sw_module, "USER_ENV", env_file):
            assert SetupWizard().needs_setup() is False

    def test_returns_false_when_sqlite_db_present(self, tmp_path: Path) -> None:
        """needs_setup() is False when KIRO_CLI_DB_FILE is in USER_ENV."""
        env_file = tmp_path / ".env"
        env_file.write_text("KIRO_CLI_DB_FILE=~/.local/share/kiro-cli/data.sqlite3\n")
        with patch.object(sw_module, "USER_ENV", env_file):
            assert SetupWizard().needs_setup() is False

    def test_returns_true_when_env_has_no_credential_keys(self, tmp_path: Path) -> None:
        """needs_setup() is True when USER_ENV exists but has no credential keys."""
        env_file = tmp_path / ".env"
        env_file.write_text("PROXY_API_KEY=secret\n")
        with patch.object(sw_module, "USER_ENV", env_file):
            assert SetupWizard().needs_setup() is True


class TestWizardRun:
    """Tests for SetupWizard.run() full flow."""

    def test_json_file_flow_writes_correct_env(self, tmp_path: Path) -> None:
        """Selecting JSON file writes KIRO_CREDS_FILE and PROXY_API_KEY."""
        env_file = tmp_path / ".env"
        config_dir = tmp_path

        # Inputs: credential type=1 (JSON), path, proxy key
        io = MockIO(["1", "/path/to/creds.json", "my-secret"])

        with patch.object(sw_module, "USER_ENV", env_file):
            with patch.object(sw_module, "CONFIG_DIR", config_dir):
                SetupWizard(io=io).run()

        content = env_file.read_text()
        assert "KIRO_CREDS_FILE=/path/to/creds.json" in content
        assert "PROXY_API_KEY=my-secret" in content

    def test_refresh_token_flow_writes_correct_env(self, tmp_path: Path) -> None:
        """Selecting refresh token writes REFRESH_TOKEN and PROXY_API_KEY."""
        env_file = tmp_path / ".env"
        config_dir = tmp_path

        io = MockIO(["2", "my-refresh-token", ""])

        with patch.object(sw_module, "USER_ENV", env_file):
            with patch.object(sw_module, "CONFIG_DIR", config_dir):
                SetupWizard(io=io).run()

        content = env_file.read_text()
        assert "REFRESH_TOKEN=my-refresh-token" in content
        assert "PROXY_API_KEY=change-me-please" in content  # default used

    def test_sqlite_db_flow_uses_default_path(self, tmp_path: Path) -> None:
        """Pressing enter for SQLite path uses the default path."""
        env_file = tmp_path / ".env"
        config_dir = tmp_path

        io = MockIO(["3", "", ""])  # type 3, empty path (use default), empty proxy key

        with patch.object(sw_module, "USER_ENV", env_file):
            with patch.object(sw_module, "CONFIG_DIR", config_dir):
                SetupWizard(io=io).run()

        content = env_file.read_text()
        assert "KIRO_CLI_DB_FILE=~/.local/share/kiro-cli/data.sqlite3" in content

    def test_invalid_choice_defaults_to_first_option(self, tmp_path: Path) -> None:
        """An invalid menu choice defaults to option 1 (JSON file)."""
        env_file = tmp_path / ".env"
        config_dir = tmp_path

        io = MockIO(["99", "/some/path.json", ""])

        with patch.object(sw_module, "USER_ENV", env_file):
            with patch.object(sw_module, "CONFIG_DIR", config_dir):
                SetupWizard(io=io).run()

        content = env_file.read_text()
        assert "KIRO_CREDS_FILE=/some/path.json" in content

    def test_keyboard_interrupt_exits_zero(self, tmp_path: Path) -> None:
        """KeyboardInterrupt during wizard exits with code 0."""

        class InterruptIO:
            def prompt(self, message: str) -> str:
                raise KeyboardInterrupt

            def print(self, message: str) -> None:
                pass

        with pytest.raises(SystemExit) as exc_info:
            SetupWizard(io=InterruptIO()).run()

        assert exc_info.value.code == 0


class TestCredentialHandlers:
    """Tests for individual CredentialHandler subclasses."""

    def test_json_file_handler_returns_correct_key(self) -> None:
        """JsonFileHandler returns KIRO_CREDS_FILE."""
        io = MockIO(["/path/to/file.json"])
        result = JsonFileHandler().prompt(io)
        assert result == {"KIRO_CREDS_FILE": "/path/to/file.json"}

    def test_refresh_token_handler_returns_correct_key(self) -> None:
        """RefreshTokenHandler returns REFRESH_TOKEN."""
        io = MockIO(["my-token"])
        result = RefreshTokenHandler().prompt(io)
        assert result == {"REFRESH_TOKEN": "my-token"}

    def test_sqlite_handler_uses_default_on_empty_input(self) -> None:
        """SqliteDbHandler uses default path when input is empty."""
        io = MockIO([""])
        result = SqliteDbHandler().prompt(io)
        assert result == {"KIRO_CLI_DB_FILE": "~/.local/share/kiro-cli/data.sqlite3"}

    def test_sqlite_handler_uses_provided_path(self) -> None:
        """SqliteDbHandler uses the provided path when given."""
        io = MockIO(["/custom/path.sqlite3"])
        result = SqliteDbHandler().prompt(io)
        assert result == {"KIRO_CLI_DB_FILE": "/custom/path.sqlite3"}
