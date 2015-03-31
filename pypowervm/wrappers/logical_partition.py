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

import pypowervm.util as u
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

import logging

LOG = logging.getLogger(__name__)

T = 'true'
F = 'false'

_DED_PROCS = 'DesiredProcessors'
_DED_MAX_PROCS = 'MaximumProcessors'
_DED_MIN_PROCS = 'MinimumProcessors'

_DED_PROC_CFG = 'DedicatedProcessorConfiguration'
_HAS_DED_PROCS = 'HasDedicatedProcessors'
_SHARING_MODE = 'SharingMode'
_CURR_SHARING_MODE = 'CurrentSharingMode'

_SHR_PROC_CFG = 'SharedProcessorConfiguration'
_PROC_UNIT = 'DesiredProcessingUnits'
_MIN_PROC_UNIT = 'MinimumProcessingUnits'
_MAX_PROC_UNIT = 'MaximumProcessingUnits'
_DES_VIRT_PROC = 'DesiredVirtualProcessors'
_MIN_VIRT_PROC = 'MinimumVirtualProcessors'
_MAX_VIRT_PROC = 'MaximumVirtualProcessors'
_SHARED_PROC_POOL_ID = 'SharedProcessorPoolID'

_MEM = 'DesiredMemory'
_MAX_MEM = 'MaximumMemory'
_MIN_MEM = 'MinimumMemory'
_RUN_MEM = 'RuntimeMemory'
_CURR_MEM = 'CurrentMemory'
_CURR_MAX_MEM = 'CurrentMaximumMemory'
_CURR_MIN_MEM = 'CurrentMinimumMemory'
_SHARED_MEM_ENABLED = 'SharedMemoryEnabled'

_LPAR_NAME = 'PartitionName'
_LPAR_ID = 'PartitionID'
_LPAR_TYPE = 'PartitionType'
_LPAR_STATE = 'PartitionState'

_LPAR_SRIOV_ETH = 'SRIOVEthernetLogicalPorts'
_LPAR_SRIOV_FC_ETH = 'SRIOVFibreChannelOverEthernetLogicalPorts'
_LPAR_CNA = 'ClientNetworkAdapters'
_LPAR_HOST_ETH = 'HostEthernetAdapterLogicalPorts'
_LPAR_ASSOCIATED_GROUPS = 'AssociatedGroups'
_LPAR_ASSOCIATED_TASKS = 'AssociatedTasks'
_LPAR_VFCA = 'VirtualFibreChannelClientAdapters'
_LPAR_VSCA = 'VirtualSCSIClientAdapters'
_LPAR_DED_NICS = 'DedicatedVirtualNICs'

_LPAR_PROC_CFG = 'PartitionProcessorConfiguration'
_LPAR_MEM_CFG = 'PartitionMemoryConfiguration'
_LPAR_IO_CFG = 'PartitionIOConfiguration'

_HOST_CHANNEL_ADAPTERS = 'HostChannelAdapters'
_PROFILE_IO_ADPTS = 'ProfileVirtualIOAdapters'

_UNCAPPED_WEIGHT = 'UncappedWeight'

_AVAIL_PRIORITY = 'AvailabilityPriority'
_RESTRICTED_IO = 'IsRestrictedIOPartition'
_SRR = 'SimplifiedRemoteRestartCapable'
_CNA_LINKS = u.xpath('ClientNetworkAdapters', c.LINK)

# Constants for the Partition I/O Configuration
IO_CFG_ROOT = _LPAR_IO_CFG
_IO_CFG_MAX_SLOTS = 'MaximumVirtualIOSlots'

# Constants for the I/O Slot Configuration
IO_SLOTS_ROOT = 'ProfileIOSlots'
IO_SLOT_ROOT = 'ProfileIOSlot'

# Constants for the Associated I/O Slot
ASSOC_IO_SLOT_ROOT = 'AssociatedIOSlot'
_ASSOC_IO_SLOT_DESC = 'Description'
_ASSOC_IO_SLOT_PHYS_LOC = 'IOUnitPhysicalLocation'
_ASSOC_IO_SLOT_ADPT_ID = 'PCAdapterID'
_ASSOC_IO_SLOT_PCI_CLASS = 'PCIClass'
_ASSOC_IO_SLOT_PCI_DEV_ID = 'PCIDeviceID'
_ASSOC_IO_SLOT_PCI_MFG_ID = 'PCIManufacturerID'
_ASSOC_IO_SLOT_PCI_REV_ID = 'PCIRevisionID'
_ASSOC_IO_SLOT_PCI_VENDOR_ID = 'PCIVendorID'
_ASSOC_IO_SLOT_SUBSYS_VENDOR_ID = 'PCISubsystemVendorID'

# Constants for generic I/O Adapter
RELATED_IO_ADPT_ROOT = 'RelatedIOAdapter'
IO_PFC_ADPT_ROOT = 'PhysicalFibreChannelAdapter'
_IO_ADPT_ID = 'AdapterID'
_IO_ADPT_DESC = 'Description'
_IO_ADPT_DYN_NAME = 'DynamicReconfigurationConnectorName'
_IO_ADPT_PHYS_LOC = 'PhysicalLocation'

# Physical Fibre Channel Port Constants
_PFC_PORT_LOC_CODE = 'LocationCode'
_PFC_PORT_NAME = 'PortName'
_PFC_PORT_UDID = 'UniqueDeviceID'
PFC_PORT_WWPN = 'WWPN'
_PFC_PORT_AVAILABLE_PORTS = 'AvailablePorts'
_PFC_PORT_TOTAL_PORTS = 'TotalPorts'
PFC_PORTS_ROOT = 'PhysicalFibreChannelPorts'
PFC_PORT_ROOT = 'PhysicalFibreChannelPort'

_CURRENT_PROC_MODE = 'CurrentProcessorCompatibilityMode'
_PENDING_PROC_MODE = 'PendingProcessorCompatibilityMode'

_LPAR_CAPABILITIES = 'PartitionCapabilities'
_DLPAR_MEM_CAPABLE = u.xpath(
    _LPAR_CAPABILITIES, 'DynamicLogicalPartitionMemoryCapable')
_DLPAR_PROC_CAPABLE = u.xpath(
    _LPAR_CAPABILITIES, 'DynamicLogicalPartitionProcessorCapable')

_OPERATING_SYSTEM_VER = 'OperatingSystemVersion'

_REF_CODE = 'ReferenceCode'
_MIGRATION_STATE = 'MigrationState'

_LPAR_EL_ORDER = (_AVAIL_PRIORITY, _LPAR_IO_CFG, _LPAR_MEM_CFG, _LPAR_NAME,
                  _LPAR_PROC_CFG, _LPAR_TYPE, _PENDING_PROC_MODE,
                  _LPAR_SRIOV_ETH, _LPAR_SRIOV_FC_ETH, _LPAR_CNA,
                  _LPAR_HOST_ETH, _LPAR_ASSOCIATED_GROUPS,
                  _LPAR_ASSOCIATED_TASKS, _LPAR_VFCA, _LPAR_VSCA,
                  _LPAR_DED_NICS, _SRR, _RESTRICTED_IO)


# Dedicated sharing modes
class DedicatedSharingModesEnum(object):
    SHARE_IDLE_PROCS = 'sre idle proces'
    SHARE_IDLE_PROCS_ACTIVE = 'sre idle procs active'
    SHARE_IDLE_PROCS_ALWAYS = 'sre idle procs always'
    KEEP_IDLE_PROCS = 'keep idle procs'
    ALL_VALUES = (SHARE_IDLE_PROCS, SHARE_IDLE_PROCS_ACTIVE,
                  SHARE_IDLE_PROCS_ALWAYS, KEEP_IDLE_PROCS)


# Shared Proc, sharing modes.
class SharingModesEnum(object):
    CAPPED = 'capped'
    UNCAPPED = 'uncapped'
    ALL_VALUES = (CAPPED, UNCAPPED)


class LPARTypeEnum(object):
    """Subset of LogicalPartitionEnvironmentEnum - client LPAR types."""
    OS400 = 'OS400'
    AIXLINUX = 'AIX/Linux'


class LPARCompatEnum(object):
    DEFAULT = 'default'
    POWER6 = 'POWER6'
    POWER6_PLUS = 'POWER6_Plus'
    POWER7 = 'POWER7'
    POWER7_PLUS = 'POWER7_Plus'
    POWER8 = 'POWER8'
    ALL_VALUES = (DEFAULT, POWER6, POWER6_PLUS, POWER7, POWER7_PLUS,
                  POWER8)


@ewrap.EntryWrapper.pvm_type('LogicalPartition',
                             child_order=_LPAR_EL_ORDER)
class LPAR(ewrap.EntryWrapper):

    search_keys = dict(name='PartitionName', id='PartitionID')

    @classmethod
    def bld(cls, name, mem_cfg, proc_cfg, env=LPARTypeEnum.AIXLINUX,
            io_cfg=None):
        """Creates an LPAR wrapper.

        :param name: The name of the lpar
        :param mem_cfg: The memory configuration wrapper
        :param proc_cfg: The processor configuration wrapper
        :param env: The type of lpar, taken from LPARTypeEnum
        :param io_cfg: The i/o configuration wrapper

        :returns: LPAR wrapper
        """

        lpar = super(LPAR, cls)._bld()
        if io_cfg:
            lpar.io_config = io_cfg
        lpar.mem_config = mem_cfg
        lpar.name = name
        lpar.proc_config = proc_cfg
        lpar._env(env)

        # Empty collections to satisfy schema
        lpar._sriov_eth_ports('')
        lpar._sriov_fc_eth_ports('')
        lpar._cnas('')
        lpar._host_eth_ports([])
        lpar._associated_groups('')
        lpar._associated_tasks('')
        lpar._virtual_fbca('')
        lpar._virtual_fsca('')
        lpar._ded_nics('')
        return lpar

    @property
    def state(self):
        """See LogicalPartitionStateEnum.

        e.g. 'not activated', 'running', 'migrating running', etc.
        """
        partition_state = self._get_val_str(_LPAR_STATE)
        return partition_state

    @property
    def name(self):
        """Short name (not ID, MTMS, or hostname)."""
        return self._get_val_str(_LPAR_NAME)

    @name.setter
    def name(self, val):
        self.set_parm_value(_LPAR_NAME, val)

    @property
    def id(self):
        """Short ID (not UUID)."""
        return int(self._get_val_str(_LPAR_ID, c.ZERO))

    @property
    def env(self):
        """See LogicalPartitionEnvironmentEnum.

        Should always be 'AIX/Linux' for LPAREntry.  'Virtual IO Server'
        should only happen for VIOSEntry.
        """
        return self._get_val_str(_LPAR_TYPE)

    def _env(self, val):
        self.set_parm_value(_LPAR_TYPE, val)

    def _sriov_eth_ports(self, val):
        self.set_parm_value(_LPAR_SRIOV_ETH, val)

    def _sriov_fc_eth_ports(self, val):
        self.set_parm_value(_LPAR_SRIOV_FC_ETH, val)

    def _cnas(self, val):
        self.set_parm_value(_LPAR_CNA, val)

    def _host_eth_ports(self, val):
        self.replace_list(_LPAR_HOST_ETH, val)

    def _associated_groups(self, val):
        self.set_parm_value(_LPAR_ASSOCIATED_GROUPS, val,
                            attrib=c.ATTR_SCHEMA120)

    def _associated_tasks(self, val):
        self.set_parm_value(_LPAR_ASSOCIATED_TASKS, val,
                            attrib=c.ATTR_SCHEMA120)

    def _virtual_fbca(self, val):
        self.set_parm_value(_LPAR_VFCA, val)

    def _virtual_fsca(self, val):
        self.set_parm_value(_LPAR_VSCA, val)

    def _ded_nics(self, val):
        self.set_parm_value(_LPAR_DED_NICS, val)

    @property
    def current_mem(self):
        return self._get_val_str(c.CURR_MEM, c.ZERO)

    @property
    def current_max_mem(self):
        return self._get_val_str(c.CURR_MAX_MEM, c.ZERO)

    @property
    def current_min_mem(self):
        return self._get_val_str(c.CURR_MIN_MEM, c.ZERO)

    @property
    def desired_mem(self):
        return self._get_val_str(c.DES_MEM, c.ZERO)

    @property
    def max_mem(self):
        return self._get_val_str(c.DES_MAX_MEM, c.ZERO)

    @property
    def min_mem(self):
        return self._get_val_str(c.DES_MIN_MEM, c.ZERO)

    @property
    def run_mem(self):
        return self._get_val_str(c.RUN_MEM, c.ZERO)

    @property
    def current_mem_share_enabled(self):
        # The default is None instead of False so that the caller
        # can know if the value is not set
        return self._get_val_bool(c.SHARED_MEM_ENABLED, None)

    @property
    def current_proc_mode_is_dedicated(self):
        """Returns boolean True if dedicated, False if shared or not found."""
        return self._get_val_bool(c.CURR_USE_DED_PROCS, False)

    @property
    def proc_mode_is_dedicated(self):
        """Returns boolean True if dedicated, False if shared or not found."""
        return self._get_val_bool(c.USE_DED_PROCS, False)

    @property
    def current_procs(self):
        return self._get_val_str(c.CURR_PROCS, c.ZERO)

    @property
    def current_max_procs(self):
        return self._get_val_str(c.CURR_MAX_PROCS, c.ZERO)

    @property
    def current_min_procs(self):
        return self._get_val_str(c.CURR_MIN_PROCS, c.ZERO)

    @property
    def desired_procs(self):
        return self._get_val_str(c.DES_PROCS, c.ZERO)

    @property
    def max_procs(self):
        return self._get_val_str(c.DES_MAX_PROCS, c.ZERO)

    @property
    def min_procs(self):
        return self._get_val_str(c.DES_MIN_PROCS, c.ZERO)

    @property
    def current_vcpus(self):
        return self._get_val_str(c.CURR_VCPU, c.ZERO)

    @property
    def current_max_vcpus(self):
        return self._get_val_str(c.CURR_MAX_VCPU, c.ZERO)

    @property
    def current_min_vcpus(self):
        return self._get_val_str(c.CURR_MIN_VCPU, c.ZERO)

    @property
    def desired_vcpus(self):
        return self._get_val_str(c.DES_VCPU, c.ZERO)

    @property
    def max_vcpus(self):
        return self._get_val_str(c.DES_MAX_VCPU, c.ZERO)

    @property
    def min_vcpus(self):
        return self._get_val_str(c.DES_MIN_VCPU, c.ZERO)

    @property
    def current_proc_units(self):
        return self._get_val_str(c.CURR_PROC_UNITS, c.ZERO)

    @property
    def current_max_proc_units(self):
        return self._get_val_str(c.CURR_MAX_PROC_UNITS, c.ZERO)

    @property
    def current_min_proc_units(self):
        return self._get_val_str(c.CURR_MIN_PROC_UNITS, c.ZERO)

    @property
    def desired_proc_units(self):
        return self._get_val_str(c.DES_PROC_UNITS, c.ZERO)

    @property
    def max_proc_units(self):
        return self._get_val_str(c.MAX_PROC_UNITS, c.ZERO)

    @property
    def min_proc_units(self):
        return self._get_val_str(c.MIN_PROC_UNITS, c.ZERO)

    @property
    def run_procs(self):
        return self._get_val_str(c.RUN_PROCS, c.ZERO)

    @property
    def run_vcpus(self):
        return self._get_val_str(c.RUN_VCPU, c.ZERO)

    @property
    def current_uncapped_weight(self):
        return self._get_val_str(c.CURR_UNCAPPED_WEIGHT, c.ZERO)

    @property
    def uncapped_weight(self):
        return self._get_val_str(c.UNCAPPED_WEIGHT, c.ZERO)

    @property
    def shared_proc_pool_id(self):
        return int(self._get_val_str(c.SHARED_PROC_POOL_ID, c.ZERO))

    @property
    def avail_priority(self):
        return self._get_val_str(_AVAIL_PRIORITY, c.ZERO)

    @property
    def sharing_mode(self):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        return self._get_val_str(c.CURR_SHARING_MODE)

    @property
    def migration_state(self):
        """See PartitionMigrationStateEnum.

        e.g. 'Not_Migrating', 'Migration_Starting', 'Migration_Failed', etc.
        Defaults to 'Not_Migrating'
        """
        return self._get_val_str(_MIGRATION_STATE, 'Not_Migrating')

    @property
    def proc_compat_mode(self):
        """*Current* processor compatibility mode.

        See LPARCompatEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self._get_val_str(_CURRENT_PROC_MODE)

    @property
    def pending_proc_compat_mode(self):
        """Pending processor compatibility mode.

        See LPARCompatEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self._get_val_str(_PENDING_PROC_MODE)

    @property
    def operating_system(self):
        """String representing the OS and version, or 'Unknown'."""
        return self._get_val_str(_OPERATING_SYSTEM_VER, 'Unknown')

    @property
    def cna_uris(self):
        """Return a list of URI strings to the LPAR's ClientNetworkAdapters.

        This is a READ ONLY list.
        """
        return self.get_href(_CNA_LINKS)

    @property
    def rmc_state(self):
        """See ResourceMonitoringControlStateEnum.

        e.g. 'active', 'inactive', 'busy', etc.
        """
        return self._get_val_str(c.RMC_STATE)

    @property
    def srr_enabled(self):
        """Simplied remote restart.

        :returns: Returns SRR config boolean
        """
        return self._get_val_bool(_SRR, False)

    @srr_enabled.setter
    def srr_enabled(self, value):
        self.set_parm_value(_SRR, u.sanitize_bool_for_api(value),
                            attrib=c.ATTR_SCHEMA120)

    @property
    def ref_code(self):
        return self._get_val_str(_REF_CODE)

    @property
    def restrictedio(self):
        return self._get_val_bool(_RESTRICTED_IO, False)

    def check_dlpar_connectivity(self):
        """Check the partition for DLPAR capability and rmc state.

        :returns: Returns true or false if DLPAR capable
        :returns: Returns RMC state as string
        """

        # Pull the dlpar and rmc values from PowerVM
        mem_dlpar = self._get_val_bool(_DLPAR_MEM_CAPABLE)
        proc_dlpar = self._get_val_bool(_DLPAR_PROC_CAPABLE)

        dlpar = mem_dlpar and proc_dlpar

        return dlpar, self.rmc_state

    @desired_mem.setter
    def desired_mem(self, value):
        self.set_parm_value(c.DES_MEM, value)

    @max_mem.setter
    def max_mem(self, value):
        self.set_parm_value(c.DES_MAX_MEM, value)

    @min_mem.setter
    def min_mem(self, value):
        self.set_parm_value(c.DES_MIN_MEM, value)

    @proc_compat_mode.setter
    def proc_compat_mode(self, value):
        """Sets *PENDING* proc compat mode.

        Note that corresponding getter retrieves the *CURRENT* proc compat
        mode.
        """
        self.set_parm_value(_PENDING_PROC_MODE, value)

    @avail_priority.setter
    def avail_priority(self, value):
        self.set_parm_value(_AVAIL_PRIORITY, value)

    @sharing_mode.setter
    def sharing_mode(self, value):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        self.set_parm_value(c.SHARING_MODE, value)

    @desired_procs.setter
    def desired_procs(self, value):
        self.set_parm_value(c.DES_PROCS, value)

    @max_procs.setter
    def max_procs(self, value):
        self.set_parm_value(c.DES_MAX_PROCS, value)

    @min_procs.setter
    def min_procs(self, value):
        self.set_parm_value(c.DES_MIN_PROCS, value)

    @desired_vcpus.setter
    def desired_vcpus(self, value):
        self.set_parm_value(c.DES_VCPU, value)

    @max_vcpus.setter
    def max_vcpus(self, value):
        self.set_parm_value(c.DES_MAX_VCPU, value)

    @min_vcpus.setter
    def min_vcpus(self, value):
        self.set_parm_value(c.DES_MIN_VCPU, value)

    @desired_proc_units.setter
    def desired_proc_units(self, value):
        self.set_parm_value(c.DES_PROC_UNITS, value)

    @max_proc_units.setter
    def max_proc_units(self, value):
        self.set_parm_value(c.MAX_PROC_UNITS, value)

    @min_proc_units.setter
    def min_proc_units(self, value):
        self.set_parm_value(c.MIN_PROC_UNITS, value)

    @uncapped_weight.setter
    def uncapped_weight(self, value):
        self.set_parm_value(c.UNCAPPED_WEIGHT, value)

    @proc_mode_is_dedicated.setter
    def proc_mode_is_dedicated(self, value):
        """Expects 'true' (string) for dedicated or 'false' for shared."""
        self.set_parm_value(c.USE_DED_PROCS, value)

    @property
    def io_config(self):
        """The Partition I/O Configuration for the LPAR."""
        elem = self.element.find(_LPAR_IO_CFG)
        return PartitionIOConfiguration.wrap(elem)

    @io_config.setter
    def io_config(self, io_cfg):
        """The Partition I/O Configuration for the LPAR."""
        elem = self._find_or_seed(_LPAR_IO_CFG)
        self.element.replace(elem, io_cfg.element)

    @property
    def mem_config(self):
        """The Partition Memory Configuration for the LPAR."""
        elem = self.element.find(_LPAR_MEM_CFG)
        return PartitionMemoryConfiguration.wrap(elem)

    @mem_config.setter
    def mem_config(self, mem_cfg):
        """The Partition Memory Configuration for the LPAR."""
        elem = self._find_or_seed(_LPAR_MEM_CFG)
        self.element.replace(elem, mem_cfg.element)

    @property
    def proc_config(self):
        """The Partition Processor Configuration for the LPAR."""
        elem = self.element.find(_LPAR_PROC_CFG)
        return PartitionProcessorConfiguration.wrap(elem)

    @proc_config.setter
    def proc_config(self, proc_config):
        """The Partition Processor Configuration for the LPAR."""
        elem = self._find_or_seed(_LPAR_PROC_CFG)
        self.element.replace(elem, proc_config.element)


@ewrap.ElementWrapper.pvm_type(_LPAR_MEM_CFG, has_metadata=True)
class PartitionMemoryConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Memory Configuration."""

    @classmethod
    def bld(cls, mem, min_mem=None, max_mem=None):
        """Creates the ParitionMemoryConfiguration.

        :param mem: The amount of memory for the partition in MB
        :param min_mem: The minimum amount of memory in MB. Defaults to
            the mem param
        :param max_mem: The maximum amount of memory in MB. Defaults to
            the mem param
        :returns: The memory configuration wrapper.
        """
        if min_mem is None:
            min_mem = mem
        if max_mem is None:
            max_mem = mem

        cfg = super(PartitionMemoryConfiguration, cls)._bld()
        cfg.desired_mem = mem
        cfg.max_mem = max_mem
        cfg.min_mem = min_mem

        return cfg

    @property
    def current_mem(self):
        return self._get_val_int(_CURR_MEM, c.ZERO)

    @property
    def current_max_mem(self):
        return self._get_val_int(_CURR_MAX_MEM, c.ZERO)

    @property
    def current_min_mem(self):
        return self._get_val_int(_CURR_MIN_MEM, c.ZERO)

    @property
    def desired_mem(self):
        return self._get_val_int(_MEM, c.ZERO)

    @desired_mem.setter
    def desired_mem(self, mem):
        self.set_parm_value(_MEM, str(mem))

    @property
    def max_mem(self):
        return self._get_val_int(_MAX_MEM, c.ZERO)

    @max_mem.setter
    def max_mem(self, mem):
        self.set_parm_value(_MAX_MEM, str(mem))

    @property
    def min_mem(self):
        return self._get_val_int(_MIN_MEM, c.ZERO)

    @min_mem.setter
    def min_mem(self, mem):
        self.set_parm_value(_MIN_MEM, str(mem))

    @property
    def run_mem(self):
        """Runtime memory."""
        return self._get_val_int(_RUN_MEM, c.ZERO)

    @property
    def current_mem_share_enabled(self):
        # The default is None instead of False so that the caller
        # can know if the value is not set
        return self._get_val_bool(_SHARED_MEM_ENABLED, None)


@ewrap.ElementWrapper.pvm_type(_LPAR_PROC_CFG, has_metadata=True)
class PartitionProcessorConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Processor Configuration.

    Comprised of either the shared or dedicated processor config.
    """

    @classmethod
    def bld_shared(cls, proc_unit, proc,
                   sharing_mode=SharingModesEnum.UNCAPPED, uncapped_weight=128,
                   min_proc_unit=None, max_proc_unit=None,
                   min_proc=None, max_proc=None, proc_pool=0):
        """Builds a Shared Processor configuration wrapper.

        :param proc_unit: Amount of desired proc units (float)
        :param proc: Number of virtual processors (int)
        :param sharing_mode: Sharing mode of the processors (uncapped)
        :param uncapped_weight: Uncapped weight of the processors (0-255)
        :param min_proc_unit: Minimum proc units, default to proc unit value
        :param max_proc_unit: Maximum proc units, default to proc unit value
        :param min_proc: Minimum processors, default to proc value
        :param max_proc: Maximum processors, default to proc value
        :param proc_pool: The shared processor pool for the lpar, defaults to 0
        :returns: Processor Config with shared processors

        """
        proc_cfg = super(PartitionProcessorConfiguration, cls)._bld()
        proc_cfg._has_dedicated_proc(False)

        sproc = SharedProcessorConfiguration.bld(
            proc_unit, proc, uncapped_weight=uncapped_weight,
            min_proc_unit=min_proc_unit, max_proc_unit=max_proc_unit,
            min_proc=min_proc, max_proc=max_proc, proc_pool=proc_pool)

        proc_cfg._shared_proc_cfg(sproc)
        proc_cfg.sharing_mode = sharing_mode
        return proc_cfg

    @classmethod
    def bld_dedicated(cls, proc, min_proc=None, max_proc=None,
                      sharing_mode=DedicatedSharingModesEnum.SHARE_IDLE_PROCS):

        """Builds a Dedicated Processor configuration wrapper.

        :param proc: Number of virtual processors (int)
        :param min_proc: Minimum processors, default to proc value
        :param max_proc: Maximum processors, default to proc value
        :param sharing_mode: Sharing mode of the processors, 'sre idle proces'
        :returns: Processor Config with dedicated processors

        """

        proc_cfg = super(PartitionProcessorConfiguration, cls)._bld()

        dproc = DedicatedProcessorConfiguration.bld(
            proc, min_proc=min_proc, max_proc=max_proc)

        proc_cfg._dedicated_proc_cfg(dproc)
        proc_cfg._has_dedicated_proc(True)
        proc_cfg.sharing_mode = sharing_mode
        return proc_cfg

    @property
    def has_dedicated_proc(self):
        return self._get_val_bool(_HAS_DED_PROCS)

    def _has_dedicated_proc(self, val):
        self.set_parm_value(_HAS_DED_PROCS, u.sanitize_bool_for_api(val))

    @property
    def sharing_mode(self):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        return self._get_val_str(_CURR_SHARING_MODE)

    @sharing_mode.setter
    def sharing_mode(self, value):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        self.set_parm_value(_SHARING_MODE, value)

    @property
    def shared_proc_cfg(self):
        """Returns the Shared Processor Configuration."""
        return SharedProcessorConfiguration.wrap(
            self.element.find(_SHR_PROC_CFG))

    def _shared_proc_cfg(self, spc):
        elem = self._find_or_seed(_SHR_PROC_CFG)
        self.element.replace(elem, spc.element)

    @property
    def dedicated_proc_cfg(self):
        """Returns the Dedicated Processor Configuration."""
        return DedicatedProcessorConfiguration.wrap(
            self.element.find(_DED_PROC_CFG))

    def _dedicated_proc_cfg(self, dpc):
        elem = self._find_or_seed(_DED_PROC_CFG)
        self.element.replace(elem, dpc.element)


@ewrap.ElementWrapper.pvm_type(_SHR_PROC_CFG, has_metadata=True)
class SharedProcessorConfiguration(ewrap.ElementWrapper):
    """Represents the partition's Shared Processor Configuration."""

    @classmethod
    def bld(cls, proc_unit, proc, uncapped_weight=None,
            min_proc_unit=None, max_proc_unit=None,
            min_proc=None, max_proc=None, proc_pool=0):
        """Builds a Shared Processor configuration wrapper.

        :param proc_unit: Amount of desired proc units (float)
        :param proc: Number of virtual processors (int)
        :param uncapped_weight: Uncapped weight of the processors, 0-255
        :param min_proc_unit: Minimum proc units, default to proc unit value
        :param max_proc_unit: Maximum proc units, default to proc unit value
        :param min_proc: Minimum processors, default to proc value
        :param max_proc: Maximum processors, default to proc value
        :param proc_pool: The shared processor pool for the lpar, defaults to 0
        :returns: Processor Config with shared processors

        """

        # Set defaults if not specified
        if min_proc_unit is None:
            min_proc_unit = proc_unit
        if max_proc_unit is None:
            max_proc_unit = proc_unit
        if min_proc is None:
            min_proc = proc
        if max_proc is None:
            max_proc = proc

        sproc = super(SharedProcessorConfiguration, cls)._bld()

        sproc.desired_proc_units = proc_unit
        sproc.desired_vcpus = proc
        sproc.max_proc_units = max_proc_unit
        sproc.max_vcpus = max_proc
        sproc.min_proc_units = min_proc_unit
        sproc.min_vcpus = min_proc
        sproc.shared_proc_pool_id = proc_pool
        if uncapped_weight is not None:
            sproc.uncapped_weight = uncapped_weight

        return sproc

    @property
    def desired_proc_units(self):
        return self._get_val_float(_PROC_UNIT)

    @desired_proc_units.setter
    def desired_proc_units(self, val):
        self.set_parm_value(_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def max_proc_units(self):
        return self._get_val_float(_MAX_PROC_UNIT)

    @max_proc_units.setter
    def max_proc_units(self, val):
        self.set_parm_value(_MAX_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def min_proc_units(self):
        return self._get_val_float(_MIN_PROC_UNIT)

    @min_proc_units.setter
    def min_proc_units(self, val):
        self.set_parm_value(_MIN_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def desired_vcpus(self):
        return self._get_val_int(_DES_VIRT_PROC, 0)

    @desired_vcpus.setter
    def desired_vcpus(self, val):
        self.set_parm_value(_DES_VIRT_PROC, val)

    @property
    def max_vcpus(self):
        return self._get_val_int(_MAX_VIRT_PROC, 0)

    @max_vcpus.setter
    def max_vcpus(self, val):
        self.set_parm_value(_MAX_VIRT_PROC, val)

    @property
    def min_vcpus(self):
        return self._get_val_int(_MIN_VIRT_PROC, 0)

    @min_vcpus.setter
    def min_vcpus(self, val):
        self.set_parm_value(_MIN_VIRT_PROC, val)

    @property
    def shared_proc_pool_id(self):
        return self._get_val_int(_SHARED_PROC_POOL_ID, 0)

    @shared_proc_pool_id.setter
    def shared_proc_pool_id(self, val):
        self.set_parm_value(_SHARED_PROC_POOL_ID, val)

    @property
    def uncapped_weight(self):
        return self._get_val_int(_UNCAPPED_WEIGHT, 0)

    @uncapped_weight.setter
    def uncapped_weight(self, val):
        self.set_parm_value(_UNCAPPED_WEIGHT, str(val))


@ewrap.ElementWrapper.pvm_type(_DED_PROC_CFG, has_metadata=True)
class DedicatedProcessorConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Dedicated Processor Configuration."""

    @classmethod
    def bld(cls, proc, min_proc=None, max_proc=None):
        """Builds a Dedicated Processor configuration wrapper.

        :param proc: Number of virtual processors (int)
        :param min_proc: Minimum processors, default to proc value
        :param max_proc: Maximum processors, default to proc value
        :returns: Processor Config with dedicated processors

        """

        # Set defaults if not specified
        if min_proc is None:
            min_proc = proc
        if max_proc is None:
            max_proc = proc

        dproc = super(DedicatedProcessorConfiguration, cls)._bld()

        dproc.desired_procs = proc
        dproc.max_procs = max_proc
        dproc.min_procs = min_proc

        return dproc

    @property
    def desired_procs(self):
        return self._get_val_str(_DED_PROCS, c.ZERO)

    @desired_procs.setter
    def desired_procs(self, value):
        self.set_parm_value(_DED_PROCS, value)

    @property
    def max_procs(self):
        return self._get_val_str(_DED_MAX_PROCS, c.ZERO)

    @max_procs.setter
    def max_procs(self, value):
        self.set_parm_value(_DED_MAX_PROCS, value)

    @property
    def min_procs(self):
        return self._get_val_str(_DED_MIN_PROCS, c.ZERO)

    @min_procs.setter
    def min_procs(self, value):
        self.set_parm_value(_DED_MIN_PROCS, value)


@ewrap.ElementWrapper.pvm_type('PartitionIOConfiguration', has_metadata=True)
class PartitionIOConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Dedicated IO Configuration.

    Comprised of I/O Slots.  There are two types of IO slots.  Those dedicated
    to physical hardware (io_slots) and those that get used by virtual
    hardware.
    """

    @classmethod
    def bld(cls, max_virt_slots):
        """Builds a Partition IO configuration wrapper.

        :param max_virt_slots: Number of virtual slots (int)
        :returns: Partition IO configuration wrapper

        """
        cfg = super(PartitionIOConfiguration, cls)._bld()
        cfg._host_channel_adpts([])
        cfg.max_virtual_slots = max_virt_slots
        cfg._io_slots([])
        cfg._profile_virtual_io_adapters([])

        return cfg

    @property
    def max_virtual_slots(self):
        """The maximum number of virtual slots.

        A slot is used for every VirtuScsiServerAdapter, TrunkAdapter, etc...
        """
        return self._get_val_int(_IO_CFG_MAX_SLOTS)

    @max_virtual_slots.setter
    def max_virtual_slots(self, value):
        self.set_parm_value(_IO_CFG_MAX_SLOTS, str(value))

    @property
    def io_slots(self):
        """The physical I/O Slots.

        Each slot will have hardware associated with it.
        """
        es = ewrap.WrapperElemList(self._find_or_seed(IO_SLOTS_ROOT), IOSlot)
        return es

    def _io_slots(self, value):
        self.replace_list(IO_SLOTS_ROOT, value)

    def _host_channel_adpts(self, value):
        self.replace_list(_HOST_CHANNEL_ADAPTERS, value)

    def _profile_virtual_io_adapters(self, value):
        self.replace_list(_PROFILE_IO_ADPTS, value)


@ewrap.ElementWrapper.pvm_type('ProfileIOSlot', has_metadata=True)
class IOSlot(ewrap.ElementWrapper):
    """An I/O Slot represents a device bus on the system.

    It may contain a piece of hardware within it.
    """

    @ewrap.ElementWrapper.pvm_type('AssociatedIOSlot', has_metadata=True)
    class AssociatedIOSlot(ewrap.ElementWrapper):
        """Internal class.  Hides the nested AssociatedIOSlot from parent.

        Every ProfileIOSlot contains one AssociatedIOSlot.  If both are
        exposed at the API level, the user would have to go from:
         - lpar -> partition i/o config -> i/o slot -> associated i/o slot ->
           i/o data

        Since every i/o slot has a single Associated I/O Slot (unless said
        I/O slot has no associated I/O), then we can just hide this from
        the user.

        We still keep the structure internally, but makes the API easier to
        consume.
        """

        @property
        def description(self):
            return self._get_val_str(_ASSOC_IO_SLOT_DESC)

        @property
        def phys_loc(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PHYS_LOC)

        @property
        def pc_adpt_id(self):
            return self._get_val_str(_ASSOC_IO_SLOT_ADPT_ID)

        @property
        def pci_class(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PCI_CLASS)

        @property
        def pci_dev_id(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PCI_DEV_ID)

        @property
        def pci_subsys_dev_id(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PCI_DEV_ID)

        @property
        def pci_mfg_id(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PCI_MFG_ID)

        @property
        def pci_rev_id(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PCI_REV_ID)

        @property
        def pci_vendor_id(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PCI_VENDOR_ID)

        @property
        def pci_subsys_vendor_id(self):
            return self._get_val_str(_ASSOC_IO_SLOT_SUBSYS_VENDOR_ID)

        @property
        def io_adapter(self):
            """Jumps over the 'Related IO Adapter' element direct to the I/O.

            This is another area where the schema has a two step jump that the
            API can avoid.  This method skips over the RelatedIOAdapter
            and jumps right to the IO Adapter.

            Return values are either the generic IOAdapter or the
            PhysFCAdapter.
            """
            # The child can be either an IO Adapter or a PhysFCAdapter.
            # Need to check for both...
            io_adpt_root = self._find(
                u.xpath(RELATED_IO_ADPT_ROOT, IOAdapter.schema_type))
            if io_adpt_root is not None:
                return IOAdapter.wrap(io_adpt_root)

            # Didn't have the generic...check for non-generic.
            io_adpt_root = self._find(
                u.xpath(RELATED_IO_ADPT_ROOT, PhysFCAdapter.schema_type))
            if io_adpt_root is not None:
                return PhysFCAdapter.wrap(io_adpt_root)

            return None

    def __get_prop(self, func):
        """Thin wrapper to get the Associated I/O Slot and get a property."""
        elem = self._find(ASSOC_IO_SLOT_ROOT)
        if elem is None:
            return None

        # Build the Associated IO Slot, find the function and execute it.
        assoc_io_slot = self.AssociatedIOSlot.wrap(elem)
        return getattr(assoc_io_slot, func)

    @property
    def description(self):
        return self.__get_prop('description')

    @property
    def phys_loc(self):
        return self.__get_prop('phys_loc')

    @property
    def pc_adpt_id(self):
        return self.__get_prop('pc_adpt_id')

    @property
    def pci_class(self):
        return self.__get_prop('pci_class')

    @property
    def pci_dev_id(self):
        return self.__get_prop('pci_dev_id')

    @property
    def pci_subsys_dev_id(self):
        return self.__get_prop('pci_subsys_dev_id')

    @property
    def pci_mfg_id(self):
        return self.__get_prop('pci_mfg_id')

    @property
    def pci_rev_id(self):
        return self.__get_prop('pci_rev_id')

    @property
    def pci_vendor_id(self):
        return self.__get_prop('pci_vendor_id')

    @property
    def pci_subsys_vendor_id(self):
        return self.__get_prop('pci_subsys_vendor_id')

    @property
    def adapter(self):
        """Returns the physical I/O Adapter for this slot.

        This will be one of two types.  Either a generic I/O Adapter or
        a Physical Fibre Channel Adapter (PhysFCAdapter).
        """
        return self.__get_prop('io_adapter')


@ewrap.ElementWrapper.pvm_type('IOAdapter', has_metadata=True)
class IOAdapter(ewrap.ElementWrapper):
    """A generic IO Adapter,

    This is a device plugged in to the system.  The location code indicates
    where it is plugged into the system.
    """

    @property
    def id(self):
        """The adapter system id."""
        return self._get_val_str(_IO_ADPT_ID)

    @property
    def description(self):
        return self._get_val_str(_IO_ADPT_DESC)

    @property
    def dev_name(self):
        return self._get_val_str(_IO_ADPT_DESC)

    @property
    def dyn_reconfig_conn_name(self):
        return self._get_val_str(_IO_ADPT_DYN_NAME)

    @property
    def phys_loc_code(self):
        return self._get_val_str(_IO_ADPT_PHYS_LOC)


@ewrap.ElementWrapper.pvm_type('PhysicalFibreChannelAdapter',
                               has_metadata=True)
class PhysFCAdapter(IOAdapter):
    """A Physical Fibre Channel I/O Adapter.

    Extends the generic I/O Adapter, but provides port detail as well.

    The adapter has a set of Physical Fibre Channel Ports (PhysFCPort).
    """

    @property
    def fc_ports(self):
        """The set of PhysFCPort's that are attached to this adapter.

        The data on this should be considered read only.
        """
        es = ewrap.WrapperElemList(self._find_or_seed(PFC_PORTS_ROOT),
                                   PhysFCPort)
        return es


@ewrap.ElementWrapper.pvm_type('PhysicalFibreChannelPort', has_metadata=True)
class PhysFCPort(ewrap.ElementWrapper):
    """A Physical Fibre Channel Port."""

    @classmethod
    def bld_ref(cls, name):
        """Create a wrapper that serves as a reference to a port.

        This is typically used when another element (ex. Virtual FC Mapping)
        requires a port to be specified in it.  Rather than query to find
        the port, one can simply be built and referenced as a child element.

        :param name: The name of the physical FC port.  End users need to
                     verify the port name.  Typically starts with 'fcs'.
        """
        port = super(PhysFCPort, cls)._bld()
        port._name(name)
        return port

    @property
    def loc_code(self):
        return self._get_val_str(_PFC_PORT_LOC_CODE)

    @property
    def name(self):
        return self._get_val_str(_PFC_PORT_NAME)

    def _name(self, value):
        return self.set_parm_value(_PFC_PORT_NAME, value)

    @property
    def udid(self):
        return self._get_val_str(_PFC_PORT_UDID)

    @property
    def wwpn(self):
        return self._get_val_str(PFC_PORT_WWPN)

    @property
    def npiv_available_ports(self):
        return self._get_val_int(_PFC_PORT_AVAILABLE_PORTS, 0)

    @property
    def npiv_total_ports(self):
        return self._get_val_int(_PFC_PORT_TOTAL_PORTS, 0)
