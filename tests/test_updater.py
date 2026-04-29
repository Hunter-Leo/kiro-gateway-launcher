"""Unit tests for Updater."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from kiro_gateway_launcher.updater import Updater


def _make_mock_repo(local_sha: str) -> MagicMock:
    """Create a mock RepoManager with a fixed head_sha."""
    repo = MagicMock()
    repo.head_sha.return_value = local_sha
    return repo


def _make_urlopen_response(sha: str):
    """Return a context-manager mock that yields a GitHub API response."""
    body = json.dumps({"sha": sha}).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = body
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestUpdaterRun:
    """Tests for Updater.run()."""

    def test_prints_up_to_date_when_shas_match(self, capsys) -> None:
        """No pull is triggered when remote SHA equals local SHA."""
        sha = "abc1234" * 5 + "abcd"  # 40 chars
        repo = _make_mock_repo(sha)

        with patch("urllib.request.urlopen", return_value=_make_urlopen_response(sha)):
            Updater(repo=repo).run()

        repo.pull.assert_not_called()
        captured = capsys.readouterr()
        assert "up to date" in captured.out.lower()

    def test_pulls_when_shas_differ(self, capsys) -> None:
        """pull() is called and new SHA is printed when update is available."""
        local_sha = "aaa" * 13 + "a"   # 40 chars
        remote_sha = "bbb" * 13 + "b"  # 40 chars
        repo = _make_mock_repo(local_sha)

        with patch("urllib.request.urlopen", return_value=_make_urlopen_response(remote_sha)):
            Updater(repo=repo).run()

        repo.pull.assert_called_once()
        captured = capsys.readouterr()
        assert "aaa" in captured.out  # local short SHA
        assert "bbb" in captured.out  # remote short SHA

    def test_exits_on_network_failure(self) -> None:
        """Network failure causes sys.exit(1)."""
        repo = _make_mock_repo("abc" * 13 + "a")

        url_error = urllib.error.URLError("connection refused")
        with patch("urllib.request.urlopen", side_effect=url_error):
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

        with patch("urllib.request.urlopen", return_value=_make_urlopen_response(sha)):
            Updater(repo=repo).run()

        assert call_order[0] == "ensure"
        assert "head_sha" in call_order

    def test_exits_on_malformed_api_response(self) -> None:
        """Malformed JSON response causes sys.exit(1)."""
        repo = _make_mock_repo("abc" * 13 + "a")

        bad_response = MagicMock()
        bad_response.read.return_value = b'{"not_sha": "oops"}'
        bad_response.__enter__ = lambda s: s
        bad_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=bad_response):
            with pytest.raises(SystemExit) as exc_info:
                Updater(repo=repo).run()

        assert exc_info.value.code == 1
