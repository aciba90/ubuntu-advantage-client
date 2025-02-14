import mock
import pytest

from uaclient.cli import main

M_PATH = "uaclient.cli."

HELP_OUTPUT = """\
usage: pro config <command> [flags]

Manage Ubuntu Pro configuration

Flags:
  -h, --help  show this help message and exit

Available Commands:
  
    show      show all Ubuntu Pro configuration setting(s)
    set       set Ubuntu Pro configuration setting
    unset     unset Ubuntu Pro configuration setting
"""  # noqa


@mock.patch("uaclient.cli.logging.error")
@mock.patch("uaclient.cli.setup_logging")
@mock.patch(M_PATH + "contract.get_available_resources")
class TestMainConfig:
    @pytest.mark.parametrize("additional_params", ([], ["--help"]))
    def test_config_help(
        self,
        _m_resources,
        _logging,
        logging_error,
        additional_params,
        capsys,
        FakeConfig,
    ):
        """Show help for --help and absent positional param"""
        with pytest.raises(SystemExit):
            with mock.patch(
                "sys.argv", ["/usr/bin/ua", "config"] + additional_params
            ):
                with mock.patch(
                    "uaclient.config.UAConfig",
                    return_value=FakeConfig(),
                ):
                    main()
        out, err = capsys.readouterr()
        assert HELP_OUTPUT == out
        if additional_params == ["--help"]:
            assert "" == err
        else:
            # When lacking show, set or unset inform about valid values
            assert "\n<command> must be one of: show, set, unset\n" == err
            assert [
                mock.call("\n<command> must be one of: show, set, unset")
            ] == logging_error.call_args_list
