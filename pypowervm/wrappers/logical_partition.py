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

from oslo_log import log as logging

import pypowervm.const as pc
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

_LPAR_VFCA = 'VirtualFibreChannelClientAdapters'
_LPAR_VSCA = 'VirtualSCSIClientAdapters'
_LPAR_DED_NICS = 'DedicatedVirtualNICs'
_LPAR_MIG_STG_VIOS_DATA_STATUS = 'MigrationStorageViosDataStatus'
_LPAR_MIG_STG_VIOS_DATA_TIME = 'MigrationStorageViosDataTimestamp'
_LPAR_RR = 'RemoteRestartCapable'
_LPAR_SRR = 'SimplifiedRemoteRestartCapable'
_LPAR_HAS_DED_PROCS_FOR_MIG = 'HasDedicatedProcessorsForMigration'
_LPAR_SUSPEND_CAP = 'SuspendCapable'
_LPAR_MIG_STATE = 'MigrationState'
_LPAR_RR_STATE = 'RemoteRestartState'
_LPAR_POWER_MGT_MODE = 'PowerManagementMode'
_LPAR_USES_HSL_OPTICONN = 'UsesHighSpeedLinkOpticonnect'
_LPAR_USES_VIRT_OPTICONN = 'UsesVirtualOpticonnect'
_LPAR_VFC_CLIENT_ADPTS = 'VirtualFibreChannelClientAdapters'
_LPAR_VSCSI_CLIENT_ADPTS = 'VirtualSCSIClientAdapters'
_LPAR_RESTRICTED_IO = 'IsRestrictedIOPartition'
_LPAR_STG_DEV_UDID = 'StorageDeviceUniqueDeviceID'
_LPAR_DES_IPL_SRC = 'DesignatedIPLSource'
_LPAR_DED_VNICS = 'DedicatedVirtualNICs'

_LPAR_EL_ORDER = bp.BP_EL_ORDER + (
    _LPAR_VFCA, _LPAR_VSCA, _LPAR_DED_NICS, _LPAR_MIG_STG_VIOS_DATA_STATUS,
    _LPAR_MIG_STG_VIOS_DATA_TIME, _LPAR_RR, _LPAR_SRR,
    _LPAR_HAS_DED_PROCS_FOR_MIG, _LPAR_SUSPEND_CAP, _LPAR_MIG_STATE,
    _LPAR_RR_STATE, _LPAR_POWER_MGT_MODE, _LPAR_USES_HSL_OPTICONN,
    _LPAR_USES_VIRT_OPTICONN, _LPAR_VFC_CLIENT_ADPTS, _LPAR_VSCSI_CLIENT_ADPTS,
    _LPAR_RESTRICTED_IO, _LPAR_STG_DEV_UDID, _LPAR_DES_IPL_SRC,
    _LPAR_DED_VNICS)


class IPLSrc(object):
    """Mirror of IPLSource.Enum (relevant to IBMi partitions only).

    Valid values for:
    - LPAR.desig_ipl_src
    - 'iIPLsource' param in pypowervm.power.power_on.

    Example usage:
    - ilpar.desig_ipl_src = IPLSrc.C
      ilpar.update()
    - power_on(..., add_parms={IPLSrc.KEY: IPLSrc.A, ...})
    """
    KEY = 'iIPLsource'
    A = 'a'
    B = 'b'
    C = 'c'
    D = 'd'
    UNKNOWN = 'Unknown'
    ALL_VALUES = (A, B, C, D, UNKNOWN)


class RRState(object):
    """Remote Restart states - mirror of PartitionRemoteRestart.Enum."""
    INVALID = "Invalid"
    RR_ABLE = "Remote_Restartable"
    SRC_RRING = "Source_Remote_Restarting"
    DEST_RRING = "Destination_Remote_Restarting"
    REM_RESTARTED = "Remote_Restarted"
    PROF_RESTORED = "Profile_Restored"
    RES_STG_DEV_UPD_FAIL = "Reserved_Storage_Device_Update_Failed"
    FORCED_SRC_RESTART = "Forced_Source_Side_Restart"
    SRC_CLEANUP_FAIL = "Source_Side_Cleanup_Failed"
    RES_STG_DEV_UPD_FAIL_W_OVRD = ("Reserved_Storage_Device_Update_Failed_With"
                                   "_Override")
    RR_ABLE_SUSPENDED = "Remote_Restartable_Suspended"
    LOC_UPD_FAIL = "Local_Update_Failed"
    PART_UPD = "Partial_Update"
    STALE_DATA = "Stale_Data"
    LOC_DATA_VALID = "Local_Data_Valid"
    OUT_OF_SPACE = "Out_Of_Space"
    LOC_DATA_INVALID = "Local_Data_Invalid"
    DEST_RR_ED = "Destination_Remote_Restarted"
    SRC_RRING_SUSPENDED = "Source_Remote_Restarting_Suspended"
    LOC_STG_UPD_FAIL = "Local_Storage_Update_Failed"
    PG_DEV_UPD_OVRD = "Page_Device_Update_Override"


class BootStorageType(object):
    """Enumeration of possible storage connection methods for devices."""
    VSCSI = 'vscsi'
    VFC = 'npiv'
    UNKNOWN = 'Unknown'
    ALL_VALUES = (VSCSI, VFC, UNKNOWN)


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

    def _can_modify(self, dlpar_cap, cap_desc):
        """Checks to determine if the LPAR can be modified.

        :param dlpar_cap: The appropriate DLPAR attribute to validate.  Only
                          used if system is active.
        :param cap_desc: A translated string indicating the DLPAR capability.
        :return capable: True if HW can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        # If we are in the LPAR, we have access to the operating system type.
        # If it is an OS400 type, then we can add/remove HW no matter what.
        if self.env == bp.LPARType.OS400:
            return True, None

        # First check is the not activated state
        if self.state == bp.LPARState.NOT_ACTIVATED:
            return True, None

        if self.rmc_state != bp.RMCState.ACTIVE:
            return False, _('LPAR does not have an active RMC connection.')
        if not dlpar_cap:
            return False, _('LPAR does not have an active DLPAR capability '
                            'for %s.') % cap_desc
        return True, None

    def can_modify_io(self):
        """Determines if a LPAR is capable of adding/removing I/O HW.

        :return capable: True if HW can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        return self._can_modify(self.capabilities.io_dlpar, _('I/O'))

    def can_modify_mem(self):
        """Determines if a LPAR is capable of adding/removing Memory.

        :return capable: True if memory can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        return self._can_modify(self.capabilities.mem_dlpar, _('Memory'))

    def can_modify_proc(self):
        """Determines if a LPAR is capable of adding/removing processors.

        :return capable: True if procs can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        return self._can_modify(self.capabilities.proc_dlpar, _('Processors'))

    def can_lpm(self, host_w):
        """Determines if a LPAR is ready for Live Partition Migration.

        This check does not validate that the target system is capable of
        handling the LPAR.  It simply validates that the LPAR has the
        essential capabilities in place for a LPM operation.

        :param host_w: The host wrapper for the system.
        :return capable: True if the LPAR is LPM capable.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of LPM.  If capable is True, the reason will
                        be None.
        """
        # First check is the not activated state
        if self.state != bp.LPARState.RUNNING:
            return False, _("LPAR is not in an active state.")

        if self.env == bp.LPARType.OS400:
            # IBM i does not require RMC, but does need to check for
            # restricted I/O.
            if not self.restrictedio:
                return False, _('IBM i LPAR does not have restricted I/O.')

            c = host_w.get_capabilities().get('ibmi_lpar_mobility_capable')
            if not c:
                return False, _('Source system does not have the IBM i LPAR '
                                'Mobility Capability.')

            compat_mode = host_w.highest_compat_mode()
            if compat_mode < 7:
                return False, _('IBM i LPAR Live Migration is only supported '
                                'on POWER7 and higher systems.')
        elif self.rmc_state != bp.RMCState.ACTIVE:
            return False, _('LPAR does not have an active RMC connection.')

        c = self.capabilities
        if not (c.mem_dlpar and c.proc_dlpar):
            return False, _('LPAR is not available for LPM due to missing '
                            'DLPAR capabilities.')
        return True, None

    @property
    def migration_state(self):
        """See PartitionMigrationStateEnum.

        e.g. 'Not_Migrating', 'Migration_Starting', 'Migration_Failed', etc.
        Defaults to 'Not_Migrating'
        """
        return self._get_val_str(_LPAR_MIG_STATE, 'Not_Migrating')

    @property
    def rr_enabled(self):
        """Remote Restart capable?"""
        return self._get_val_bool(_LPAR_RR, False)

    @rr_enabled.setter
    def rr_enabled(self, value):
        """Turn Remote Restart on or off.

        LPAR must be powered off.
        """
        self.set_parm_value(_LPAR_RR, u.sanitize_bool_for_api(value))

    @property
    def rr_state(self):
        return self._get_val_str(_LPAR_RR_STATE)

    @property
    def srr_enabled(self):
        """Simplied remote restart.

        :returns: Returns SRR config boolean
        """
        return self._get_val_bool(_LPAR_SRR, False)

    @srr_enabled.setter
    def srr_enabled(self, value):
        self.set_parm_value(_LPAR_SRR, u.sanitize_bool_for_api(value),
                            attrib=pc.ATTR_SCHEMA120)

    @property
    def restrictedio(self):
        return self._get_val_bool(_LPAR_RESTRICTED_IO, False)

    @restrictedio.setter
    def restrictedio(self, value):
        self.set_parm_value(_LPAR_RESTRICTED_IO,
                            u.sanitize_bool_for_api(value))

    @property
    def desig_ipl_src(self):
        """Designated IPL Source - see IPLSrc enumeration."""
        return self._get_val_str(_LPAR_DES_IPL_SRC)

    @desig_ipl_src.setter
    def desig_ipl_src(self, value):
        """Designated IPL Source - see IPLSrc enumeration."""
        if value not in IPLSrc.ALL_VALUES:
            raise ValueError(_("Invalid IPLSrc '%s'.") % value)
        self.set_parm_value(_LPAR_DES_IPL_SRC, value)

    def set_uuid(self, value):
        # LPAR uuids must be uppercase.
        up_uuid = str(value).upper()
        super(LPAR, self).set_uuid(up_uuid)
        self.set_parm_value(bp._BP_UUID, up_uuid)
