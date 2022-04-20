import mock
import pytest

from uaclient import exceptions, messages
from uaclient.cli import action_refresh, main

HELP_OUTPUT = """\
usage: ua refresh [contract|config] [flags]

Refresh existing Ubuntu Advantage contract and update services.

positional arguments:
  {contract,config,motd}
                        Target to refresh. `ua refresh contract` will update
                        contract details from the server and perform any
                        updates necessary. `ua refresh config` will reload
                        /etc/ubuntu-advantage/uaclient.conf and perform any
                        changes necessary. `ua refresh motd` will refresh the
                        MOTD messages associated with UA. `ua refresh` is the
                        equivalent of `ua refresh config && ua refresh
                        contract && ua refresh motd`.

Flags:
  -h, --help            show this help message and exit
"""


@mock.patch("os.getuid", return_value=0)
class TestActionRefresh:
    @mock.patch("uaclient.cli.contract.get_available_resources")
    def test_refresh_help(self, _m_resources, _getuid, capsys):
        with pytest.raises(SystemExit):
            with mock.patch("sys.argv", ["/usr/bin/ua", "refresh", "--help"]):
                main()
        out, _err = capsys.readouterr()
        print(out)
        assert HELP_OUTPUT in out

    def test_non_root_users_are_rejected(self, getuid, FakeConfig):
        """Check that a UID != 0 will receive a message and exit non-zero"""
        getuid.return_value = 1

        cfg = FakeConfig.for_attached_machine()
        with pytest.raises(exceptions.NonRootUserError):
            action_refresh(mock.MagicMock(), cfg=cfg)

    @pytest.mark.parametrize(
        "target, expect_unattached_error",
        [(None, True), ("contract", True), ("config", False)],
    )
    @mock.patch("uaclient.config.UAConfig.write_cfg")
    def test_not_attached_errors(
        self, _m_write_cfg, getuid, target, expect_unattached_error, FakeConfig
    ):
        """Check that an unattached machine emits message and exits 1"""
        cfg = FakeConfig()

        cfg.update_messaging_timer = 0
        cfg.update_status_timer = 0
        cfg.metering_timer = 0

        if expect_unattached_error:
            with pytest.raises(exceptions.UnattachedError):
                action_refresh(mock.MagicMock(target=target), cfg=cfg)
        else:
            action_refresh(mock.MagicMock(target=target), cfg=cfg)

    @mock.patch("uaclient.cli.util.subp")
    def test_lock_file_exists(self, m_subp, _getuid, FakeConfig):
        """Check inability to refresh if operation holds lock file."""
        cfg = FakeConfig().for_attached_machine()
        with open(cfg.data_path("lock"), "w") as stream:
            stream.write("123:ua disable")
        with pytest.raises(exceptions.LockHeldError) as err:
            action_refresh(mock.MagicMock(), cfg=cfg)
        assert [mock.call(["ps", "123"])] == m_subp.call_args_list
        assert (
            "Unable to perform: ua refresh.\n"
            "Operation in progress: ua disable (pid:123)"
        ) == err.value.msg

    @mock.patch("logging.exception")
    @mock.patch("uaclient.contract.request_updated_contract")
    def test_refresh_contract_error_on_failure_to_update_contract(
        self, request_updated_contract, logging_error, getuid, FakeConfig
    ):
        """On failure in request_updates_contract emit an error."""
        request_updated_contract.side_effect = exceptions.UrlError(
            mock.MagicMock()
        )

        cfg = FakeConfig.for_attached_machine()

        with pytest.raises(exceptions.UserFacingError) as excinfo:
            action_refresh(mock.MagicMock(target="contract"), cfg=cfg)

        assert messages.REFRESH_CONTRACT_FAILURE == excinfo.value.msg

    @mock.patch("uaclient.contract.request_updated_contract")
    def test_refresh_contract_happy_path(
        self, request_updated_contract, getuid, capsys, FakeConfig
    ):
        """On success from request_updates_contract root user can refresh."""
        request_updated_contract.return_value = True

        cfg = FakeConfig.for_attached_machine()
        ret = action_refresh(mock.MagicMock(target="contract"), cfg=cfg)

        assert 0 == ret
        assert messages.REFRESH_CONTRACT_SUCCESS in capsys.readouterr()[0]
        assert [mock.call(cfg)] == request_updated_contract.call_args_list

    @mock.patch("uaclient.cli.update_apt_and_motd_messages")
    def test_refresh_motd_error(self, m_update_motd, getuid, FakeConfig):
        """On failure in update_apt_and_motd_messages emit an error."""
        m_update_motd.side_effect = exceptions.UserFacingError(
            messages.REFRESH_MOTD_FAILURE
        )

        with pytest.raises(exceptions.UserFacingError) as excinfo:
            action_refresh(mock.MagicMock(target="motd"), cfg=FakeConfig())

        assert messages.REFRESH_MOTD_FAILURE == excinfo.value.msg

    @mock.patch("uaclient.util.which")
    @mock.patch("uaclient.cli.update_apt_and_motd_messages")
    def test_refresh_motd_run_parts_error(
        self, m_update_motd, m_which, getuid, FakeConfig
    ):
        m_which.return_value = False

        with pytest.raises(exceptions.UserFacingError) as excinfo:
            action_refresh(mock.MagicMock(target="motd"), cfg=FakeConfig())

        assert (
            messages.UPDATE_MOTD_NO_REQUIRED_CMD.format(cmd="run-parts")
            == excinfo.value.msg
        )

    @mock.patch("uaclient.cli.refresh_motd")
    @mock.patch("uaclient.cli.update_apt_and_motd_messages")
    def test_refresh_motd_happy_path(
        self, m_update_motd, m_refresh_motd, getuid, capsys, FakeConfig
    ):
        """On success from request_updates_contract root user can refresh."""
        cfg = FakeConfig()
        ret = action_refresh(mock.MagicMock(target="motd"), cfg=cfg)

        assert 0 == ret
        assert messages.REFRESH_MOTD_SUCCESS in capsys.readouterr()[0]
        assert [mock.call(cfg)] == m_update_motd.call_args_list
        assert [mock.call()] == m_refresh_motd.call_args_list

    @mock.patch("logging.exception")
    @mock.patch(
        "uaclient.config.UAConfig.process_config", side_effect=RuntimeError()
    )
    def test_refresh_config_error_on_failure_to_process_config(
        self, _m_process_config, _m_logging_error, getuid, FakeConfig
    ):
        """On failure in process_config emit an error."""

        cfg = FakeConfig.for_attached_machine()

        with pytest.raises(exceptions.UserFacingError) as excinfo:
            action_refresh(mock.MagicMock(target="config"), cfg=cfg)

        assert messages.REFRESH_CONFIG_FAILURE == excinfo.value.msg

    @mock.patch("uaclient.config.UAConfig.process_config")
    def test_refresh_config_happy_path(
        self, m_process_config, getuid, capsys, FakeConfig
    ):
        """On success from process_config root user gets success message."""

        cfg = FakeConfig.for_attached_machine()
        ret = action_refresh(mock.MagicMock(target="config"), cfg=cfg)

        assert 0 == ret
        assert messages.REFRESH_CONFIG_SUCCESS in capsys.readouterr()[0]
        assert [mock.call()] == m_process_config.call_args_list

    @mock.patch("uaclient.contract.request_updated_contract")
    @mock.patch("uaclient.config.UAConfig.process_config")
    def test_refresh_all_happy_path(
        self,
        m_process_config,
        m_request_updated_contract,
        getuid,
        capsys,
        FakeConfig,
    ):
        """On success from process_config root user gets success message."""

        cfg = FakeConfig.for_attached_machine()
        ret = action_refresh(mock.MagicMock(target=None), cfg=cfg)
        out, err = capsys.readouterr()

        assert 0 == ret
        assert messages.REFRESH_CONFIG_SUCCESS in out
        assert messages.REFRESH_CONTRACT_SUCCESS in out
        assert [mock.call()] == m_process_config.call_args_list
        assert [mock.call(cfg)] == m_request_updated_contract.call_args_list
