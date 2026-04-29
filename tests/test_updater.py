"""Unit tests for Updater."""

from subprocess import CalledProcessError, CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from kiro_gateway_launcher.updater import Updater


def _make_mock_repo(local_sha: str) -> MagicMock:
    """Create a mock RepoManager with a fixed head_sha."""
    repo = MagicMock()
    repo.head_sha.return_value = local_sha
    return repo


def _make_completed_process(stdout: str = "", stderr: str = "", returncode: int = 0, text: bool = True):
    """Create a mock CompletedProcess for subprocess.run.

    Args:
        stdout: Standard output (string if text=True, bytes if text=False)
        stderr: Standard error (string if text=True, bytes if text=False)
        returncode: Exit code
        text: Whether the process was run with text=True
    """
    if text:
        # When text=True, stdout/stderr are strings
        return CompletedProcess(
            args=["git", "fetch"],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )
    else:
        # When text=False, stdout/stderr are bytes
        return CompletedProcess(
            args=["git", "fetch"],
            returncode=returncode,
            stdout=stdout.encode() if isinstance(stdout, str) else stdout,
            stderr=stderr.encode() if isinstance(stderr, str) else stderr,
        )


class TestUpdaterRun:
    """Tests for Updater.run()."""

    def test_prints_up_to_date_when_shas_match(self, capsys) -> None:
        """No pull is triggered when remote SHA equals local SHA."""
        sha = "abc1234" * 5 + "abcd"  # 40 chars
        repo = _make_mock_repo(sha)

        # Mock subprocess.run for both git fetch and git rev-parse
        with patch(
            "kiro_gateway_launcher.updater.subprocess.run",
            side_effect=[
                _make_completed_process(),  # git fetch
                _make_completed_process(stdout=sha + "\n"),  # git rev-parse origin/main (with newline)
            ],
        ):
            Updater(repo=repo).run()

        repo.pull.assert_not_called()
        captured = capsys.readouterr()
        assert "up to date" in captured.out.lower()

    def test_pulls_when_shas_differ(self, capsys) -> None:
        """pull() is called and new SHA is printed when update is available."""
        local_sha = "aaa" * 13 + "a"   # 40 chars
        remote_sha = "bbb" * 13 + "b"  # 40 chars
        repo = _make_mock_repo(local_sha)

        with patch(
            "kiro_gateway_launcher.updater.subprocess.run",
            side_effect=[
                _make_completed_process(),  # git fetch
                _make_completed_process(stdout=remote_sha),  # git rev-parse origin/main
                _make_completed_process(),  # git pull
            ],
        ):
            Updater(repo=repo).run()

        repo.pull.assert_not_called()  # We use subprocess.run for pull, not repo.pull
        captured = capsys.readouterr()
        assert "aaa" in captured.out  # local short SHA
        assert "bbb" in captured.out  # remote short SHA

    def test_exits_on_git_fetch_failure(self) -> None:
        """Git fetch failure causes sys.exit(1)."""
        repo = _make_mock_repo("abc" * 13 + "a")

        with patch(
            "kiro_gateway_launcher.updater.subprocess.run",
            side_effect=CalledProcessError(
                returncode=128, cmd=["git", "fetch"], stderr=b"fatal: network error"
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                Updater(repo=repo).run()

        assert exc_info.value.code == 1

    def test_exits_on_git_rev_parse_failure(self) -> None:
        """Git rev-parse failure causes sys.exit(1)."""
        repo = _make_mock_repo("abc" * 13 + "a")

        with patch(
            "kiro_gateway_launcher.updater.subprocess.run",
            side_effect=[
                _make_completed_process(),  # git fetch succeeds
                CalledProcessError(
                    returncode=128, cmd=["git", "rev-parse"], stderr=b"fatal: not a git repo"
                ),
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                Updater(repo=repo).run()

        assert exc_info.value.code == 1

    def test_exits_on_git_pull_failure(self) -> None:
        """Git pull failure causes sys.exit(1)."""
        local_sha = "aaa" * 13 + "a"
        remote_sha = "bbb" * 13 + "b"
        repo = _make_mock_repo(local_sha)

        with patch(
            "kiro_gateway_launcher.updater.subprocess.run",
            side_effect=[
                _make_completed_process(),  # git fetch succeeds
                _make_completed_process(stdout=remote_sha),  # git rev-parse succeeds
                CalledProcessError(
                    returncode=1, cmd=["git", "pull"], stderr=b"error: merge conflict"
                ),
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                Updater(repo=repo).run()

        assert exc_info.value.code == 1

    def test_ensure_called_before_sha_check(self) -> None:
        """ensure() is called on the repo before fetching the remote SHA."""
        sha = "abc" * 13 + "a"
        repo = _make_mock_repo(sha)
        call_order: list[str] = []

        repo.ensure.side_effect = lambda: call_order.append("ensure")
        repo.head_sha.side_effect = lambda: call_order.append("head_sha") or sha

        with patch(
            "kiro_gateway_launcher.updater.subprocess.run",
            side_effect=[
                _make_completed_process(),  # git fetch
                _make_completed_process(stdout=sha + "\n"),  # git rev-parse origin/main (with newline)
            ],
        ):
            Updater(repo=repo).run()

        assert call_order[0] == "ensure"
        assert "head_sha" in call_order
