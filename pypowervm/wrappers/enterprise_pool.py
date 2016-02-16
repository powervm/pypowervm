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

from pypowervm import const
from pypowervm.i18n import _
from pypowervm.wrappers import entry_wrapper
from pypowervm.wrappers import mtms as mtms_wrapper

LOG = logging.getLogger(__name__)


_POWER_ENTERPRISE_POOL = 'PowerEnterprisePool'
_POWER_ENTERPRISE_POOL_MEMBER = 'PowerEnterprisePoolMember'

_P_POOL_ID = 'PoolID'
_P_POOL_NAME = 'PoolName'

_P_COMPLIANCE_STATE = 'ComplianceState'
_P_COMPLIANCE_REMAINING_HOURS = 'ComplianceRemainingHours'
_PM_PROC_COMPLIANCE_HOURS_LEFT = 'ProcComplianceRemainingHours'
_PM_MEM_COMPLIANCE_HOURS_LEFT = 'MemComplianceRemainingHours'

_P_TOTAL_MOBILE_PROCS = 'TotalMobileCoDProcUnits'
_P_AVAIL_MOBILE_PROCS = 'AvailableMobileCoDProcUnits'
_UNRET_MOBILE_PROCS = 'UnreturnedMobileCoDProcUnits'
_P_TOTAL_MOBILE_MEM = 'TotalMobileCoDMemory'
_P_AVAIL_MOBILE_MEM = 'AvailableMobileCoDMemory'
_UNRET_MOBILE_MEM = 'UnreturnedMobileCoDMemory'

_PM_MOBILE_PROCS = 'MobileCoDProcUnits'
_PM_MOBILE_MEM = 'MobileCoDMemory'
_PM_INACTIVE_PROCS = 'InactiveProcUnits'
_PM_INACTIVE_MEM = 'InactiveMemory'

_PM_SYS_NAME = 'ManagedSystemName'
_PM_SYS_INSTALLED_PROCS = 'ManagedSystemInstalledProcUnits'
_PM_SYS_INSTALLED_MEM = 'ManagedSystemInstalledMemory'
_PM_SYS_MTMS = 'ManagedSystemMachineTypeModelSerialNumber'
_PM_SYS_STATE = 'ManagedSystemState'

_MGMT_CONSOLES = 'PowerEnterprisePoolManagementConsoles'
_MGMT_CONSOLE = 'PowerEnterprisePoolManagementConsole'
_MGMT_CONSOLE_NAME = 'ManagementConsoleName'
_MGMT_CONSOLE_MTMS = 'ManagementConsoleMachineTypeModelSerialNumber'
_MGMT_CONSOLE_IS_MASTER_CONSOLE = 'IsMasterConsole'
_MGMT_CONSOLE_IP_ADDR = 'ManagementConsoleIPAddress'


class ComplianceState(object):
    IN_COMPLIANCE = 'InCompliance'
    APPROACHING_OUT_OF_COMPLIANCE_SERVER = 'ApproachingOutOfComplianceServer'
    APPROACHING_OUT_OF_COMPLIANCE_POOL = 'ApproachingOutOfCompliancePool'
    OUT_OF_COMPLIANCE = 'OutOfCompliance'
    UNAVAILABLE = 'Unavailable'


@entry_wrapper.EntryWrapper.pvm_type(_POWER_ENTERPRISE_POOL, has_metadata=True)
class Pool(entry_wrapper.EntryWrapper):
    """Wraps the Pool entries."""

    @property
    def id(self):
        """Integer enterprise pool ID."""
        return self._get_val_int(_P_POOL_ID)

    @property
    def name(self):
        """The name of the enterprise pool."""
        return self._get_val_str(_P_POOL_NAME)

    @property
    def compliance_state(self):
        """The compliance state of the enterprise pool."""
        return self._get_val_str(_P_COMPLIANCE_STATE)

    @entry_wrapper.Wrapper.xag_property(const.XAG.ADV)
    def compliance_hours_left(self):
        """Integer num of hours until the pool is considered out of compliance.

        Return default of 0 if it is not found.
        """
        return self._get_val_int(_P_COMPLIANCE_REMAINING_HOURS, default=0)

    @property
    def total_mobile_procs(self):
        """Integer num of the total mobile CoD proc units in the pool."""
        return self._get_val_int(_P_TOTAL_MOBILE_PROCS)

    @property
    def avail_mobile_procs(self):
        """Integer num of the available mobile CoD proc units in the pool."""
        return self._get_val_int(_P_AVAIL_MOBILE_PROCS, default=0)

    @property
    def unret_mobile_procs(self):
        """Integer num of the unreturned mobile CoD proc units in the pool."""
        return self._get_val_int(_UNRET_MOBILE_PROCS)

    @property
    def total_mobile_mem(self):
        """Integer num of the total mobile CoD memory (GB) in the pool."""
        return self._get_val_int(_P_TOTAL_MOBILE_MEM)

    @property
    def avail_mobile_mem(self):
        """Integer num of the available mobile CoD memory (GB) in the pool."""
        return self._get_val_int(_P_AVAIL_MOBILE_MEM, default=0)

    @property
    def unret_mobile_mem(self):
        """Integer num of the unreturned mobile CoD memory (GB) in the pool."""
        return self._get_val_int(_UNRET_MOBILE_MEM)

    @property
    def mgmt_consoles(self):
        """Returns a WrapperElemList of PoolMgmtConsole's."""
        elem = self._find_or_seed(_MGMT_CONSOLES)
        return entry_wrapper.WrapperElemList(
            elem, PoolMgmtConsole)

    @property
    def master_console_mtms(self):
        """The master console MTMS (machine type, model, serial number)."""
        for console in self.mgmt_consoles:
            if console.is_master_console:
                return console.mtms

        LOG.error(_('Unable to determine master management console MTMS '
                    '(machine type, model, serial number) from '
                    '%(identifier)s because no %(param)s was marked as the '
                    'master console for the pool.') %
                  {'identifier': self._type_and_uuid,
                   'param': _MGMT_CONSOLE})

        return None


@entry_wrapper.EntryWrapper.pvm_type(_POWER_ENTERPRISE_POOL_MEMBER,
                                     has_metadata=True)
class PoolMember(entry_wrapper.EntryWrapper):
    """Wraps the PoolMember entries."""

    @property
    def mobile_procs(self):
        """Integer num of the mobile CoD proc units on the system."""
        return self._get_val_int(_PM_MOBILE_PROCS)

    @mobile_procs.setter
    def mobile_procs(self, value):
        self.set_parm_value(_PM_MOBILE_PROCS, value)

    @property
    def mobile_mem(self):
        """Integer amount of mobile CoD memory (GB) on the system."""
        return self._get_val_int(_PM_MOBILE_MEM)

    @mobile_mem.setter
    def mobile_mem(self, value):
        self.set_parm_value(_PM_MOBILE_MEM, value)

    @property
    def inactive_procs(self):
        """Integer num of the inactive (dark) proc units on the system."""
        return self._get_val_int(_PM_INACTIVE_PROCS)

    @property
    def inactive_mem(self):
        """Integer amount of inactive (dark) memory (GB) on the system."""
        return self._get_val_int(_PM_INACTIVE_MEM)

    @property
    def unret_mobile_procs(self):
        """Integer num of the unreturned mobile CoD proc units on the sys."""
        return self._get_val_int(_UNRET_MOBILE_PROCS)

    @property
    def unret_mobile_mem(self):
        """Integer amount of unreturned mobile CoD memory (GB) on the sys."""
        return self._get_val_int(_UNRET_MOBILE_MEM)

    @entry_wrapper.Wrapper.xag_property(const.XAG.ADV)
    def proc_compliance_hours_left(self):
        """Integer num of proc compliance hours remaining.

        Number of hours remaining until the system is considered out of
        compliance in terms of mobile procs.

        Return default of 0 if it is not found.
        """
        return self._get_val_int(_PM_PROC_COMPLIANCE_HOURS_LEFT, default=0)

    @entry_wrapper.Wrapper.xag_property(const.XAG.ADV)
    def mem_compliance_hours_left(self):
        """Integer num of memory compliance hours remaining.

        Number of hours remaining until the system is considered out of
        compliance in terms of mobile memory.

        Return default of 0 if it is not found.
        """
        return self._get_val_int(_PM_MEM_COMPLIANCE_HOURS_LEFT, default=0)

    @property
    def sys_name(self):
        """The name of the system that corresponds to this pool member."""
        return self._get_val_str(_PM_SYS_NAME)

    @property
    def sys_installed_procs(self):
        """Integer num of the installed proc units on the system."""
        return self._get_val_int(_PM_SYS_INSTALLED_PROCS)

    @property
    def sys_installed_mem(self):
        """Integer amount of installed memory (MB) on the system."""
        return self._get_val_int(_PM_SYS_INSTALLED_MEM)

    @property
    def sys_mtms(self):
        """The MTMS (machine type, model, serial number) of the system."""
        sys_mtms_element = self._find(_PM_SYS_MTMS)
        return mtms_wrapper.MTMS.wrap(sys_mtms_element)

    @property
    def sys_state(self):
        """The state of the system."""
        return self._get_val_str(_PM_SYS_STATE)

    @property
    def mgmt_consoles(self):
        """Returns a WrapperElemList of PoolMgmtConsole's."""
        elem = self._find_or_seed(_MGMT_CONSOLES)
        return entry_wrapper.WrapperElemList(
            elem, PoolMgmtConsole)


@entry_wrapper.ElementWrapper.pvm_type(_MGMT_CONSOLE,
                                       has_metadata=True)
class PoolMgmtConsole(entry_wrapper.ElementWrapper):
    """Wraps the PoolMgmtConsole elements."""

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
    def ip_addr(self):
        """String value for the IP address of the console."""
        return self._get_val_str(_MGMT_CONSOLE_IP_ADDR)
