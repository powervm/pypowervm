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

from oslo_log import log as logging

from pypowervm.i18n import _
from pypowervm.wrappers import entry_wrapper
from pypowervm.wrappers import mtms

LOG = logging.getLogger(__name__)

_POOL_ID = 'PoolID'
_POOL_NAME = 'PoolName'

_COMPLIANCE_STATE = 'ComplianceState'
_COMPLIANCE_REMAINING_HOURS = 'ComplianceRemainingHours'
_PROC_COMPLIANCE_REMAINING_HOURS = 'ProcComplianceRemainingHours'
_MEM_COMPLIANCE_REMAINING_HOURS = 'MemComplianceRemainingHours'

_TOTAL_MOBILE_COD_PROC_UNITS = 'TotalMobileCoDProcUnits'
_AVAILABLE_MOBILE_COD_PROC_UNITS = 'AvailableMobileCoDProcUnits'
_UNRETURNED_MOBILE_COD_PROC_UNITS = 'UnreturnedMobileCoDProcUnits'
_TOTAL_MOBILE_COD_MEMORY = 'TotalMobileCoDMemory'
_AVAILABLE_MOBILE_COD_MEMORY = 'AvailableMobileCoDMemory'
_UNRETURNED_MOBILE_COD_MEMORY = 'UnreturnedMobileCoDMemory'

_MOBILE_COD_PROC_UNITS = 'MobileCoDProcUnits'
_MOBILE_COD_MEMORY = 'MobileCoDMemory'
_INACTIVE_PROC_UNITS = 'InactiveProcUnits'
_INACTIVE_MEMORY = 'InactiveMemory'

_SYS_NAME = 'ManagedSystemName'
_SYS_INSTALLED_PROC_UNITS = 'ManagedSystemInstalledProcUnits'
_SYS_INSTALLED_MEMORY = 'ManagedSystemInstalledMemory'
_SYS_MTMS = 'ManagedSystemMachineTypeModelSerialNumber'

_MGMT_CONSOLES = 'PowerEnterprisePoolManagementConsoles'
_MGMT_CONSOLE = 'PowerEnterprisePoolManagementConsole'
_MGMT_CONSOLE_MTMS = 'ManagementConsoleMachineTypeModelSerialNumber'
_IS_MASTER_CONSOLE = 'IsMasterConsole'


class ComplianceState(object):
    IN_COMPLIANCE = 'InCompliance'
    # TODO(tpeoples): find out what these values are exactly
    WITHIN_SERVER_GRACE_PERIOD = ('ApproachingOutOfCompliance'
                                  'WithinServerGracePeriod')
    WITHIN_POOL_GRACE_PERIOD = ('ApproachingOutOfCompliance'
                                'WithinPoolGracePeriod')
    OUT_OF_COMPLIANCE = 'OutOfCompliance'


@entry_wrapper.EntryWrapper.pvm_type('PowerEnterprisePool')
class EnterprisePool(entry_wrapper.EntryWrapper):
    """Wraps the EnterprisePool entries."""

    @property
    def id(self):
        """Integer enterprise pool ID."""
        return self._get_val_int(_POOL_ID)

    @property
    def name(self):
        """The name of the enterprise pool."""
        return self._get_val_str(_POOL_NAME)

    @property
    def compliance_state(self):
        """The compliance state of the enterprise pool."""
        return self._get_val_str(_COMPLIANCE_STATE)

    @property
    def compliance_remaining_hours(self):
        """Integer num of hours until the pool is considered out of compliance.

        Note: will only be included in the response if xag is specified to be
        not None.
        """
        return self._get_val_int(_COMPLIANCE_REMAINING_HOURS)

    @property
    def total_mobile_proc_units(self):
        """Integer num of the total mobile CoD proc units in the pool."""
        return self._get_val_int(_TOTAL_MOBILE_COD_PROC_UNITS)

    @property
    def available_mobile_proc_units(self):
        """Integer num of the available mobile CoD proc units in the pool."""
        return self._get_val_int(_AVAILABLE_MOBILE_COD_PROC_UNITS, default=0)

    @property
    def unreturned_mobile_proc_units(self):
        """Integer num of the unreturned mobile CoD proc units in the pool."""
        return self._get_val_int(_UNRETURNED_MOBILE_COD_PROC_UNITS)

    @property
    def total_mobile_memory(self):
        """Integer num of the total mobile CoD memory in the pool."""
        return self._get_val_int(_TOTAL_MOBILE_COD_MEMORY)

    @property
    def available_mobile_memory(self):
        """Integer num of the available mobile CoD memory in the pool."""
        return self._get_val_int(_AVAILABLE_MOBILE_COD_MEMORY, default=0)

    @property
    def unreturned_mobile_memory(self):
        """Integer num of the unreturned mobile CoD memory in the pool."""
        return self._get_val_int(_UNRETURNED_MOBILE_COD_MEMORY)

    @property
    def management_consoles(self):
        # TODO(tpeoples): return all of the management consoles info
        pass

    @property
    def master_console_mtms(self):
        """The master console MTMS (machine type, model, serial number)."""
        mgmt_consoles_element = self._find(_MGMT_CONSOLES)

        if not mgmt_consoles_element:
            self.log_missing_value(_MGMT_CONSOLES)
            return None

        mgmt_console_elements = mgmt_consoles_element.findall(_MGMT_CONSOLE)

        master_console_mtms = None
        for mgmt_console_element in mgmt_console_elements:
            is_master_console = mgmt_console_element.findtext(
                _IS_MASTER_CONSOLE)

            if not is_master_console:
                self.log_missing_value(_IS_MASTER_CONSOLE)
                continue

            if is_master_console.lower() != 'true':
                continue

            # This is the master management console element, so find the mtms
            mtms_element = mgmt_console_element.find(_MGMT_CONSOLE_MTMS)

            if not mtms_element:
                self.log_missing_value(_MGMT_CONSOLE_MTMS)
                continue

            mtms_wrapper = mtms.MTMS.wrap(mtms_element)
            master_console_mtms = mtms_wrapper.mtms_str
            break
        else:
            LOG.error(_('Unable to determine master management console MTMS '
                        '(machine type, model, serial number) from '
                        '%(identifier)s because no %(param)s was marked as '
                        'the master console for the pool.') %
                      {'identifier': self._type_and_uuid,
                       'param': _MGMT_CONSOLE})

        return master_console_mtms


@entry_wrapper.EntryWrapper.pvm_type('PowerEnterprisePoolMember')
class EnterprisePoolMember(entry_wrapper.EntryWrapper):
    """Wraps the EnterprisePoolMember entries."""

    @property
    def mobile_proc_units(self):
        """Integer num of the mobile CoD proc units on the system."""
        return self._get_val_int(_MOBILE_COD_PROC_UNITS)

    @mobile_proc_units.setter
    def mobile_proc_units(self, value):
        self.set_parm_value(_MOBILE_COD_PROC_UNITS, value)

    @property
    def mobile_memory(self):
        """Integer amount of mobile CoD memory on the system."""
        return self._get_val_int(_MOBILE_COD_MEMORY)

    @mobile_memory.setter
    def mobile_memory(self, value):
        self.set_parm_value(_MOBILE_COD_MEMORY, value)

    @property
    def inactive_proc_units(self):
        """Integer num of the inactive (dark) proc units on the system."""
        return self._get_val_int(_INACTIVE_PROC_UNITS)

    @property
    def inactive_memory(self):
        """Integer amount of inactive (dark) memory on the system."""
        return self._get_val_int(_INACTIVE_MEMORY)

    @property
    def unreturned_mobile_proc_units(self):
        """Integer num of the unreturned mobile CoD proc units on the sys."""
        return self._get_val_int(_UNRETURNED_MOBILE_COD_PROC_UNITS)

    @property
    def unreturned_mobile_memory(self):
        """Integer amount of unreturned mobile CoD memory on the system."""
        return self._get_val_int(_UNRETURNED_MOBILE_COD_MEMORY)

    @property
    def proc_compliance_remaining_hours(self):
        """Integer num of hours remaining until the sys is...

        considered out of compliance in terms of mobile proc units.

        Note: will only be included in the response if xag is specified to be
        not None.
        """
        return self._get_val_int(_PROC_COMPLIANCE_REMAINING_HOURS)

    @property
    def mem_compliance_remaining_hours(self):
        """Integer num of the hours remaining until the sys is...

        considered out of compliance in terms of mobile memory.

        Note: will only be included in the response if xag is specified to be
        not None.
        """
        return self._get_val_int(_MEM_COMPLIANCE_REMAINING_HOURS)

    @property
    def system_name(self):
        """The name of the system that corresponds to this pool member."""
        return self._get_val_str(_SYS_NAME)

    @property
    def system_installed_proc_units(self):
        """Integer num of the installed proc units on the system."""
        return self._get_val_int(_SYS_INSTALLED_PROC_UNITS)

    @property
    def system_installed_memory(self):
        """Integer amount of installed memory on the system."""
        return self._get_val_int(_SYS_INSTALLED_MEMORY)

    @property
    def system_mtms(self):
        """The MTMS (machine type, model, serial number) of the system."""
        sys_mtms_element = self._find(_SYS_MTMS)
        sys_mtms_wrapper = mtms.MTMS.wrap(sys_mtms_element)
        return sys_mtms_wrapper.mtms_str

    @property
    def management_consoles(self):
        # TODO(tpeoples): do we need this?
        pass
