"""Repository manager for kiro-gateway-launcher.

Manages the jwadow/kiro-gateway source code clone at a fixed location
and injects it into sys.path so that `import kiro` works at runtime.

The upstream project has no pyproject.toml and cannot be installed as a
Python package, so we clone it and use sys.path injection instead.
"""

import subprocess
import sys
from pathlib import Path


UPSTREAM: str = "https://github.com/jwadow/kiro-gateway"
REPO_DIR: Path = Path.home() / ".local" / "share" / "kiro-gateway-launcher" / "repo"


class RepoManager:
    """Manages the kiro-gateway source repository.

    Clones the upstream repository on first use and injects its path into
    sys.path so that `import kiro` resolves correctly inside the launcher's
    uv-managed virtual environment.
    """

    def ensure(self) -> None:
        """Ensure the repo is cloned and available on sys.path.

        Clones the upstream repository if REPO_DIR does not exist, then
        injects REPO_DIR into sys.path so kiro modules can be imported.
        """
        if not REPO_DIR.exists():
            self._clone()
        self._inject_sys_path()

    def pull(self) -> str:
        """Pull the latest changes from upstream.

        Returns:
            The new HEAD commit SHA after the pull.

        Raises:
            SystemExit: If git is not found or the pull fails.
        """
        self._run_git(["git", "-C", str(REPO_DIR), "pull"], "git pull")
        return self.head_sha()

    def head_sha(self) -> str:
        """Return the current HEAD commit SHA of the local repo.

        Reads .git/HEAD to resolve the current branch ref, then reads the
        corresponding ref file to obtain the commit SHA.

        Returns:
            The 40-character commit SHA string.

        Raises:
            FileNotFoundError: If the repo directory or git files are missing.
        """
        head_file = REPO_DIR / ".git" / "HEAD"
        head_content = head_file.read_text(encoding="utf-8").strip()

        if head_content.startswith("ref: "):
            # Symbolic ref — resolve to the actual SHA file
            ref_path = head_content[len("ref: "):]
            sha_file = REPO_DIR / ".git" / ref_path
            return sha_file.read_text(encoding="utf-8").strip()

        # Detached HEAD — content is the SHA directly
        return head_content

    def _clone(self) -> None:
        """Clone the upstream repository into REPO_DIR.

        Raises:
            SystemExit: If git is not found or the clone fails.
        """
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        print(f"[kiro-gateway-launcher] Cloning {UPSTREAM} ...")
        self._run_git(["git", "clone", UPSTREAM, str(REPO_DIR)], "git clone")
        print("[kiro-gateway-launcher] Clone complete.")

    def _inject_sys_path(self) -> None:
        """Insert REPO_DIR at the front of sys.path (idempotent).

        If REPO_DIR is already present in sys.path, this is a no-op.
        """
        repo_str = str(REPO_DIR)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

    def _run_git(self, cmd: list[str], label: str) -> None:
        """Run a git command, exiting with an error on failure.

        Args:
            cmd: The command list to pass to subprocess.run.
            label: Human-readable label used in error messages.

        Raises:
            SystemExit: If git is not found (code 1) or the command fails (code 1).
        """
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            print(
                "[kiro-gateway-launcher] Error: git is not installed or not in PATH.\n"
                "  Install git and try again."
            )
            sys.exit(1)

        if result.returncode != 0:
            print(
                f"[kiro-gateway-launcher] Error: {label} failed.\n"
                f"  {result.stderr.strip()}"
            )
            sys.exit(1)
