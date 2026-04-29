"""Unit tests for cli.py."""

import sys
from unittest.mock import MagicMock, call, patch

import pytest

import kiro_gateway_launcher.cli as cli_module
from kiro_gateway_launcher.cli import _handle_config, _parse_args, main


class TestParseArgs:
    """Tests for _parse_args()."""

    def test_default_command_is_none(self) -> None:
        """No subcommand results in command=None."""
        with patch("sys.argv", ["kiro-gateway-launcher"]):
            args = _parse_args()
        assert args.command is None

    def test_config_command_parsed(self) -> None:
        """'config' subcommand is parsed correctly."""
        with patch("sys.argv", ["kiro-gateway-launcher", "config"]):
            args = _parse_args()
        assert args.command == "config"
        assert not args.edit
        assert not args.reset
        assert not args.show_path

    def test_config_edit_flag(self) -> None:
        """'config --edit' sets edit=True."""
        with patch("sys.argv", ["kiro-gateway-launcher", "config", "--edit"]):
            args = _parse_args()
        assert args.edit is True

    def test_config_reset_flag(self) -> None:
        """'config --reset' sets reset=True."""
        with patch("sys.argv", ["kiro-gateway-launcher", "config", "--reset"]):
            args = _parse_args()
        assert args.reset is True

    def test_config_show_path_flag(self) -> None:
        """'config --show-path' sets show_path=True."""
        with patch("sys.argv", ["kiro-gateway-launcher", "config", "--show-path"]):
            args = _parse_args()
        assert args.show_path is True

    def test_update_command_parsed(self) -> None:
        """'update' subcommand is parsed correctly."""
        with patch("sys.argv", ["kiro-gateway-launcher", "update"]):
            args = _parse_args()
        assert args.command == "update"

    def test_host_and_port_flags(self) -> None:
        """--host and --port are parsed correctly."""
        with patch("sys.argv", ["kiro-gateway-launcher", "-H", "127.0.0.1", "-p", "9000"]):
            args = _parse_args()
        assert args.host == "127.0.0.1"
        assert args.port == 9000


class TestHandleConfig:
    """Tests for _handle_config() dispatch."""

    def test_no_flags_calls_show(self) -> None:
        """No flags → ConfigEditor.show()."""
        args = MagicMock()
        args.edit = False
        args.reset = False
        args.show_path = False

        with patch("kiro_gateway_launcher.cli.ConfigEditor") as MockEditor:
            _handle_config(args)

        MockEditor.return_value.show.assert_called_once()

    def test_edit_flag_calls_wizard_run(self) -> None:
        """--edit → SetupWizard.run()."""
        args = MagicMock()
        args.edit = True
        args.reset = False
        args.show_path = False

        with patch("kiro_gateway_launcher.cli.SetupWizard") as MockWizard:
            _handle_config(args)

        MockWizard.return_value.run.assert_called_once()

    def test_reset_flag_calls_editor_reset(self) -> None:
        """--reset → ConfigEditor.reset()."""
        args = MagicMock()
        args.edit = False
        args.reset = True
        args.show_path = False

        with patch("kiro_gateway_launcher.cli.ConfigEditor") as MockEditor:
            _handle_config(args)

        MockEditor.return_value.reset.assert_called_once()

    def test_show_path_flag_calls_editor_show_path(self) -> None:
        """--show-path → ConfigEditor.show_path()."""
        args = MagicMock()
        args.edit = False
        args.reset = False
        args.show_path = True

        with patch("kiro_gateway_launcher.cli.ConfigEditor") as MockEditor:
            _handle_config(args)

        MockEditor.return_value.show_path.assert_called_once()


class TestMain:
    """Tests for main() initialization order."""

    def test_config_loader_called_before_repo_manager(self) -> None:
        """ConfigLoader.load() is called before RepoManager.ensure()."""
        call_order: list[str] = []

        mock_loader = MagicMock()
        mock_loader.return_value.load.side_effect = lambda: call_order.append("load")

        mock_repo = MagicMock()
        mock_repo.return_value.ensure.side_effect = lambda: call_order.append("ensure")

        with patch("kiro_gateway_launcher.cli.ConfigLoader", mock_loader):
            with patch("kiro_gateway_launcher.cli.RepoManager", mock_repo):
                with patch("sys.argv", ["kiro-gateway-launcher", "update"]):
                    with patch("kiro_gateway_launcher.cli.Updater") as MockUpdater:
                        main()

        assert call_order.index("load") < call_order.index("ensure")

    def test_update_command_calls_updater_run(self) -> None:
        """'update' command calls Updater.run()."""
        with patch("kiro_gateway_launcher.cli.ConfigLoader"):
            with patch("kiro_gateway_launcher.cli.RepoManager"):
                with patch("sys.argv", ["kiro-gateway-launcher", "update"]):
                    with patch("kiro_gateway_launcher.cli.Updater") as MockUpdater:
                        main()

        MockUpdater.return_value.run.assert_called_once()

    def test_config_command_dispatched(self) -> None:
        """'config' command calls _handle_config."""
        with patch("kiro_gateway_launcher.cli.ConfigLoader"):
            with patch("kiro_gateway_launcher.cli.RepoManager"):
                with patch("sys.argv", ["kiro-gateway-launcher", "config"]):
                    with patch("kiro_gateway_launcher.cli._handle_config") as mock_handle:
                        main()

        mock_handle.assert_called_once()
