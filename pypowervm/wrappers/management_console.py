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

"""Wrappers, constants, and helpers around ManagementConsole."""

from oslo_log import log as logging

import pypowervm.const as c
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.mtms as mtmwrap

LOG = logging.getLogger(__name__)

_MGD_FRAMES = 'ManagedFrames'
_MGD_SYS = 'ManagedSystems'
_MGMT_CON_NAME = 'ManagementConsoleName'

# NETI XPath constants
_NETI_ROOT = 'NetworkInterfaces'

_MGMT_TPLT_OBJ_MOD_VERS = 'TemplateObjectModelVersion'
_MGMT_USR_OBJ_MOD_VERS = 'UserObjectModelVersion'
_MGMT_VERS_INFO = 'VersionInfo'
_MGMT_LOC_VIOS_IMG_NAMES = 'LocalVirtualIOServerImageNames'
_MGMT_WEB_OBJ_MOD_VERS = 'WebObjectModelVersion'

_PWR_ENT_POOLS = 'PowerEnterprisePools'

# SSH Config
_PUB_KEY = 'PublicSSHKey'
_AUTH_KEYS = 'AuthorizedKeys'
_AUTH_KEY = 'AuthorizedKey'

_MGMT_NETI_ROOT = 'ManagementConsoleNetworkInterface'
_MGMT_NETI_NAME = 'InterfaceName'
_MGMT_NETI_ADDRESS = 'NetworkAddress'

_CONS_EL_ORDER = (
    mtmwrap.MTMS_ROOT, _MGD_FRAMES, _MGD_SYS, _MGMT_CON_NAME, _NETI_ROOT,
    _MGMT_TPLT_OBJ_MOD_VERS, _MGMT_USR_OBJ_MOD_VERS, _MGMT_VERS_INFO,
    _MGMT_LOC_VIOS_IMG_NAMES, _MGMT_WEB_OBJ_MOD_VERS, _PWR_ENT_POOLS, _PUB_KEY,
    _AUTH_KEYS)


@ewrap.EntryWrapper.pvm_type('ManagementConsole', child_order=_CONS_EL_ORDER)
class ManagementConsole(ewrap.EntryWrapper):
    """The PowerVM ManagementConsole.

    This refers to the console that is managing PowerVM system. It's the
    one providing the REST API interface.
    """
    @property
    def name(self):
        return self._get_val_str(_MGMT_CON_NAME)

    @property
    def mtms(self):
        return mtmwrap.MTMS.wrap(self.element.find(mtmwrap.MTMS_ROOT))

    @property
    def network_interfaces(self):
        return NetworkInterfaces.wrap(self.element.find(_NETI_ROOT))

    @property
    def ssh_public_key(self):
        return self._get_val_str(_PUB_KEY)

    @property
    def ssh_authorized_keys(self):
        """Returns a list of keys.

        The returned tuple contains the keys as plain strings.
        """
        return tuple(key_w.key for key_w in
                     ewrap.WrapperElemList(self._find_or_seed(_AUTH_KEYS),
                                           AuthorizedKey))

    @ssh_authorized_keys.setter
    def ssh_authorized_keys(self, keys):
        """Sets the keys given a list of key strings."""
        self.replace_list(
            _AUTH_KEYS, [AuthorizedKey.bld(self.adapter, key) for key in keys],
            attrib=c.ATTR_SCHEMA_KSV130)


@ewrap.ElementWrapper.pvm_type(_AUTH_KEY, attrib={})
class AuthorizedKey(ewrap.ElementWrapper):
    """The Authorized Key wrapper."""

    @classmethod
    def bld(cls, adapter, key):
        new_key = super(AuthorizedKey, cls)._bld(adapter)
        new_key.key = key
        return new_key

    @property
    def key(self):
        return self.element.text

    @key.setter
    def key(self, val):
        self.element.text = val


@ewrap.ElementWrapper.pvm_type(_NETI_ROOT, has_metadata=True)
class NetworkInterfaces(ewrap.ElementWrapper):
    """The Network Interfaces wrapper."""

    @property
    def console_interface(self):
        return ConsoleNetworkInterfaces.wrap(
            self.element.find(_MGMT_NETI_ROOT))


@ewrap.ElementWrapper.pvm_type(_MGMT_NETI_ROOT, has_metadata=True)
class ConsoleNetworkInterfaces(ewrap.ElementWrapper):
    """The Console Network Interfaces wrapper."""

    @property
    def name(self):
        return self._get_val_str(_MGMT_NETI_NAME)

    @property
    def address(self):
        return self._get_val_str(_MGMT_NETI_ADDRESS)
