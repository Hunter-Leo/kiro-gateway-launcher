"""Unit tests for ConfigEditor."""

from pathlib import Path
from unittest.mock import patch

import pytest

import kiro_gateway_launcher.config_editor as ce_module
from kiro_gateway_launcher.config_editor import ConfigEditor


class MockIO:
    """Test WizardIO that replays scripted inputs."""

    def __init__(self, inputs: list[str] | None = None) -> None:
        self._inputs = list(inputs or [])
        self.printed: list[str] = []

    def prompt(self, message: str) -> str:
        return self._inputs.pop(0) if self._inputs else ""

    def print(self, message: str) -> None:
        self.printed.append(message)


class TestShow:
    """Tests for ConfigEditor.show()."""

    def test_masks_token_key(self, tmp_path: Path) -> None:
        """Values for keys containing TOKEN are masked as ****."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=super-secret\n")

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "REFRESH_TOKEN=****" in output
        assert "super-secret" not in output

    def test_masks_key_in_name(self, tmp_path: Path) -> None:
        """Values for keys containing KEY are masked."""
        env_file = tmp_path / ".env"
        env_file.write_text("PROXY_API_KEY=my-key\n")

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "PROXY_API_KEY=****" in output

    def test_masks_secret_in_name(self, tmp_path: Path) -> None:
        """Values for keys containing SECRET are masked."""
        env_file = tmp_path / ".env"
        env_file.write_text("MY_SECRET=hidden\n")

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "MY_SECRET=****" in output

    def test_masks_password_in_name(self, tmp_path: Path) -> None:
        """Values for keys containing PASSWORD are masked."""
        env_file = tmp_path / ".env"
        env_file.write_text("DB_PASSWORD=hunter2\n")

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "DB_PASSWORD=****" in output

    def test_non_sensitive_key_shown_plaintext(self, tmp_path: Path) -> None:
        """Non-sensitive values are displayed as-is."""
        env_file = tmp_path / ".env"
        env_file.write_text("KIRO_CREDS_FILE=/path/to/file.json\n")

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "KIRO_CREDS_FILE=/path/to/file.json" in output

    def test_friendly_message_when_file_missing(self, tmp_path: Path) -> None:
        """show() prints a friendly message when USER_ENV does not exist."""
        missing = tmp_path / ".env"

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", missing):
            ConfigEditor(io=io).show()  # must not raise

        output = "\n".join(io.printed)
        assert "No configuration found" in output


class TestShowPath:
    """Tests for ConfigEditor.show_path()."""

    def test_prints_user_env_path(self, tmp_path: Path) -> None:
        """show_path() prints the resolved path to USER_ENV."""
        env_file = tmp_path / ".env"

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show_path()

        assert str(env_file.resolve()) in io.printed[0]


class TestReset:
    """Tests for ConfigEditor.reset()."""

    def test_deletes_file_on_confirmation(self, tmp_path: Path) -> None:
        """reset() deletes USER_ENV when user confirms with 'y'."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=abc\n")

        io = MockIO(inputs=["y"])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).reset()

        assert not env_file.exists()

    def test_does_not_delete_on_denial(self, tmp_path: Path) -> None:
        """reset() keeps USER_ENV when user does not confirm."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=abc\n")

        io = MockIO(inputs=["n"])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).reset()

        assert env_file.exists()

    def test_does_not_delete_on_empty_input(self, tmp_path: Path) -> None:
        """reset() keeps USER_ENV when user presses enter (default N)."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=abc\n")

        io = MockIO(inputs=[""])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).reset()

        assert env_file.exists()

    def test_friendly_message_when_file_missing(self, tmp_path: Path) -> None:
        """reset() prints a message when there is nothing to reset."""
        missing = tmp_path / ".env"

        io = MockIO()
        with patch.object(ce_module, "USER_ENV", missing):
            ConfigEditor(io=io).reset()

        output = "\n".join(io.printed)
        assert "No configuration file" in output
