# Copyright 2014, 2015 IBM Corp.
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

"""LPAR, the EntryWrapper for LogicalPartition."""

import pypowervm.const as pc
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.entry_wrapper as ewrap

import logging

LOG = logging.getLogger(__name__)

_LPAR_ASSOCIATED_GROUPS = 'AssociatedGroups'
_LPAR_ASSOCIATED_TASKS = 'AssociatedTasks'
_LPAR_VFCA = 'VirtualFibreChannelClientAdapters'
_LPAR_VSCA = 'VirtualSCSIClientAdapters'
_LPAR_DED_NICS = 'DedicatedVirtualNICs'

_HOST_CHANNEL_ADAPTERS = 'HostChannelAdapters'


_RESTRICTED_IO = 'IsRestrictedIOPartition'
_SRR = 'SimplifiedRemoteRestartCapable'
_DESIGNATED_IPL_SRC = 'DesignatedIPLSource'

_OPERATING_SYSTEM_VER = 'OperatingSystemVersion'

_REF_CODE = 'ReferenceCode'
_MIGRATION_STATE = 'MigrationState'

_LPAR_EL_ORDER = bp.BP_EL_ORDER + (
    _LPAR_ASSOCIATED_GROUPS, _LPAR_ASSOCIATED_TASKS, _LPAR_VFCA, _LPAR_VSCA,
    _LPAR_DED_NICS, _SRR, _RESTRICTED_IO, _DESIGNATED_IPL_SRC)


class IPLSrc(object):
    """Mirror of IPLSource.Enum."""
    A = 'a'
    B = 'b'
    C = 'c'
    D = 'd'
    UNKNOWN = 'Unknown'
    ALL_VALUES = (A, B, C, D, UNKNOWN)


@ewrap.EntryWrapper.pvm_type('LogicalPartition',
                             child_order=_LPAR_EL_ORDER)
class LPAR(bp.BasePartition, ewrap.WrapperSetUUIDMixin):

    @classmethod
    def bld(cls, adapter, name, mem_cfg, proc_cfg, env=bp.LPARType.AIXLINUX,
            io_cfg=None):
        """Creates an LPAR wrapper.

        Thin wrapper around BasePartition._bld_base, defaulting env.
        """
        return super(LPAR, cls)._bld_base(adapter, name, mem_cfg, proc_cfg,
                                          env, io_cfg)

    def check_modification_ability(self, ok_if_off=True):
        """Determines if a LPAR is capable of adding/removing HW.

        There are many different scenarios that require checking the state of
        a system to determine if HW can be added or removed.  This may be:
         - Adding/Removing a NIC
         - Adding/Removing a VFC or SCSI mapping
         - Performing a live migration
         - etc...

        This method will return if a VM is capable of adding/removing hardware.

        :param lpar_w: The LPAR wrapper.
        :param ok_if_off: (Optional, Default True) If set to true, will return
                          that the LPAR is modifiable if the system is powered
                          off.
        :return capable: True if HW can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        # If we are in the LPAR, we have access to the operating system type.
        # If it is an OS400 type, then we can add/remove HW no matter what.
        if self.operating_system == bp.LPARType.OS400:
            return True, None

        # Delegate the other checks to the parent.
        return super(LPAR, self).check_modification_ability()

    @property
    def migration_state(self):
        """See PartitionMigrationStateEnum.

        e.g. 'Not_Migrating', 'Migration_Starting', 'Migration_Failed', etc.
        Defaults to 'Not_Migrating'
        """
        return self._get_val_str(_MIGRATION_STATE, 'Not_Migrating')

    @property
    def operating_system(self):
        """String representing the OS and version, or 'Unknown'."""
        return self._get_val_str(_OPERATING_SYSTEM_VER, 'Unknown')

    @property
    def srr_enabled(self):
        """Simplied remote restart.

        :returns: Returns SRR config boolean
        """
        return self._get_val_bool(_SRR, False)

    @srr_enabled.setter
    def srr_enabled(self, value):
        self.set_parm_value(_SRR, u.sanitize_bool_for_api(value),
                            attrib=pc.ATTR_SCHEMA120)

    @property
    def ref_code(self):
        return self._get_val_str(_REF_CODE)

    @property
    def restrictedio(self):
        return self._get_val_bool(_RESTRICTED_IO, False)

    @property
    def desig_ipl_src(self):
        """Designated IPL Source - see IPLSrc enumeration."""
        return self._get_val_str(_DESIGNATED_IPL_SRC)

    @desig_ipl_src.setter
    def desig_ipl_src(self, value):
        """Designated IPL Source - see IPLSrc enumeration."""
        if value not in IPLSrc.ALL_VALUES:
            raise ValueError(_("Invalid IPLSrc '%s'.") % value)
        self.set_parm_value(_DESIGNATED_IPL_SRC, value)

    def set_uuid(self, value):
        # LPAR uuids must be uppercase.
        up_uuid = str(value).upper()
        super(LPAR, self).set_uuid(up_uuid)
        self.set_parm_value(bp._BP_UUID, up_uuid)
