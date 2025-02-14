#!/usr/bin/env python3

"""
This function is called from lib/upgrade_lts_contract.py and from
lib/reboot_cmds.py

This function should be used after running do-release-upgrade in a machine.
It will detect any contract deltas between the release before
do-release-upgrade and the current release. If we find any differences in
the uaclient contract between those releases, we will apply that difference
in the upgraded release.

For example, suppose we are on Trusty and we are upgrading to Xenial. We found
that the apt url for esm services on trusty:

https://esm.ubuntu.com/ubuntu

While on Xenial, the apt url is:

https://esm.ubuntu.com/infra/ubuntu

This script will detect differences like that and update the Xenial system
to reflect them.
"""

import logging
import sys
import time

from uaclient import contract, defaults, system
from uaclient.api.u.pro.status.is_attached.v1 import _is_attached
from uaclient.config import UAConfig

# We consider the past release for LTSs to be the last LTS,
# because we don't have any services available on non-LTS.
# This makes it safer for us to try to process contract deltas.
# For example, we had "jammy": "focal" even when Impish was
# still supported.
current_codename_to_past_codename = {
    "xenial": "trusty",
    "bionic": "xenial",
    "focal": "bionic",
    "jammy": "focal",
    "kinetic": "jammy",
}


def process_contract_delta_after_apt_lock(cfg: UAConfig) -> None:
    logging.debug("Check whether to upgrade-lts-contract")
    if not _is_attached(cfg).is_attached:
        logging.debug("Skipping upgrade-lts-contract. Machine is unattached")
        return
    out, _err = system.subp(["lsof", "/var/lib/apt/lists/lock"], rcs=[0, 1])
    msg = "Starting upgrade-lts-contract."
    if out:
        msg += " Retrying every 10 seconds waiting on released apt lock"
    print(msg)
    logging.debug(msg)

    current_release = system.get_release_info().series

    past_release = current_codename_to_past_codename.get(current_release)
    if past_release is None:
        msg = "Could not find past release for: {}".format(current_release)
        print(msg)
        logging.warning(msg)
        sys.exit(1)

    past_entitlements = UAConfig(
        series=past_release,
    ).machine_token_file.entitlements
    new_entitlements = UAConfig(
        series=current_release,
    ).machine_token_file.entitlements

    retry_count = 0
    while out:
        # Loop until apt hold is released at the end of `do-release-upgrade`
        time.sleep(10)
        out, _err = system.subp(
            ["lsof", "/var/lib/apt/lists/lock"], rcs=[0, 1]
        )
        retry_count += 1

    msg = "upgrade-lts-contract processing contract deltas: {} -> {}".format(
        past_release, current_release
    )
    print(msg)
    logging.debug(msg)

    contract.process_entitlements_delta(
        cfg=cfg,
        past_entitlements=past_entitlements,
        new_entitlements=new_entitlements,
        allow_enable=True,
        series_overrides=False,
    )
    msg = "upgrade-lts-contract succeeded after {} retries".format(retry_count)
    print(msg)
    logging.debug(msg)


def remove_private_esm_apt_cache():
    system.ensure_folder_absent(defaults.ESM_APT_ROOTDIR)
