# Copyright 2016 IBM Corp.
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
from pypowervm.i18n import _


class dlpar_capable (object):
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
        # First check is the not activated state
        if self.state == LPARState.NOT_ACTIVATED:
            return True, None
        if self.rmc_state != RMCState.ACTIVE and not self.is_mgmt_partition:
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

    def can_lpm(self, host_w, migr_data=None):
        """Determines if a LPAR is ready for Live Partition Migration.

        This check validates that the target system is capable of
        handling the LPAR if the LPAR is an IBMi.  It simply validates that
        the LPAR has the essential capabilities in place for a LPM operation.

        :param host_w: The host wrapper for the system.
        :param migr_data: The dictionary of migration data for the target host.
                          If parameters are not passed in, will skip the check
                          and let the low levels surface related error.
                          The supported key today is:
                          - ibmi_lpar_mobility_capable: Boolean
                          TODO(IBM): add more destination checks here. Ex.
                          migrate an AIX or IBMi VM to a Linux only host.
        :return capable: True if the LPAR is LPM capable.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of LPM.  If capable is True, the reason will
                        be None.
        """
        return False


class LPARState(object):
    """State of a given LPAR.

    From LogicalPartitionStateEnum.
    """
    ERROR = 'error'
    NOT_ACTIVATED = 'not activated'
    NOT_AVAILBLE = 'not available'
    OPEN_FIRMWARE = 'open firmware'
    RUNNING = 'running'
    SHUTTING_DOWN = 'shutting down'
    STARTING = 'starting'
    MIGRATING_NOT_ACTIVE = 'migrating not active'
    MIGRATING_RUNNING = 'migrating running'
    HARDWARE_DISCOVERY = 'hardware discovery'
    SUSPENDED = 'suspended'
    SUSPENDING = 'suspending'
    RESUMING = 'resuming'
    UNKNOWN = 'Unknown'


class RMCState(object):
    """Various RMC States.

    From ResourceMonitoringControlStateEnum.
    """
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    NONE = 'none'
    UNKNOWN = 'unknown'
    BUSY = 'busy'
