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
from pypowervm.wrappers import mtms as mtms_wrapper

LOG = logging.getLogger(__name__)


_POWER_ENTERPRISE_POOL = 'PowerEnterprisePool'
_POWER_ENTERPRISE_POOL_MEMBER = 'PowerEnterprisePoolMember'

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
_SYS_STATE = 'State'

_MGMT_CONSOLES = 'PowerEnterprisePoolManagementConsoles'
_MGMT_CONSOLE = 'PowerEnterprisePoolManagementConsole'
_MGMT_CONSOLE_NAME = 'ManagementConsoleName'
_MGMT_CONSOLE_MTMS = 'ManagementConsoleMachineTypeModelSerialNumber'
_MGMT_CONSOLE_IS_MASTER_CONSOLE = 'IsMasterConsole'
_MGMT_CONSOLE_IP_ADDR = 'ManagementConsoleIPAddress'


class ComplianceState(object):
    IN_COMPLIANCE = 'InCompliance'
    OUT_OF_COMPLIANCE = 'OutOfCompliance'


@entry_wrapper.EntryWrapper.pvm_type(_POWER_ENTERPRISE_POOL, has_metadata=True)
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
        """Returns a WrapperElemList of EnterprisePoolManagementConsole's."""
        elem = self._find(_MGMT_CONSOLES)
        return entry_wrapper.WrapperElemList(
            elem, EnterprisePoolManagementConsole)

    @property
    def master_console_mtms(self):
        """The master console MTMS (machine type, model, serial number)."""
        master_console_mtms = None

        for console in self.management_consoles:
            if console.is_master_console:
                master_console_mtms = console.mtms.mtms_str
                break
        else:
            LOG.error(_('Unable to determine master management console MTMS '
                        '(machine type, model, serial number) from '
                        '%(identifier)s because no %(param)s was marked as '
                        'the master console for the pool.') %
                      {'identifier': self._type_and_uuid,
                       'param': _MGMT_CONSOLE})

        return master_console_mtms


@entry_wrapper.EntryWrapper.pvm_type(_POWER_ENTERPRISE_POOL_MEMBER,
                                     has_metadata=True)
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
        sys_mtms_wrapper = mtms_wrapper.MTMS.wrap(sys_mtms_element)
        return sys_mtms_wrapper.mtms_str

    @property
    def system_state(self):
        """The state of the system."""
        return self._get_val_str(_SYS_STATE)


@entry_wrapper.ElementWrapper.pvm_type(_MGMT_CONSOLE,
                                       has_metadata=True)
class EnterprisePoolManagementConsole(entry_wrapper.ElementWrapper):
    """Wraps the EnterprisePoolManagementConsole elements."""

    @property
    def name(self):
        """String value for the name of the management console."""
        return self._get_val_str(_MGMT_CONSOLE_NAME)

    @property
    def mtms(self):
        """The MTMS (machine type, model, serial number) of the console."""
        return mtms_wrapper.MTMS.wrap(self.element.find(_MGMT_CONSOLE_MTMS))

    @property
    def is_master_console(self):
        """Boolean for whether or not this console is master for the pool."""
        return self._get_val_bool(_MGMT_CONSOLE_IS_MASTER_CONSOLE)

    @property
    def ip_address(self):
        """String value for the IP address of the console."""
        return self._get_val_str(_MGMT_CONSOLE_IP_ADDR)
