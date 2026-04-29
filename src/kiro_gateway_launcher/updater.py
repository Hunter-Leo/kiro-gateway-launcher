"""Update checker for kiro-gateway-launcher.

Runs git fetch and git pull to update the local kiro-gateway repo.
No GitHub API calls - uses git directly to avoid rate limits.
"""

import subprocess
import sys

from kiro_gateway_launcher.repo_manager import REPO_DIR, RepoManager


class Updater:
    """Updates the local kiro-gateway repo via git fetch and pull.

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

        Runs git fetch to check for updates, then git pull if there are
        changes on the remote.

        Raises:
            SystemExit: With code 1 on git failure.
        """
        # Ensure repo exists before updating
        self._repo.ensure()

        local_sha = self._repo.head_sha()

        # Fetch latest from remote
        try:
            subprocess.run(
                ["git", "fetch", "origin", "main"],
                cwd=REPO_DIR,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"[kiro-gateway-launcher] Error: git fetch failed\n"
                f"  {exc.stderr.decode().strip()}"
            )
            sys.exit(1)

        # Check if remote has new commits
        try:
            result = subprocess.run(
                ["git", "rev-parse", "origin/main"],
                cwd=REPO_DIR,
                check=True,
                capture_output=True,
                text=True,
            )
            remote_sha = result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            print(
                f"[kiro-gateway-launcher] Error: failed to get remote SHA\n"
                f"  {exc.stderr.decode().strip()}"
            )
            sys.exit(1)

        if remote_sha == local_sha:
            print(f"[kiro-gateway-launcher] Already up to date ({local_sha[:7]}).")
            return

        print(
            f"[kiro-gateway-launcher] Update available: "
            f"{local_sha[:7]} → {remote_sha[:7]}"
        )
        print("[kiro-gateway-launcher] Pulling latest changes...")

        try:
            subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=REPO_DIR,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"[kiro-gateway-launcher] Error: git pull failed\n"
                f"  {exc.stderr.decode().strip()}"
            )
            sys.exit(1)

        print("[kiro-gateway-launcher] Update complete.")
