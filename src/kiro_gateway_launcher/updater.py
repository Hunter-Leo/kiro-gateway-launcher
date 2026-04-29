"""Update checker for kiro-gateway-launcher.

Compares the local kiro-gateway repo HEAD SHA against the latest commit
on the upstream GitHub repository and runs git pull when an update is
available.

Uses only stdlib (urllib.request) — no new dependencies.
"""

import json
import sys
import urllib.error
import urllib.request

from kiro_gateway_launcher.repo_manager import RepoManager


UPSTREAM_API: str = (
    "https://api.github.com/repos/jwadow/kiro-gateway/commits/main"
)


class Updater:
    """Checks for upstream kiro-gateway updates and applies them via git pull.

    Depends on RepoManager for local repo operations. Injecting RepoManager
    enables testing without touching the filesystem or network.
    """

    def __init__(self, repo: RepoManager | None = None) -> None:
        """Initialise the updater with an optional RepoManager.

        Args:
            repo: RepoManager instance to use. Defaults to a new RepoManager.
        """
        self._repo = repo or RepoManager()

    def run(self) -> None:
        """Check for updates and apply if available.

        Fetches the latest commit SHA from the GitHub API, compares it with
        the local HEAD SHA, and runs git pull when they differ.

        Raises:
            SystemExit: With code 1 on network failure.
        """
        # Ensure repo exists before checking SHA
        self._repo.ensure()

        remote_sha = self._fetch_remote_sha()
        local_sha = self._repo.head_sha()

        if remote_sha == local_sha:
            print(f"[kiro-gateway-launcher] Already up to date ({local_sha[:7]}).")
            return

        print(
            f"[kiro-gateway-launcher] Update available: "
            f"{local_sha[:7]} → {remote_sha[:7]}"
        )
        print("[kiro-gateway-launcher] Pulling latest changes...")
        self._repo.pull()
        print("[kiro-gateway-launcher] Update complete.")

    def _fetch_remote_sha(self) -> str:
        """Fetch the latest commit SHA from the GitHub API.

        Returns:
            The full 40-character commit SHA of the latest main branch commit.

        Raises:
            SystemExit: With code 1 if the network request fails.
        """
        req = urllib.request.Request(
            UPSTREAM_API,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["sha"]
        except urllib.error.URLError as exc:
            print(
                f"[kiro-gateway-launcher] Error: network request failed: {exc.reason}\n"
                "  Check your internet connection and try again."
            )
            sys.exit(1)
        except (KeyError, json.JSONDecodeError) as exc:
            print(
                f"[kiro-gateway-launcher] Error: unexpected GitHub API response: {exc}\n"
                "  Try again later."
            )
            sys.exit(1)
