"""Unit tests for ConfigLoader."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from kiro_gateway_launcher.config_loader import ConfigLoader, USER_ENV


@pytest.fixture(autouse=True)
def clean_env():
    """Remove test keys from os.environ before and after each test."""
    test_keys = ["TEST_KEY", "TEST_KEY2", "MULTI_EQUALS", "COMMENT_KEY", "BLANK_KEY"]
    for k in test_keys:
        os.environ.pop(k, None)
    yield
    for k in test_keys:
        os.environ.pop(k, None)


class TestConfigLoaderLoad:
    """Tests for ConfigLoader.load() priority chain."""

    def test_user_env_values_loaded(self, tmp_path: Path) -> None:
        """Values from USER_ENV are injected into os.environ."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=from_user_env\n")

        with patch("kiro_gateway_launcher.config_loader.USER_ENV", env_file):
            with patch("pathlib.Path.cwd", return_value=tmp_path / "empty"):
                ConfigLoader().load()

        assert os.environ["TEST_KEY"] == "from_user_env"

    def test_cwd_env_overrides_user_env(self, tmp_path: Path) -> None:
        """cwd .env takes priority over USER_ENV."""
        user_env = tmp_path / "user.env"
        user_env.write_text("TEST_KEY=from_user\n")

        cwd_dir = tmp_path / "cwd"
        cwd_dir.mkdir()
        (cwd_dir / ".env").write_text("TEST_KEY=from_cwd\n")

        with patch("kiro_gateway_launcher.config_loader.USER_ENV", user_env):
            with patch("pathlib.Path.cwd", return_value=cwd_dir):
                ConfigLoader().load()

        assert os.environ["TEST_KEY"] == "from_cwd"

    def test_existing_os_environ_not_overwritten(self, tmp_path: Path) -> None:
        """Keys already in os.environ are never overwritten."""
        os.environ["TEST_KEY"] = "original"
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=from_file\n")

        with patch("kiro_gateway_launcher.config_loader.USER_ENV", env_file):
            with patch("pathlib.Path.cwd", return_value=tmp_path / "empty"):
                ConfigLoader().load()

        assert os.environ["TEST_KEY"] == "original"

    def test_missing_file_silently_skipped(self, tmp_path: Path) -> None:
        """Missing .env files do not raise exceptions."""
        missing = tmp_path / "nonexistent.env"
        with patch("kiro_gateway_launcher.config_loader.USER_ENV", missing):
            with patch("pathlib.Path.cwd", return_value=tmp_path / "also_missing"):
                ConfigLoader().load()  # must not raise

    def test_comment_lines_skipped(self, tmp_path: Path) -> None:
        """Lines starting with # are ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("# this is a comment\nTEST_KEY=value\n")

        with patch("kiro_gateway_launcher.config_loader.USER_ENV", env_file):
            with patch("pathlib.Path.cwd", return_value=tmp_path / "empty"):
                ConfigLoader().load()

        assert os.environ["TEST_KEY"] == "value"
        assert "# this is a comment" not in os.environ

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        """Blank lines do not cause errors."""
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nTEST_KEY=value\n\n")

        with patch("kiro_gateway_launcher.config_loader.USER_ENV", env_file):
            with patch("pathlib.Path.cwd", return_value=tmp_path / "empty"):
                ConfigLoader().load()

        assert os.environ["TEST_KEY"] == "value"

    def test_value_with_equals_sign(self, tmp_path: Path) -> None:
        """Values containing '=' are parsed correctly (split on first '=' only)."""
        env_file = tmp_path / ".env"
        env_file.write_text("MULTI_EQUALS=a=b=c\n")

        with patch("kiro_gateway_launcher.config_loader.USER_ENV", env_file):
            with patch("pathlib.Path.cwd", return_value=tmp_path / "empty"):
                ConfigLoader().load()

        assert os.environ["MULTI_EQUALS"] == "a=b=c"

    def test_unreadable_file_prints_warning(self, tmp_path: Path, capsys) -> None:
        """Unreadable files emit a warning and do not raise."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=value\n")

        with patch("kiro_gateway_launcher.config_loader.USER_ENV", env_file):
            with patch("pathlib.Path.cwd", return_value=tmp_path / "empty"):
                with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
                    ConfigLoader().load()  # must not raise

        captured = capsys.readouterr()
        assert "Warning" in captured.out or "warning" in captured.out.lower()
