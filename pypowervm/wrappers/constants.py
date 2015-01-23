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

from oslo.config import cfg

CONF = cfg.CONF

DEFAULT_SCHEMA_VERSION = 'V1_0'
SCHEMA_VER = 'schemaVersion'
DEFAULT_SCHEMA_ATTR = {SCHEMA_VER: DEFAULT_SCHEMA_VERSION}

DELIM = '/'
ROOT = './'
LINK = 'link'

PRIMARY_IP_ADDRESS = 'PrimaryIPAddress'
STATE = 'State'
UUID = 'id'

PVMA_TEXT = 'text'

# PowerVM Types
MGT_CONSOLE = 'ManagementConsole'
MGT_SYS = 'ManagedSystem'
LPAR = 'LogicalPartition'
VIOS = 'VirtualIOServer'
SHR_PRC_PL = 'SharedProcessorPool'
VOL_GROUP = 'VolumeGroup'
JOBS = 'jobs'
VSWITCH = 'VirtualSwitch'

NEXT_SLOT = 'UseNextAvailableSlotID'

# PVM adapter xpaths
PARTITION_NAME = ROOT + 'PartitionName'
PARTITION_ID = ROOT + 'PartitionID'
PARTITION_UUID = ROOT + 'PartitionUUID'
PARTITION_STATE = ROOT + 'PartitionState'
PARTITION_TYPE = ROOT + 'PartitionType'
AVAIL_PRIORITY = ROOT + 'AvailabilityPriority'
LPAR_MEM_CONFIG = ROOT + 'PartitionMemoryConfiguration'
LPAR_PROC_CONFIG = ROOT + 'PartitionProcessorConfiguration'
LPAR_CAPABILITIES = ROOT + 'PartitionCapabilities'
PARTITION_IO = ROOT + 'PartitionIOConfiguration'
IPL_SOURCE = ROOT + 'DesignatedIPLSource'
KEY_LOCK = ROOT + 'KeylockPosition'
RESTRICTED_IO = ROOT + 'IsRestrictedIOPartition'
CNA_LINKS = ROOT + 'ClientNetworkAdapters' + DELIM + LINK

# Managed System properties
SYS_CAPABILITIES = ROOT + 'AssociatedSystemCapabilities'
SYS_MEM_CONFIG = ROOT + 'AssociatedSystemMemoryConfiguration'
SYS_PROC_CONFIG = ROOT + 'AssociatedSystemProcessorConfiguration'

MODEL_SERIAL = ROOT + 'MachineTypeModelAndSerialNumber'
MACHINE_MODEL = MODEL_SERIAL + DELIM + 'Model'
MACHINE_TYPE = MODEL_SERIAL + DELIM + 'MachineType'
MACHINE_SERIAL = MODEL_SERIAL + DELIM + 'SerialNumber'

MOVER_SERVICE_PARTITION = ROOT + 'MoverServicePartition'
ACTIVE_LPM_CAP = (
    SYS_CAPABILITIES + DELIM + 'ActiveLogicalPartitionMobilityCapable')
CURR_LMB_SIZE = SYS_MEM_CONFIG + DELIM + 'CurrentLogicalMemoryBlockSize'
INACTIVE_LPM_CAP = (
    SYS_CAPABILITIES + DELIM + 'InactiveLogicalPartitionMobilityCapable')
VETH_MAC_ADDR_CAP = (
    SYS_CAPABILITIES + DELIM + 'VirtualEthernetCustomMACAddressCapable')
IBMi_LPM_CAP = SYS_CAPABILITIES + DELIM + 'IBMiLogicalPartitionMobilityCapable'
IBMi_RESTRICTEDIO_CAP = (
    SYS_CAPABILITIES + DELIM + 'IBMiRestrictedIOModeCapable')

# Migration Constants
PROC_COMPAT_MODES = (
    SYS_PROC_CONFIG + DELIM + 'SupportedPartitionProcessorCompatibilityModes')
MIGR_INFO = ROOT + 'SystemMigrationInformation'
MAX_ACTIVE_MIGR = MIGR_INFO + DELIM + 'MaximumActiveMigrations'
MAX_INACTIVE_MIGR = MIGR_INFO + DELIM + 'MaximumInactiveMigrations'
ACTIVE_MIGR_RUNNING = MIGR_INFO + DELIM + 'NumberOfActiveMigrationsInProgress'
INACTIVE_MIGR_RUNNING = (
    MIGR_INFO + DELIM + 'NumberOfInactiveMigrationsInProgress')
MAX_FIRMWARE_MIGR = MIGR_INFO + DELIM + 'MaximumFirmwareActiveMigrations'

SYSTEM_NAME = ROOT + 'SystemName'

PROC_UNITS_INSTALLED = (
    SYS_PROC_CONFIG + DELIM + 'InstalledSystemProcessorUnits')

PROC_UNITS_AVAIL = (
    SYS_PROC_CONFIG + DELIM + 'CurrentAvailableSystemProcessorUnits')

PROC_UNITS_CONFIGURABLE = (
    SYS_PROC_CONFIG + DELIM + 'ConfigurableSystemProcessorUnits')

MAX_PROCS_PER_PARTITION = (
    SYS_PROC_CONFIG + DELIM + 'CurrentMaximumAllowedProcessorsPerPartition')

MAX_PROCS_PER_AIX_LINUX_PARTITION = (
    SYS_PROC_CONFIG + DELIM + 'CurrentMaximumProcessorsPerAIXOrLinuxPartition')

MAX_VCPUS_PER_PARTITION = (
    SYS_PROC_CONFIG + DELIM + 'MaximumAllowedVirtualProcessorsPerPartition')

MAX_VCPUS_PER_AIX_LINUX_PARTITION = (
    SYS_PROC_CONFIG + DELIM +
    'CurrentMaximumVirtualProcessorsPerAIXOrLinuxPartition')

MEMORY_INSTALLED = (SYS_MEM_CONFIG + DELIM + 'InstalledSystemMemory')

MEMORY_AVAIL = (SYS_MEM_CONFIG + DELIM + 'CurrentAvailableSystemMemory')

MEMORY_CONFIGURABLE = (SYS_MEM_CONFIG + DELIM + 'ConfigurableSystemMemory')

MEMORY_REGION_SIZE = (SYS_MEM_CONFIG + DELIM + 'MemoryRegionSize')

SYS_FIRMWARE_MEM = (SYS_MEM_CONFIG + DELIM + 'MemoryUsedByHypervisor')

HOST_IP_ADDRESS = ROOT + PRIMARY_IP_ADDRESS

# VIOS
VIOS_LINK = ROOT + "AssociatedVirtualIOServers" + DELIM + "link"


# procs
CURR_USE_DED_PROCS = LPAR_PROC_CONFIG + DELIM + 'CurrentHasDedicatedProcessors'
USE_DED_PROCS = LPAR_PROC_CONFIG + DELIM + 'HasDedicatedProcessors'
DED_PROC_CONFIG = (
    LPAR_PROC_CONFIG + DELIM + 'DedicatedProcessorConfiguration')
CURR_DED_PROC_CONFIG = (
    LPAR_PROC_CONFIG + DELIM + 'CurrentDedicatedProcessorConfiguration')
SHARED_PROC_CONFIG = (
    LPAR_PROC_CONFIG + DELIM + 'SharedProcessorConfiguration')
CURR_SHARED_PROC_CONFIG = (
    LPAR_PROC_CONFIG + DELIM + 'CurrentSharedProcessorConfiguration')
CURR_SHARING_MODE = LPAR_PROC_CONFIG + DELIM + 'CurrentSharingMode'
SHARING_MODE = LPAR_PROC_CONFIG + DELIM + 'SharingMode'

# dedicated proc
CURR_PROCS = CURR_DED_PROC_CONFIG + DELIM + 'CurrentProcessors'
CURR_MAX_PROCS = CURR_DED_PROC_CONFIG + DELIM + 'CurrentMaximumProcessors'
CURR_MIN_PROCS = CURR_DED_PROC_CONFIG + DELIM + 'CurrentMinimumProcessors'

RUN_PROCS = CURR_DED_PROC_CONFIG + DELIM + 'RunProcessors'

DES_PROCS = DED_PROC_CONFIG + DELIM + 'DesiredProcessors'
DES_MAX_PROCS = DED_PROC_CONFIG + DELIM + 'MaximumProcessors'
DES_MIN_PROCS = DED_PROC_CONFIG + DELIM + 'MinimumProcessors'

# shared proc
POOL_ID = ROOT + 'PoolID'
CURR_VCPU = CURR_SHARED_PROC_CONFIG + DELIM + 'AllocatedVirtualProcessors'
CURR_MAX_VCPU = (
    CURR_SHARED_PROC_CONFIG + DELIM + 'CurrentMaximumVirtualProcessors')
CURR_MIN_VCPU = (
    CURR_SHARED_PROC_CONFIG + DELIM + 'CurrentMinimumVirtualProcessors')

RUN_VCPU = CURR_SHARED_PROC_CONFIG + DELIM + 'AllocatedVirtualProcessors'

DES_VCPU = SHARED_PROC_CONFIG + DELIM + 'DesiredVirtualProcessors'
DES_MAX_VCPU = SHARED_PROC_CONFIG + DELIM + 'MaximumVirtualProcessors'
DES_MIN_VCPU = SHARED_PROC_CONFIG + DELIM + 'MinimumVirtualProcessors'
CURR_PROC_UNITS = CURR_SHARED_PROC_CONFIG + DELIM + 'CurrentProcessingUnits'
CURR_MAX_PROC_UNITS = (
    CURR_SHARED_PROC_CONFIG + DELIM + 'CurrentMaximumProcessingUnits')
CURR_MIN_PROC_UNITS = (
    CURR_SHARED_PROC_CONFIG + DELIM + 'CurrentMinimumProcessingUnits')
CURR_RSRV_PROC_UNITS = ROOT + 'CurrentReservedProcessingUnits'
DES_PROC_UNITS = SHARED_PROC_CONFIG + DELIM + 'DesiredProcessingUnits'
MAX_PROC_UNITS = SHARED_PROC_CONFIG + DELIM + 'MaximumProcessingUnits'
MIN_PROC_UNITS = SHARED_PROC_CONFIG + DELIM + 'MinimumProcessingUnits'
CURR_UNCAPPED_WEIGHT = (
    CURR_SHARED_PROC_CONFIG + DELIM + 'CurrentUncappedWeight')
UNCAPPED_WEIGHT = SHARED_PROC_CONFIG + DELIM + 'UncappedWeight'
SHARED_PROC_POOL_ID = SHARED_PROC_CONFIG + DELIM + 'SharedProcessorPoolID'

# memory
CURR_MEM = LPAR_MEM_CONFIG + DELIM + 'CurrentMemory'
CURR_MAX_MEM = LPAR_MEM_CONFIG + DELIM + 'CurrentMaximumMemory'
CURR_MIN_MEM = LPAR_MEM_CONFIG + DELIM + 'CurrentMinimumMemory'
DES_MEM = LPAR_MEM_CONFIG + DELIM + 'DesiredMemory'
DES_MAX_MEM = LPAR_MEM_CONFIG + DELIM + 'MaximumMemory'
DES_MIN_MEM = LPAR_MEM_CONFIG + DELIM + 'MinimumMemory'

RUN_MEM = LPAR_MEM_CONFIG + DELIM + 'RuntimeMemory'

SHARED_MEM_ENABLED = LPAR_MEM_CONFIG + DELIM + 'SharedMemoryEnabled'

DEFAULT_SHARING_MODE = 'share_idle_procs'
DEFAULT = 'default'
FALSE = 'false'
ZERO = '0'
CURRENT_PROC_MODE = ROOT + 'CurrentProcessorCompatibilityMode'
PENDING_PROC_MODE = ROOT + 'PendingProcessorCompatibilityMode'
OPERATING_SYSTEM_VER = ROOT + 'OperatingSystemVersion'
DLPAR_MEM_CAPABLE = (
    LPAR_CAPABILITIES + DELIM + 'DynamicLogicalPartitionMemoryCapable')
DLPAR_PROC_CAPABLE = (
    LPAR_CAPABILITIES + DELIM + 'DynamicLogicalPartitionProcessorCapable')
RMC_STATE = 'ResourceMonitoringControlState'
REF_CODE = 'ReferenceCode'
MIGRATION_STATE = 'MigrationState'

# Tagged IO
TAGGED_IO = PARTITION_IO + DELIM + 'TaggedIO'
LOAD_SOURCE = TAGGED_IO + DELIM + 'LoadSource'

SUFFIX_TYPE_DO = 'do'
SUFFIX_PARM_POWER_ON = 'PowerOn'
SUFFIX_PARM_POWER_OFF = 'PowerOff'
SUFFIX_PARM_MIGRATE = 'Migrate'
SUFFIX_PARM_CLI_RUNNER = 'CLIRunner'
SUFFIX_PARM_MIGRATE_RECOVER = 'MigrateRecover'
SUFFIX_PARM_QUERY_RESERVE_MEM = 'QueryReservedMemoryRequiredForPartition'
SUFFIX_PARM_CLOSE_VTERM = 'CloseVterm'
SUFFIX_PARM_LUA_RECOVERY = 'LUARecovery'

WEB_NS = 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'

# LUA Recovery status codes
LUA_STATUS_DEVICE_IN_USE = '1'
LUA_STATUS_ITL_NOT_RELIABLE = '2'
LUA_STATUS_DEVICE_AVIALABLE = '3'
LUA_STATUS_STORAGE_NOT_INTEREST = '4'
LUA_STATUS_LUA_NOT_INTEREST = '5'
LUA_STATUS_INCORRECT_ITL = '6'
LUA_STATUS_FOUND_DEVICE_UNKNOWN_UDID = '7'
LUA_STATUS_FOUND_ITL_ERR = '8'

# HTTP status code
HTTP_STATUS_INVALID_URL = 400
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_ETAG_MISMATCH = 412
HTTP_STATUS_CONNECTION_RESET = 104

# extended properties
VIOS_VSCSI_MAP_EXT_PROP = 'ViosSCSIMapping'
VIOS_VFC_MAP_EXT_PROP = 'ViosFCMapping'
VIOS_STORAGE_EXT_PROP = 'ViosStorage'
VIOS_NET_EXT_PROP = 'ViosNetwork'
ALL_VIOS_EXT_PROPS = [VIOS_VFC_MAP_EXT_PROP, VIOS_NET_EXT_PROP,
                      VIOS_VSCSI_MAP_EXT_PROP, VIOS_STORAGE_EXT_PROP]

# Attributes
ETAG = 'etag'
# indicating whether we are dealing VirtualSCSIMappings or
# VirtualFibreChannelMappings
SCSI = 'scsi'
VFC = 'vfc'

# Adapter elements, values, and path
SERVER_ADAPTER = 'ServerAdapter'
CLIENT_ADAPTER = 'ClientAdapter'
ADAPTER_TYPE = 'AdapterType'
SERVER = 'Server'
CLIENT = 'Client'
PORT = 'Port'
PORT_NAME = 'PortName'
USE_NEXT_AVAIL_SLOT = 'UseNextAvailableSlotID'
LOCAL_LPAR_ID = 'LocalPartitionID'
REMOTE_LPAR_ID = 'RemoteLogicalPartitionID'
CONN_LPAR_ID = 'ConnectingPartitionID'
VIR_SLOT_NUM = 'VirtualSlotNumber'
REMOTE_SLOT_NUM = 'RemoteSlotNumber'
CONN_SLOT_NUM = 'ConnectingVirtualSlotNumber'
SCSI_CLIENT = 'VirtualSCSIClientAdapter'
FC_CLIENT = 'VirtualFibreChannelClientAdapter'
SERVER_LPAR_ID_PATH = ROOT + SERVER_ADAPTER + DELIM + LOCAL_LPAR_ID
ASSOC_LPAR = 'AssociatedLogicalPartition'
BACKING_DEV = 'BackingDeviceName'
MAP_PORT = 'MapPort'
PORT_WWPN = 'WWPN'
WWPNS = 'WWPNs'
SHARED_ETHERNET_ADAPTERS = ROOT + 'SharedEthernetAdapters'
SHARED_ETHERNET_ADAPTER = (
    SHARED_ETHERNET_ADAPTERS + DELIM + 'SharedEthernetAdapter')
FREE_ETHERNET_ADAPTERS = ROOT + 'FreeEthenetBackingDevicesForSEA'
IO_ADAPTER_CHOICE = FREE_ETHERNET_ADAPTERS + DELIM + 'IOAdapterChoice'
ETHERNET_BACKING_DEVICE = IO_ADAPTER_CHOICE + DELIM + 'EthernetBackingDevice'
IP_INTERFACE = 'IPInterface'
IP_ADDRESS = 'IPAddress'
IF_ADDR = IP_INTERFACE + DELIM + IP_ADDRESS
VSWITCH_ID = ROOT + 'VirtualSwitchID'
ASSOC_VSWITCH = ROOT + 'AssociatedVirtualSwitch'
ASSOC_VSWITCH_LINK = ASSOC_VSWITCH + DELIM + LINK
PORT_VLAN_ID = ROOT + 'PortVLANID'
VIRTUAL_NETWORKS = ROOT + 'VirtualNetworks'
DEVICE_NAME = 'DeviceName'
TAGGED_VLAN_SUPPORTED = 'TaggedVLANSupported'
TAGGED_VLAN_IDS = ROOT + 'TaggedVLANIDs'
TRUNK_ADAPTERS = ROOT + 'TrunkAdapters'
TRUNK_ADAPTER = TRUNK_ADAPTERS + DELIM + 'TrunkAdapter'
VIRTUAL_SWITCH_ID = ROOT + 'VirtualSwitchID'
TRUNK_PRIORITY = ROOT + 'TrunkPriority'
LOAD_GROUPS = ROOT + 'LoadGroups'
LOAD_GROUP = LOAD_GROUPS + DELIM + 'LoadGroup'

# TODO(efried): .//MACAddress ?
MAC_ADDRESS = ROOT + DELIM + 'MACAddress'
# like vhost0
ADAPTER_NAME = 'AdapterName'
# Storage mapping names and path
SCSI_MAPPINGS = 'VirtualSCSIMappings'
VIRT_SCSI_MAPPINGS = ROOT + SCSI_MAPPINGS
SCSI_MAPPING_ELEM = 'VirtualSCSIMapping'
SCSI_MAPPING_PATH = ROOT + SCSI_MAPPINGS + DELIM + SCSI_MAPPING_ELEM
FC_MAPPINGS = 'VirtualFibreChannelMappings'
VIRT_FIBRE_CHANNEL_COLLECTION = ROOT + FC_MAPPINGS
FC_MAPPING_ELEM = 'VirtualFibreChannelMapping'
FC_MAPPING_PATH = VIRT_FIBRE_CHANNEL_COLLECTION + DELIM + FC_MAPPING_ELEM
VFC_MAPPING_CLIENT_ADAPTER_PATH = FC_MAPPING_PATH + DELIM + 'ClientAdapter'
WWPNS_PATH = VFC_MAPPING_CLIENT_ADAPTER_PATH + DELIM + WWPNS
SWITCH_ID = 'SwitchId'
SWITCH_NAME = 'SwitchName'
SERVER_ADAPTER_PATH = ROOT + SERVER_ADAPTER
CLIENT_ADAPTER_PATH = ROOT + CLIENT_ADAPTER
CLIENT_VIR_SLOT_NUM_REL_PATH = CLIENT_ADAPTER_PATH + DELIM + VIR_SLOT_NUM
CLIENT_CONN_LPAR_REL_PATH = CLIENT_ADAPTER_PATH + DELIM + CONN_LPAR_ID
CLIENT_REMOTE_LPAR_REL_PATH = CLIENT_ADAPTER_PATH + DELIM + REMOTE_LPAR_ID
SERVER_VIR_SLOT_NUM_REL_PATH = SERVER_ADAPTER_PATH + DELIM + VIR_SLOT_NUM
SERVER_REMOTE_LPAR_REL_PATH = SERVER_ADAPTER_PATH + DELIM + REMOTE_LPAR_ID
SERVER_REMOTE_SLOT_REL_PATH = SERVER_ADAPTER_PATH + DELIM + REMOTE_SLOT_NUM
SERVER_CONN_LPAR_REL_PATH = SERVER_ADAPTER_PATH + DELIM + CONN_LPAR_ID
SERVER_CONN_SLOT_REL_PATH = SERVER_ADAPTER_PATH + DELIM + CONN_SLOT_NUM
SERVER_BACKING_DEV_REL_PATH = SERVER_ADAPTER_PATH + DELIM + BACKING_DEV
SERVER_MAP_PORT_REL_PATH = SERVER_ADAPTER_PATH + DELIM + MAP_PORT
CLIENT_LPAR_REL_PATH = CLIENT_ADAPTER_PATH + DELIM + LOCAL_LPAR_ID
CLIENT_WWPNS_REL_PATH = CLIENT_ADAPTER_PATH + DELIM + WWPNS
PORT_WWPN_REL_PATH = ROOT + PORT + DELIM + PORT_WWPN

# Storage element
STORAGE = 'Storage'
# Storage schema names
PV = 'PhysicalVolume'
PVS = 'PhysicalVolumes'
PVS_PATH = PVS + DELIM + PV
VDISK = 'VirtualDisk'
LU = 'LogicalUnit'
VOPT = 'VirtualOpticalMedia'
STORAGE_POOLS = 'StoragePools'
STORAGE_POOL_LINKS = ROOT + STORAGE_POOLS + DELIM + LINK
NPIV = 'npiv'
# vdisk attribute
DISK_NAME = 'DiskName'
# vDisk Types
BROKERED_MEDIA_ISO = 'BROKERED_MEDIA_ISO'
BROKERED_DISK_IMAGE = 'BROKERED_DISK_IMAGE'
# physical volume attribute
RESERVE_POLICY = 'ReservePolicy'
VOL_NAME = 'VolumeName'
VOL_SIZE = 'VolumeCapacity'
VOL_UID = 'VolumeUniqueID'
# LU attribute
UDID = 'UniqueDeviceID'
UDID_PATH = ROOT
UNIT_NAME = 'UnitName'
UNIT_SIZE = 'UnitCapacity'

# Target Device
TARGET_DEV = 'TargetDevice'
VIRT_TARGET_DEV = 'VirtualTargetDevice'
LU_ADDR = 'LogicalUnitAddress'
LU_ADDR_REL_PATH = ROOT + VIRT_TARGET_DEV + DELIM + LU_ADDR
# like vtscsi1
TARGET_NAME = 'TargetName'
TARGET_NAME_REL_PATH = ROOT + VIRT_TARGET_DEV + DELIM + TARGET_NAME

# Storage type element
STORAGE_TYPE = 'StorageType'
# Storage type acceepted by PowerVM
VDISK_TYPE = 'VIRTUAL_DISK'
PV_TYPE = 'PHYSICAL_VOLUME'
LU_TYPE = 'LOGICAL_UNIT'
VOPT_TYPE = 'VIRTUAL_OPTICAL_MEDIA'

POST_RETRIES = CONF.pypowervm_update_collision_retries

# PowerVM extended properties
EXT_SCSI_MAP = VIOS_VSCSI_MAP_EXT_PROP
EXT_FC_MAP = VIOS_VFC_MAP_EXT_PROP

# constants to help initialize variables
SCSI_MAP_ATTRS = dict(map_type=SCSI_MAPPING_ELEM,
                      map_collection=SCSI_MAPPINGS,
                      serv_remote_lpar_path=SERVER_REMOTE_LPAR_REL_PATH,
                      serv_remote_slot_path=SERVER_REMOTE_SLOT_REL_PATH,
                      serv_backing_dev_path=SERVER_BACKING_DEV_REL_PATH,
                      pvm_ext_prop=EXT_SCSI_MAP)
FC_MAP_ATTRS = dict(map_type=FC_MAPPING_ELEM,
                    map_collection=FC_MAPPINGS,
                    serv_remote_lpar_path=SERVER_CONN_LPAR_REL_PATH,
                    serv_remote_slot_path=SERVER_CONN_SLOT_REL_PATH,
                    serv_backing_dev_path=SERVER_MAP_PORT_REL_PATH,
                    pvm_ext_prop=EXT_FC_MAP)
STG_ATTRS = dict(scsi=SCSI_MAP_ATTRS, vfc=FC_MAP_ATTRS)


REQ_RES_API_ERR_PREFIX = 'HSCL294D'


# Updates failed indications
VIOS_UPDATE_FAILED = [HTTP_STATUS_ETAG_MISMATCH,
                      HTTP_STATUS_CONNECTION_RESET,
                      HTTP_STATUS_INVALID_URL]

# PCM
RAW_METRICS_TYPE = 'RawMetrics'
LONG_TERM_MONITOR_TYPE = 'LongTermMonitor'
PCM_SERVICE = 'pcm'
COMPUTE_LTM_ENABLED_PROPERTY = 'ComputeLTMEnabled'
LTM_ENABLED_PROPERTY = 'LongTermMonitorEnabled'
PREFERENCES_TYPE = 'preferences'

# Job Constants
PVM_JOB_STATUS_NOT_ACTIVE = 'NOT_STARTED'
PVM_JOB_STATUS_RUNNING = 'RUNNING'
PVM_JOB_STATUS_COMPLETED_OK = 'COMPLETED_OK'
PVM_JOB_STATUS_COMPLETED_WITH_WARNINGS = 'COMPLETED_WITH_WARNINGS'
PVM_JOB_STATUS_COMPLETED_WITH_ERROR = 'COMPLETED_WITH_ERROR'
JOB_ID = ROOT + 'JobID'
JOB_STATUS = ROOT + 'Status'
RESPONSE_EXCEPTION = ROOT + 'ResponseException'
JOB_MESSAGE = RESPONSE_EXCEPTION + DELIM + 'Message'
JOB_STACKTRACE = RESPONSE_EXCEPTION + DELIM + 'StackTrace'
JOB_PARAM = ROOT + 'Results' + DELIM + 'JobParameter'
JOB_RESULTS_NAME = JOB_PARAM + DELIM + 'ParameterName'
JOB_RESULTS_VALUE = JOB_PARAM + DELIM + 'ParameterValue'
REQ_OP = ROOT + 'RequestedOperation'
JOB_GROUP_NAME = REQ_OP + DELIM + 'GroupName'
JOB_OPERATION_NAME = REQ_OP + DELIM + 'OperationName'

# Media Repositories
MEDIA_REPOSITORIES = 'MediaRepositories'
VIRTUAL_MEDIA_REPOS_ELEM = 'VirtualMediaRepository'
REPOSITORY_NAME = 'RepositoryName'
REPOSITORY_SIZE = 'RepositorySize'
OPTICAL_MEDIA = 'OpticalMedia'
VIRTUAL_OPTICAL_MEDIA = 'VirtualOpticalMedia'
MEDIA_NAME = 'MediaName'
MEDIA_REPOSITORIES_PATH = ROOT + MEDIA_REPOSITORIES
VIRT_MEDIA_REPOSITORY_PATH = (
    MEDIA_REPOSITORIES_PATH + DELIM + VIRTUAL_MEDIA_REPOS_ELEM)
OPTICAL_MEDIA_PATH = (
    VIRT_MEDIA_REPOSITORY_PATH + DELIM + OPTICAL_MEDIA)
VOPT_MEDIA_PATH = ROOT + STORAGE + DELIM + VOPT + DELIM + MEDIA_NAME
