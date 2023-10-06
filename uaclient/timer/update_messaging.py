"""
Update messaging text for use in MOTD and APT custom Ubuntu Pro messages.

Messaging files will be emitted to /var/lib/ubuntu-advantage/message-* which
will be sourced by apt-hook/hook.cc and various /etc/update-motd.d/ hooks to
present updated text about Ubuntu Pro service and token state.
"""

import logging
import os
from os.path import exists

from uaclient import contract, defaults, messages, system, util
from uaclient.api.u.pro.packages.updates.v1 import (
    _updates as api_u_pro_packages_updates_v1,
)
from uaclient.api.u.pro.status.is_attached.v1 import (
    ContractExpiryStatus,
    _is_attached,
)
from uaclient.config import UAConfig
from uaclient.entitlements import ESMAppsEntitlement, ESMInfraEntitlement
from uaclient.entitlements.entitlement_status import ApplicationStatus

MOTD_CONTRACT_STATUS_FILE_NAME = "motd-contract-status"
UPDATE_NOTIFIER_MOTD_SCRIPT = (
    "/usr/lib/update-notifier/update-motd-updates-available"
)
LOG = logging.getLogger(util.replace_top_level_logger_name(__name__))


def update_contract_expiry(cfg: UAConfig):
    orig_token = cfg.machine_token
    machine_token = orig_token.get("machineToken", "")
    contract_id = (
        orig_token.get("machineTokenInfo", {})
        .get("contractInfo", {})
        .get("id", None)
    )
    contract_client = contract.UAContractClient(cfg)
    resp = contract_client.get_contract_machine(machine_token, contract_id)
    resp_expiry = (
        resp.get("machineTokenInfo", {})
        .get("contractInfo", {})
        .get("effectiveTo", None)
    )
    if (
        resp_expiry is not None
        and resp_expiry != cfg.machine_token_file.contract_expiry_datetime
    ):
        orig_token["machineTokenInfo"]["contractInfo"][
            "effectiveTo"
        ] = resp_expiry
        cfg.machine_token_file.write(orig_token)


def update_motd_messages(cfg: UAConfig) -> bool:
    """Emit human-readable status message used by motd.

    Used by /etc/update.motd.d/91-contract-ua-esm-status

    :param cfg: UAConfig instance for this environment.
    """
    is_attached_info = _is_attached(cfg)
    if not is_attached_info.is_attached:
        return False

    LOG.info("Updating Ubuntu Pro messages for MOTD.")
    motd_contract_status_msg_path = os.path.join(
        cfg.data_dir, "messages", MOTD_CONTRACT_STATUS_FILE_NAME
    )

    expiry_status = is_attached_info.contract_status
    remaining_days = is_attached_info.contract_remaining_days

    if expiry_status in (
        ContractExpiryStatus.ACTIVE_EXPIRED_SOON.value,
        ContractExpiryStatus.EXPIRED_GRACE_PERIOD.value,
        ContractExpiryStatus.EXPIRED.value,
    ):
        update_contract_expiry(cfg)
        is_attached_info = _is_attached(cfg)
        expiry_status = is_attached_info.contract_status
        remaining_days = is_attached_info.contract_remaining_days

    if expiry_status in (
        ContractExpiryStatus.ACTIVE.value,
        ContractExpiryStatus.NONE.value,
    ):
        system.ensure_file_absent(motd_contract_status_msg_path)
    elif expiry_status == ContractExpiryStatus.ACTIVE_EXPIRED_SOON.value:
        system.write_file(
            motd_contract_status_msg_path,
            messages.CONTRACT_EXPIRES_SOON.pluralize(remaining_days).format(
                remaining_days=remaining_days,
            )
            + "\n\n",
        )
    elif expiry_status == ContractExpiryStatus.EXPIRED_GRACE_PERIOD.value:
        grace_period_remaining = (
            defaults.CONTRACT_EXPIRY_GRACE_PERIOD_DAYS + remaining_days
        )
        exp_dt = cfg.machine_token_file.contract_expiry_datetime
        if exp_dt is None:
            exp_dt_str = "Unknown"
        else:
            exp_dt_str = exp_dt.strftime("%d %b %Y")
        system.write_file(
            motd_contract_status_msg_path,
            messages.CONTRACT_EXPIRED_GRACE_PERIOD.pluralize(
                remaining_days
            ).format(
                expired_date=exp_dt_str,
                remaining_days=grace_period_remaining,
            )
            + "\n\n",
        )
    elif expiry_status == ContractExpiryStatus.EXPIRED.value:
        service = "n/a"
        pkg_num = 0

        if system.is_current_series_active_esm():
            esm_infra_status, _ = ESMInfraEntitlement(cfg).application_status()
            if esm_infra_status == ApplicationStatus.ENABLED:
                service = "esm-infra"
                pkg_num = api_u_pro_packages_updates_v1(
                    cfg
                ).summary.num_esm_infra_updates
        elif system.is_current_series_lts():
            esm_apps_status, _ = ESMAppsEntitlement(cfg).application_status()
            if esm_apps_status == ApplicationStatus.ENABLED:
                service = "esm-apps"
                pkg_num = api_u_pro_packages_updates_v1(
                    cfg
                ).summary.num_esm_apps_updates

        if pkg_num == 0:
            system.write_file(
                motd_contract_status_msg_path,
                messages.CONTRACT_EXPIRED + "\n\n",
            )
        else:
            system.write_file(
                motd_contract_status_msg_path,
                messages.CONTRACT_EXPIRED_WITH_PKGS.pluralize(pkg_num).format(
                    pkg_num=pkg_num,
                    service=service,
                )
                + "\n\n",
            )

    return True


def refresh_motd():
    # If update-notifier is present, we might as well update
    # the package updates count related to MOTD
    if exists(UPDATE_NOTIFIER_MOTD_SCRIPT):
        # If this command fails, we shouldn't break the entire command,
        # since this command should already be triggered by
        # update-notifier apt hooks
        try:
            system.subp([UPDATE_NOTIFIER_MOTD_SCRIPT, "--force"])
        except Exception as exc:
            LOG.exception(exc)
