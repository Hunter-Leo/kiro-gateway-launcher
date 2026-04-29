"""Unit tests for RepoManager."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import kiro_gateway_launcher.repo_manager as rm_module
from kiro_gateway_launcher.repo_manager import RepoManager


@pytest.fixture(autouse=True)
def restore_sys_path():
    """Restore sys.path after each test."""
    original = sys.path.copy()
    yield
    sys.path[:] = original


class TestEnsure:
    """Tests for RepoManager.ensure()."""

    def test_clones_when_repo_missing(self, tmp_path: Path) -> None:
        """ensure() triggers clone when REPO_DIR does not exist."""
        fake_repo = tmp_path / "repo"

        with patch.object(rm_module, "REPO_DIR", fake_repo):
            with patch.object(RepoManager, "_clone") as mock_clone:
                with patch.object(RepoManager, "_inject_sys_path") as mock_inject:
                    RepoManager().ensure()

        mock_clone.assert_called_once()
        mock_inject.assert_called_once()

    def test_skips_clone_when_repo_exists(self, tmp_path: Path) -> None:
        """ensure() skips clone when REPO_DIR already exists."""
        fake_repo = tmp_path / "repo"
        fake_repo.mkdir()

        with patch.object(rm_module, "REPO_DIR", fake_repo):
            with patch.object(RepoManager, "_clone") as mock_clone:
                with patch.object(RepoManager, "_inject_sys_path") as mock_inject:
                    RepoManager().ensure()

        mock_clone.assert_not_called()
        mock_inject.assert_called_once()


class TestInjectSysPath:
    """Tests for RepoManager._inject_sys_path()."""

    def test_adds_repo_dir_to_sys_path(self, tmp_path: Path) -> None:
        """REPO_DIR is inserted at sys.path[0]."""
        fake_repo = tmp_path / "repo"

        with patch.object(rm_module, "REPO_DIR", fake_repo):
            RepoManager()._inject_sys_path()

        assert str(fake_repo) in sys.path

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling _inject_sys_path() twice does not add duplicate entries."""
        fake_repo = tmp_path / "repo"

        with patch.object(rm_module, "REPO_DIR", fake_repo):
            RepoManager()._inject_sys_path()
            RepoManager()._inject_sys_path()

        assert sys.path.count(str(fake_repo)) == 1


class TestHeadSha:
    """Tests for RepoManager.head_sha()."""

    def test_reads_sha_from_symbolic_ref(self, tmp_path: Path) -> None:
        """head_sha() resolves a symbolic ref to the commit SHA."""
        fake_repo = tmp_path / "repo"
        git_dir = fake_repo / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        refs_dir = git_dir / "refs" / "heads"
        refs_dir.mkdir(parents=True)
        (refs_dir / "main").write_text("abc1234def5678\n")

        with patch.object(rm_module, "REPO_DIR", fake_repo):
            sha = RepoManager().head_sha()

        assert sha == "abc1234def5678"

    def test_reads_sha_from_detached_head(self, tmp_path: Path) -> None:
        """head_sha() returns the SHA directly when HEAD is detached."""
        fake_repo = tmp_path / "repo"
        git_dir = fake_repo / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "HEAD").write_text("deadbeef12345678\n")

        with patch.object(rm_module, "REPO_DIR", fake_repo):
            sha = RepoManager().head_sha()

        assert sha == "deadbeef12345678"


class TestRunGit:
    """Tests for RepoManager._run_git() error handling."""

    def test_exits_when_git_not_found(self) -> None:
        """Missing git binary causes sys.exit(1)."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(SystemExit) as exc_info:
                RepoManager()._run_git(["git", "status"], "git status")

        assert exc_info.value.code == 1

    def test_exits_on_nonzero_return_code(self) -> None:
        """Non-zero git exit code causes sys.exit(1)."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: not a git repository"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(SystemExit) as exc_info:
                RepoManager()._run_git(["git", "status"], "git status")

        assert exc_info.value.code == 1

    def test_succeeds_on_zero_return_code(self) -> None:
        """Zero return code does not raise."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            RepoManager()._run_git(["git", "status"], "git status")  # must not raise
