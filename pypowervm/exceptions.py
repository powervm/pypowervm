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

import abc

import six

from pypowervm.i18n import _


class Error(Exception):
    """Error on PowerVM API Adapter method invocation."""

    def __init__(self, msg, response=None):
        """Initializes Error with optional `response` object."""
        self.response = response
        self.orig_response = None
        super(Error, self).__init__(msg)


class ConnectionError(Error):
    """Connection Error on PowerVM API Adapter method invocation."""


class SSLError(Error):
    """SSL Error on PowerVM API Adapter method invocation."""


class TimeoutError(Error):
    """Timeout Error on PowerVM API Adapter method invocation."""


class HttpError(Error):
    """HTTP Error on PowerVM API Adapter method invocation."""

    def __init__(self, msg, response):
        """Initializes HttpError with required `response` object."""
        super(HttpError, self).__init__(msg, response=response)


class AtomError(Error):
    """Atom Error on PowerVM API Adapter method invocation."""

    def __init__(self, msg, response):
        """Initializes AtomError with required `response` object."""
        super(AtomError, self).__init__(msg, response=response)


@six.add_metaclass(abc.ABCMeta)
class AbstractMsgFmtError(Error):
    """Used to raise an exception with a formattable/parameterized message.

    The subclass must set the msg_fmt class variable.  The consumer should
    instantiate the subclass with **kwargs appropriate to its msg_fmt.
    """
    def __init__(self, response=None, **kwa):
        msg = self.msg_fmt % kwa
        super(AbstractMsgFmtError, self).__init__(msg, response=response)


class InvalidVIOConfig(AbstractMsgFmtError):
    msg_fmt = _("The virtual adapter configuration is invalid.")


class AttrRequired(AbstractMsgFmtError):
    msg_fmt = _("%(attr)s is a required attribute for virtual machine "
                "'%(instance_name)s'.")


class AttrValueInvalid(AbstractMsgFmtError):
    msg_fmt = _("'%(value)s' is not a valid value for %(attr)s for "
                "virtual machine '%(instance_name)s'.")


class DesiredLTMin(AbstractMsgFmtError):
    msg_fmt = _("The value for minimum %(attr)s (%(value)s) cannot be greater "
                "than the desired %(attr)s (%(des_value)s) for virtual "
                "machine '%(instance_name)s'.")


class DesiredGTMax(AbstractMsgFmtError):
    msg_fmt = _("The value for maximum %(attr)s (%(value)s) cannot be less "
                "than the desired %(attr)s (%(des_value)s) for virtual "
                "machine '%(instance_name)s'.")


class BothMinMax(AbstractMsgFmtError):
    msg_fmt = _("If you specify a minimum or maximum value for %(attr)s, "
                "you must specify both minimum and maximum %(attr)s for "
                "virtual machine '%(instance_name)s'.")


class NotLMBMultiple(AbstractMsgFmtError):
    msg_fmt = _("%(attr)s (%(value)d MB) is not a multiple of the region "
                "memory size (%(lmb)d MB) for virtual machine "
                "'%(instance_name)s'. Specify a value that is a multiple "
                "of the region memory size.")


class InvalidAvailPriority(AbstractMsgFmtError):
    msg_fmt = _("'%(availability_priority)s' is not a valid value for "
                "availability priority for virtual machine "
                "'%(instance_name)s'. Specify a value between 0 and 255.")


class InvalidProcCompat(AbstractMsgFmtError):
    msg_fmt = _("'%(processor_compatibility)s' is not a valid option for "
                "processor compatibility for virtual machine "
                "'%(instance_name)s'. Valid options include the "
                "following: '%(valid_values)s'.")


class InvalidProcCompatIBMi(AbstractMsgFmtError):
    msg_fmt = _("Changing '%(processor_compatibility)s' "
                "is not supported because for an IBM i "
                "virtual machine '%(instance_name)s', its "
                "processor compatibility mode can only be "
                "set as 'default' on Power6 host.")


class InvalidBoolean(AbstractMsgFmtError):
    msg_fmt = _("'%(value)s' is not valid for virtual machine "
                "'%(instance_name)s'. %(option)s must either be "
                "true or false. ")


class InvalidDedShareMode(AbstractMsgFmtError):
    msg_fmt = _("'%(ded_share_mode)s' is not a valid option for sharing mode "
                "for dedicated processors for virtual machine "
                "'%(instance_name)s'. Valid options include the following: "
                "'%(valid_values)s'.")


class InvalidAttrWithDed(AbstractMsgFmtError):
    msg_fmt = _("'%(option)s' is not a valid option for dedicated processor "
                "mode for virtual machine '%(instance_name)s'.")


class InvalidAttrWithShared(AbstractMsgFmtError):
    msg_fmt = _("'%(option)s' is not a valid option for shared processor "
                "mode for virtual machine '%(instance_name)s'.")


class InvalidAttrWithCapped(AbstractMsgFmtError):
    msg_fmt = _("Sharing weight is not a valid option for capped sharing "
                "mode for virtual machine '%(instance_name)s'.")


class InvalidSharedWeight(AbstractMsgFmtError):
    msg_fmt = _("'%(shared_weight)s' is not a valid value for shared "
                "processor weight for virtual machine '%(instance_name)s'. "
                "Specify a value between 0 and 255.")


class MustSpecifyVCPURange(AbstractMsgFmtError):
    msg_fmt = _("If you specify a minimum and maximum value for processing "
                "units, you must also specify a minimum and maximum value for "
                "virtual CPUs for virtual machine '%(instance_name)s'.")


class MustSpecifyProcUnits(AbstractMsgFmtError):
    msg_fmt = _("If you specify a minimum and maximum value for processing "
                "units, you must also specify a value for desired processing "
                "units for virtual machine '%(instance_name)s'.")


class InvalidProcUnitsPerVCPU(AbstractMsgFmtError):
    msg_fmt = _("There must be a minimum of %(proc_units_per_vcpu)s "
                "processing units per virtual CPU. The requested %(level)s "
                "processing units were '%(proc_units)s' and the requested "
                "%(level)s virtual CPUs were '%(vcpus)d' for virtual machine "
                "'%(instance_name)s'.")


class ProcUnitsGTVCPUs(AbstractMsgFmtError):
    msg_fmt = _("The number of processing units cannot be a larger value than "
                "the number of virtual CPUs. The requested %(level)s "
                "processing units were '%(proc_units)s' and the requested "
                "%(level)s virtual CPUs were '%(vcpus)d' for virtual machine "
                "'%(instance_name)s'.")


class VCPUsAboveMaxAllowed(AbstractMsgFmtError):
    msg_fmt = _("The desired processors (%(vcpus)d) cannot be above the "
                "maximum processors allowed per partition (%(max_allowed)d) "
                "for virtual machine '%(instance_name)s'.")


class MaxVCPUsAboveMaxAllowed(AbstractMsgFmtError):
    msg_fmt = _("The maximum processors (%(vcpus)d) cannot be above the "
                "maximum system capacity processor limit %(max_allowed)d) "
                "for virtual machine '%(instance_name)s'.")


class NoRMCConnectivity(AbstractMsgFmtError):
    msg_fmt = _("Unable to resize virtual machine '%(instance_name)s'. "
                "Resizing an active virtual machine requires RMC "
                "connectivity.")


class VolumeAttachFailed(AbstractMsgFmtError):
    msg_fmt = _("Unable to attach storage %(backing_dev)s to virtual machine "
                "%(instance_name)s. %(reason)s")


class VolumeDetachFailed(AbstractMsgFmtError):
    msg_fmt = _("Unable to detach storage %(backing_dev)s from virtual "
                "machine %(instance_name)s. %(reason)s")


class VolumeLookupFailed(AbstractMsgFmtError):
    msg_fmt = _("Unable to determine that the volume with id %(uuid)s has "
                "been discovered or mapped on a Virtual I/O Server")


class VIOSNotFound(AbstractMsgFmtError):
    msg_fmt = _("Unable to locate the Virtual I/O Server for this operation")


class StorageTypeNotSupported(AbstractMsgFmtError):
    msg_fmt = _("The storage type specified '%(storage_type)s' is "
                "not supported for this operation")


class DesiredOutsideCurrentRange(AbstractMsgFmtError):
    msg_fmt = _("Desired %(attr)s requested (%(desired)s) is outside the "
                "currently assigned minimum (%(min)s) and maximum (%(max)s) "
                "values for virtual machine '%(instance_name)s'. Either "
                "specify a valid value for desired %(attr)s or power off the "
                "virtual machine before resizing.")


class UnsupportedInDLPAR(AbstractMsgFmtError):
    msg_fmt = _("Changing %(attr)s is not supported while virtual machine "
                "'%(instance_name)s' is running. The virtual machine must "
                "be powered off first.")


class UpdateFailed(AbstractMsgFmtError):
    msg_fmt = _("Failed to update object properties for %(uuid)s because "
                "the object information is out of date.")


class SNoStorageConnectivityFound(AbstractMsgFmtError):
    msg_fmt = _("Unable to find a supported storage connection type in the "
                "list of storage connectivity groups: %(scg_conn_types)s")


class AdapterCreateFailed(AbstractMsgFmtError):
    msg_fmt = _("Unable to create virtual adapter for attaching storage "
                "to virtual machine %(instance_name)s. Reason: %(reason)s")


class InvalidStorageConnectivityInfo(AbstractMsgFmtError):
    msg_fmt = _("Unable to perform this operation with the storage "
                "connectivity group provided for virtual machine "
                "%(instance_name)s.")


class UpdateInfoIncomplete(AbstractMsgFmtError):
    msg_fmt = _("Failed to update object properties for %(uuid)s because "
                "the object information is incomplete.")


class NoRMCConnectivityForStorage(AbstractMsgFmtError):
    msg_fmt = _("Unable to configure storage for virtual machine "
                "'%(instance_name)s'. Configuring storage for a virtual "
                "machine in Active state requires RMC connectivity.")


class InvalidExtraSpec(AbstractMsgFmtError):
    msg_fmt = _("Invalid attribute name '%(key)s' was passed in as part of "
                "the flavor extra specs for virtual machine "
                "'%(instance_name)s'.")


class HostBusy(AbstractMsgFmtError):
    msg_fmt = _("The operation cannot complete because the system is busy. "
                "Wait a few minutes and then try the operation again.")


class VGMissing(AbstractMsgFmtError):
    msg_fmt = _("Unable to find volume group "
                "'%(volume_group_name)s' on Virtual I/O Server '%(uuid)s'.")


class IncompleteHostStatistics(AbstractMsgFmtError):
    msg_fmt = _("Unable to retrieve host statistics for managed host "
                "%(host)s.")


class RmReqAdapter(AbstractMsgFmtError):
    msg_fmt = _("Unable to remove the virtual adapter from Virtual I/O Server "
                "%(uuid)s because it is a required adapter.")


class CreateAdapter(AbstractMsgFmtError):
    msg_fmt = _("Unable to create virtual adapters on Virtual I/O Server "
                "'%(uuid)s'. Run the Verify Environment tool. "
                "You can either click the Verify Environment button on the "
                "GUI Home page or type the powervc-validate command on the "
                "command line. Verify that a sufficient number of virtual "
                "resources are configured for the Virtual I/O Server. Then, "
                "try the operation again.")


class VIOSLicenseNotAccepted(AbstractMsgFmtError):
    msg_fmt = _("The license for Virtual I/O Server %(vios_name)s "
                "has not been accepted.")


class VIOSIsNotRunning(AbstractMsgFmtError):
    msg_fmt = _("Virtual I/O Server %(vios_name)s is not running. "
                "The current state is: %(vios_state)s")


class VIOSRMCNotAcitve(AbstractMsgFmtError):
    msg_fmt = _("Virtual I/O Server %(vios_name)s does not have an active "
                "Resource Monitoring Control state.")


class VIOSIsTooBusy(AbstractMsgFmtError):
    msg_fmt = _("Virtual I/O Server %(vios_name)s is currently "
                "too busy to process update operations.")


class VIOSMissingPhysicalPort(AbstractMsgFmtError):
    msg_fmt = _("Virtual I/O Server %(vios_name)s does not have any "
                "fibre channel ports listed in the storage connectivity "
                "group.")


class InsufficientVIOSForStg(AbstractMsgFmtError):
    msg_fmt = _("There are not enough Virtual I/O Servers with the necessary "
                "connectivity within the storage connectivity group for "
                "virtual machine '%(instance_name)s' volume configuration: "
                "(Requested: %(min_vios)s Available: %(avail_vios)s). "
                "%(reasons)s")


class AllocStgForMinVIOSFailed(AbstractMsgFmtError):
    msg_fmt = _("Unable to configure storage adapters for virtual machine "
                "%(instance_name)s on the required number of "
                "Virtual I/O Servers for the volume. "
                "Minimum number of Virtual I/O Servers required per volume: "
                "%(min_vios)s. %(reasons)s")


class AllocStgForDualFabricFailed(AbstractMsgFmtError):
    msg_fmt = _("Unable to configure storage adapters for virtual machine "
                "%(instance_name)s on available physical Fibre Channel ports "
                "that satisfy the NPIV switch fabric requirement of the "
                "storage connectivity group. %(reasons)s")


class MACNotSupported(AbstractMsgFmtError):
    msg_fmt = _("The virtual machine %(name)s cannot use the specified "
                "port because it would require MAC address %(mac)s to be set. "
                "The host does not support custom MAC addresses.")


class HostNotOperating(AbstractMsgFmtError):
    msg_fmt = _("The operation failed because it is only allowed when the "
                "managed host is in the Standby or Operating state.")


class VIOSError(AbstractMsgFmtError):
    msg_fmt = _("Error getting information from the Virtual I/O Server(s). "
                "This could be because the it is down or too busy to process "
                "the request.")


class NotFound(AbstractMsgFmtError):
    msg_fmt = _('Element not found: %(element_type)s %(element)s')


class LPARNotFound(AbstractMsgFmtError):
    msg_fmt = _('LPAR not found: %(lpar_name)s')


class SystemNotFound(AbstractMsgFmtError):
    msg_fmt = _('System not found: %(system_name)s')


class MigrationFailed(AbstractMsgFmtError):
    msg_fmt = _("The migration task failed. %(error)s")


class MigrationInProgress(AbstractMsgFmtError):
    msg_fmt = _("Migration of %(lpar_name)s is already in progress.")


class ProgressUpdateError(AbstractMsgFmtError):
    msg_fmt = _("Unable to update progress for virtual machine '%(uuid)s'.")


class MediaRepOutOfSpace(AbstractMsgFmtError):
    msg_fmt = _("The media library is too small for the ISO image. The "
                "media library requires %(medialib_mb_required)d MB of space "
                "but only %(mediavg_mb_avail)d MB is available.")


class LPARIsRunningDuringCapture(AbstractMsgFmtError):
    msg_fmt = _("Virtual machine '%(instance_name)s' is running during "
                "capture. Virtual machines must be stopped before they "
                "can be captured.")


class LPARInstanceNotFound(AbstractMsgFmtError):
    msg_fmt = _("Unable to find virtual machine '%(instance_name)s'.")


class InsufficientResources(AbstractMsgFmtError):
    msg_fmt = _("Insufficient resources")


class MemoryBelowMin(InsufficientResources):
    msg_fmt = _("The requested memory (%(mem_requested)d MB) is below "
                "the minimum required value (%(mem_min)d MB)")


class DiskBelowActual(InsufficientResources):
    msg_fmt = _("The requested disk (%(new_disk_size)d GB) is lesser than "
                "the existing disk (%(disk_size)d GB)")


class CPUsBelowMin(InsufficientResources):
    msg_fmt = _("The requested CPUs (%(cpus_requested)d) are below "
                "the minimum required value (%(cpus_min)d) ")


class ProcUnitsBelowMin(InsufficientResources):
    msg_fmt = _("The requested processing units (%(units_requested)d) are "
                "below the minimum required value (%(units_min)d) ")


class InsufficientFreeMemory(InsufficientResources):
    msg_fmt = _("Insufficient free memory: (%(mem_requested)d MB "
                "requested, %(mem_avail)d MB free)")


class InsufficientCPU(AbstractMsgFmtError):
    msg_fmt = _("Insufficient CPUs available on host for "
                "virtual machine '%(instance_name)s' (%(cpus_requested)d "
                "requested and %(cpus_avail)d available)")


class InsufficientProcUnits(InsufficientResources):
    msg_fmt = _("Insufficient available processing units: "
                "(%(units_requested)d requested, "
                "%(units_avail)d available)")


class JobRequestFailed(AbstractMsgFmtError):
    msg_fmt = _("The '%(operation_name)s' operation failed. %(error)s")


class JobRequestTimedOut(JobRequestFailed):
    msg_fmt = _("The '%(operation_name)s' operation failed. "
                "Failed to complete the task in %(seconds)d seconds.")


class LPARInstanceCleanupFailed(AbstractMsgFmtError):
    msg_fmt = _("Virtual machine '%(instance_name)s' cleanup failed. "
                "Reason: %(reason)s")


class InstanceTerminationFailure(AbstractMsgFmtError):
    msg_fmt = _("Failed to delete virtual machine. %(reason)s")


class NoInstanceBootDeviceDefined(AbstractMsgFmtError):
    msg_fmt = _("The boot device name attribute is not defined for virtual "
                "machine %(instance_name)s with ID %(instance_uuid)s.")


class IBMiDiskResizeNotSupported(AbstractMsgFmtError):
    msg_fmt = _("Unable to change disk size for virtual machine "
                "%(instance_name)s because disk size change is not supported "
                "for IBM i.")


class InvalidImageObject(AbstractMsgFmtError):
    msg_fmt = _("Unable to save the captured image meta data for virtual "
                "machine %(instance_name)s because the image object is "
                "invalid.")


class InvalidBootVolume(AbstractMsgFmtError):
    msg_fmt = _("Boot volume %(volume)s is invalid for virtual machine "
                "%(instance_name)s with ID %(instance_uuid)s.")


class BootVolumeCloneFailure(AbstractMsgFmtError):
    msg_fmt = _("Clone for boot volume %(image_volume)s failed for virtual "
                "machine %(instance_name)s with ID %(instance_uuid)s.")


class PowerVMAPIError(AbstractMsgFmtError):
    msg_fmt = _("An error occurred while working with objects returned "
                "from the PowerVM API.")


class NoOSForVM(AbstractMsgFmtError):
    msg_fmt = _("Virtual machine '%(instance_name)s' does not have an "
                "operating system identified.  The process for bringing "
                "the virtual machine under management by PowerVC must "
                "be completed.")


class UnsupportedOSForVM(AbstractMsgFmtError):
    msg_fmt = _("The operating system %(os_distro)s for virtual machine "
                "'%(instance_name)s' is not supported. Supported operating "
                "systems include the following: %(options)s")


class UnsupportedMultiDiskForVM(AbstractMsgFmtError):
    msg_fmt = _("Unable to capture virtual machine '%(instance_name)s' "
                "because IBM i does not support multi-disks capture.")


class ErrorExtendingVolume(AbstractMsgFmtError):
    msg_fmt = _("An error occurred when extending volume %(volume_id)s")


class NoLicenseSRC(AbstractMsgFmtError):
    msg_fmt = _("Unable to deploy virtual machine '%(instance_name)s' "
                "because the host does not support the operating system "
                "installed on this image")


class UnSupportedOSVersion(AbstractMsgFmtError):
    msg_fmt = _("Unable to deploy virtual machine '%(instance_name)s' "
                "because the host does not support the operating system"
                "version installed on this image")


class LUADiscoveryFailed(AbstractMsgFmtError):
    msg_fmt = _("Failed to discover the volume error code %(status)s")


class LUADiscoveryITLError(AbstractMsgFmtError):
    msg_fmt = _("LUA Discovery Completed with few ITL Error:"
                "Device %(dev)s Discovered, Status: %(status)s"
                "Reason: %(msg)s")


class VMPowerOffFailure(AbstractMsgFmtError):
    msg_fmt = _("Failed to power off Virtual Machine %(lpar_nm)s: %(reason)s")


class VMPowerOnFailure(AbstractMsgFmtError):
    msg_fmt = _("Failed to power on Virtual Machine %(lpar_nm)s: %(reason)s")


class PvidOfNetworkBridgeError(AbstractMsgFmtError):
    msg_fmt = _("Unable to remove VLAN %(vlan_id)d as it is the Primary VLAN "
                "Identifier on a different Network Bridge.")


class DuplicateLUNameError(AbstractMsgFmtError):
    msg_fmt = _("A Logical Unit with name %(lu_name)s already exists on "
                "Shared Storage Pool %(ssp_name)s.")


class LUNotFoundError(AbstractMsgFmtError):
    msg_fmt = _("Could not find Logical Unit %(lu_label)s in Shared Storage "
                "Pool %(ssp_name)s.")


class BackingLUNotFoundError(AbstractMsgFmtError):
    msg_fmt = _("Could not find backing Image LU for Disk LU %(lu_name)s in "
                "Shared Storage Pool %(ssp_name)s")


class UnableToFindFCPortMap(AbstractMsgFmtError):
    msg_fmt = _("Unable to find a physical port to map a virtual Fibre "
                "Channel port to.  This is due to either a Virtual I/O "
                "Server being unavailable, or improper port specification "
                "for the physical Fibre Channel ports.")
