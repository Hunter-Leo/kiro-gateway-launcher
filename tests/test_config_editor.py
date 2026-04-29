"""Unit tests for ConfigEditor."""

from pathlib import Path
from unittest.mock import patch

import pytest

import kiro_gateway_launcher.config_editor as ce_module
from kiro_gateway_launcher.config_editor import ConfigEditor, update_config_value, read_config_file


class MockIO:
    """Test WizardIO that replays scripted inputs."""

    def __init__(self, inputs: list[str] | None = None, confirms: list[bool] | None = None) -> None:
        self._inputs = list(inputs or [])
        self._confirms = list(confirms or [])
        self.printed: list[str] = []

    def prompt(self, message: str, default: str = "") -> str:
        if self._inputs:
            val = self._inputs.pop(0)
            return val if val else default
        return default

    def confirm(self, message: str) -> bool:
        return self._confirms.pop(0) if self._confirms else False

    def print(self, message: str) -> None:
        self.printed.append(message)


class TestShow:
    """Tests for ConfigEditor.show() interactive editor."""

    def test_quits_on_q(self, tmp_path: Path) -> None:
        """Entering 'q' exits the editor loop."""
        env_file = tmp_path / ".env"
        env_file.write_text("KIRO_CREDS_FILE=/path/to/file.json\n")

        io = MockIO(inputs=["q"])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()  # must not hang

    def test_quits_on_empty_input(self, tmp_path: Path) -> None:
        """Pressing enter (empty input) exits the editor loop."""
        env_file = tmp_path / ".env"
        env_file.write_text("KIRO_CREDS_FILE=/path/to/file.json\n")

        io = MockIO(inputs=[""])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

    def test_edit_non_sensitive_value(self, tmp_path: Path) -> None:
        """Selecting a variable by number and entering a value saves it."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        # Variable 2 is KIRO_CREDS_FILE; enter new value then quit
        io = MockIO(inputs=["2", "/new/path.json", "q"])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        content = env_file.read_text()
        assert "KIRO_CREDS_FILE=/new/path.json" in content

    def test_sensitive_value_masked_in_display(self, tmp_path: Path) -> None:
        """Sensitive values are masked in the printed list."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=supersecrettoken123\n")

        io = MockIO(inputs=["q"])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "supersecrettoken123" not in output
        assert "****" in output

    def test_invalid_choice_shows_error(self, tmp_path: Path) -> None:
        """Invalid number shows error and loops."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        io = MockIO(inputs=["999", "q"])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "Invalid" in output

    def test_shows_not_yet_created_message_when_file_missing(self, tmp_path: Path) -> None:
        """Missing config file shows a warning in the header."""
        missing = tmp_path / ".env"

        io = MockIO(inputs=["q"])
        with patch.object(ce_module, "USER_ENV", missing):
            ConfigEditor(io=io).show()

        output = "\n".join(io.printed)
        assert "not yet created" in output or "Config file" in output


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
        """reset() deletes USER_ENV when user confirms."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=abc\n")

        io = MockIO(confirms=[True])
        with patch.object(ce_module, "USER_ENV", env_file):
            ConfigEditor(io=io).reset()

        assert not env_file.exists()

    def test_does_not_delete_on_denial(self, tmp_path: Path) -> None:
        """reset() keeps USER_ENV when user does not confirm."""
        env_file = tmp_path / ".env"
        env_file.write_text("REFRESH_TOKEN=abc\n")

        io = MockIO(confirms=[False])
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


class TestReadWriteHelpers:
    """Tests for read_config_file and update_config_value helpers."""

    def test_read_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        """read_config_file returns {} when file does not exist."""
        assert read_config_file(tmp_path / "missing.env") == {}

    def test_update_writes_new_key(self, tmp_path: Path) -> None:
        """update_config_value writes a new key to the file."""
        env_file = tmp_path / ".env"
        env_file.write_text("")
        update_config_value(env_file, "SERVER_PORT", "9000")
        assert "SERVER_PORT=9000" in env_file.read_text()

    def test_update_removes_key_on_empty_value(self, tmp_path: Path) -> None:
        """update_config_value removes a key when value is empty string."""
        env_file = tmp_path / ".env"
        env_file.write_text("SERVER_PORT=9000\n")
        update_config_value(env_file, "SERVER_PORT", "")
        assert "SERVER_PORT" not in env_file.read_text()
