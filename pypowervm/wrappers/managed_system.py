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

"""Wrappers, constants, and helpers around ManagedSystem and its children."""

import pypowervm.const as c
import pypowervm.util as u
import pypowervm.wrappers.common_wrap as cwrap
import pypowervm.wrappers.entry_wrapper as ewrap

import logging

LOG = logging.getLogger(__name__)

# ManagedSystem XPath constants
_PRIMARY_IP_ADDRESS = 'PrimaryIPAddress'
_HOST_IP_ADDRESS = _PRIMARY_IP_ADDRESS
_STATE = 'State'
_SYSTEM_NAME = 'SystemName'

_SYS_CAPABILITIES = 'AssociatedSystemCapabilities'
_ACTIVE_LPM_CAP = u.xpath(
    _SYS_CAPABILITIES, 'ActiveLogicalPartitionMobilityCapable')
_INACTIVE_LPM_CAP = u.xpath(
    _SYS_CAPABILITIES, 'InactiveLogicalPartitionMobilityCapable')
_VETH_MAC_ADDR_CAP = u.xpath(
    _SYS_CAPABILITIES, 'VirtualEthernetCustomMACAddressCapable')
_IBMi_LPM_CAP = u.xpath(
    _SYS_CAPABILITIES, 'IBMiLogicalPartitionMobilityCapable')
_IBMi_RESTRICTEDIO_CAP = u.xpath(
    _SYS_CAPABILITIES, 'IBMiRestrictedIOModeCapable')
_SIMP_REMOTE_RESTART_CAP = u.xpath(
    _SYS_CAPABILITIES, 'PowerVMLogicalPartitionSimplifiedRemoteRestartCapable')

_SYS_MEM_CONFIG = 'AssociatedSystemMemoryConfiguration'
_MEMORY_INSTALLED = u.xpath(_SYS_MEM_CONFIG, 'InstalledSystemMemory')
_MEMORY_AVAIL = u.xpath(_SYS_MEM_CONFIG, 'CurrentAvailableSystemMemory')
_MEMORY_CONFIGURABLE = u.xpath(_SYS_MEM_CONFIG, 'ConfigurableSystemMemory')
_MEMORY_REGION_SIZE = u.xpath(_SYS_MEM_CONFIG, 'MemoryRegionSize')
_SYS_FIRMWARE_MEM = u.xpath(_SYS_MEM_CONFIG, 'MemoryUsedByHypervisor')

# Migration Constants
_SYS_PROC_CONFIG = 'AssociatedSystemProcessorConfiguration'
_PROC_COMPAT_MODES = u.xpath(
    _SYS_PROC_CONFIG, 'SupportedPartitionProcessorCompatibilityModes')
_MIGR_INFO = 'SystemMigrationInformation'
_MAX_ACTIVE_MIGR = u.xpath(_MIGR_INFO, 'MaximumActiveMigrations')
_MAX_INACTIVE_MIGR = u.xpath(_MIGR_INFO, 'MaximumInactiveMigrations')
_ACTIVE_MIGR_RUNNING = u.xpath(
    _MIGR_INFO, 'NumberOfActiveMigrationsInProgress')
_INACTIVE_MIGR_RUNNING = u.xpath(
    _MIGR_INFO, 'NumberOfInactiveMigrationsInProgress')
_MAX_FIRMWARE_MIGR = u.xpath(_MIGR_INFO, 'MaximumFirmwareActiveMigrations')

_PROC_UNITS_INSTALLED = u.xpath(
    _SYS_PROC_CONFIG, 'InstalledSystemProcessorUnits')

_PROC_UNITS_AVAIL = u.xpath(
    _SYS_PROC_CONFIG, 'CurrentAvailableSystemProcessorUnits')

_PROC_UNITS_CONFIGURABLE = u.xpath(
    _SYS_PROC_CONFIG, 'ConfigurableSystemProcessorUnits')

_MAX_PROCS_PER_PARTITION = u.xpath(
    _SYS_PROC_CONFIG, 'CurrentMaximumAllowedProcessorsPerPartition')

_MAX_PROCS_PER_AIX_LINUX_PARTITION = u.xpath(
    _SYS_PROC_CONFIG, 'CurrentMaximumProcessorsPerAIXOrLinuxPartition')

_MAX_VCPUS_PER_PARTITION = u.xpath(
    _SYS_PROC_CONFIG, 'MaximumAllowedVirtualProcessorsPerPartition')

_MAX_VCPUS_PER_AIX_LINUX_PARTITION = u.xpath(
    _SYS_PROC_CONFIG,  'CurrentMaximumVirtualProcessorsPerAIXOrLinuxPartition')

_VIOS_LINK = u.xpath("AssociatedVirtualIOServers", c.LINK)

# AssociatedSystemIOConfig constants
_ASIO_ROOT = 'AssociatedSystemIOConfiguration'
_ASIO_AVAIL_WWPNS = 'AvailableWWPNs'
_ASIO_HCA = 'HostChannelAdapters'
_ASIO_HEA = 'HostEthernetAdapters'
_ASIO_IOBUSES = 'IOBuses'
_ASIO_IOSLOTS = 'IOSlots'
_ASIO_SRIOV = 'SRIOVAdapters'
_ASIO_ASVNET = 'AssociatedSystemVirtualNetwork'
_ASIO_WWPN_PREFIX = 'WWPNPrefix'

_IOSLOT_ROOT = 'IOSlot'
_IOSLOT_BUS_GRP_REQ = 'BusGroupingRequired'
_IOSLOT_DESC = 'Description'
_IOSLOT_FEAT_CODES = 'FeatureCodes'
_IOSLOT_PCI_CLASS = 'PCIClass'
_IOSLOT_PCI_SUB_DEV_ID = 'PCISubsystemDeviceID'
_IOSLOT_PCI_REV_ID = 'PCIRevisionID'
_IOSLOT_PCI_VEND_ID = 'PCIVendorID'
_IOSLOT_PCI_SUB_VEND_ID = 'PCISubsystemVendorID'
_IOSLOT_DYN_REC_CON_INDEX = 'SlotDynamicReconfigurationConnectorIndex'
_IOSLOT_DYN_REC_CON_NAME = 'SlotDynamicReconfigurationConnectorName'


@ewrap.EntryWrapper.pvm_type('ManagedSystem')
class System(ewrap.EntryWrapper):

    @property
    def system_name(self):
        return self._get_val_str(_SYSTEM_NAME)

    @property
    def mtms(self):
        return cwrap.MTMS.wrap(self.element.find(cwrap.MTMS_ROOT))

    @property
    def asio_config(self):
        return ASIOConfig.wrap(self.element.find(_ASIO_ROOT))

    @property
    def system_state(self):
        return self._get_val_str(_STATE, 'unknown')

    @property
    def proc_units(self):
        return self._get_val_str(_PROC_UNITS_INSTALLED, 0)

    @property
    def proc_units_configurable(self):
        return self._get_val_str(_PROC_UNITS_CONFIGURABLE, 0)

    @property
    def proc_units_avail(self):
        return self._get_val_str(_PROC_UNITS_AVAIL, 0)

    @property
    def max_sys_procs_limit(self):
        return self._get_val_int(_MAX_PROCS_PER_PARTITION, 0)

    @property
    def max_procs_per_aix_linux_lpar(self):
        val = self._get_val_int(_MAX_PROCS_PER_AIX_LINUX_PARTITION, 0)
        # Some systems will not have maximum procs per lpar based on
        # partition type. In that case, use system max procs per partition.
        if val == 0:
            val = self.max_sys_procs_limit

        return val

    @max_procs_per_aix_linux_lpar.setter
    def max_procs_per_aix_linux_lpar(self, value):
        self.set_parm_value(_MAX_PROCS_PER_AIX_LINUX_PARTITION, str(value))

    @property
    def max_sys_vcpus_limit(self):
        return self._get_val_int(_MAX_VCPUS_PER_PARTITION, 0)

    @property
    def max_vcpus_per_aix_linux_lpar(self):
        val = self._get_val_int(_MAX_VCPUS_PER_AIX_LINUX_PARTITION, 0)
        # Some systems will not have maximum vcpus per lpar based on
        # partition type. In that case, use system max vcpus per partition.
        if val == 0:
            val = self.max_sys_vcpus_limit

        return val

    @max_vcpus_per_aix_linux_lpar.setter
    def max_vcpus_per_aix_linux_lpar(self, value):
        self.set_parm_value(_MAX_VCPUS_PER_AIX_LINUX_PARTITION, str(value))

    @property
    def memory_total(self):
        return self._get_val_int(_MEMORY_INSTALLED, 0)

    @property
    def memory_free(self):
        return self._get_val_int(_MEMORY_AVAIL, 0)

    @property
    def memory_configurable(self):
        return self._get_val_int(_MEMORY_CONFIGURABLE, 0)

    @property
    def memory_region_size(self):
        return self._get_val_int(_MEMORY_REGION_SIZE, 0)

    @property
    def firmware_memory(self):
        return self._get_val_int(_SYS_FIRMWARE_MEM, 0)

    @property
    def host_ip_address(self):
        prop = _HOST_IP_ADDRESS
        val = self._get_val_str(prop)

        return val

    def get_capabilities(self):
        """returns: The system capabilities from Power."""
        # VirtualEthernetCustomMACAddressCapable (custom_mac_addr_capable) will
        # default to True, which is the correct setting for POWER7 servers.
        cap_data = {'active_lpar_mobility_capable':
                    self._get_val_bool(_ACTIVE_LPM_CAP),
                    'inactive_lpar_mobility_capable':
                    self._get_val_bool(_INACTIVE_LPM_CAP),
                    'ibmi_lpar_mobility_capable':
                    self._get_val_bool(_IBMi_LPM_CAP, False),
                    'custom_mac_addr_capable':
                    self._get_val_bool(_VETH_MAC_ADDR_CAP, True),
                    'ibmi_restrictedio_capable':
                    self._get_val_bool(_IBMi_RESTRICTEDIO_CAP, False),
                    'simplified_remote_restart_capable':
                    self._get_val_bool(_SIMP_REMOTE_RESTART_CAP, False)
                    }
        return cap_data

    @property
    def proc_compat_modes(self):
        """List of strings containing the processor compatibility modes.

        This is a READ-ONLY list.
        """
        return tuple(self._get_vals(_PROC_COMPAT_MODES))

    @property
    def migration_data(self):
        """returns: The migration properties from PowerVM.

        This information should not be changed and should be treated as read
        only.
        """

        max_migr_sup = self._get_val_int(_MAX_FIRMWARE_MIGR)
        act_migr_sup = self._get_val_int(_MAX_ACTIVE_MIGR)
        inact_migr_sup = self._get_val_int(_MAX_INACTIVE_MIGR)
        pref_act_migr_sup = act_migr_sup
        pref_inact_migr_sup = inact_migr_sup
        act_migr_prog = self._get_val_int(_ACTIVE_MIGR_RUNNING)
        inact_migr_prog = self._get_val_int(_INACTIVE_MIGR_RUNNING)

        migr_data = {'max_migration_ops_supported': max_migr_sup,
                     'active_migrations_supported': act_migr_sup,
                     'inactive_migrations_supported': inact_migr_sup,
                     'preferred_active_migrations_supported':
                     pref_act_migr_sup,
                     'preferred_inactive_migrations_supported':
                     pref_inact_migr_sup,
                     'active_migrations_in_progress': act_migr_prog,
                     'inactive_migrations_in_progress': inact_migr_prog,
                     }
        return migr_data

    @property
    def vios_links(self):
        """List of hrefs from AssociatedVirtualIOServers.

        This is a READ-ONLY list.
        """
        return self.get_href(_VIOS_LINK)


@ewrap.ElementWrapper.pvm_type(_ASIO_ROOT, has_metadata=True)
class ASIOConfig(ewrap.ElementWrapper):
    """The associated system IO configuration for this system."""

    @property
    def avail_wwpns(self):
        return self._get_val_int(_ASIO_AVAIL_WWPNS)

    @property
    def io_slots(self):
        es = ewrap.WrapperElemList(self._find_or_seed(_ASIO_IOSLOTS), IOSlot)
        return es

    @property
    def wwpn_prefix(self):
        return self._get_val_str(_ASIO_WWPN_PREFIX)


@ewrap.ElementWrapper.pvm_type(_IOSLOT_ROOT, has_metadata=True)
class IOSlot(ewrap.ElementWrapper):
    """An I/O Slot represents a device bus on the system.

    It may contain a piece of hardware within it.
    """

    @property
    def bus_grp_required(self):
        return self._get_val_bool(_IOSLOT_BUS_GRP_REQ)

    @property
    def description(self):
        return self._get_val_str(_IOSLOT_DESC)

    @property
    def feat_codes(self):
        return self._get_val_int(_IOSLOT_FEAT_CODES)

    @property
    def pci_class(self):
        return self._get_val_int(_IOSLOT_PCI_CLASS)

    @property
    def pci_sub_dev_id(self):
        return self._get_val_int(_IOSLOT_PCI_SUB_DEV_ID)

    @property
    def pci_revision_id(self):
        return self._get_val_int(_IOSLOT_PCI_REV_ID)

    @property
    def pci_vendor_id(self):
        return self._get_val_int(_IOSLOT_PCI_VEND_ID)

    @property
    def pci_sub_vendor_id(self):
        return self._get_val_int(_IOSLOT_PCI_SUB_VEND_ID)

    @property
    def dyn_reconfig_conn_index(self):
        return self._get_val_int(_IOSLOT_DYN_REC_CON_INDEX)

    @property
    def dyn_reconfig_conn_name(self):
        return self._get_val_str(_IOSLOT_DYN_REC_CON_NAME)
