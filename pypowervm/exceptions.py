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


class VMPowerOffFailure(AbstractMsgFmtError):
    msg_fmt = _("Failed to power off Virtual Machine %(lpar_nm)s: %(reason)s")


class VMPowerOnFailure(AbstractMsgFmtError):
    msg_fmt = _("Failed to power on Virtual Machine %(lpar_nm)s: %(reason)s")


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


class MultipleExceptionsInFeedTask(Exception):
    """Exception containing tracebacks in WrappedFailure exceptions.

    Exception raised when a pypowervm.utils.transaction.FeedTask run raises a
    tasflow.exceptions.WrappedFailure containing more than one exception.  The
    message string is a concatenation of the tracebacks of the wrapped
    exceptions.
    """
    pass
