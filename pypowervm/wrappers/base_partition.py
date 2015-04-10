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

import pypowervm.util as u
import pypowervm.wrappers.constants as wc
import pypowervm.wrappers.entry_wrapper as ewrap

_BP_AVAIL_PRIORITY = 'AvailabilityPriority'
_BP_CURRENT_PROC_MODE = 'CurrentProcessorCompatibilityMode'
_BP_CAPABILITIES = 'PartitionCapabilities'
_BP_ID = 'PartitionID'
_BP_IO_CFG = 'PartitionIOConfiguration'
_BP_MEM_CFG = 'PartitionMemoryConfiguration'
_BP_NAME = 'PartitionName'
_BP_PROC_CFG = 'PartitionProcessorConfiguration'
_BP_STATE = 'PartitionState'
_BP_TYPE = 'PartitionType'
_BP_PENDING_PROC_MODE = 'PendingProcessorCompatibilityMode'
_BP_RMC_STATE = 'ResourceMonitoringControlState'
_BP_ASSOCIATED_SYSTEM = 'AssociatedManagedSystem'
_BP_SRIOV_ETH = 'SRIOVEthernetLogicalPorts'
_BP_SRIOV_FC_ETH = 'SRIOVFibreChannelOverEthernetLogicalPorts'
_BP_CNAS = 'ClientNetworkAdapters'
_BP_CNA_LINKS = u.xpath('ClientNetworkAdapters', wc.LINK)
_BP_HOST_ETH = 'HostEthernetAdapterLogicalPorts'

BP_EL_ORDER = (
    _BP_AVAIL_PRIORITY, _BP_CURRENT_PROC_MODE, _BP_CAPABILITIES, _BP_ID,
    _BP_IO_CFG, _BP_MEM_CFG, _BP_NAME, _BP_PROC_CFG, _BP_STATE, _BP_TYPE,
    _BP_PENDING_PROC_MODE, _BP_ASSOCIATED_SYSTEM, _BP_SRIOV_ETH,
    _BP_SRIOV_FC_ETH, _BP_CNAS, _BP_HOST_ETH
)

# Dedicated Processor Configuration (_DPC)
_DPC_DES_PROCS = 'DesiredProcessors'
_DPC_MAX_PROCS = 'MaximumProcessors'
_DPC_MIN_PROCS = 'MinimumProcessors'

# Shared Processor Configuration (_SPC)
_SPC_DES_PROC_UNIT = 'DesiredProcessingUnits'
_SPC_MIN_PROC_UNIT = 'MinimumProcessingUnits'
_SPC_MAX_PROC_UNIT = 'MaximumProcessingUnits'
_SPC_DES_VIRT_PROC = 'DesiredVirtualProcessors'
_SPC_MIN_VIRT_PROC = 'MinimumVirtualProcessors'
_SPC_MAX_VIRT_PROC = 'MaximumVirtualProcessors'
_SPC_SHARED_PROC_POOL_ID = 'SharedProcessorPoolID'
_SPC_UNCAPPED_WEIGHT = 'UncappedWeight'

# Partition Memory Configuration (_MEM)
_MEM_DES = 'DesiredMemory'
_MEM_MAX = 'MaximumMemory'
_MEM_MIN = 'MinimumMemory'
_MEM_RUN = 'RuntimeMemory'
_MEM_CURR = 'CurrentMemory'
_MEM_CURR_MAX = 'CurrentMaximumMemory'
_MEM_CURR_MIN = 'CurrentMinimumMemory'
_MEM_SHARED_MEM_ENABLED = 'SharedMemoryEnabled'

# Partition I/O Configuration (_IO)
IO_CFG_ROOT = _BP_IO_CFG
_IO_MAX_SLOTS = 'MaximumVirtualIOSlots'

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

_CAP_DLPAR_MEM_CAPABLE = u.xpath(
    _BP_CAPABILITIES, 'DynamicLogicalPartitionMemoryCapable')
_CAP_DLPAR_PROC_CAPABLE = u.xpath(
    _BP_CAPABILITIES, 'DynamicLogicalPartitionProcessorCapable')

# Processor Configuration (_PC)
_PC_HAS_DED_PROCS = 'HasDedicatedProcessors'
_PC_DED_PROC_CFG = 'DedicatedProcessorConfiguration'
_PC_SHR_PROC_CFG = 'SharedProcessorConfiguration'
_PC_SHARING_MODE = 'SharingMode'
_PC_CURR_SHARING_MODE = 'CurrentSharingMode'
_PC_CURR_USE_DED_PROCS = u.xpath(_BP_PROC_CFG, 'CurrentHasDedicatedProcessors')
_PC_DED_PROC_CONFIG = u.xpath(_BP_PROC_CFG, 'DedicatedProcessorConfiguration')
_PC_CURR_DED_PROC_CONFIG = u.xpath(
    _BP_PROC_CFG, 'CurrentDedicatedProcessorConfiguration')
_PC_CURR_SHARED_PROC_CONFIG = u.xpath(
    _BP_PROC_CFG, 'CurrentSharedProcessorConfiguration')

# Current Dedicated Processor Configuration (_CDPC)
_CDPC_CURR_PROCS = u.xpath(_PC_CURR_DED_PROC_CONFIG, 'CurrentProcessors')
_CDPC_CURR_MAX_PROCS = u.xpath(
    _PC_CURR_DED_PROC_CONFIG, 'CurrentMaximumProcessors')
_CDPC_CURR_MIN_PROCS = u.xpath(
    _PC_CURR_DED_PROC_CONFIG, 'CurrentMinimumProcessors')
_CDPC_RUN_PROCS = u.xpath(_PC_CURR_DED_PROC_CONFIG, 'RunProcessors')

# Current Shared Processor Configuration (_CSPC)
_CSPC_ALLOC_VCPU = u.xpath(
    _PC_CURR_SHARED_PROC_CONFIG, 'AllocatedVirtualProcessors')
_CSPC_MAX_VCPU = u.xpath(
    _PC_CURR_SHARED_PROC_CONFIG, 'CurrentMaximumVirtualProcessors')
_CSPC_MIN_VCPU = u.xpath(
    _PC_CURR_SHARED_PROC_CONFIG, 'CurrentMinimumVirtualProcessors')
_CSPC_PROC_UNITS = u.xpath(
    _PC_CURR_SHARED_PROC_CONFIG, 'CurrentProcessingUnits')
_CSPC_MAX_PROC_UNITS = u.xpath(
    _PC_CURR_SHARED_PROC_CONFIG, 'CurrentMaximumProcessingUnits')
_CSPC_MIN_PROC_UNITS = u.xpath(
    _PC_CURR_SHARED_PROC_CONFIG, 'CurrentMinimumProcessingUnits')
_CSPC_UNCAPPED_WEIGHT = u.xpath(
    _PC_CURR_SHARED_PROC_CONFIG, 'CurrentUncappedWeight')


# Shared Proc, sharing modes.
class SharingModesEnum(object):
    CAPPED = 'capped'
    UNCAPPED = 'uncapped'
    ALL_VALUES = (CAPPED, UNCAPPED)


# Dedicated sharing modes
class DedicatedSharingModesEnum(object):
    SHARE_IDLE_PROCS = 'sre idle proces'
    SHARE_IDLE_PROCS_ACTIVE = 'sre idle procs active'
    SHARE_IDLE_PROCS_ALWAYS = 'sre idle procs always'
    KEEP_IDLE_PROCS = 'keep idle procs'
    ALL_VALUES = (SHARE_IDLE_PROCS, SHARE_IDLE_PROCS_ACTIVE,
                  SHARE_IDLE_PROCS_ALWAYS, KEEP_IDLE_PROCS)


class LPARTypeEnum(object):
    """Subset of LogicalPartitionEnvironmentEnum."""
    OS400 = 'OS400'
    AIXLINUX = 'AIX/Linux'
    VIOS = 'Virtual IO Server'


class LPARCompatEnum(object):
    DEFAULT = 'default'
    POWER6 = 'POWER6'
    POWER6_PLUS = 'POWER6_Plus'
    POWER7 = 'POWER7'
    POWER7_PLUS = 'POWER7_Plus'
    POWER8 = 'POWER8'
    ALL_VALUES = (DEFAULT, POWER6, POWER6_PLUS, POWER7, POWER7_PLUS,
                  POWER8)


class BasePartition(ewrap.EntryWrapper):

    search_keys = dict(name=_BP_NAME, id=_BP_ID)

    @classmethod
    def bld(cls, name, mem_cfg, proc_cfg, env, io_cfg=None):
        """Creates a BasePartition wrapper.

        :param name: The name of the partition
        :param mem_cfg: The memory configuration wrapper
        :param proc_cfg: The processor configuration wrapper
        :param env: The type of partition, taken from LPARTypeEnum
        :param io_cfg: The I/O configuration wrapper

        :returns: New BasePartition wrapper
        """

        partition = super(BasePartition, cls)._bld()
        if io_cfg:
            partition.io_config = io_cfg
        partition.mem_config = mem_cfg
        partition.name = name
        partition.proc_config = proc_cfg
        partition._env(env)

        return partition

    @property
    def state(self):
        """See LogicalPartitionStateEnum.

        e.g. 'not activated', 'running', 'migrating running', etc.
        """
        return self._get_val_str(_BP_STATE)

    @property
    def is_running(self):
        return self.state == 'running'

    @property
    def name(self):
        """Short name (not ID, MTMS, or hostname)."""
        return self._get_val_str(_BP_NAME)

    @name.setter
    def name(self, val):
        self.set_parm_value(_BP_NAME, val)

    @property
    def id(self):
        """Short ID (not UUID)."""
        # TODO(efried): This should use _get_val_int and default to None
        return int(self._get_val_str(_BP_ID, wc.ZERO))

    @property
    def env(self):
        """See LogicalPartitionEnvironmentEnum.

        Should always be 'AIX/Linux' for LPAREntry.  'Virtual IO Server'
        should only happen for VIOSEntry.
        """
        return self._get_val_str(_BP_TYPE)

    def _env(self, val):
        self.set_parm_value(_BP_TYPE, val)

    @property
    def assoc_sys_uuid(self):
        """UUID of the associated ManagedSystem."""
        href = self.get_href(_BP_ASSOCIATED_SYSTEM, one_result=True)
        return u.get_req_path_uuid(href, preserve_case=True) if href else None

    @property
    def cna_uris(self):
        """List of URI strings to the partition's ClientNetworkAdapters.

        This is a READ ONLY list.
        """
        return self.get_href(_BP_CNA_LINKS)

    @property
    def rmc_state(self):
        """See ResourceMonitoringControlStateEnum.

        e.g. 'active', 'inactive', 'busy', etc.
        """
        return self._get_val_str(_BP_RMC_STATE)

    @property
    def is_rmc_active(self):
        return self.rmc_state == 'active'

    @property
    def io_config(self):
        """The Partition I/O Configuration."""
        elem = self._find(_BP_IO_CFG)
        return PartitionIOConfiguration.wrap(elem)

    @io_config.setter
    def io_config(self, io_cfg):
        """The Partition I/O Configuration for the LPAR."""
        elem = self._find_or_seed(_BP_IO_CFG)
        # TODO(efried): All instances of _find_or_seed + element.replace should
        # probably be inject instead
        self.element.replace(elem, io_cfg.element)

    @property
    def mem_config(self):
        """The Partition Memory Configuration for the LPAR."""
        elem = self._find(_BP_MEM_CFG)
        return PartitionMemoryConfiguration.wrap(elem)

    @mem_config.setter
    def mem_config(self, mem_cfg):
        """The Partition Memory Configuration for the LPAR."""
        elem = self._find_or_seed(_BP_MEM_CFG)
        self.element.replace(elem, mem_cfg.element)

    @property
    def proc_config(self):
        """The Partition Processor Configuration for the LPAR."""
        elem = self._find(_BP_PROC_CFG)
        return PartitionProcessorConfiguration.wrap(elem)

    @proc_config.setter
    def proc_config(self, proc_config):
        """The Partition Processor Configuration for the LPAR."""
        elem = self._find_or_seed(_BP_PROC_CFG)
        self.element.replace(elem, proc_config.element)

    @property
    def avail_priority(self):
        return self._get_val_str(_BP_AVAIL_PRIORITY, wc.ZERO)

    @avail_priority.setter
    def avail_priority(self, value):
        self.set_parm_value(_BP_AVAIL_PRIORITY, value)

    @property
    def proc_compat_mode(self):
        """*Current* processor compatibility mode.

        See LPARCompatEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self._get_val_str(_BP_CURRENT_PROC_MODE)

    @property
    def pending_proc_compat_mode(self):
        """Pending processor compatibility mode.

        See LPARCompatEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self._get_val_str(_BP_PENDING_PROC_MODE)

    @proc_compat_mode.setter
    def proc_compat_mode(self, value):
        """Sets *PENDING* proc compat mode.

        Note that corresponding getter retrieves the *CURRENT* proc compat
        mode.
        """
        self.set_parm_value(_BP_PENDING_PROC_MODE, value)

    def check_dlpar_connectivity(self):
        """Check the partition for DLPAR capability and rmc state.

        :returns: Returns true or false if DLPAR capable
        :returns: Returns RMC state as string
        """

        # Pull the dlpar and rmc values from PowerVM
        mem_dlpar = self._get_val_bool(_CAP_DLPAR_MEM_CAPABLE)
        proc_dlpar = self._get_val_bool(_CAP_DLPAR_PROC_CAPABLE)

        dlpar = mem_dlpar and proc_dlpar

        return dlpar, self.rmc_state

    @property
    def current_mem(self):
        return self.mem_config.current_mem

    @property
    def current_max_mem(self):
        return self.mem_config.current_max_mem

    @property
    def current_min_mem(self):
        return self.mem_config.current_min_mem

    @property
    def desired_mem(self):
        return self.mem_config.desired_mem

    @property
    def max_mem(self):
        return self.mem_config.max_mem

    @property
    def min_mem(self):
        return self.mem_config.min_mem

    @property
    def run_mem(self):
        return self.mem_config.run_mem

    @property
    def current_mem_share_enabled(self):
        return self.mem_config.current_mem_share_enabled

    @property
    def current_proc_mode_is_dedicated(self):
        """Returns boolean True if dedicated, False if shared or not found."""
        return self._get_val_bool(_PC_CURR_USE_DED_PROCS, False)

    @property
    def proc_mode_is_dedicated(self):
        return self.proc_config.has_dedicated_proc

    @property
    def current_procs(self):
        return self._get_val_str(_CDPC_CURR_PROCS, wc.ZERO)

    @property
    def current_max_procs(self):
        return self._get_val_str(_CDPC_CURR_MAX_PROCS, wc.ZERO)

    @property
    def current_min_procs(self):
        return self._get_val_str(_CDPC_CURR_MIN_PROCS, wc.ZERO)

    @property
    def desired_procs(self):
        return self.proc_config.dedicated_proc_cfg.desired_procs

    @property
    def max_procs(self):
        return self.proc_config.dedicated_proc_cfg.max_procs

    @property
    def min_procs(self):
        return self.proc_config.dedicated_proc_cfg.min_procs

    @property
    def current_vcpus(self):
        return self._get_val_str(_CSPC_ALLOC_VCPU, wc.ZERO)

    @property
    def current_max_vcpus(self):
        return self._get_val_str(_CSPC_MAX_VCPU, wc.ZERO)

    @property
    def current_min_vcpus(self):
        return self._get_val_str(_CSPC_MIN_VCPU, wc.ZERO)

    @property
    def desired_vcpus(self):
        return self.proc_config.shared_proc_cfg.desired_vcpus

    @property
    def max_vcpus(self):
        return self.proc_config.shared_proc_cfg.max_vcpus

    @property
    def min_vcpus(self):
        return self.proc_config.shared_proc_cfg.min_vcpus

    @property
    def current_proc_units(self):
        return self._get_val_str(_CSPC_PROC_UNITS, wc.ZERO)

    @property
    def current_max_proc_units(self):
        return self._get_val_str(_CSPC_MAX_PROC_UNITS, wc.ZERO)

    @property
    def current_min_proc_units(self):
        return self._get_val_str(_CSPC_MIN_PROC_UNITS, wc.ZERO)

    @property
    def desired_proc_units(self):
        return self.proc_config.shared_proc_cfg.desired_proc_units

    @property
    def max_proc_units(self):
        return self.proc_config.shared_proc_cfg.max_proc_units

    @property
    def min_proc_units(self):
        return self.proc_config.shared_proc_cfg.min_proc_units

    @property
    def run_procs(self):
        return self._get_val_str(_CDPC_RUN_PROCS, wc.ZERO)

    @property
    def current_uncapped_weight(self):
        return self._get_val_str(_CSPC_UNCAPPED_WEIGHT, wc.ZERO)

    @property
    def uncapped_weight(self):
        return self.proc_config.shared_proc_cfg.uncapped_weight

    @property
    def shared_proc_pool_id(self):
        return self.proc_config.shared_proc_cfg.shared_proc_pool_id

    @property
    def sharing_mode(self):
        return self.proc_config.sharing_mode

    @desired_mem.setter
    def desired_mem(self, value):
        self.mem_config.desired_mem = value

    @max_mem.setter
    def max_mem(self, value):
        self.mem_config.max_mem = value

    @min_mem.setter
    def min_mem(self, value):
        self.mem_config.min_mem = value

    @sharing_mode.setter
    def sharing_mode(self, value):
        self.proc_config.sharing_mode = value

    @desired_procs.setter
    def desired_procs(self, value):
        self.proc_config.dedicated_proc_cfg.desired_procs = value

    @max_procs.setter
    def max_procs(self, value):
        self.proc_config.dedicated_proc_cfg.max_procs = value

    @min_procs.setter
    def min_procs(self, value):
        self.proc_config.dedicated_proc_cfg.min_procs = value

    @desired_vcpus.setter
    def desired_vcpus(self, value):
        self.proc_config.shared_proc_cfg.desired_vcpus = value

    @max_vcpus.setter
    def max_vcpus(self, value):
        self.proc_config.shared_proc_cfg.max_vcpus = value

    @min_vcpus.setter
    def min_vcpus(self, value):
        self.proc_config.shared_proc_cfg.min_vcpus = value

    @desired_proc_units.setter
    def desired_proc_units(self, value):
        self.proc_config.shared_proc_cfg.desired_proc_units = value

    @max_proc_units.setter
    def max_proc_units(self, value):
        self.proc_config.shared_proc_cfg.max_proc_units = value

    @min_proc_units.setter
    def min_proc_units(self, value):
        self.proc_config.shared_proc_cfg.min_proc_units = value

    @uncapped_weight.setter
    def uncapped_weight(self, value):
        self.proc_config.shared_proc_cfg.uncapped_weight = value

    @proc_mode_is_dedicated.setter
    def proc_mode_is_dedicated(self, value):
        """Expects 'true' (string) for dedicated or 'false' for shared."""
        self.proc_config._has_dedicated_proc = value


@ewrap.ElementWrapper.pvm_type(_BP_PROC_CFG, has_metadata=True)
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
        """Returns boolean True if dedicated, False if shared or not found."""
        return self._get_val_bool(_PC_HAS_DED_PROCS)

    def _has_dedicated_proc(self, val):
        """Expects 'true' (string) for dedicated or 'false' for shared."""
        self.set_parm_value(_PC_HAS_DED_PROCS, u.sanitize_bool_for_api(val))

    @property
    def sharing_mode(self):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        return self._get_val_str(_PC_CURR_SHARING_MODE)

    @sharing_mode.setter
    def sharing_mode(self, value):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        self.set_parm_value(_PC_SHARING_MODE, value)

    @property
    def shared_proc_cfg(self):
        """Returns the Shared Processor Configuration."""
        return SharedProcessorConfiguration.wrap(
            self._find(_PC_SHR_PROC_CFG))

    def _shared_proc_cfg(self, spc):
        elem = self._find_or_seed(_PC_SHR_PROC_CFG)
        self.element.replace(elem, spc.element)

    @property
    def dedicated_proc_cfg(self):
        """Returns the Dedicated Processor Configuration."""
        return DedicatedProcessorConfiguration.wrap(
            self._find(_PC_DED_PROC_CFG))

    def _dedicated_proc_cfg(self, dpc):
        elem = self._find_or_seed(_PC_DED_PROC_CFG)
        self.element.replace(elem, dpc.element)


@ewrap.ElementWrapper.pvm_type(_BP_MEM_CFG, has_metadata=True)
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
        return self._get_val_int(_MEM_CURR, wc.ZERO)

    @property
    def current_max_mem(self):
        return self._get_val_int(_MEM_CURR_MAX, wc.ZERO)

    @property
    def current_min_mem(self):
        return self._get_val_int(_MEM_CURR_MIN, wc.ZERO)

    @property
    def desired_mem(self):
        return self._get_val_int(_MEM_DES, wc.ZERO)

    @desired_mem.setter
    def desired_mem(self, mem):
        self.set_parm_value(_MEM_DES, str(mem))

    @property
    def max_mem(self):
        return self._get_val_int(_MEM_MAX, wc.ZERO)

    @max_mem.setter
    def max_mem(self, mem):
        self.set_parm_value(_MEM_MAX, str(mem))

    @property
    def min_mem(self):
        return self._get_val_int(_MEM_MIN, wc.ZERO)

    @min_mem.setter
    def min_mem(self, mem):
        self.set_parm_value(_MEM_MIN, str(mem))

    @property
    def run_mem(self):
        """Runtime memory."""
        return self._get_val_int(_MEM_RUN, wc.ZERO)

    @property
    def current_mem_share_enabled(self):
        # The default is None instead of False so that the caller
        # can know if the value is not set
        return self._get_val_bool(_MEM_SHARED_MEM_ENABLED, None)


@ewrap.ElementWrapper.pvm_type(_PC_SHR_PROC_CFG, has_metadata=True)
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
        return self._get_val_float(_SPC_DES_PROC_UNIT)

    @desired_proc_units.setter
    def desired_proc_units(self, val):
        self.set_parm_value(_SPC_DES_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def max_proc_units(self):
        return self._get_val_float(_SPC_MAX_PROC_UNIT)

    @max_proc_units.setter
    def max_proc_units(self, val):
        self.set_parm_value(_SPC_MAX_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def min_proc_units(self):
        return self._get_val_float(_SPC_MIN_PROC_UNIT)

    @min_proc_units.setter
    def min_proc_units(self, val):
        self.set_parm_value(_SPC_MIN_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def desired_vcpus(self):
        return self._get_val_int(_SPC_DES_VIRT_PROC, 0)

    @desired_vcpus.setter
    def desired_vcpus(self, val):
        self.set_parm_value(_SPC_DES_VIRT_PROC, val)

    @property
    def max_vcpus(self):
        return self._get_val_int(_SPC_MAX_VIRT_PROC, 0)

    @max_vcpus.setter
    def max_vcpus(self, val):
        self.set_parm_value(_SPC_MAX_VIRT_PROC, val)

    @property
    def min_vcpus(self):
        return self._get_val_int(_SPC_MIN_VIRT_PROC, 0)

    @min_vcpus.setter
    def min_vcpus(self, val):
        self.set_parm_value(_SPC_MIN_VIRT_PROC, val)

    @property
    def shared_proc_pool_id(self):
        return self._get_val_int(_SPC_SHARED_PROC_POOL_ID, 0)

    @shared_proc_pool_id.setter
    def shared_proc_pool_id(self, val):
        self.set_parm_value(_SPC_SHARED_PROC_POOL_ID, val)

    @property
    def uncapped_weight(self):
        return self._get_val_int(_SPC_UNCAPPED_WEIGHT, 0)

    @uncapped_weight.setter
    def uncapped_weight(self, val):
        self.set_parm_value(_SPC_UNCAPPED_WEIGHT, str(val))


@ewrap.ElementWrapper.pvm_type(_PC_DED_PROC_CFG, has_metadata=True)
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
        return self._get_val_str(_DPC_DES_PROCS, wc.ZERO)

    @desired_procs.setter
    def desired_procs(self, value):
        self.set_parm_value(_DPC_DES_PROCS, value)

    @property
    def max_procs(self):
        return self._get_val_str(_DPC_MAX_PROCS, wc.ZERO)

    @max_procs.setter
    def max_procs(self, value):
        self.set_parm_value(_DPC_MAX_PROCS, value)

    @property
    def min_procs(self):
        return self._get_val_str(_DPC_MIN_PROCS, wc.ZERO)

    @min_procs.setter
    def min_procs(self, value):
        self.set_parm_value(_DPC_MIN_PROCS, value)


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
        cfg.max_virtual_slots = max_virt_slots

        return cfg

    @property
    def max_virtual_slots(self):
        """The maximum number of virtual slots.

        A slot is used for every VirtuScsiServerAdapter, TrunkAdapter, etc...
        """
        return self._get_val_int(_IO_MAX_SLOTS)

    @max_virtual_slots.setter
    def max_virtual_slots(self, value):
        self.set_parm_value(_IO_MAX_SLOTS, value)

    @property
    def io_slots(self):
        """The physical I/O Slots.

        Each slot will have hardware associated with it.
        """
        es = ewrap.WrapperElemList(self._find_or_seed(IO_SLOTS_ROOT), IOSlot)
        return es


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
