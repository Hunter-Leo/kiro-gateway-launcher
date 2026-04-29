"""CLI entry point for kiro-gateway-launcher.

Dispatches to ConfigLoader, RepoManager, SetupWizard, ConfigEditor,
Updater, and the kiro-gateway server in the correct order.

Critical ordering in main():
    1. ConfigLoader.load()    — inject env vars into os.environ
    2. RepoManager.ensure()   — clone repo if needed, inject sys.path
    3. Parse arguments
    4. Dispatch command

All `import kiro.*` and `import main` statements are deferred inside
function bodies so that steps 1 and 2 always complete first.
"""

import argparse
import sys

from kiro_gateway_launcher.config_loader import USER_ENV, ConfigLoader
from kiro_gateway_launcher.config_editor import ConfigEditor
from kiro_gateway_launcher.repo_manager import RepoManager
from kiro_gateway_launcher.setup_wizard import ConsoleIO, SetupWizard
from kiro_gateway_launcher.updater import Updater


def main() -> None:
    """Main entry point for the kiro-gateway-launcher command.

    Initialises configuration and the kiro-gateway repository before
    parsing arguments and dispatching to the appropriate handler.
    """
    # ① Inject env vars before any kiro import
    ConfigLoader().load()
    # ② Clone repo if needed and inject into sys.path
    RepoManager().ensure()

    args = _parse_args()

    if args.command == "config":
        _handle_config(args)
    elif args.command == "update":
        Updater().run()
    else:
        _handle_start(args)


def _parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments.

    Returns:
        Parsed argument namespace with command, host, port, and config flags.
    """
    parser = argparse.ArgumentParser(
        prog="kiro-gateway-launcher",
        description="CLI launcher for kiro-gateway (jwadow/kiro-gateway)",
    )
    parser.add_argument(
        "-H", "--host",
        default=None,
        metavar="HOST",
        help="Server host address (default: 0.0.0.0, env: SERVER_HOST)",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=None,
        metavar="PORT",
        help="Server port (default: 8000, env: SERVER_PORT)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # config subcommand
    config_parser = subparsers.add_parser(
        "config",
        help="View or manage configuration",
    )
    config_group = config_parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--edit",
        action="store_true",
        help="Re-run the setup wizard to reconfigure credentials",
    )
    config_group.add_argument(
        "--reset",
        action="store_true",
        help="Delete the user configuration file (requires confirmation)",
    )
    config_group.add_argument(
        "--show-path",
        action="store_true",
        help="Print the path to the configuration file",
    )

    # update subcommand
    subparsers.add_parser(
        "update",
        help="Pull the latest kiro-gateway source from upstream",
    )

    return parser.parse_args()


def _handle_config(args: argparse.Namespace) -> None:
    """Dispatch config subcommand flags to the appropriate handler.

    Args:
        args: Parsed argument namespace containing config flags.
    """
    io = ConsoleIO()
    if args.edit:
        SetupWizard(io=io).run()
    elif args.reset:
        ConfigEditor(io=io).reset()
    elif args.show_path:
        ConfigEditor(io=io).show_path()
    else:
        ConfigEditor(io=io).show()


def _handle_start(args: argparse.Namespace) -> None:
    """Start the kiro-gateway server.

    Runs the setup wizard if no credentials are configured, validates
    credentials, then starts uvicorn with the kiro-gateway FastAPI app.

    Args:
        args: Parsed argument namespace with optional host and port overrides.
    """
    io = ConsoleIO()
    wizard = SetupWizard(io=io)
    if wizard.needs_setup():
        wizard.run()

    # Deferred imports — env vars and sys.path are fully set at this point
    try:
        import main as kiro_main  # noqa: PLC0415  (kiro-gateway repo root)
        import uvicorn             # noqa: PLC0415
    except ImportError as exc:
        print(
            f"[kiro-gateway-launcher] Error: cannot import kiro-gateway: {exc}\n"
            "  Run 'kiro-gateway-launcher update' to download kiro-gateway."
        )
        sys.exit(1)

    _validate_credentials(kiro_main)

    host: str = args.host or kiro_main.SERVER_HOST
    port: int = args.port or kiro_main.SERVER_PORT

    kiro_main.print_startup_banner(host, port)
    kiro_main._warn_timeout_configuration()

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_config=kiro_main.UVICORN_LOG_CONFIG,
    )


def _validate_credentials(kiro_main) -> None:  # type: ignore[no-untyped-def]
    """Validate that at least one Kiro credential is configured.

    Checks the same conditions as kiro-gateway's validate_configuration()
    but prints a launcher-specific error message that points to the correct
    config file path instead of suggesting `cp .env.example .env`.

    Args:
        kiro_main: The imported kiro-gateway main module.

    Raises:
        SystemExit: With code 1 if no valid credentials are found.
    """
    import os
    from pathlib import Path

    has_refresh_token = bool(kiro_main.REFRESH_TOKEN)
    has_creds_file = bool(kiro_main.KIRO_CREDS_FILE) and Path(
        kiro_main.KIRO_CREDS_FILE
    ).expanduser().exists()
    has_cli_db = bool(kiro_main.KIRO_CLI_DB_FILE) and Path(
        kiro_main.KIRO_CLI_DB_FILE
    ).expanduser().exists()

    if not (has_refresh_token or has_creds_file or has_cli_db):
        print(
            "\n[kiro-gateway-launcher] No valid Kiro credentials found.\n"
            f"  Config file: {USER_ENV}\n"
            "  Run: kiro-gateway-launcher config --edit\n"
        )
        sys.exit(1)
