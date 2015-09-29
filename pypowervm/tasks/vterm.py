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

import logging
import select
import socket
import subprocess
import threading
import time

import pypowervm.const as c
from pypowervm import exceptions as pvm_exc
from pypowervm.i18n import _
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as pvm_lpar

LOG = logging.getLogger(__name__)

_SUFFIX_PARM_CLOSE_VTERM = 'CloseVterm'

# Used to track the VNC Repeaters
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
    subprocess.check_output(['rmvterm', '--id', lpar_id])

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
    std_out = subprocess.check_output(cmd)

    # The first line of the std_out should be the VNC port
    return int(std_out.splitlines()[0])


def open_remotable_vnc_vterm(
        adapter, lpar_uuid, local_ip, validation_string=None, remote_ip=None):
    """Opens a VNC vTerm to a given LPAR.  Wraps in some validation.

    Must run on the management partition.

    :param adapter: The adapter to drive the PowerVM API
    :param lpar_uuid: Partition UUID.
    :param local_ip: The IP Address to bind the VNC server to.  This would be
                     the IP of the management network on the system.
    :param validation_string: (Optional, Default: None) A special string that
                              can be used to validate the beginning of the VNC
                              request.  The first bytes passed in on the VNC
                              socket would have to equal this validation_string
                              in order to allow a connection.
                              NOTE: This is clear text.  It is not a password,
                              nor should it be.  This is just to help solidify
                              that only certain clients are allowed through.
    :param remote_ip: (Optional, Default: None) A binding to only accept
                      clients that are from a specific IP address through.
                      Default is None, and therefore will allow any remote
                      IP to connect.
    :return: The VNC Port that the terminal is running on.
    """
    # This API can only run if local.
    if not adapter.traits.local_api:
        raise pvm_exc.ConsoleNotLocal()

    # Open the VNC Port.  If already open, it will just return the same port,
    # so no harm re-opening.
    vnc_port = open_localhost_vnc_vterm(adapter, lpar_uuid)

    # See if we have a VNC repeater already...if so, nothing to do.  If not,
    # start it up.
    global _LOCAL_VNC_SERVERS, _LOCAL_VNC_UUID_TO_PORT
    if _LOCAL_VNC_SERVERS.get(vnc_port) is None:
        repeater = _VNCRepeaterServer(lpar_uuid, local_ip, vnc_port,
                                      validation_string=validation_string)
        repeater.start()
        _LOCAL_VNC_SERVERS[vnc_port] = repeater
        _LOCAL_VNC_UUID_TO_PORT[lpar_uuid] = vnc_port


def _get_lpar_id(adapter, lpar_uuid):
    lpar_resp = adapter.read(pvm_lpar.LPAR.schema_type, root_id=lpar_uuid,
                             suffix_type='quick', suffix_parm='PartitionID')
    return lpar_resp.body


class _VNCRepeaterServer(threading.Thread):

    def __init__(self, lpar_uuid, local_ip, port, validation_string=None):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((local_ip, port))
        self.server.listen(10)

        self.lpar_uuid = lpar_uuid
        self.port = port
        self.validation_string = validation_string

        self.alive = True

    def stop(self):
        # This will stop listening for all clients
        self.alive = False

        # Remove ourselves from the VNC listeners.
        global _LOCAL_VNC_SERVERS, _LOCAL_VNC_UUID_TO_PORT
        if _LOCAL_VNC_SERVERS.get(self.port) is not None:
            del _LOCAL_VNC_SERVERS[self.port]
        if _LOCAL_VNC_UUID_TO_PORT.get(self.lpar_uuid) is not None:
            del _LOCAL_VNC_UUID_TO_PORT[self.lpar_uuid]

    def run(self):
        input_list = [self.server]
        peers = {}
        while self.alive:
            time.sleep(.0001)

            # The select will determine which inputs (and outputs/excepts)
            # have input waiting for them.
            # The input_list consists of:
            # - The main server, accepting new requests
            # - N pairs of inputs.  Each pair is an independent entry...
            # --- Side 1 is client vnc to localhost vnc
            # --- Side 2 is localhost vnc to client vnc
            # --- They are a pair of inputs, such that whenever they receive
            #     input, they send to their peers output.
            s_inputs, s_outputs, s_excepts = select.select(input_list, [], [])

            for s_input in s_inputs:
                # If the input is the server, then we have a new client
                # requesting access.
                if s_input is self.server:
                    self._new_client(input_list, peers)
                    continue

                # At this point, we need to read the data.  We know that data
                # is ready.  However, if that data that is ready is length
                # 0, then we know that its ready to close this.
                data = s_input.recv(4096)
                if len(data) == 0:
                    self._close_client(s_input, input_list, peers)

                    # Note that we have to break here.  We do that because the
                    # input_list has changed with the close.  So its peer
                    # is no longer valid.
                    # The remaining inputs will just be picked up on the next
                    # pass, so nothing to worry about.
                    break

                # Just process the data.
                peers[s_input].send(data)

        # At this point, force a close on all remaining inputs.
        input_list.remove(self.server)
        for remaining_input in input_list:
            remaining_input.close()
        self.server.close()

    def _new_client(self, input_list, peers):
        # Get the forwarder.  This will be the socket we read FROM the
        # localhost.
        fwd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fwd.connect(('127.0.0.1', self.port))

        # This is the socket FROM the client side
        client_socket, client_addr = self.server.accept()

        # Add both sockets to the input list.  This ensures that they will be
        # selected upon.
        input_list.extend([fwd, client_socket])

        # Set them up as peers in the dictionary
        peers[fwd], peers[client_socket] = client_socket, fwd

    def _close_client(self, s_input, input_list, peers):
        peer = peers[s_input]

        # Remove the two from the input list
        input_list.remove(peer)
        input_list.remove(s_input)

        # Close the sockets
        peer.close()
        input.close()

        # And remove from the peer list, so that we've removed all pointers to
        # them
        del peers[peer]
        del peers[s_input]
