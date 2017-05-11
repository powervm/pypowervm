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

"""Module-specific error/exception subclasses."""

import abc
from lxml import etree
import six

from pypowervm import const as c
from pypowervm import entities as ent
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

    def __init__(self, resp):
        """Initializes HttpError with required `response` object.

        1) Constructs the exception message based on the contents of the
        response parameter.

        2) If possible, initializes a 'her_wrap' member which is a
        pypowervm.wrappers.http_error.HttpError - an EntryWrapper for the
        <HttpErrorResponse/> payload.  Consumers should check this member for
        None before using.

        :param resp: pypowervm.adapter.Response containing an
                     <HttpErrorResponse/> response from the REST server.
        """
        self.her_wrap = None
        reason = resp.reason
        # Attempt to extract PowerVM API's HttpErrorResponse object.
        # Since this is an exception path, we use best effort only - don't want
        # problems here to obscure the real exception.
        try:
            root = etree.fromstring(resp.body)
            if root is not None and root.tag == str(etree.QName(c.ATOM_NS,
                                                                'entry')):
                resp.entry = ent.Entry.unmarshal_atom_entry(root, resp)
                # Import inline to avoid circular dependencies
                import pypowervm.wrappers.http_error as he
                self.her_wrap = he.HttpError.wrap(resp)

                # Add the message to the reason if it is available.
                if self.her_wrap.message:
                    reason += ' -- ' + self.her_wrap.message
        except Exception:
            pass
        # Construct the exception message
        msg = ('HTTP error %(status)s for method %(method)s on path '
               '%(path)s: %(reason)s') % dict(status=resp.status,
                                              method=resp.reqmethod,
                                              path=resp.reqpath,
                                              reason=reason)
        # Initialize the exception
        super(HttpError, self).__init__(msg, response=resp)


class HttpNotFound(HttpError):
    """HttpError subclass where response.status == c.HTTPStatus.NOT_FOUND."""
    pass


class HttpUnauth(HttpError):
    """HttpError where response.status == c.HTTPStatus.UNAUTHORIZED."""
    pass


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


class UnableToDerivePhysicalPortForNPIV(AbstractMsgFmtError):
    msg_fmt = _("Unable to derive the appropriate physical FC port for WWPN "
                "%(wwpn)s.  The VIOS Extended Attribute Groups may have been "
                "insufficient.  The VIOS URI for the query was %(vio_uri)s.")


class NotFound(AbstractMsgFmtError):
    msg_fmt = _('Element not found: %(element_type)s %(element)s')


class LPARNotFound(AbstractMsgFmtError):
    msg_fmt = _('LPAR not found: %(lpar_name)s')


class JobRequestFailed(AbstractMsgFmtError):
    msg_fmt = _("The '%(operation_name)s' operation failed. %(error)s")


class JobRequestTimedOut(JobRequestFailed):
    msg_fmt = _("The '%(operation_name)s' operation failed. "
                "Failed to complete the task in %(seconds)d seconds.")


class OSShutdownNoRMC(AbstractMsgFmtError):
    msg_fmt = _("Can not perform OS shutdown on Virtual Machine %(lpar_nm)s "
                "because its RMC connection is not active.")


class VMPowerOffFailure(AbstractMsgFmtError):
    msg_fmt = _("Failed to power off Virtual Machine %(lpar_nm)s: %(reason)s")


class VMPowerOffTimeout(VMPowerOffFailure):
    msg_fmt = _("Power off of Virtual Machine %(lpar_nm)s timed out after "
                "%(timeout)d seconds.")


class VMPowerOnFailure(AbstractMsgFmtError):
    msg_fmt = _("Failed to power on Virtual Machine %(lpar_nm)s: %(reason)s")


class VMPowerOnTimeout(VMPowerOnFailure):
    msg_fmt = _("Power on of Virtual Machine %(lpar_nm)s timed out after "
                "%(timeout)d seconds.")


class PvidOfNetworkBridgeError(AbstractMsgFmtError):
    msg_fmt = _("Unable to remove VLAN %(vlan_id)d as it is the Primary VLAN "
                "Identifier on a different Network Bridge.")


class OrphanVLANFoundOnProvision(AbstractMsgFmtError):
    msg_fmt = _("Unable to provision VLAN %(vlan_id)d.  It appears to be "
                "contained on device '%(dev_name)s' on Virtual I/O Server "
                "%(vios)s.  That device is not connected to any Network "
                "Bridge (Shared Ethernet Adapter).  Please manually remove "
                "the device or add it to the Network Bridge before "
                "continuing.")


class DuplicateLUNameError(AbstractMsgFmtError):
    msg_fmt = _("A Logical Unit with name %(lu_name)s already exists on "
                "Shared Storage Pool %(ssp_name)s.")


class UnableToFindFCPortMap(AbstractMsgFmtError):
    msg_fmt = _("Unable to find a physical port to map a virtual Fibre "
                "Channel port to.  This is due to either a Virtual I/O "
                "Server being unavailable, or improper port specification "
                "for the physical Fibre Channel ports.")


class ConsoleNotLocal(AbstractMsgFmtError):
    msg_fmt = _("Unable to start the console to the Virtual Machine.  The "
                "pypowervm API is running in a non-local mode.  The console "
                "can only be deployed when pypowervm is co-located with "
                "the PowerVM API.")


class WrapperTaskNoSubtasks(AbstractMsgFmtError):
    msg_fmt = _("WrapperTask %(name)s has no subtasks!")


class FeedTaskEmptyFeed(AbstractMsgFmtError):
    msg_fmt = _("FeedTask can't have an empty feed.")


class AuthFileReadError(AbstractMsgFmtError):
    msg_fmt = _("OS denied access to file %(access_file)s.")


class AuthFileAccessError(AbstractMsgFmtError):
    msg_fmt = _("OS encountered an I/O error attempting to read file "
                "%(access_file)s: %(error)s")


class MigrationFailed(AbstractMsgFmtError):
    msg_fmt = _("The migration task failed. %(error)s")


class IBMiLoadSourceNotFound(AbstractMsgFmtError):
    msg_fmt = _("No load source found for VM %(vm_name)s")


class UnableToBuildPG83EncodingMissingParent(AbstractMsgFmtError):
    msg_fmt = _("Unable to derive the pg83 encoding for hdisk %(dev_name)s.  "
                "The parent_entry attribute is not set.  This may be due to "
                "using a PV obtained through an unsupported property chain.  "
                "The PV must be accessed via VIOS.phys_vols, VG.phys_vols, or "
                "VIOS.scsi_mappings[n].backing_storage.")


class FoundDevMultipleTimes(AbstractMsgFmtError):
    msg_fmt = _("Found device %(devname)s %(count)d times; expected to find "
                "it at most once.")


class MultipleExceptionsInFeedTask(AbstractMsgFmtError):
    """Exception concatenating messages in WrappedFailure exceptions.

    Exception raised when a pypowervm.utils.transaction.FeedTask run raises a
    tasflow.exceptions.WrappedFailure containing more than one exception.  The
    message string is a concatenation of the message strings of the wrapped
    exceptions.
    """
    def __init__(self, ft_name, wrapped_failure):
        # In case the caller wants to trap this and get at the WrappedFailure
        self.wrapped_failure = wrapped_failure
        self.msg_fmt = _("FeedTask %(ft_name)s experienced multiple "
                         "exceptions:\n\t%(concat_msgs)s")
        concat_msgs = '\n\t'.join([fail.exception_str
                                   for fail in wrapped_failure])
        super(MultipleExceptionsInFeedTask, self).__init__(
            response=None, ft_name=ft_name, concat_msgs=concat_msgs)


class ManagementPartitionNotFoundException(AbstractMsgFmtError):
    """Couldn't find exactly one management partition on the system."""
    msg_fmt = _("Expected to find exactly one management partition; found "
                "%(count)d.")


class ThisPartitionNotFoundException(AbstractMsgFmtError):
    """Couldn't find exactly one partition with the local VM's short ID."""
    msg_fmt = _("Expected to find exactly one partition with ID %(lpar_id)d; "
                "found %(count)d.")


class NoDefaultTierFoundOnSSP(AbstractMsgFmtError):
    """Looked for a default Tier on the SSP, but didn't find it."""
    msg_fmt = _("Couldn't find the default Tier on Shared Storage Pool "
                "%(ssp_name)s.")


class InvalidHostForRebuild(AbstractMsgFmtError):
    pass


class InvalidHostForRebuildNoVIOSForUDID(InvalidHostForRebuild):
    msg_fmt = _("The device with UDID %(udid)s was not found on any of the "
                "Virtual I/O Servers.")


class InvalidHostForRebuildNotEnoughVIOS(InvalidHostForRebuild):
    msg_fmt = _("There are not enough Virtual I/O Servers to support the "
                "virtual machine's device with UDID %(udid)s.")


class InvalidHostForRebuildFabricsNotFound(InvalidHostForRebuild):
    msg_fmt = _("The expected fabrics (%(fabrics)s) were not found on any of "
                "the Virtual I/O Servers.")


class InvalidHostForRebuildInvalidIOType(InvalidHostForRebuild):
    msg_fmt = _("Can not rebuild the virtual machine.  It is using an I/O "
                "type of %(io_type)s which is not supported for VM rebuild.")


class InvalidHostForRebuildSlotMismatch(InvalidHostForRebuild):
    msg_fmt = _("The number of VFC slots on the target system "
                "(%(rebuild_slots)d) does not match the number of slots on "
                "the client system (%(original_slots)d).  Unable to rebuild "
                "this virtual machine on this system.")


class InvalidVirtualNetworkDeviceType(AbstractMsgFmtError):
    msg_fmt = _("To register the slot information of the network device a "
                "CNA or VNIC adapter is needed. Instead the following "
                "was given: %(wrapper)s.")


class NotEnoughActiveVioses(AbstractMsgFmtError):
    msg_fmt = _("There are not enough active Virtual I/O Servers available. "
                "Expected %(exp)d; found %(act)d.")


class ViosNotAvailable(AbstractMsgFmtError):
    msg_fmt = _("No Virtual I/O Servers are available.  Attempted to wait for "
                "a VIOS to become active for %(wait_time)d seconds.  Please "
                "check the RMC connectivity between the PowerVM NovaLink and "
                "the Virtual I/O Servers.")


class NoRunningSharedSriovAdapters(AbstractMsgFmtError):
    # sriov_loc_mode_state should be a string comprising one SRIOV adapter per
    # line, each line comprising the physical location code, the mode, and the
    # state, separated by ' | '.
    msg_fmt = _("Could not find any SR-IOV adapters in Sriov mode and Running "
                "state.\nLocation | Mode | State\n%(sriov_loc_mode_state)s")


class InsufficientSRIOVCapacity(AbstractMsgFmtError):
    msg_fmt = _("Unable to fulfill redundancy requirement of %(red)d.  Found "
                "%(found_vfs)d viable backing device(s).")


class SystemNotVNICCapable(AbstractMsgFmtError):
    msg_fmt = _("The Managed System is not vNIC capable.")


class NoVNICCapableVIOSes(AbstractMsgFmtError):
    msg_fmt = _("There are no active vNIC-capable VIOSes.")


class VNICFailoverNotSupportedSys(AbstractMsgFmtError):
    msg_fmt = _("A redundancy of %(red)d was specified, but the Managed "
                "System is not vNIC failover capable.")


class VNICFailoverNotSupportedVIOS(AbstractMsgFmtError):
    msg_fmt = _("A redundancy of %(red)d was specified, but there are no "
                "active vNIC failover-capable VIOSes.")


class NoMediaRepoVolumeGroupFound(AbstractMsgFmtError):
    msg_fmt = _("Unable to locate the volume group %(vol_grp)s to store the "
                "virtual optical media within.  Unable to create the "
                "media repository.")


class CantUpdatePPortsInUse(AbstractMsgFmtError):
    msg_fmt = _("The ManagedSystem update was not attempted because changes "
                "were requested to one or more SR-IOV physical ports which "
                "are in use by vNICs.\n%(warnings)s")


class VNCBasedTerminalFailedToOpen(AbstractMsgFmtError):
    msg_fmt = _("Unable to create VNC based virtual terminal: %(err)s")


class CacheNotSupportedException(AbstractMsgFmtError):
    msg_fmt = _("The Adapter cache is not supported.")


class InvalidEnumValue(AbstractMsgFmtError):
    msg_fmt = _("Invalid value '%(value)s' for '%(enum)s'.  Valid values are: "
                "%(valid_values)s")


class VIOSNotFound(AbstractMsgFmtError):
    msg_fmt = _("No VIOS found with name %(vios_name)s.")


class VGNotFound(AbstractMsgFmtError):
    msg_fmt = _("No volume group found with name %(vg_name)s.")


class PartitionIsNotIBMi(AbstractMsgFmtError):
    msg_fmt = _("Partition with name %(part_name)s is not an IBMi partition.")


class PanelFunctionRequiresPartition(AbstractMsgFmtError):
    msg_fmt = _("PanelJob function partition argument is empty.")


class InvalidIBMiPanelFunctionOperation(AbstractMsgFmtError):
    msg_fmt = _("Panel function operation %(op_name)s is invalid. "
                "One of %(valid_ops)s expected.")


class ISCSIDiscoveryFailed(AbstractMsgFmtError):
    msg_fmt = _("ISCSI discovery failed for VIOS %(vios_uuid)s. "
                "Return code: %(status)s")


class ISCSILogoutFailed(AbstractMsgFmtError):
    msg_fmt = _("ISCSI Logout failed for VIOS %(vios_uuid)s. "
                "Return code: %(status)s")
