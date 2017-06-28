# Copyright 2014, 2017 IBM Corp.
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
import re
import warnings

from oslo_log import log as logging

import pypowervm.const as c
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.mtms as mtmwrap

LOG = logging.getLogger(__name__)

# ManagedSystem XPath constants
_PRIMARY_IP_ADDRESS = 'PrimaryIPAddress'
_HOST_IP_ADDRESS = _PRIMARY_IP_ADDRESS
_STATE = 'State'
_SYSTEM_NAME = 'SystemName'
_MASTER_MODE = 'IsPowerVMManagementMaster'

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
_AME_CAP = u.xpath(_SYS_CAPABILITIES, 'ActiveMemoryExpansionCapable')
_AIX_CAP = u.xpath(_SYS_CAPABILITIES, 'AIXCapable')
_IBMi_CAP = u.xpath(_SYS_CAPABILITIES, 'IBMiCapable')
_LINUX_CAP = u.xpath(_SYS_CAPABILITIES, 'LinuxCapable')
_SHR_PROC_POOL_CAP = u.xpath(
    _SYS_CAPABILITIES, 'SharedProcessorPoolCapable')
_VNIC_CAP = u.xpath(_SYS_CAPABILITIES, 'VirtualNICDedicatedSRIOVCapable')
_VNIC_FAILOVER_CAP = u.xpath(_SYS_CAPABILITIES, 'VirtualNICFailOverCapable')
_DYN_SRR_CAP = u.xpath(
    _SYS_CAPABILITIES, 'DynamicSimplifiedRemoteRestartToggleCapable')
_IBMi_NATIVE_IO_CAP = u.xpath(_SYS_CAPABILITIES, 'IBMiNativeIOCapable')
_DISABLE_SECURE_BOOT_CAP = u.xpath(
    _SYS_CAPABILITIES, 'DisableSecureBootCapable')

_CAPABILITY_MAP = {
    'active_lpar_mobility_capable': {
        'prop': _ACTIVE_LPM_CAP, 'default': False},
    'inactive_lpar_mobility_capable': {
        'prop': _INACTIVE_LPM_CAP, 'default': False},
    # custom_mac_addr_capable True is correct for POWER7
    'custom_mac_addr_capable': {
        'prop': _VETH_MAC_ADDR_CAP, 'default': True},
    'ibmi_lpar_mobility_capable': {
        'prop': _IBMi_LPM_CAP, 'default': False},
    'ibmi_restrictedio_capable': {
        'prop': _IBMi_RESTRICTEDIO_CAP, 'default': False},
    'simplified_remote_restart_capable': {
        'prop': _SIMP_REMOTE_RESTART_CAP, 'default': False},
    'active_memory_expansion_capable': {
        'prop': _AME_CAP, 'default': False},
    # aix_capable defaults to True for backward compat (that is what we
    # returned before there was a capability for this in the PowerVM REST API)
    'aix_capable': {
        'prop': _AIX_CAP, 'default': True},
    'ibmi_capable': {
        'prop': _IBMi_CAP, 'default': False},
    'linux_capable': {
        'prop': _LINUX_CAP, 'default': True},
    'shared_processor_pool_capable': {
        'prop': _SHR_PROC_POOL_CAP, 'default': False},
    'vnic_capable': {
        'prop': _VNIC_CAP, 'default': False},
    'vnic_failover_capable': {
        'prop': _VNIC_FAILOVER_CAP, 'default': False},
    'dynamic_srr_capable': {
        'prop': _DYN_SRR_CAP, 'default': False},
    'ibmi_nativeio_capable': {
        'prop': _IBMi_NATIVE_IO_CAP, 'default': False},
    'disable_secure_boot_capable': {
        'prop': _DISABLE_SECURE_BOOT_CAP, 'default': False},
}

_SYS_MEM_CONFIG = 'AssociatedSystemMemoryConfiguration'
_MEMORY_INSTALLED = u.xpath(_SYS_MEM_CONFIG, 'InstalledSystemMemory')
_MEMORY_AVAIL = u.xpath(_SYS_MEM_CONFIG, 'CurrentAvailableSystemMemory')
_MEMORY_CONFIGURABLE = u.xpath(_SYS_MEM_CONFIG, 'ConfigurableSystemMemory')
_MEMORY_REGION_SIZE = u.xpath(_SYS_MEM_CONFIG, 'MemoryRegionSize')
_SYS_FIRMWARE_MEM = u.xpath(_SYS_MEM_CONFIG, 'MemoryUsedByHypervisor')
_PAGE_TABLE_RATIO = u.xpath(_SYS_MEM_CONFIG, 'DefaultHardwarePageTableRatio')

# Migration Constants
_SYS_PROC_CONFIG = 'AssociatedSystemProcessorConfiguration'
_PROC_COMPAT_MODES = u.xpath(
    _SYS_PROC_CONFIG, 'SupportedPartitionProcessorCompatibilityModes')
_MIN_PROC_UNITS_PER_CPU = u.xpath(
    _SYS_PROC_CONFIG, 'MinimumProcessorUnitsPerVirtualProcessor')
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
    _SYS_PROC_CONFIG, 'CurrentMaximumVirtualProcessorsPerAIXOrLinuxPartition')

_VIOS_LINK = u.xpath("AssociatedVirtualIOServers", c.LINK)

# AssociatedSystemIOConfig constants
_ASIO_ROOT = 'AssociatedSystemIOConfiguration'
_ASIO_AVAIL_WWPNS = 'AvailableWWPNs'
_ASIO_HCA = 'HostChannelAdapters'
_ASIO_HEA = 'HostEthernetAdapters'
_ASIO_IOBUSES = 'IOBuses'
_ASIO_IOSLOTS = 'IOSlots'
_ASIO_SRIOVS = 'SRIOVAdapters'
_ASIO_ASVNET = 'AssociatedSystemVirtualNetwork'
_ASIO_WWPN_PREFIX = 'WWPNPrefix'

_IOSLOT_ROOT = 'IOSlot'
_IOSLOT_BUS_GRP_REQ = 'BusGroupingRequired'
_IOSLOT_DESC = 'Description'
_IOSLOT_FEAT_CODES = 'FeatureCodes'
_IOSLOT_PCI_CLASS = 'PCIClass'
_IOSLOT_PCI_DEV_ID = 'PCIDeviceID'
_IOSLOT_PCI_SUB_DEV_ID = 'PCISubsystemDeviceID'
_IOSLOT_PCI_REV_ID = 'PCIRevisionID'
_IOSLOT_PCI_VEND_ID = 'PCIVendorID'
_IOSLOT_PCI_SUB_VEND_ID = 'PCISubsystemVendorID'
_IOSLOT_DYN_REC_CON_INDEX = 'SlotDynamicReconfigurationConnectorIndex'
_IOSLOT_DYN_REC_CON_NAME = 'SlotDynamicReconfigurationConnectorName'


@ewrap.EntryWrapper.pvm_type('ManagedSystem')
class System(ewrap.EntryWrapper):
    """The PowerVM system that is being managed."""

    @property
    def system_name(self):
        return self._get_val_str(_SYSTEM_NAME)

    @property
    def mtms(self):
        return mtmwrap.MTMS.wrap(self.element.find(mtmwrap.MTMS_ROOT))

    @property
    def asio_config(self):
        return ASIOConfig.wrap(self.element.find(_ASIO_ROOT))

    @property
    def system_state(self):
        return self._get_val_str(_STATE, 'unknown')

    @property
    def proc_units(self):
        return self._get_val_float(_PROC_UNITS_INSTALLED, 0)

    @property
    def min_proc_units(self):
        return self._get_val_float(_MIN_PROC_UNITS_PER_CPU, 0)

    @property
    def proc_units_configurable(self):
        return self._get_val_float(_PROC_UNITS_CONFIGURABLE, 0)

    @property
    def proc_units_avail(self):
        return self._get_val_float(_PROC_UNITS_AVAIL, 0)

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
    def page_table_ratio(self):
        return self._get_val_int(_PAGE_TABLE_RATIO, 0)

    @property
    def host_ip_address(self):
        prop = _HOST_IP_ADDRESS
        val = self._get_val_str(prop)

        return val

    def get_capability(self, key):
        """returns: The requested system capability from Power."""
        if key in _CAPABILITY_MAP:
            prop = _CAPABILITY_MAP[key]['prop']
            default = _CAPABILITY_MAP[key]['default']
            if key == 'aix_capable':
                str_val = self._get_val_str(prop)
                # we can get 'unavailable' if PHYP interface is running an
                # older level and doesn't support query of this information
                if str_val is not None and str_val.lower() == 'inactive':
                    return False
                return default
            return self._get_val_bool(prop, default=default)
        return None

    def get_capabilities(self):
        """returns: The system capabilities from Power."""
        return {key: self.get_capability(key) for key in _CAPABILITY_MAP}

    @property
    def proc_compat_modes(self):
        """List of strings containing the processor compatibility modes.

        This is a READ-ONLY list.
        """
        return tuple(self._get_vals(_PROC_COMPAT_MODES))

    def highest_compat_mode(self):
        """This method returns the highest compatibility mode of the host."""
        modes = []
        pattern = r'^power(\d+)\+?$'
        for mode in self.proc_compat_modes:
            match = re.search(pattern, mode.lower())
            if match:
                modes.append(int(match.group(1)))
        modes = sorted(modes)
        if modes:
            return modes[-1]
        else:
            return 0

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
        proc_compat = (','.join(self.proc_compat_modes))

        migr_data = {'max_migration_ops_supported': max_migr_sup,
                     'active_migrations_supported': act_migr_sup,
                     'inactive_migrations_supported': inact_migr_sup,
                     'preferred_active_migrations_supported':
                     pref_act_migr_sup,
                     'preferred_inactive_migrations_supported':
                     pref_inact_migr_sup,
                     'active_migrations_in_progress': act_migr_prog,
                     'inactive_migrations_in_progress': inact_migr_prog,
                     'proc_compat': proc_compat}

        # Copy get_capabilities() dictionary into migration_data in case
        # sometimes we need validate the host is capable for mobility.
        cap_data = self.get_capabilities()
        migr_data.update(cap_data)

        return migr_data

    @property
    def vios_links(self):
        """List of hrefs from AssociatedVirtualIOServers.

        This is a READ-ONLY list.
        """
        return self.get_href(_VIOS_LINK)

    @property
    def session_is_master(self):
        """The master mode state of this managed system.

        Use pypowervm.tasks.master_mode.request_master to request master mode
        :returns: True if the management node of this System's adapter.session
                  is the master.
        """
        return self._get_val_bool(_MASTER_MODE, True)


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

    @property
    def sriov_adapters(self):
        es = ewrap.WrapperElemList(self._find_or_seed(_ASIO_SRIOVS),
                                   child_class=card.SRIOVAdapter,
                                   indirect='IOAdapterChoice')
        return es


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
    def pci_dev_id(self):
        return self._get_val_int(_IOSLOT_PCI_DEV_ID)

    @property
    def pci_subsys_dev_id(self):
        return self._get_val_int(_IOSLOT_PCI_SUB_DEV_ID)

    @property
    def pci_sub_dev_id(self):
        """Deprecated - use pci_subsys_dev_id instead."""
        warnings.warn(_(
            "This property is deprecated! "
            "Use pci_subsys_dev_id instead."), DeprecationWarning)
        return self.pci_subsys_dev_id

    @property
    def pci_rev_id(self):
        return self._get_val_int(_IOSLOT_PCI_REV_ID)

    @property
    def pci_revision_id(self):
        """Deprecated - use pci_rev_id instead."""
        warnings.warn(_(
            "This property is deprecated! "
            "Use pci_rev_id instead."), DeprecationWarning)
        return self.pci_rev_id

    @property
    def pci_vendor_id(self):
        return self._get_val_int(_IOSLOT_PCI_VEND_ID)

    @property
    def pci_subsys_vendor_id(self):
        return self._get_val_int(_IOSLOT_PCI_SUB_VEND_ID)

    @property
    def pci_sub_vendor_id(self):
        """Deprecated - use pci_subsys_vendor_id instead."""
        warnings.warn(_(
            "This property is deprecated! "
            "Use pci_subsys_vendor_id instead."), DeprecationWarning)
        return self.pci_subsys_vendor_id

    @property
    def drc_index(self):
        return self._get_val_int(_IOSLOT_DYN_REC_CON_INDEX)

    @property
    def dyn_reconfig_conn_index(self):
        """Deprecated - use drc_index instead."""
        warnings.warn(_(
            "This property is deprecated! "
            "Use drc_index instead."), DeprecationWarning)
        return self.drc_index

    @property
    def drc_name(self):
        return self._get_val_str(_IOSLOT_DYN_REC_CON_NAME)

    @property
    def dyn_reconfig_conn_name(self):
        """Deprecated - use drc_name instead."""
        warnings.warn(_(
            "This property is deprecated! "
            "Use drc_name instead."), DeprecationWarning)
        return self.drc_name
