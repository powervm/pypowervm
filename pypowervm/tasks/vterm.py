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

"""Manage LPAR virtual terminals."""

import select
import socket
import subprocess
import threading

from oslo_currency import lockutils as lock
from oslo_log import log as logging

import pypowervm.const as c
from pypowervm import exceptions as pvm_exc
from pypowervm.i18n import _
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as pvm_lpar

LOG = logging.getLogger(__name__)

_SUFFIX_PARM_CLOSE_VTERM = 'CloseVterm'

# Used to track the VNC Repeaters.  These are global variables used below.
# Since they are defined up here, need to use global as a way for modification
# of the fields to stick.  We do this so that we keep track of all of the
# connections.
_LOCAL_VNC_SERVERS = {}
_LOCAL_VNC_UUID_TO_PORT = {}


def close_vterm(adapter, lpar_uuid):
    """Close the vterm associated with an lpar

    :param adapter: The adapter to talk over the API.
    :param lpar_uuid: partition uuid

    """
    if adapter.traits.local_api:
        _close_vterm_local(adapter, lpar_uuid)
    else:
        _close_vterm_non_local(adapter, lpar_uuid)


def _close_vterm_non_local(adapter, lpar_uuid):
    """Job to force the close of the terminal when the API is remote.

    :param adapter: The adapter to talk over the API.
    :param lpar_uuid: partition uuid
    """
    # Close vterm on the lpar
    resp = adapter.read(pvm_lpar.LPAR.schema_type, lpar_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=_SUFFIX_PARM_CLOSE_VTERM)
    job_wrapper = job.Job.wrap(resp.entry)

    try:
        job_wrapper.run_job(lpar_uuid)
    except Exception:
        LOG.exception(_('Unable to close vterm.'))
        raise


def _close_vterm_local(adapter, lpar_uuid):
    """Forces the close of the terminal on a local system.

    Will check for a VNC server as well in case it was started via that
    mechanism.

    :param adapter: The adapter to talk over the API.
    :param lpar_uuid: partition uuid
    """
    lpar_id = _get_lpar_id(adapter, lpar_uuid)
    _run_proc(['rmvterm', '--id', lpar_id])

    # Stop the port.
    global _LOCAL_VNC_SERVERS, _LOCAL_VNC_UUID_TO_PORT
    vnc_port = _LOCAL_VNC_UUID_TO_PORT.get(lpar_uuid, 0)
    if _LOCAL_VNC_SERVERS.get(vnc_port) is not None:
        _LOCAL_VNC_SERVERS[vnc_port].stop()


def open_localhost_vnc_vterm(adapter, lpar_uuid):
    """Opens a VNC vTerm to a given LPAR.  Always binds to localhost.

    :param adapter: The adapter to drive the PowerVM API
    :param lpar_uuid: Partition UUID.
    :return: The VNC Port that the terminal is running on.
    """
    # This API can only run if local.
    if not adapter.traits.local_api:
        raise pvm_exc.ConsoleNotLocal()

    lpar_id = _get_lpar_id(adapter, lpar_uuid)

    cmd = ['mkvterm', '--id', str(lpar_id), '--vnc', '--local']
    std_out, std_err = _run_proc(cmd)

    # The first line of the std_out should be the VNC port
    return int(std_out.splitlines()[0])


def open_remotable_vnc_vterm(
        adapter, lpar_uuid, local_ip, remote_ips=None, validation_check=None,
        validation_success=None, validation_fail=None):
    """Opens a VNC vTerm to a given LPAR.  Wraps in some validation.

    Must run on the management partition.

    :param adapter: The adapter to drive the PowerVM API
    :param lpar_uuid: Partition UUID.
    :param local_ip: The IP Address to bind the VNC server to.  This would be
                     the IP of the management network on the system.
    :param remote_ips: (Optional, Default: None) A binding to only accept
                       clients that are from a specific list of IP addresses
                       through. Default is None, and therefore will allow any
                       remote IP to connect.
    :param validation_check: (Optional, Default: None) A special string that
                             can be used to validate the beginning of the VNC
                             request.  The first bytes passed in on the VNC
                             socket would have to equal this validation_check
                             in order to allow a connection.

                             NOTE: This is clear text.  It is not a password,
                             nor should it be.  This is just to help solidify
                             that only certain clients are allowed through.

    :param validation_success: (Optional, Default: None) Should be specified
                               if the validation_check is.  Will be sent back
                               to the invoker if the validation check matches
                               when a request comes in.  No-op if
                               validation_check is not specified.

                               NOTE: This is clear text.  It is not a password,
                               nor should it be.  This is just to help
                               solidify that only certain clients are allowed
                               through.

    :param validation_fail: (Optional, Default: None) Should be specified if
                            the validation_check is.  Will be sent back to the
                            invoker if the validation check does not match.
                            The socket will also be closed.  No-op if
                            validation_check is not specified.

                            NOTE: This is clear text.  It is not a password,
                            nor should it be.  This is just to help solidify
                            that only certain clients are allowed through.

    :return: The VNC Port that the terminal is running on.
    """
    # This API can only run if local.
    if not adapter.traits.local_api:
        raise pvm_exc.ConsoleNotLocal()

    # Open the VNC Port.  If already open, it will just return the same port,
    # so no harm re-opening.  The stdout will just print out the existing port.
    vnc_port = open_localhost_vnc_vterm(adapter, lpar_uuid)

    # See if we have a VNC repeater already...if so, nothing to do.  If not,
    # start it up.
    global _LOCAL_VNC_SERVERS, _LOCAL_VNC_UUID_TO_PORT
    if _LOCAL_VNC_SERVERS.get(vnc_port) is None:
        repeater = _VNCRepeaterServer(
            lpar_uuid, local_ip, vnc_port, remote_ips=remote_ips,
            validation_check=validation_check, validation_fail=validation_fail,
            validation_success=validation_success)
        _LOCAL_VNC_SERVERS[vnc_port] = repeater
        _LOCAL_VNC_UUID_TO_PORT[lpar_uuid] = vnc_port

        @lock.synchronized('powervm_vnc_term')
        def start_repeater():
            repeater.start()

        start_repeater()

    return vnc_port


def _run_proc(cmd):
    """Simple wrapper to run a process.

    Will return the stdout and stderr.  Does not look at output code, as it is
    typical that mkvterm can return a non-zero error code to indicate partial
    success.

    This is why check_output does not suffice.

    :return: The stdout and stderr from the command.
    """
    process = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               close_fds=True, env=None)
    process.wait()
    stdout, stderr = process.communicate()
    return stdout, stderr


def _get_lpar_id(adapter, lpar_uuid):
    lpar_resp = adapter.read(pvm_lpar.LPAR.schema_type, root_id=lpar_uuid,
                             suffix_type='quick', suffix_parm='PartitionID')
    return lpar_resp.body


class _VNCRepeaterServer(threading.Thread):
    """Repeats a VNC connection from localhost to a given client.

    This is useful because it provides an additional layer of validation that
    the correct client will consume the connection.  This can be done with
    a restricted list of source IPs, or via validation string checks.

    The validation string requires that a client first sent a given message
    (before jumping to VNC negotiation).  If the validation_check string
    matches, the repeater will pass on the validation_success message.  If it
    does not match, the validation_fail message will be sent and the port will
    be closed.

    This is a very light weight thread, only one is needed per PowerVM LPAR.
    """

    def __init__(self, lpar_uuid, local_ip, port, remote_ips=None,
                 validation_check=None, validation_success=None,
                 validation_fail=None):
        """
        Creates the repeater.

        :param lpar_uuid: Partition UUID.
        :param local_ip: The IP Address to bind the VNC server to.  This would
                         be the IP of the management network on the system.
        :param remote_ips: (Optional, Default: None) A binding to only accept
                           clients that are from a specific list of IP
                           addresses through. Default is None, and therefore
                           will allow any remote IP to connect.
        :param validation_check: (Optional, Default: None) A special string
                                 that can be used to validate the beginning of
                                 the VNC request.  The first bytes passed in on
                                 the VNC socket would have to equal this
                                 validation_check in order to allow a
                                 connection.
                                 NOTE: This is clear text.  It is not a
                                 password, nor should it be.  This is just to
                                 help solidify that only certain clients are
                                 allowed through.
        :param validation_success: (Optional, Default: None) Should be
                                   specified if the validation_check is.  Will
                                   be sent back to the invoker if the
                                   validation check matches when a request
                                   comes in.  No-op if validation_check is not
                                   specified.
        :param validation_fail: (Optional, Default: None) Should be specified
                                if the validation_check is.  Will be sent back
                                to the invoker if the validation check does not
                                match. The socket will also be closed.  No-op
                                if validation_check is not specified.
        """
        super(_VNCRepeaterServer, self).__init__()

        self.lpar_uuid = lpar_uuid
        self.local_ip = local_ip
        self.port = port
        self.validation_check = validation_check
        self.validation_success = validation_success
        self.validation_fail = validation_fail
        self.remote_ips = remote_ips

        self.alive = True

    @lock.synchronized('powervm_vnc_term')
    def stop(self):
        """Stops the repeater from running."""
        # This will stop listening for all clients
        self.alive = False

        # Remove ourselves from the VNC listeners.
        global _LOCAL_VNC_SERVERS, _LOCAL_VNC_UUID_TO_PORT
        if _LOCAL_VNC_SERVERS.get(self.port) is not None:
            del _LOCAL_VNC_SERVERS[self.port]
        if _LOCAL_VNC_UUID_TO_PORT.get(self.lpar_uuid) is not None:
            del _LOCAL_VNC_UUID_TO_PORT[self.lpar_uuid]

    def run(self):
        """Used by the thread to run the repeater."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.local_ip, self.port))
        server.listen(10)

        # The list of peers keeps track of the client and the server.  This
        # is a 1 to 1 mapping between sockets.  As the localhost receives data
        # it gets sent to its peer (the client).  As the client receives data
        # it gets sent to its peer (the localhost).
        peers = {}

        while self.alive:
            # The select will determine which inputs (and outputs/excepts)
            # have input waiting for them.
            # The input_list consists of:
            # - The main server, accepting new requests
            # - N pairs of inputs.  Each pair is an independent entry...
            # --- Side 1 is client vnc to localhost vnc
            # --- Side 2 is localhost vnc to client vnc
            # --- They are a pair of inputs, such that whenever they receive
            #     input, they send to their peer's output.
            input_list = peers.keys() + [server]
            s_inputs, s_outputs, s_excepts = select.select(
                input_list, [], [], .05)

            for s_input in s_inputs:
                # If the input is the server, then we have a new client
                # requesting access.
                if s_input == server:
                    # If a new client, then just skip back to start.  Note
                    # that if new_client fails, nothing is added to the
                    # s_inputs list.  So no harm in case of failure.
                    self._new_client(server, peers)
                    continue

                # At this point, we need to read the data.  We know that data
                # is ready.  However, if that data that is ready is length
                # 0, then we know that we're ready to close this.
                data = s_input.recv(4096)
                if len(data) == 0:
                    self._close_client(s_input, peers)

                    # Note that we have to break here.  We do that because the
                    # peer dictionary has changed with the close.  So the list
                    # to iterate over should be re-evaluated.
                    # The remaining inputs will just be picked up on the next
                    # pass, so nothing to worry about.
                    break

                # Just process the data.
                peers[s_input].send(data)

        # At this point, force a close on all remaining inputs.
        for input_socket in peers.keys():
            input_socket.close()
        server.close()

    def _new_client(self, server, peers):
        """Listens for a new client.

        :param server: The server socket.
        :param peers: The peer dictionary.  Will map the new client to the new
                      forwarding port.
        """
        # This is the socket FROM the client side.  client_addr is a tuple
        # of format ('1.2.3.4', '5678') - ip and port.
        client_socket, client_addr = server.accept()

        # If only select IPs are allowed through, validate
        if self.remote_ips is not None:
            if client_addr[0] not in self.remote_ips:
                # Close the connection, exit.
                client_socket.close()
                return

        # If the client socket has a validation string.
        if self.validation_check is not None:
            # Check to ensure that there is output waiting.
            c_input, c_output, c_exc = select.select(
                [client_socket], [], [], 1)

            # If no input, then just assume a close.  We waited a second.
            if not c_input:
                client_socket.sendall(self.validation_fail)
                client_socket.close()
                return

            # We know we had data waiting.  Receive (at max) the validation
            # check string.  All data after this validation string is the
            # actual VNC data.
            data = client_socket.recv(len(self.validation_check))
            if data == self.validation_check:
                # Send back the success message.
                client_socket.sendall(self.validation_success)
            else:
                # Was not a success, exit.
                client_socket.sendall(self.validation_fail)
                client_socket.close()
                return

        # Get the forwarder.  This will be the socket we read FROM the
        # localhost.  When this receives data, it will be sent to the client
        # socket.
        fwd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fwd.connect(('127.0.0.1', self.port))

        # Set them up as peers in the dictionary.  They will now be considered
        # as input sources.
        peers[fwd], peers[client_socket] = client_socket, fwd

    def _close_client(self, s_input, peers):
        """Closes down a client.

        :param s_input: The socket that has received a clost.
        :param peers: The dictionary that maps the clients and the forwarding
                      sockets to each other.
        """
        # Close the sockets
        peer = peers[s_input]
        peer.close()
        s_input.close()

        # And remove from the peer list, so that we've removed all pointers to
        # them
        del peers[peer]
        del peers[s_input]
