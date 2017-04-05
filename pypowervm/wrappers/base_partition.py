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

"""Base classes, enums, and constants shared by LPAR and VIOS EntryWrappers."""
from pypowervm import const
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.iocard as card

# Base Partition (_BP)
_BP_ALLOW_PERF_DATA_COLL = 'AllowPerformanceDataCollection'
_BP_ASSOC_PROF = 'AssociatedPartitionProfile'
_BP_AVAIL_PRIORITY = 'AvailabilityPriority'
_BP_CURR_BSR_ARRAYS = 'CurrentAllocatedBarrierSynchronizationRegisterArrays'
_BP_CURRENT_PROC_MODE = 'CurrentProcessorCompatibilityMode'
_BP_PROFILE_SYNC = 'CurrentProfileSync'
_BP_HOSTNAME = 'Hostname'
_BP_BOOTABLE = 'IsBootable'
_BP_CALL_HOME = 'IsCallHomeEnabled'
_BP_CONN_MONITORING = 'IsConnectionMonitoringEnabled'
_BP_OP_IN_PROGRESS = 'IsOperationInProgress'
_BP_REDUNDANT_ERR_PATH_REP = 'IsRedundantErrorPathReportingEnabled'
_BP_TIME_REF = 'IsTimeReferencePartition'
_BP_ATTN_LED = 'IsVirtualServiceAttentionLEDOn'
_BP_TRUSTED_PLATFORM = 'IsVirtualTrustedPlatformModuleEnabled'
_BP_KEYLOCK_POS = 'KeylockPosition'
_BP_LOGICAL_SERIAL_NUM = 'LogicalSerialNumber'
_BP_OS_VER = 'OperatingSystemVersion'
_BP_CAPABILITIES = 'PartitionCapabilities'
_BP_ID = 'PartitionID'
_BP_IO_CFG = 'PartitionIOConfiguration'
_BP_MEM_CFG = 'PartitionMemoryConfiguration'
_BP_NAME = 'PartitionName'
_BP_PROC_CFG = 'PartitionProcessorConfiguration'
_BP_PROFS = 'PartitionProfiles'
_BP_STATE = 'PartitionState'
_BP_TYPE = 'PartitionType'
_BP_UUID = 'PartitionUUID'
_BP_PENDING_PROC_MODE = 'PendingProcessorCompatibilityMode'
_BP_PROC_POOL = 'ProcessorPool'
_BP_PROG_DATA_REMAIN = 'ProgressPartitionDataRemaining'
_BP_PROG_DATA_TOTAL = 'ProgressPartitionDataTotal'
_BP_PROG_STATE = 'ProgressState'
_BP_RMC_STATE = 'ResourceMonitoringControlState'
_BP_RMC_IP = 'ResourceMonitoringIPAddress'
_BP_VAL_INT_PERF = 'ValidInteractivePerformance'
_BP_ASSOC_SYSTEM = 'AssociatedManagedSystem'
_BP_SRIOV_ETH = 'SRIOVEthernetLogicalPorts'
_BP_SRIOV_ROCE = 'SRIOVRoCELogicalPorts'
_BP_SRIOV_FC_ETH = 'SRIOVFibreChannelOverEthernetLogicalPorts'
_BP_CNAS = 'ClientNetworkAdapters'
_BP_HOST_ETH = 'HostEthernetAdapterLogicalPorts'
_BP_MAC_PREF = 'MACAddressPrefix'
_BP_SVC_PARTITION = 'IsServicePartition'
_BP_MGMT_CAP = 'PowerVMManagementCapable'
_BP_REF_CODE = 'ReferenceCode'
_BP_REF_CODE_FULL = 'ReferenceCodeFull'
_BP_MGT_PARTITION = 'IsManagementPartition'
_BP_AUTO_START = 'AutoStart'
_BP_BOOT_MODE = 'BootMode'
_BP_NVRAM = 'PartitionNVRAM'
_BP_UPTIME = 'Uptime'
_BP_DISABLE_SECURE_BOOT = 'DisableSecureBoot'
_BP_ASSOC_GROUPS = 'AssociatedGroups'
_BP_POWER_ON_WITH_HYP = 'PowerOnWithHypervisor'
_BP_ASSOC_TASKS = 'AssociatedTasks'
_BP_DESC = 'Description'

BP_EL_ORDER = (
    _BP_ALLOW_PERF_DATA_COLL, _BP_ASSOC_PROF, _BP_AVAIL_PRIORITY,
    _BP_CURR_BSR_ARRAYS, _BP_CURRENT_PROC_MODE, _BP_PROFILE_SYNC, _BP_HOSTNAME,
    _BP_BOOTABLE, _BP_CALL_HOME, _BP_CONN_MONITORING, _BP_OP_IN_PROGRESS,
    _BP_REDUNDANT_ERR_PATH_REP, _BP_TIME_REF, _BP_ATTN_LED,
    _BP_TRUSTED_PLATFORM, _BP_KEYLOCK_POS, _BP_LOGICAL_SERIAL_NUM, _BP_OS_VER,
    _BP_CAPABILITIES, _BP_ID, _BP_IO_CFG, _BP_MEM_CFG, _BP_NAME, _BP_PROC_CFG,
    _BP_PROFS, _BP_STATE, _BP_TYPE, _BP_UUID, _BP_PENDING_PROC_MODE,
    _BP_PROC_POOL, _BP_PROG_DATA_REMAIN, _BP_PROG_DATA_TOTAL, _BP_PROG_STATE,
    _BP_RMC_STATE, _BP_RMC_IP, _BP_VAL_INT_PERF, _BP_ASSOC_SYSTEM,
    _BP_SRIOV_ETH, _BP_SRIOV_ROCE, _BP_SRIOV_FC_ETH, _BP_CNAS, _BP_HOST_ETH,
    _BP_MAC_PREF, _BP_SVC_PARTITION, _BP_MGMT_CAP, _BP_REF_CODE,
    _BP_REF_CODE_FULL, _BP_MGT_PARTITION, _BP_AUTO_START, _BP_BOOT_MODE,
    _BP_NVRAM, _BP_UPTIME, _BP_DISABLE_SECURE_BOOT, _BP_ASSOC_GROUPS,
    _BP_POWER_ON_WITH_HYP, _BP_ASSOC_TASKS, _BP_DESC
)

# Partition Capabilities (_CAP)
_CAP_DLPAR_IO_CAPABLE = 'DynamicLogicalPartitionIOCapable'
_CAP_DLPAR_MEM_CAPABLE = 'DynamicLogicalPartitionMemoryCapable'
_CAP_DLPAR_PROC_CAPABLE = 'DynamicLogicalPartitionProcessorCapable'
_CAP_INTRUSION_DETECT_CAPABLE = 'InternalAndExternalIntrusionDetectionCapable'
_CAP_RMC_OS_SHUTDOWN_CAPABLE = ('ResourceMonitoringControlOperatingSystem'
                                'ShutdownCapable')
_CAP_EL_ORDER = (_CAP_DLPAR_IO_CAPABLE, _CAP_DLPAR_MEM_CAPABLE,
                 _CAP_DLPAR_PROC_CAPABLE, _CAP_INTRUSION_DETECT_CAPABLE,
                 _CAP_RMC_OS_SHUTDOWN_CAPABLE,)

# Processor Configuration (_PC)
_PC_DED_PROC_CFG = 'DedicatedProcessorConfiguration'
_PC_HAS_DED_PROCS = 'HasDedicatedProcessors'
_PC_SHR_PROC_CFG = 'SharedProcessorConfiguration'
_PC_SHARING_MODE = 'SharingMode'
_PC_CURR_HAS_DED_PROCS = 'CurrentHasDedicatedProcessors'
_PC_CURR_SHARING_MODE = 'CurrentSharingMode'
_PC_CURR_DED_PROC_CFG = 'CurrentDedicatedProcessorConfiguration'
_PC_RUN_HAS_DED_PROCS = 'RuntimeHasDedicatedProcessors'
_PC_RUN_SHARING_MODE = 'RuntimeSharingMode'
_PC_CURR_SHR_PROC_CFG = 'CurrentSharedProcessorConfiguration'
_PC_EL_ORDER = (_PC_DED_PROC_CFG, _PC_HAS_DED_PROCS, _PC_SHR_PROC_CFG,
                _PC_SHARING_MODE, _PC_CURR_HAS_DED_PROCS,
                _PC_CURR_SHARING_MODE, _PC_CURR_DED_PROC_CFG,
                _PC_RUN_HAS_DED_PROCS, _PC_RUN_SHARING_MODE,
                _PC_CURR_SHR_PROC_CFG)

# Shared Processor Configuration (_SPC)
_SPC_DES_PROC_UNIT = 'DesiredProcessingUnits'
_SPC_DES_VIRT_PROC = 'DesiredVirtualProcessors'
_SPC_MAX_PROC_UNIT = 'MaximumProcessingUnits'
_SPC_MAX_VIRT_PROC = 'MaximumVirtualProcessors'
_SPC_MIN_PROC_UNIT = 'MinimumProcessingUnits'
_SPC_MIN_VIRT_PROC = 'MinimumVirtualProcessors'
_SPC_SHARED_PROC_POOL_ID = 'SharedProcessorPoolID'
_SPC_UNCAPPED_WEIGHT = 'UncappedWeight'
_SPC_ALLOC_VIRT_PROC = 'AllocatedVirtualProcessors'
_SPC_CURR_MAX_PROC_UNIT = 'CurrentMaximumProcessingUnits'
_SPC_CURR_MIN_PROC_UNIT = 'CurrentMinimumProcessingUnits'
_SPC_CURR_PROC_UNIT = 'CurrentProcessingUnits'
_SPC_CURR_SHARED_PROC_POOL_ID = 'CurrentSharedProcessorPoolID'
_SPC_CURR_UNCAPPED_WEIGHT = 'CurrentUncappedWeight'
_SPC_CURR_MIN_VIRT_PROC = 'CurrentMinimumVirtualProcessors'
_SPC_CURR_MAX_VIRT_PROC = 'CurrentMaximumVirtualProcessors'
_SPC_RUN_PROC_UNIT = 'RuntimeProcessingUnits'
_SPC_RUN_UNCAPPED_WEIGHT = 'RuntimeUncappedWeight'
_SPC_EL_ORDER = (_SPC_DES_PROC_UNIT, _SPC_DES_VIRT_PROC, _SPC_MAX_PROC_UNIT,
                 _SPC_MAX_VIRT_PROC, _SPC_MIN_PROC_UNIT, _SPC_MIN_VIRT_PROC,
                 _SPC_SHARED_PROC_POOL_ID, _SPC_UNCAPPED_WEIGHT,
                 _SPC_ALLOC_VIRT_PROC, _SPC_CURR_MAX_PROC_UNIT,
                 _SPC_CURR_MIN_PROC_UNIT, _SPC_CURR_PROC_UNIT,
                 _SPC_CURR_SHARED_PROC_POOL_ID, _SPC_CURR_UNCAPPED_WEIGHT,
                 _SPC_CURR_MIN_VIRT_PROC, _SPC_CURR_MAX_VIRT_PROC,
                 _SPC_RUN_PROC_UNIT, _SPC_RUN_UNCAPPED_WEIGHT)

# Dedicated Processor Configuration (_DPC)
_DPC_DES_PROCS = 'DesiredProcessors'
_DPC_MAX_PROCS = 'MaximumProcessors'
_DPC_MIN_PROCS = 'MinimumProcessors'

# Partition Memory Configuration (_MEM)
_MEM_PROF_AME_ENABLED = 'ActiveMemoryExpansionEnabled'
_MEM_AMS_ENABLED = 'ActiveMemorySharingEnabled'
_MEM_BSR_ARRAY_CT = 'BarrierSynchronizationRegisterArrayCount'
_MEM_DES_ENT = 'DesiredEntitledMemory'
_MEM_DES_HUGE_PAGE_CT = 'DesiredHugePageCount'
_MEM_DES = 'DesiredMemory'
_MEM_EXP_FACTOR = 'ExpansionFactor'
_MEM_HW_PG_TBL_RATIO = 'HardwarePageTableRatio'
_MEM_MAN_ENT_MODE_ENABLED = 'ManualEntitledModeEnabled'
_MEM_MAX_HUGE_PG_CT = 'MaximumHugePageCount'
_MEM_MAX = 'MaximumMemory'
_MEM_WT = 'MemoryWeight'
_MEM_MIN_HUGE_PG_CT = 'MinimumHugePageCount'
_MEM_MIN = 'MinimumMemory'
_MEM_PRI_PGING_SVC_PART = 'PrimaryPagingServicePartition'
_MEM_SEC_PGING_SVC_PART = 'SecondaryPagingServicePartition'
_MEM_AUTO_ENT_MEM_ENABLED = 'AutoEntitledMemoryEnabled'
_MEM_CURR_BSR_ARRAYS = 'CurrentBarrierSynchronizationRegisterArrays'
_MEM_CURR_ENT = 'CurrentEntitledMemory'
_MEM_CURR_EXP_FACT = 'CurrentExpansionFactor'
_MEM_CURR_HW_PG_TBL_RATIO = 'CurrentHardwarePageTableRatio'
_MEM_CURR_HUGE_PG_CT = 'CurrentHugePageCount'
_MEM_CURR_MAX_HUGE_PG_CT = 'CurrentMaximumHugePageCount'
_MEM_CURR_MAX = 'CurrentMaximumMemory'
_MEM_CUR = 'CurrentMemory'
_MEM_CURR_MEM_WT = 'CurrentMemoryWeight'
_MEM_CURR_MIN_HUGE_PG_CT = 'CurrentMinimumHugePageCount'
_MEM_CURR_MIN = 'CurrentMinimumMemory'
_MEM_CURR_PGING_SVC_PART = 'CurrentPagingServicePartition'
_MEM_EXP_HW_ACC_ENABLED = 'MemoryExpansionHardwareAccessEnabled'
_MEM_ENC_HW_ACC_ENABLED = 'MemoryEncryptionHardwareAccessEnabled'
_MEM_AME_ENABLED = 'MemoryExpansionEnabled'
_MEM_RELEASABLE = 'MemoryReleaseable'
_MEM_TO_RELEASE = 'MemoryToRelease'
_MEM_RED_ERR_PATH_REP_ENABLED = 'RedundantErrorPathReportingEnabled'
_MEM_REQ_MIN_FOR_MAX = 'RequiredMinimumForMaximum'
_MEM_RUNT_ENT = 'RuntimeEntitledMemory'
_MEM_RUNT_EXP_FACT = 'RuntimeExpansionFactor'
_MEM_RUNT_HUGE_PG_CT = 'RuntimeHugePageCount'
_MEM_RUNT = 'RuntimeMemory'
_MEM_RUNT_WT = 'RuntimeMemoryWeight'
_MEM_RUNT_MIN = 'RuntimeMinimumMemory'
_MEM_SHARED_MEM_ENABLED = 'SharedMemoryEnabled'

_MEM_EL_ORDER = (
    _MEM_PROF_AME_ENABLED, _MEM_AMS_ENABLED, _MEM_BSR_ARRAY_CT, _MEM_DES_ENT,
    _MEM_DES_HUGE_PAGE_CT, _MEM_DES, _MEM_EXP_FACTOR, _MEM_HW_PG_TBL_RATIO,
    _MEM_MAN_ENT_MODE_ENABLED, _MEM_MAX_HUGE_PG_CT, _MEM_MAX, _MEM_WT,
    _MEM_MIN_HUGE_PG_CT, _MEM_MIN, _MEM_PRI_PGING_SVC_PART,
    _MEM_SEC_PGING_SVC_PART, _MEM_AUTO_ENT_MEM_ENABLED, _MEM_CURR_BSR_ARRAYS,
    _MEM_CURR_ENT, _MEM_CURR_EXP_FACT, _MEM_CURR_HW_PG_TBL_RATIO,
    _MEM_CURR_HUGE_PG_CT, _MEM_CURR_MAX_HUGE_PG_CT, _MEM_CURR_MAX, _MEM_CUR,
    _MEM_CURR_MEM_WT, _MEM_CURR_MIN_HUGE_PG_CT, _MEM_CURR_MIN,
    _MEM_CURR_PGING_SVC_PART, _MEM_EXP_HW_ACC_ENABLED, _MEM_ENC_HW_ACC_ENABLED,
    _MEM_AME_ENABLED, _MEM_RELEASABLE, _MEM_TO_RELEASE,
    _MEM_RED_ERR_PATH_REP_ENABLED, _MEM_REQ_MIN_FOR_MAX, _MEM_RUNT_ENT,
    _MEM_RUNT_EXP_FACT, _MEM_RUNT_HUGE_PG_CT, _MEM_RUNT, _MEM_RUNT_WT,
    _MEM_RUNT_MIN, _MEM_SHARED_MEM_ENABLED)

# Partition I/O Configuration (_IO)
IO_CFG_ROOT = _BP_IO_CFG
_IO_MAX_SLOTS = 'MaximumVirtualIOSlots'
_IO_TIO = 'TaggedIO'

# Tagged I/O (_TIO)
_TIO_ALT_CONSOLE = 'AlternateConsole'
_TIO_ALT_LOAD_SRC = 'AlternateLoadSource'
_TIO_CONSOLE = 'Console'
_TIO_LOAD_SRC = 'LoadSource'
_TIO_OP_CONSOLE = 'OperationsConsole'
_TIO_EL_ORDER = (_TIO_ALT_CONSOLE, _TIO_ALT_LOAD_SRC, _TIO_CONSOLE,
                 _TIO_LOAD_SRC, _TIO_OP_CONSOLE)

# Constants for the I/O Slot Configuration
IO_SLOTS_ROOT = 'ProfileIOSlots'
IO_SLOT_ROOT = 'ProfileIOSlot'
_IO_SLOT_REQ = 'IsRequired'

# Constants for the Associated I/O Slot
ASSOC_IO_SLOT_ROOT = 'AssociatedIOSlot'
_ASSOC_IO_SLOT_BUS_GRP = 'BusGroupingRequired'
_ASSOC_IO_SLOT_DESC = 'Description'
_ASSOC_IO_SLOT_FEAT_CODES = 'FeatureCodes'
_ASSOC_IO_SLOT_PHYS_LOC = 'IOUnitPhysicalLocation'
_ASSOC_IO_SLOT_ADPT_ID = 'PCAdapterID'
_ASSOC_IO_SLOT_PCI_CLASS = 'PCIClass'
_ASSOC_IO_SLOT_PCI_DEV_ID = 'PCIDeviceID'
_ASSOC_IO_SLOT_PCI_SUBSYS_DEV_ID = 'PCISubsystemDeviceID'
_ASSOC_IO_SLOT_PCI_MFG_ID = 'PCIManufacturerID'
_ASSOC_IO_SLOT_PCI_REV_ID = 'PCIRevisionID'
_ASSOC_IO_SLOT_PCI_VENDOR_ID = 'PCIVendorID'
_ASSOC_IO_SLOT_SUBSYS_VENDOR_ID = 'PCISubsystemVendorID'
_ASSOC_IO_SLOT_DRC_INDEX = 'SlotDynamicReconfigurationConnectorIndex'
_ASSOC_IO_SLOT_DRC_NAME = 'SlotDynamicReconfigurationConnectorName'

# Constants for generic I/O Adapter
IO_ADPT_ROOT = 'IOAdapter'
RELATED_IO_ADPT_ROOT = 'RelatedIOAdapter'

_IO_SLOT_ORDER = (ASSOC_IO_SLOT_ROOT, _IO_SLOT_REQ)

_AIO_ORDER = (_ASSOC_IO_SLOT_BUS_GRP, _ASSOC_IO_SLOT_DESC,
              _ASSOC_IO_SLOT_FEAT_CODES, _ASSOC_IO_SLOT_PHYS_LOC,
              _ASSOC_IO_SLOT_ADPT_ID, _ASSOC_IO_SLOT_PCI_CLASS,
              _ASSOC_IO_SLOT_PCI_DEV_ID, _ASSOC_IO_SLOT_PCI_SUBSYS_DEV_ID,
              _ASSOC_IO_SLOT_PCI_MFG_ID, _ASSOC_IO_SLOT_PCI_REV_ID,
              _ASSOC_IO_SLOT_PCI_VENDOR_ID, _ASSOC_IO_SLOT_SUBSYS_VENDOR_ID,
              RELATED_IO_ADPT_ROOT, _ASSOC_IO_SLOT_DRC_INDEX,
              _ASSOC_IO_SLOT_DRC_NAME)

IO_PFC_ADPT_ROOT = 'PhysicalFibreChannelAdapter'
_IO_ADPT_ID = 'AdapterID'
_IO_ADPT_DESC = 'Description'
_IO_ADPT_DEV_NAME = 'DeviceName'
_IO_ADPT_DEV_TYPE = 'DeviceType'
_IO_ADPT_DYN_NAME = 'DynamicReconfigurationConnectorName'
_IO_ADPT_PHYS_LOC = 'PhysicalLocation'
_IO_ADPT_UDID = 'UniqueDeviceID'

PFC_PORT_WWPN = card.PFC_PORT_WWPN
PFC_PORTS_ROOT = card.PFC_PORTS_ROOT
PFC_PORT_ROOT = card.PFC_PORT_ROOT

IOAdapter = card.IOAdapter
PhysFCAdapter = card.PhysFCAdapter
PhysFCPort = card.PhysFCPort


class SharingMode(object):
    """Shared Processor sharing modes.

    Subset of LogicalPartitionProcessorSharingModeEnum.
    """
    CAPPED = 'capped'
    UNCAPPED = 'uncapped'
    ALL_VALUES = (CAPPED, UNCAPPED)


class DedicatedSharingMode(object):
    """Dedicated Processor sharing modes.

    Subset of LogicalPartitionProcessorSharingModeEnum.
    """
    SHARE_IDLE_PROCS = 'sre idle proces'
    SHARE_IDLE_PROCS_ACTIVE = 'sre idle procs active'
    SHARE_IDLE_PROCS_ALWAYS = 'sre idle procs always'
    KEEP_IDLE_PROCS = 'keep idle procs'
    ALL_VALUES = (SHARE_IDLE_PROCS, SHARE_IDLE_PROCS_ACTIVE,
                  SHARE_IDLE_PROCS_ALWAYS, KEEP_IDLE_PROCS)


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


class LPARType(object):
    """Subset of LogicalPartitionEnvironmentEnum."""
    OS400 = 'OS400'
    AIXLINUX = 'AIX/Linux'
    VIOS = 'Virtual IO Server'


class LPARCompat(object):
    """LPAR compatibility modes.

    From LogicalPartitionProcessorCompatibilityModeEnum.
    """
    DEFAULT = 'default'
    POWER6 = 'POWER6'
    POWER6_PLUS = 'POWER6_Plus'
    POWER6_PLUS_ENHANCED = 'POWER6_Plus_Enhanced'
    POWER7 = 'POWER7'
    POWER8 = 'POWER8'
    POWER9 = 'POWER9'
    ALL_VALUES = (DEFAULT, POWER6, POWER6_PLUS, POWER6_PLUS_ENHANCED, POWER7,
                  POWER8, POWER9)


class RMCState(object):
    """Various RMC States.

    From ResourceMonitoringControlStateEnum.
    """
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    NONE = 'none'
    UNKNOWN = 'unknown'
    BUSY = 'busy'


class BootMode(object):
    """Mirror of PartitionBootMode.Enum.

    Valid values for LPAR.bootmode/VIOS.bootmode.

    Not to be confused with pypowervm.tasks.power.BootMode.

    Example usage:
        lwrap.bootmode = BootMode.NORM
        lwrap.update()
    """
    NORM = 'Normal'
    SMS = 'System_Management_Services'
    DD = 'Diagnostic_With_Default_Boot_List'
    DS = 'Diagnostic_With_Stored_Boot_List'
    OF = 'Open_Firmware'
    UNAVAILABLE = 'Unavailable'
    DEFAULT = 'Default'
    UNKNOWN = 'Unknown'
    ALL_VALUES = (NORM, SMS, DD, DS, OF, UNAVAILABLE, DEFAULT, UNKNOWN)


class KeylockPos(object):
    """Mirror of KeylockPosition.Enum.

    Valid values for LPAR.keylock_pos/VIOS.keylock_pos.

    Not to be confused with pypowervm.tasks.power.KeylockPos.

    Example usage:
        lwrap.keylock_pos = KeylockPos.MANUAL
        lwrap.update()
    """
    MANUAL = 'manual'
    NORMAL = 'normal'
    UNKNOWN = 'unknown'
    ALL_VALUES = (MANUAL, NORMAL, UNKNOWN)


class _DlparCapable(object):
    def _can_modify(self, dlpar_cap, cap_desc):
        """Checks to determine if the partition can be modified.

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
            return False, _('Partition does not have an active RMC '
                            'connection.')
        if not dlpar_cap:
            return False, _('Partition does not have an active DLPAR '
                            'capability for %s.') % cap_desc
        return True, None

    def can_modify_io(self):
        """Determines if a partition is capable of adding/removing I/O HW.

        :return capable: True if HW can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        return self._can_modify(self.capabilities.io_dlpar, _('I/O'))

    def can_modify_mem(self):
        """Determines if a partition is capable of adding/removing Memory.

        :return capable: True if memory can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        return self._can_modify(self.capabilities.mem_dlpar, _('Memory'))

    def can_modify_proc(self):
        """Determines if a partition is capable of adding/removing processors.

        :return capable: True if procs can be added/removed.  False otherwise.
        :return reason: A translated message that will indicate why it was not
                        capable of modification.  If capable is True, the
                        reason will be None.
        """
        return self._can_modify(self.capabilities.proc_dlpar, _('Processors'))


@ewrap.Wrapper.base_pvm_type
class BasePartition(ewrap.EntryWrapper, _DlparCapable):
    """Base class for Logical Partition (LPAR) & Virtual I/O Server (VIOS).

    This corresponds to the abstract BasePartition object in the PowerVM
    schema.
    """

    search_keys = dict(name=_BP_NAME, id=_BP_ID)

    @classmethod
    def _bld_base(cls, adapter, name, mem_cfg, proc_cfg, env, io_cfg=None):
        """Creates a BasePartition wrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name of the partition
        :param mem_cfg: The memory configuration wrapper
        :param proc_cfg: The processor configuration wrapper
        :param env: The type of partition, taken from LPARType
        :param io_cfg: The I/O configuration wrapper

        :returns: New BasePartition wrapper
        """

        partition = super(BasePartition, cls)._bld(adapter)
        if io_cfg:
            partition.io_config = io_cfg
        partition.mem_config = mem_cfg
        partition.name = name
        partition.proc_config = proc_cfg
        partition._env(env)

        return partition

    @property
    def state(self):
        """See LPARState.

        e.g. 'not activated', 'running', 'migrating running', etc.
        """
        return self._get_val_str(_BP_STATE)

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
        return self._get_val_int(_BP_ID)

    def _id(self, value):
        """Set ID (not UUID). Only settable on creation of the partition."""
        self.set_parm_value(_BP_ID, int(value))

    @property
    def env(self):
        """See the LPARType Enumeration.

        Should usually be 'AIX/Linux' for LPAR.  'Virtual IO Server' should
        only happen for VIOS.
        """
        return self._get_val_str(_BP_TYPE)

    def _env(self, val):
        self.set_parm_value(_BP_TYPE, val)

    @property
    def partition_uuid(self):
        return self._get_val_str(_BP_UUID)

    @property
    def assoc_sys_uuid(self):
        """UUID of the associated ManagedSystem."""
        href = self.get_href(_BP_ASSOC_SYSTEM, one_result=True)
        return u.get_req_path_uuid(href, preserve_case=True) if href else None

    @property
    def rmc_state(self):
        """See RMCState.

        e.g. 'active', 'inactive', 'busy', etc.
        """
        return self._get_val_str(_BP_RMC_STATE)

    @property
    def rmc_ip(self):
        """IP address used for RMC communication, as a string."""
        return self._get_val_str(_BP_RMC_IP)

    @property
    def operating_system(self):
        """String representing the OS and version, or 'Unknown'."""
        return self._get_val_str(_BP_OS_VER, 'Unknown')

    @property
    def ref_code(self):
        return self._get_val_str(_BP_REF_CODE)

    @property
    def ref_code_full(self):
        return self._get_val_str(_BP_REF_CODE_FULL)

    @property
    def avail_priority(self):
        return self._get_val_int(_BP_AVAIL_PRIORITY, 0)

    @avail_priority.setter
    def avail_priority(self, value):
        self.set_parm_value(_BP_AVAIL_PRIORITY, value)

    @property
    def profile_sync(self):
        return self._get_val_str(_BP_PROFILE_SYNC, default='Off') == 'On'

    @profile_sync.setter
    def profile_sync(self, value):
        if type(value) == bool:
            value = 'On' if value else 'Off'
        self.set_parm_value(_BP_PROFILE_SYNC, value)

    @property
    def proc_compat_mode(self):
        """*Current* processor compatibility mode.

        See LPARCompat.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self._get_val_str(_BP_CURRENT_PROC_MODE)

    @property
    def pending_proc_compat_mode(self):
        """Pending processor compatibility mode.

        See LPARCompat.  E.g. 'POWER7',
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

    @property
    def is_mgmt_partition(self):
        """Is this the management partition?  Default False if field absent."""
        return self._get_val_bool(_BP_MGT_PARTITION)

    @property
    def is_service_partition(self):
        """Is this the service partition?  Default False if field absent."""
        return self._get_val_bool(_BP_SVC_PARTITION)

    @is_service_partition.setter
    def is_service_partition(self, value):
        """Set if this is the service partition."""
        self.set_parm_value(_BP_SVC_PARTITION, u.sanitize_bool_for_api(value))

    @property
    def keylock_pos(self):
        """Keylock position - see KeylockPos enumeration."""
        return self._get_val_str(_BP_KEYLOCK_POS)

    @keylock_pos.setter
    def keylock_pos(self, value):
        """Keylock position - see KeylockPos enumeration."""
        if value not in KeylockPos.ALL_VALUES:
            raise ValueError(_("Invalid KeylockPos '%s'.") % value)
        self.set_parm_value(_BP_KEYLOCK_POS, value)

    @property
    def bootmode(self):
        """Boot mode - one of the BootMode enum values."""
        return self._get_val_str(_BP_BOOT_MODE)

    @bootmode.setter
    def bootmode(self, val):
        if val not in BootMode.ALL_VALUES:
            raise ValueError(_("Invalid BootMode '%s'.") % val)
        self.set_parm_value(_BP_BOOT_MODE, val)

    @property
    def disable_secure_boot(self):
        return self._get_val_bool(_BP_DISABLE_SECURE_BOOT)

    @disable_secure_boot.setter
    def disable_secure_boot(self, value):
        self.set_parm_value(
            _BP_DISABLE_SECURE_BOOT, u.sanitize_bool_for_api(value),
            attrib=const.ATTR_KSV150)

    @property
    def allow_perf_data_collection(self):
        return self._get_val_bool(_BP_ALLOW_PERF_DATA_COLL)

    @allow_perf_data_collection.setter
    def allow_perf_data_collection(self, value):
        self.set_parm_value(_BP_ALLOW_PERF_DATA_COLL,
                            u.sanitize_bool_for_api(value))

    @property
    def capabilities(self):
        elem = self._find(_BP_CAPABILITIES)
        return PartitionCapabilities.wrap(elem)

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

    @ewrap.Wrapper.xag_property(const.XAG.NVRAM)
    def nvram(self):
        return self._get_val_str(_BP_NVRAM)

    @nvram.setter
    def nvram(self, nvram):
        self.set_parm_value(_BP_NVRAM, nvram,
                            attrib=u.xag_attrs(const.XAG.NVRAM,
                                               base=const.ATTR_KSV130))

    @property
    def uptime(self):
        """Integer time since partition boot, in seconds."""
        return self._get_val_int(_BP_UPTIME)


@ewrap.ElementWrapper.pvm_type(_BP_CAPABILITIES, has_metadata=True,
                               child_order=_CAP_EL_ORDER)
class PartitionCapabilities(ewrap.ElementWrapper):
    """See LogicalPartitionCapabilities."""
    @property
    def io_dlpar(self):
        return self._get_val_bool(_CAP_DLPAR_IO_CAPABLE)

    @property
    def mem_dlpar(self):
        return self._get_val_bool(_CAP_DLPAR_MEM_CAPABLE)

    @property
    def proc_dlpar(self):
        return self._get_val_bool(_CAP_DLPAR_PROC_CAPABLE)


@ewrap.ElementWrapper.pvm_type(_BP_PROC_CFG, has_metadata=True,
                               child_order=_PC_EL_ORDER)
class PartitionProcessorConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Processor Configuration.

    Comprised of either the shared or dedicated processor config.
    """

    @classmethod
    def bld_shared(cls, adapter, proc_unit, proc,
                   sharing_mode=SharingMode.UNCAPPED, uncapped_weight=128,
                   min_proc_unit=None, max_proc_unit=None, min_proc=None,
                   max_proc=None, proc_pool=0):
        """Builds a Shared Processor configuration wrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
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
        proc_cfg = super(PartitionProcessorConfiguration, cls)._bld(adapter)
        proc_cfg._has_dedicated(False)

        sproc = SharedProcessorConfiguration.bld(
            adapter, proc_unit, proc, uncapped_weight=uncapped_weight,
            min_proc_unit=min_proc_unit, max_proc_unit=max_proc_unit,
            min_proc=min_proc, max_proc=max_proc, proc_pool=proc_pool)

        proc_cfg._shared_proc_cfg(sproc)
        proc_cfg.sharing_mode = sharing_mode
        return proc_cfg

    @classmethod
    def bld_dedicated(cls, adapter, proc, min_proc=None, max_proc=None,
                      sharing_mode=DedicatedSharingMode.SHARE_IDLE_PROCS):

        """Builds a Dedicated Processor configuration wrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param proc: Number of virtual processors (int)
        :param min_proc: Minimum processors, default to proc value
        :param max_proc: Maximum processors, default to proc value
        :param sharing_mode: Sharing mode of the processors, 'sre idle proces'
        :returns: Processor Config with dedicated processors

        """

        proc_cfg = super(PartitionProcessorConfiguration, cls)._bld(adapter)

        dproc = DedicatedProcessorConfiguration.bld(
            adapter, proc, min_proc=min_proc, max_proc=max_proc)

        proc_cfg._dedicated_proc_cfg(dproc)
        proc_cfg._has_dedicated(True)
        proc_cfg.sharing_mode = sharing_mode
        return proc_cfg

    @property
    def has_dedicated(self):
        """Returns boolean True if dedicated, False if shared or not found."""
        return self._get_val_bool(_PC_HAS_DED_PROCS)

    def _has_dedicated(self, val):
        """Expects 'true' (string) for dedicated or 'false' for shared."""
        self.set_parm_value(_PC_HAS_DED_PROCS, u.sanitize_bool_for_api(val))

    @property
    def sharing_mode(self):
        return self._get_val_str(_PC_SHARING_MODE)

    @sharing_mode.setter
    def sharing_mode(self, value):
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


@ewrap.ElementWrapper.pvm_type(_BP_MEM_CFG, has_metadata=True,
                               child_order=_MEM_EL_ORDER)
class PartitionMemoryConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Memory Configuration."""

    @classmethod
    def bld(cls, adapter, mem, min_mem=None, max_mem=None):
        """Creates the ParitionMemoryConfiguration.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
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

        cfg = super(PartitionMemoryConfiguration, cls)._bld(adapter)
        cfg.desired = mem
        cfg.max = max_mem
        cfg.min = min_mem

        return cfg

    @property
    def current(self):
        return self._get_val_int(_MEM_CUR)

    @property
    def desired(self):
        return self._get_val_int(_MEM_DES)

    @desired.setter
    def desired(self, mem):
        self.set_parm_value(_MEM_DES, str(mem))

    @property
    def max(self):
        return self._get_val_int(_MEM_MAX)

    @max.setter
    def max(self, mem):
        self.set_parm_value(_MEM_MAX, str(mem))

    @property
    def min(self):
        return self._get_val_int(_MEM_MIN)

    @min.setter
    def min(self, mem):
        self.set_parm_value(_MEM_MIN, str(mem))

    @property
    def shared_enabled(self):
        # The default is None instead of False so that the caller
        # can know if the value is not set
        return self._get_val_bool(_MEM_SHARED_MEM_ENABLED, None)

    @property
    def ame_enabled(self):
        return self._get_val_bool(_MEM_AME_ENABLED)

    @property
    def exp_factor(self):
        """The Active Memory Expansion Factor

        The expansion factor represents the target memory multiplier.
        e.g. An LPAR with EF = 2 which has 4 GB of memory will have a target
        expansion memory of 8 GB.
        """
        return self._get_val_float(_MEM_EXP_FACTOR, default=0)

    @exp_factor.setter
    def exp_factor(self, exp_factor):
        """The Active Memory Expansion Factor

        :param exp_factor: The expansion factor value. Setting this to 0 will
                           turn/keep AME off. The valid values are
                           1.0 <= x <= 10.0 up to 2 decimal places.
        """
        self.set_parm_value(_MEM_EXP_FACTOR,
                            u.sanitize_float_for_api(exp_factor))


@ewrap.ElementWrapper.pvm_type(_PC_SHR_PROC_CFG, has_metadata=True,
                               child_order=_SPC_EL_ORDER)
class SharedProcessorConfiguration(ewrap.ElementWrapper):
    """Represents the partition's Shared Processor Configuration."""

    @classmethod
    def bld(cls, adapter, proc_unit, proc, uncapped_weight=None,
            min_proc_unit=None, max_proc_unit=None,
            min_proc=None, max_proc=None, proc_pool=0):
        """Builds a Shared Processor configuration wrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
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

        sproc = super(SharedProcessorConfiguration, cls)._bld(adapter)

        sproc.desired_units = proc_unit
        sproc.desired_virtual = proc
        sproc.max_units = max_proc_unit
        sproc.max_virtual = max_proc
        sproc.min_units = min_proc_unit
        sproc.min_virtual = min_proc
        sproc.pool_id = proc_pool
        if uncapped_weight is not None:
            sproc.uncapped_weight = uncapped_weight

        return sproc

    @property
    def desired_units(self):
        return self._get_val_float(_SPC_DES_PROC_UNIT)

    @desired_units.setter
    def desired_units(self, val):
        self.set_parm_value(_SPC_DES_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def max_units(self):
        return self._get_val_float(_SPC_MAX_PROC_UNIT)

    @max_units.setter
    def max_units(self, val):
        self.set_parm_value(_SPC_MAX_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def min_units(self):
        return self._get_val_float(_SPC_MIN_PROC_UNIT)

    @min_units.setter
    def min_units(self, val):
        self.set_parm_value(_SPC_MIN_PROC_UNIT, u.sanitize_float_for_api(val))

    @property
    def desired_virtual(self):
        return self._get_val_int(_SPC_DES_VIRT_PROC)

    @desired_virtual.setter
    def desired_virtual(self, val):
        self.set_parm_value(_SPC_DES_VIRT_PROC, val)

    @property
    def max_virtual(self):
        return self._get_val_int(_SPC_MAX_VIRT_PROC)

    @max_virtual.setter
    def max_virtual(self, val):
        self.set_parm_value(_SPC_MAX_VIRT_PROC, val)

    @property
    def min_virtual(self):
        return self._get_val_int(_SPC_MIN_VIRT_PROC)

    @min_virtual.setter
    def min_virtual(self, val):
        self.set_parm_value(_SPC_MIN_VIRT_PROC, val)

    @property
    def pool_id(self):
        return self._get_val_int(_SPC_SHARED_PROC_POOL_ID, 0)

    @pool_id.setter
    def pool_id(self, val):
        self.set_parm_value(_SPC_SHARED_PROC_POOL_ID, val)

    @property
    def uncapped_weight(self):
        return self._get_val_int(_SPC_UNCAPPED_WEIGHT, 0)

    @uncapped_weight.setter
    def uncapped_weight(self, val):
        self.set_parm_value(_SPC_UNCAPPED_WEIGHT, val)


@ewrap.ElementWrapper.pvm_type(_PC_DED_PROC_CFG, has_metadata=True)
class DedicatedProcessorConfiguration(ewrap.ElementWrapper):
    """Represents the partition's Dedicated Processor Configuration."""

    @classmethod
    def bld(cls, adapter, proc, min_proc=None, max_proc=None):
        """Builds a Dedicated Processor configuration wrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
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

        dproc = super(DedicatedProcessorConfiguration, cls)._bld(adapter)

        dproc.desired = proc
        dproc.max = max_proc
        dproc.min = min_proc

        return dproc

    @property
    def desired(self):
        return self._get_val_int(_DPC_DES_PROCS, 0)

    @desired.setter
    def desired(self, value):
        self.set_parm_value(_DPC_DES_PROCS, value)

    @property
    def max(self):
        return self._get_val_int(_DPC_MAX_PROCS, 0)

    @max.setter
    def max(self, value):
        self.set_parm_value(_DPC_MAX_PROCS, value)

    @property
    def min(self):
        return self._get_val_int(_DPC_MIN_PROCS, 0)

    @min.setter
    def min(self, value):
        self.set_parm_value(_DPC_MIN_PROCS, value)


@ewrap.ElementWrapper.pvm_type('PartitionIOConfiguration', has_metadata=True)
class PartitionIOConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Dedicated IO Configuration.

    Comprised of I/O Slots.  There are two types of IO slots.  Those dedicated
    to physical hardware (io_slots) and those that get used by virtual
    hardware.
    """

    @classmethod
    def bld(cls, adapter, max_virt_slots):
        """Builds a Partition IO configuration wrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param max_virt_slots: Number of virtual slots (int)
        :returns: Partition IO configuration wrapper

        """
        cfg = super(PartitionIOConfiguration, cls)._bld(adapter)
        cfg.max_virtual_slots = max_virt_slots

        return cfg

    @property
    def max_virtual_slots(self):
        """The maximum number of virtual slots.

        Slots are used for every VirtualScsiServerAdapter, TrunkAdapter, etc...
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

    @io_slots.setter
    def io_slots(self, val):
        self.replace_list(IO_SLOTS_ROOT, val)

    @property
    def tagged_io(self):
        """IBMi only - tagged I/O attributes of the I/O configuration."""
        tio = self._find(_IO_TIO)
        return TaggedIO.wrap(tio) if tio else None

    @tagged_io.setter
    def tagged_io(self, tio):
        self.inject(tio.element)


@ewrap.ElementWrapper.pvm_type('TaggedIO', has_metadata=True,
                               child_order=_TIO_EL_ORDER)
class TaggedIO(ewrap.ElementWrapper):
    """IBMi only - tagged I/O attributes of the I/O configuration."""

    @classmethod
    def bld(cls, adapter, load_src='0', console='HMC', alt_load_src='NONE'):
        """Builds a Partition TaggedIO wrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param load_src: Load source to use
        :param console: Console to use for IBMi
        :param alt_load_src: Alternate load source to use
        :returns: Partition TaggedIO wrapper

        """
        cfg = super(TaggedIO, cls)._bld(adapter)
        cfg.load_src = load_src
        cfg.console = console
        cfg.alt_load_src = alt_load_src
        return cfg

    @property
    def alt_load_src(self):
        """Value may or may not be an integer - always returned as string."""
        return self._get_val_str(_TIO_ALT_LOAD_SRC)

    @alt_load_src.setter
    def alt_load_src(self, value):
        self.set_parm_value(_TIO_ALT_LOAD_SRC, value)

    @property
    def console(self):
        """Value may or may not be an integer - always returned as string."""
        return self._get_val_str(_TIO_CONSOLE)

    @console.setter
    def console(self, value):
        self.set_parm_value(_TIO_CONSOLE, value)

    @property
    def load_src(self):
        """Value may or may not be an integer - always returned as string."""
        return self._get_val_str(_TIO_LOAD_SRC)

    @load_src.setter
    def load_src(self, value):
        self.set_parm_value(_TIO_LOAD_SRC, value)


@ewrap.ElementWrapper.pvm_type('ProfileIOSlot', has_metadata=True,
                               child_order=_IO_SLOT_ORDER)
class IOSlot(ewrap.ElementWrapper):
    """An I/O Slot represents a device bus on the system.

    It may contain a piece of hardware within it.
    """
    @classmethod
    def bld(cls, adapter, bus_grp_required, drc_index, required=False):
        """Build a new IOSlot wrapper with all required parameters.

        :returns: A new IOSlot wrapper.
        """
        new_slot = super(IOSlot, cls)._bld(adapter)

        new_slot.required = required

        # Build out the AssociatedIOSlot
        assoc_io_slot = cls.AssociatedIOSlot._bld_new(adapter,
                                                      bus_grp_required,
                                                      drc_index)

        # Inject the AssociatedIOSlot into this wrapper
        new_slot.inject(assoc_io_slot.element)

        return new_slot

    @ewrap.ElementWrapper.pvm_type(ASSOC_IO_SLOT_ROOT, has_metadata=True,
                                   child_order=_AIO_ORDER)
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
        @classmethod
        def _bld_new(cls, adapter, bus_grp_required, drc_index):
            """Build a new AssociatedIOSlot wrapper.

            This will not typically be called outside of the IOSlot.bld
            class method.

            :returns: A new AssociatedIOSlot wrapper.
            """
            new_slot = super(IOSlot.AssociatedIOSlot, cls)._bld(adapter)
            new_slot._bus_grp_required(bus_grp_required)
            new_slot._drc_index(drc_index)

            return new_slot

        @property
        def bus_grp_required(self):
            return self._get_val_bool(_ASSOC_IO_SLOT_BUS_GRP)

        def _bus_grp_required(self, val):
            self.set_parm_value(_ASSOC_IO_SLOT_BUS_GRP,
                                u.sanitize_bool_for_api(val))

        @property
        def description(self):
            return self._get_val_str(_ASSOC_IO_SLOT_DESC)

        @property
        def phys_loc(self):
            return self._get_val_str(_ASSOC_IO_SLOT_PHYS_LOC)

        @property
        def pc_adpt_id(self):
            return self._get_val_int(_ASSOC_IO_SLOT_ADPT_ID)

        @property
        def pci_class(self):
            return self._get_val_int(_ASSOC_IO_SLOT_PCI_CLASS)

        @property
        def pci_dev_id(self):
            return self._get_val_int(_ASSOC_IO_SLOT_PCI_DEV_ID)

        @property
        def pci_subsys_dev_id(self):
            return self._get_val_int(_ASSOC_IO_SLOT_PCI_SUBSYS_DEV_ID)

        @property
        def pci_mfg_id(self):
            return self._get_val_int(_ASSOC_IO_SLOT_PCI_MFG_ID)

        @property
        def pci_rev_id(self):
            return self._get_val_int(_ASSOC_IO_SLOT_PCI_REV_ID)

        @property
        def pci_vendor_id(self):
            return self._get_val_int(_ASSOC_IO_SLOT_PCI_VENDOR_ID)

        @property
        def pci_subsys_vendor_id(self):
            return self._get_val_int(_ASSOC_IO_SLOT_SUBSYS_VENDOR_ID)

        @property
        def drc_index(self):
            return self._get_val_int(_ASSOC_IO_SLOT_DRC_INDEX)

        def _drc_index(self, val):
            self.set_parm_value(_ASSOC_IO_SLOT_DRC_INDEX, val)

        @property
        def drc_name(self):
            return self._get_val_str(_ASSOC_IO_SLOT_DRC_NAME)

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

    @property
    def required(self):
        return self._get_val_bool(_IO_SLOT_REQ)

    @required.setter
    def required(self, val):
        self.set_parm_value(_IO_SLOT_REQ, u.sanitize_bool_for_api(val))

    def __get_prop(self, func):
        """Thin wrapper to get the Associated I/O Slot and get a property."""
        elem = self._find(ASSOC_IO_SLOT_ROOT)
        if elem is None:
            return None

        # Build the Associated IO Slot, find the function and execute it.
        assoc_io_slot = self.AssociatedIOSlot.wrap(elem)
        return getattr(assoc_io_slot, func)

    @property
    def bus_grp_required(self):
        return self.__get_prop('bus_grp_required')

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
    def drc_index(self):
        return self.__get_prop('drc_index')

    @property
    def drc_name(self):
        return self.__get_prop('drc_name')

    @property
    def adapter(self):
        """DEPRECATED - use 'io_adapter' method instead."""
        import warnings
        warnings.warn(
            _("IOSlot.adapter is deprecated!  Use IOSlot.io_adapter instead."),
            DeprecationWarning)
        return self.io_adapter

    @property
    def io_adapter(self):
        """Returns the physical I/O Adapter for this slot.

        This will be one of two types.  Either a generic I/O Adapter or
        a Physical Fibre Channel Adapter (PhysFCAdapter).
        """
        return self.__get_prop('io_adapter')
