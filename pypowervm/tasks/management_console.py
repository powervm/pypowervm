# Copyright 2015 IBM Corp.
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from pypowervm.utils import transaction as trans
from pypowervm.wrappers import management_console as mc


def get_public_key(adapter):
    """Get the public key for the management console.

    :param adapter: The adapter for the pypowervm API.
    :return: The public key
    """
    # Get the consoles feed and use the first, there is just one.
    console = mc.ManagementConsole.wrap(
        adapter.read(mc.ManagementConsole.schema_type))[0]
    return console.ssh_public_key


def add_authorized_key(adapter, public_key):
    """Add an authorized public key to the management console.

    The public_key will be added if it doesn't already exist.

    :param adapter: The adapter for the pypowervm API.
    :param public_key: The public key to be added.
    """
    console_w = mc.ManagementConsole.wrap(
        adapter.read(mc.ManagementConsole.schema_type))[0]

    @trans.entry_transaction
    def run_update(console):
        keys = console.ssh_authorized_keys
        if public_key not in keys:
            keys = list(keys)
            keys.append(public_key)
            console.ssh_authorized_keys = keys
            console.update()

    run_update(console_w)


def get_authorized_keys(adapter):
    """Get all authorized keys on the management console.

    :param adapter: The adapter for the pypowervm API.
    """
    console_w = mc.ManagementConsole.wrap(
        adapter.read(mc.ManagementConsole.schema_type))[0]

    return console_w.ssh_authorized_keys
