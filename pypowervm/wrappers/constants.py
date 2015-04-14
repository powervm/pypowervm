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

DELIM = '/'
LINK = 'link'

# Types
MGT_CONSOLE = 'ManagementConsole'

SUFFIX_TYPE_DO = 'do'

# Adapter elements, values, and path
VIR_SLOT_NUM = 'VirtualSlotNumber'
WWPNS = 'WWPNs'
SHARED_ETHERNET_ADAPTERS = 'SharedEthernetAdapters'
SHARED_ETHERNET_ADAPTER = (
    SHARED_ETHERNET_ADAPTERS + DELIM + 'SharedEthernetAdapter')
FREE_ETHERNET_ADAPTERS = 'FreeEthenetBackingDevicesForSEA'
IO_ADAPTER_CHOICE = FREE_ETHERNET_ADAPTERS + DELIM + 'IOAdapterChoice'
ETHERNET_BACKING_DEVICE = IO_ADAPTER_CHOICE + DELIM + 'EthernetBackingDevice'
IP_INTERFACE = 'IPInterface'
IP_ADDRESS = 'IPAddress'
IF_ADDR = IP_INTERFACE + DELIM + IP_ADDRESS
PORT_VLAN_ID = 'PortVLANID'

# Storage mapping names and path
FC_MAPPINGS = 'VirtualFibreChannelMappings'
VIRT_FIBRE_CHANNEL_COLLECTION = FC_MAPPINGS
FC_MAPPING_ELEM = 'VirtualFibreChannelMapping'
FC_MAPPING_PATH = VIRT_FIBRE_CHANNEL_COLLECTION + DELIM + FC_MAPPING_ELEM
VFC_MAPPING_CLIENT_ADAPTER_PATH = FC_MAPPING_PATH + DELIM + 'ClientAdapter'
WWPNS_PATH = VFC_MAPPING_CLIENT_ADAPTER_PATH + DELIM + WWPNS

# Storage schema names
PV = 'PhysicalVolume'
PVS = 'PhysicalVolumes'
PVS_PATH = PVS + DELIM + PV
# physical volume attribute
RESERVE_POLICY = 'ReservePolicy'
VOL_NAME = 'VolumeName'
VOL_UID = 'VolumeUniqueID'

UDID = 'UniqueDeviceID'

# Job Constants
PVM_JOB_STATUS_NOT_ACTIVE = 'NOT_STARTED'
PVM_JOB_STATUS_RUNNING = 'RUNNING'
PVM_JOB_STATUS_COMPLETED_OK = 'COMPLETED_OK'
PVM_JOB_STATUS_COMPLETED_WITH_WARNINGS = 'COMPLETED_WITH_WARNINGS'
PVM_JOB_STATUS_COMPLETED_WITH_ERROR = 'COMPLETED_WITH_ERROR'
JOB_ID = 'JobID'
JOB_STATUS = 'Status'
RESPONSE_EXCEPTION = 'ResponseException'
JOB_MESSAGE = RESPONSE_EXCEPTION + DELIM + 'Message'
JOB_STACKTRACE = RESPONSE_EXCEPTION + DELIM + 'StackTrace'
JOB_PARAM = 'Results' + DELIM + 'JobParameter'
JOB_RESULTS_NAME = JOB_PARAM + DELIM + 'ParameterName'
JOB_RESULTS_VALUE = JOB_PARAM + DELIM + 'ParameterValue'
REQ_OP = 'RequestedOperation'
JOB_GROUP_NAME = REQ_OP + DELIM + 'GroupName'
JOB_OPERATION_NAME = REQ_OP + DELIM + 'OperationName'

# TODO(efried): (Re)move these
# Media Repositories
MEDIA_REPOSITORIES = 'MediaRepositories'
VIRTUAL_MEDIA_REPOS_ELEM = 'VirtualMediaRepository'
OPTICAL_MEDIA = 'OpticalMedia'
MEDIA_REPOSITORIES_PATH = MEDIA_REPOSITORIES
VIRT_MEDIA_REPOSITORY_PATH = (
    MEDIA_REPOSITORIES_PATH + DELIM + VIRTUAL_MEDIA_REPOS_ELEM)
