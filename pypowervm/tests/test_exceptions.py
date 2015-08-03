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

import os
import unittest

import six

import pypowervm.exceptions as pvmex

msg_params = {
    "attr": "attr_param",
    "availability_priority": "availability_priority_param",
    "avail_vios": "avail_vios_param",
    "backing_dev": "backing_dev_param",
    "cpus_avail": 890,
    "cpus_min": 357,
    "cpus_requested": 789,
    "cpu_size": 678,
    "ded_share_mode": "ded_share_mode_param",
    "desired": "desired_param",
    "des_value": "des_value_param",
    "dev": "dev_param",
    "disk_size": 246,
    "element": "element_param",
    "element_type": "element_type_param",
    "error": "error_param",
    "file_name": "file_name_param",
    "host": "host_param",
    "image_volume": "image_volume_param",
    "instance_name": "instance_name_param",
    "instance_uuid": "instance_uuid_param",
    "key": "key_param",
    "level": "level_param",
    "lpar_name": "lpar_name_param",
    "lmb": 123,
    "mac": "mac_param",
    "max": "max_param",
    "max_allowed": 234,
    "medialib_mb_required": 913,
    "mediavg_mb_avail": 802,
    "mem_avail": 468,
    "mem_min": 901,
    "mem_requested": 567,
    "min": "min_param",
    "min_vios": "min_vios_param",
    "msg": "msg_param",
    "name": "name_param",
    "new_disk_size": 135,
    "operation_name": "operation_name_param",
    "option": "option_param",
    "options": "options_param",
    "os_distro": "os_distro_param",
    "processor_compatibility": "processor_compatibility_param",
    "proc_units": "proc_units_param",
    "proc_units_per_vcpu": "proc_units_per_vcpu_param",
    "reason": "reason_param",
    "reasons": "reasons_param",
    "scg_conn_types": "scg_conn_types_param",
    "seconds": 147,
    "shared_weight": "shared_weight_param",
    "status": "status_param",
    "storage_type": "storage_type_param",
    "system_name": "system_name_param",
    "units_avail": 579,
    "units_min": 791,
    "units_requested": 680,
    "uuid": "uuid_param",
    "valid_values": "valid_values_param",
    "value": 345,
    "vcpus": 456,
    "vios_name": "vios_name_param",
    "vios_state": "vios_state_param",
    "volume": "volume_param",
    "volume_group_name": "volume_group_name_param",
    "volume_id": "volume_id_param",
    "f_id": 1,
    "p_id": 2
}

os.environ['LANG'] = 'en_US'

class2msg = {
    pvmex.InvalidVIOConfig:
    "The virtual adapter configuration is invalid.",
    pvmex.InvalidAttrWithCapped:
    "Sharing weight is not a valid option for capped sharing mode for virtual "
    "machine 'instance_name_param'.",
    pvmex.IncompleteHostStatistics:
    "Unable to retrieve host statistics for managed host host_param.",
    pvmex.AllocStgForMinVIOSFailed:
    "Unable to configure storage adapters for virtual machine "
    "instance_name_param on the required number of Virtual I/O Servers for "
    "the volume. Minimum number of Virtual I/O Servers required per volume: "
    "min_vios_param. reasons_param",
    pvmex.UnsupportedInDLPAR:
    "Changing attr_param is not supported while virtual machine "
    "'instance_name_param' is running. The virtual machine must be powered "
    "off first.",
    pvmex.VCPUsAboveMaxAllowed:
    "The desired processors (456) cannot be above the maximum processors "
    "allowed per partition (234) for virtual machine 'instance_name_param'.",
    pvmex.NoRMCConnectivityForStorage:
    "Unable to configure storage for virtual machine 'instance_name_param'. "
    "Configuring storage for a virtual machine in Active state requires RMC "
    "connectivity.",
    pvmex.VIOSRMCNotAcitve:
    "Virtual I/O Server vios_name_param does not have an active Resource "
    "Monitoring Control state.",
    pvmex.SNoStorageConnectivityFound:
    "Unable to find a supported storage connection type in the list of "
    "storage connectivity groups: scg_conn_types_param",
    pvmex.UpdateInfoIncomplete:
    "Failed to update object properties for uuid_param because the object "
    "information is incomplete.",
    pvmex.HostBusy:
    "The operation cannot complete because the system is busy. Wait a few "
    "minutes and then try the operation again.",
    pvmex.InvalidAttrWithShared:
    "'option_param' is not a valid option for shared processor mode for "
    "virtual machine 'instance_name_param'.",
    pvmex.MustSpecifyVCPURange:
    "If you specify a minimum and maximum value for processing units, you "
    "must also specify a minimum and maximum value for virtual CPUs for "
    "virtual machine 'instance_name_param'.",
    pvmex.UpdateFailed:
    "Failed to update object properties for uuid_param because the object "
    "information is out of date.",
    pvmex.InvalidSharedWeight:
    "'shared_weight_param' is not a valid value for shared processor weight "
    "for virtual machine 'instance_name_param'. Specify a value between 0 and "
    "255.",
    pvmex.RmReqAdapter:
    "Unable to remove the virtual adapter from Virtual I/O Server uuid_param "
    "because it is a required adapter.",
    pvmex.CreateAdapter:
    "Unable to create virtual adapters on Virtual I/O Server 'uuid_param'. "
    "Run the Verify Environment tool. You can either click the Verify "
    "Environment button on the GUI Home page or type the powervc-validate "
    "command on the command line. Verify that a sufficient number of virtual "
    "resources are configured for the Virtual I/O Server. Then, try the "
    "operation again.",
    pvmex.NotLMBMultiple:
    "attr_param (345 MB) is not a multiple of the region memory size ("
    "123 MB) for virtual machine 'instance_name_param'. Specify a value that "
    "is a multiple of the region memory size.",
    pvmex.InvalidAttrWithDed:
    "'option_param' is not a valid option for dedicated processor mode for "
    "virtual machine 'instance_name_param'.",
    pvmex.AdapterCreateFailed:
    "Unable to create virtual adapter for attaching storage to virtual "
    "machine instance_name_param. Reason: reason_param",
    pvmex.MustSpecifyProcUnits:
    "If you specify a minimum and maximum value for processing units, you "
    "must also specify a value for desired processing units for virtual "
    "machine 'instance_name_param'.",
    pvmex.VolumeAttachFailed:
    "Unable to attach storage backing_dev_param to virtual machine "
    "instance_name_param. reason_param",
    pvmex.InvalidExtraSpec:
    "Invalid attribute name 'key_param' was passed in as part of the flavor "
    "extra specs for virtual machine 'instance_name_param'.",
    pvmex.InvalidProcCompatIBMi:
    "Changing 'processor_compatibility_param' is not supported because for an "
    "IBM i virtual machine 'instance_name_param', its processor compatibility "
    "mode can only be set as 'default' on Power6 host.",
    pvmex.VIOSLicenseNotAccepted:
    "The license for Virtual I/O Server vios_name_param has not been "
    "accepted.",
    pvmex.InsufficientCPU:
    "Insufficient CPUs available on host for virtual machine "
    "'instance_name_param' (789 requested and "
    "890 available)",
    pvmex.InsufficientVIOSForStg:
    "There are not enough Virtual I/O Servers with the necessary connectivity "
    "within the storage connectivity group for virtual machine "
    "'instance_name_param' volume configuration: (Requested: min_vios_param "
    "Available: avail_vios_param). reasons_param",
    pvmex.AttrValueInvalid:
    "'345' is not a valid value for attr_param for virtual machine "
    "'instance_name_param'.",
    pvmex.InvalidProcCompat:
    "'processor_compatibility_param' is not a valid option for processor "
    "compatibility for virtual machine 'instance_name_param'. Valid options "
    "include the following: 'valid_values_param'.",
    pvmex.ProcUnitsGTVCPUs:
    "The number of processing units cannot be a larger value than the number "
    "of virtual CPUs. The requested level_param processing units were "
    "'proc_units_param' and the requested level_param virtual CPUs were '456' "
    "for virtual machine 'instance_name_param'.",
    pvmex.AttrRequired:
    "attr_param is a required attribute for virtual machine "
    "'instance_name_param'.",
    pvmex.DesiredGTMax:
    "The value for maximum attr_param (345) cannot be less than the desired "
    "attr_param (des_value_param) for virtual machine 'instance_name_param'.",
    pvmex.VIOSNotFound:
    "Unable to locate the Virtual I/O Server for this operation",
    pvmex.MACNotSupported:
    "The virtual machine name_param cannot use the specified port because it "
    "would require MAC address mac_param to be set. The host does not support "
    "custom MAC addresses.",
    pvmex.VolumeLookupFailed:
    "Unable to determine that the volume with id uuid_param has been "
    "discovered or mapped on a Virtual I/O Server",
    pvmex.StorageTypeNotSupported:
    "The storage type specified 'storage_type_param' is not supported for "
    "this operation",
    pvmex.BothMinMax:
    "If you specify a minimum or maximum value for attr_param, you must "
    "specify both minimum and maximum attr_param for virtual machine "
    "'instance_name_param'.",
    pvmex.InvalidBoolean:
    "'345' is not valid for virtual machine 'instance_name_param'. "
    "option_param must either be true or false. ",
    pvmex.NoRMCConnectivity:
    "Unable to resize virtual machine 'instance_name_param'. Resizing an "
    "active virtual machine requires RMC connectivity.",
    pvmex.InvalidProcUnitsPerVCPU:
    "There must be a minimum of proc_units_per_vcpu_param processing units "
    "per virtual CPU. The requested level_param processing units were "
    "'proc_units_param' and the requested level_param virtual CPUs were '456' "
    "for virtual machine 'instance_name_param'.",
    pvmex.InvalidAvailPriority:
    "'availability_priority_param' is not a valid value for availability "
    "priority for virtual machine 'instance_name_param'. Specify a value "
    "between 0 and 255.",
    pvmex.DesiredLTMin:
    "The value for minimum attr_param (345) cannot be greater than the "
    "desired attr_param (des_value_param) for virtual machine "
    "'instance_name_param'.",
    pvmex.VIOSMissingPhysicalPort:
    "Virtual I/O Server vios_name_param does not have any fibre channel "
    "ports listed in the storage connectivity group.",
    pvmex.VGMissing:
    "Unable to find volume group 'volume_group_name_param' on Virtual I/O "
    "Server 'uuid_param'.",
    pvmex.InvalidDedShareMode:
    "'ded_share_mode_param' is not a valid option for sharing mode for "
    "dedicated processors for virtual machine 'instance_name_param'. Valid "
    "options include the following: 'valid_values_param'.",
    pvmex.VIOSIsNotRunning:
    "Virtual I/O Server vios_name_param is not running. The current state is: "
    "vios_state_param",
    pvmex.DesiredOutsideCurrentRange:
    "Desired attr_param requested (desired_param) is outside the currently "
    "assigned minimum (min_param) and maximum (max_param) values for virtual "
    "machine 'instance_name_param'. Either specify a valid value for desired "
    "attr_param or power off the virtual machine before resizing.",
    pvmex.VIOSError:
    "Error getting information from the Virtual I/O Server(s). This could be "
    "because the it is down or too busy to process the request.",
    pvmex.MaxVCPUsAboveMaxAllowed:
    "The maximum processors (456) cannot be above the maximum system capacity "
    "processor limit 234) for virtual machine 'instance_name_param'.",
    pvmex.HostNotOperating:
    "The operation failed because it is only allowed when the managed host is "
    "in the Standby or Operating state.",
    pvmex.AllocStgForDualFabricFailed:
    "Unable to configure storage adapters for virtual machine "
    "instance_name_param on available physical Fibre Channel ports that "
    "satisfy the NPIV switch fabric requirement of the storage connectivity "
    "group. reasons_param",
    pvmex.VIOSIsTooBusy:
    "Virtual I/O Server vios_name_param is currently too busy to process "
    "update operations.",
    pvmex.VolumeDetachFailed:
    "Unable to detach storage backing_dev_param from virtual machine "
    "instance_name_param. reason_param",
    pvmex.InvalidStorageConnectivityInfo:
    "Unable to perform this operation with the storage connectivity group "
    "provided for virtual machine instance_name_param.",
    pvmex.NotFound:
    "Element not found: element_type_param element_param",
    pvmex.LPARNotFound:
    "LPAR not found: lpar_name_param",
    pvmex.SystemNotFound:
    "System not found: system_name_param",

    pvmex.MigrationFailed:
    "The migration task failed. error_param",
    pvmex.MigrationInProgress:
    "Migration of lpar_name_param is already in progress.",
    pvmex.ProgressUpdateError:
    "Unable to update progress for virtual machine 'uuid_param'.",
    pvmex.MediaRepOutOfSpace:
    "The media library is too small for the ISO image. The "
    "media library requires 913 MB of space but only "
    "802 MB is available.",
    pvmex.LPARIsRunningDuringCapture:
    "Virtual machine 'instance_name_param' is running during "
    "capture. Virtual machines must be stopped before they "
    "can be captured.",
    pvmex.LPARInstanceNotFound:
    "Unable to find virtual machine 'instance_name_param'.",
    pvmex.InsufficientResources:
    "Insufficient resources",
    pvmex.MemoryBelowMin:
    "The requested memory (567 MB) is below "
    "the minimum required value (901 MB)",
    pvmex.DiskBelowActual:
    "The requested disk (135 GB) is lesser than "
    "the existing disk (246 GB)",
    pvmex.CPUsBelowMin:
    "The requested CPUs (789) are below "
    "the minimum required value (357) ",
    pvmex.ProcUnitsBelowMin:
    "The requested processing units (680) are "
    "below the minimum required value (791) ",
    pvmex.InsufficientFreeMemory:
    "Insufficient free memory: (567 MB "
    "requested, 468 MB free)",
    pvmex.InsufficientProcUnits:
    "Insufficient available processing units: "
    "(680 requested, "
    "579 available)",
    pvmex.JobRequestFailed:
    "The 'operation_name_param' operation failed. error_param",
    pvmex.JobRequestTimedOut:
    "The 'operation_name_param' operation failed. "
    "Failed to complete the task in 147 seconds.",
    pvmex.LPARInstanceCleanupFailed:
    "Virtual machine 'instance_name_param' cleanup failed. "
    "Reason: reason_param",
    pvmex.InstanceTerminationFailure:
    "Failed to delete virtual machine. reason_param",
    pvmex.NoInstanceBootDeviceDefined:
    "The boot device name attribute is not defined for virtual "
    "machine instance_name_param with ID instance_uuid_param.",
    pvmex.IBMiDiskResizeNotSupported:
    "Unable to change disk size for virtual machine "
    "instance_name_param because disk size change is not supported "
    "for IBM i.",
    pvmex.InvalidImageObject:
    "Unable to save the captured image meta data for virtual "
    "machine instance_name_param because the image object is "
    "invalid.",
    pvmex.InvalidBootVolume:
    "Boot volume volume_param is invalid for virtual machine "
    "instance_name_param with ID instance_uuid_param.",
    pvmex.BootVolumeCloneFailure:
    "Clone for boot volume image_volume_param failed for virtual "
    "machine instance_name_param with ID instance_uuid_param.",
    pvmex.PowerVMAPIError:
    "An error occurred while working with objects returned "
    "from the PowerVM API.",
    pvmex.NoOSForVM:
    "Virtual machine 'instance_name_param' does not have an "
    "operating system identified.  The process for bringing "
    "the virtual machine under management by PowerVC must "
    "be completed.",
    pvmex.UnsupportedOSForVM:
    "The operating system os_distro_param for virtual machine "
    "'instance_name_param' is not supported. Supported operating "
    "systems include the following: options_param",
    pvmex.UnsupportedMultiDiskForVM:
    "Unable to capture virtual machine 'instance_name_param' "
    "because IBM i does not support multi-disks capture.",
    pvmex.ErrorExtendingVolume:
    "An error occurred when extending volume volume_id_param",
    pvmex.NoLicenseSRC:
    "Unable to deploy virtual machine 'instance_name_param' "
    "because the host does not support the operating system "
    "installed on this image",
    pvmex.UnSupportedOSVersion:
    "Unable to deploy virtual machine 'instance_name_param' "
    "because the host does not support the operating system"
    "version installed on this image",
    pvmex.LUADiscoveryFailed:
    "Failed to discover the volume error code status_param",
    pvmex.LUADiscoveryITLError:
    "LUA Discovery Completed with few ITL Error:"
    "Device dev_param Discovered, Status: status_param"
    "Reason: msg_param",
    pvmex.AuthFileReadError:
    "Failed to read session file.",
    pvmex.AuthFileReadMismatchOwnerError:
    "Failed to read session file. Process group ID 2 must match "
    "file group owner ID 1.",
}


class TestExceptions(unittest.TestCase):
    """Test coverage for the pypowervm.exceptions module."""

    def raise_helper(self, e):
        raise e

    def fmt_helper(self, eclass, expected_message):
        e = eclass(**msg_params)
        self.assertRaises(eclass, self.raise_helper, e)
        try:
            raise e
        except eclass as e1:
            self.assertEqual(e1.args[0], expected_message)

    def test_Error(self):
        e = pvmex.Error("test")
        self.assertRaises(pvmex.Error, self.raise_helper, e)
        try:
            raise e
        except pvmex.Error as e1:
            self.assertEqual(e1.args[0], "test")

    def test_fmterrors(self):
        for e, s in six.iteritems(class2msg):
            try:
                self.fmt_helper(e, s)
            except ValueError:
                self.fail(s)

    def test_bogusformatparams(self):
        class Bogus(pvmex.AbstractMsgFmtError):
            msg_fmt = "This has a %(bogus)s format parameter."

        self.assertRaises(KeyError, Bogus, **msg_params)

if __name__ == "__main__":
    unittest.main()
