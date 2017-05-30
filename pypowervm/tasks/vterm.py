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

import re
import select
import six
import socket
import ssl
import struct
import subprocess
import threading
import time

from oslo_concurrency import lockutils as lock
from oslo_log import log as logging
from oslo_utils import encodeutils

import pypowervm.const as c
from pypowervm import exceptions as pvm_exc
from pypowervm.i18n import _
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as pvm_lpar

LOG = logging.getLogger(__name__)

_SUFFIX_PARM_CLOSE_VTERM = 'CloseVterm'

# Used to track of the mapping between the ports and the Listeners/Repeaters
# that we construct for those and also keeping track of which local port
# is for a given LPAR UUID and want VNC Path String is provided for the LPAR.
#
# These are global variables used below. Since they are defined up here, need
# to use global as a way for modification of the fields to stick.  We do this
# so that we keep track of all of the connections.
_VNC_REMOTE_PORT_TO_LISTENER = {}
_VNC_LOCAL_PORT_TO_REPEATER = {}
_VNC_UUID_TO_LOCAL_PORT = {}
_VNC_PATH_TO_UUID = {}
# For the single remote port case, we will hard-code that to 5901 for now
_REMOTE_PORT = 5901


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
    with lock.lock('powervm_vnc_term'):
        vnc_port = _VNC_UUID_TO_LOCAL_PORT.get(lpar_uuid, 0)
        if vnc_port in _VNC_LOCAL_PORT_TO_REPEATER:
            _VNC_LOCAL_PORT_TO_REPEATER[vnc_port].stop()


def open_localhost_vnc_vterm(adapter, lpar_uuid, force=False):
    """Opens a VNC vTerm to a given LPAR.  Always binds to localhost.

    :param adapter: The adapter to drive the PowerVM API
    :param lpar_uuid: Partition UUID.
    :param force: (Optional, Default: False) If set to true will force the
                  console to be opened as VNC even if it is already opened
                  via some other means.
    :return: The VNC Port that the terminal is running on.
    """
    # This API can only run if local.
    if not adapter.traits.local_api:
        raise pvm_exc.ConsoleNotLocal()

    lpar_id = _get_lpar_id(adapter, lpar_uuid)

    def _run_mkvterm_cmd(lpar_uuid, force):
        cmd = ['mkvterm', '--id', str(lpar_id), '--vnc', '--local']
        ret_code, std_out, std_err = _run_proc(cmd)

        # If the vterm was already started, the mkvterm command will always
        # return an error message with a return code of 3.  However, there
        # are 2 scenarios here, one where it was started with the VNC option
        # previously, which we will get a valid port number back (which is
        # the good path scenario), and one where it was started out-of-band
        # where we will get no port.  If it is the out-of-band scenario and
        # they asked us to force the connection, then we will attempt to
        # terminate the old vterm session so we can start up one with VNC.
        if force and ret_code == 3 and not _parse_vnc_port(std_out):
            LOG.warning(_("Invalid output on vterm open.  Trying to reset the "
                          "vterm.  Error was %s"), std_err)
            close_vterm(adapter, lpar_uuid)
            ret_code, std_out, std_err = _run_proc(cmd)

        # The only error message that is fine is a return code of 3 that a
        # session is already started, where we got back the port back meaning
        # that it was started as VNC.  Else, raise up the error message.
        if ret_code != 0 and not (ret_code == 3 and _parse_vnc_port(std_out)):
            raise pvm_exc.VNCBasedTerminalFailedToOpen(err=std_err)

        # Parse the VNC Port out of the stdout returned from mkvterm
        return _parse_vnc_port(std_out)

    return _run_mkvterm_cmd(lpar_uuid, force)


def open_remotable_vnc_vterm(
        adapter, lpar_uuid, local_ip, remote_ips=None, vnc_path=None,
        use_x509_auth=False, ca_certs=None, server_cert=None, server_key=None,
        force=False):
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
    :param vnc_path: (Optional, Default: None) If provided, the vnc client must
                     pass in this path (in HTTP format) to connect to the
                     VNC server.

                     The path is in HTTP format.  So if the vnc_path is 'Test'
                     the first packet request into the VNC must be:
                     "CONNECT Test HTTP/1.1\r\n\r\n"

                     If the client passes in an invalid request, a 400 Bad
                     Request will be returned.  If the client sends in the
                     correct path a 200 OK will be returned.

                     If no vnc_path is specified, then no path is expected
                     to be passed in by the VNC client and it will listen
                     on the same remote port as local port.  If the path is
                     specified then it will listen on the on a single remote
                     port of 5901 and determine the LPAR based on this path.
    :param use_x509_auth: (Optional, Default: False) If enabled, uses X509
                          Authentication for the VNC sessions started for VMs.
    :param ca_certs: (Optional, Default: None) Path to CA certificate to
                     use for verifying VNC X509 Authentication.  Only used
                     if use_x509_auth is set to True.
    :param server_cert: (Optional, Default: None) Path to Server certificate
                        to use for verifying VNC X509 Authentication.  Only
                        used if use_x509_auth is set to True.
    :param server_key: (Optional, Default: None) Path to Server private key
                       to use for verifying VNC X509 Authentication.  Only
                       used if use_x509_auth is set to True.
    :param force: (Optional, Default: False) If set to true will force the
                  console to be opened as VNC even if it is already opened
                  via some other means.
    :return: The VNC Port that the terminal is running on.
    """
    # This API can only run if local.
    if not adapter.traits.local_api:
        raise pvm_exc.ConsoleNotLocal()

    # Open the VNC Port.  If already open, it will just return the same port,
    # so no harm re-opening.  The stdout will just print out the existing port.
    local_port = open_localhost_vnc_vterm(adapter, lpar_uuid, force=force)
    # If a VNC path is provided then we have a way to map an incoming
    # connection to a given LPAR and will use the single 5901 port, otherwise
    # we need to listen for remote connections on the same port as the local
    # one so we know which VNC session to forward the connection's data to
    remote_port = _REMOTE_PORT if vnc_path is not None else local_port
    _VNC_UUID_TO_LOCAL_PORT[lpar_uuid] = local_port

    # We will use a flag to the Socket Listener to tell it whether the
    # user provided us a VNC Path we should use to look up the UUID from
    if vnc_path is not None:
        verify_vnc_path = True
        _VNC_PATH_TO_UUID[vnc_path] = lpar_uuid
    else:
        verify_vnc_path = False

    # See if we have a VNC repeater already...if so, nothing to do.  If not,
    # start it up.
    with lock.lock('powervm_vnc_term'):
        if remote_port not in _VNC_REMOTE_PORT_TO_LISTENER:
            listener = _VNCSocketListener(
                adapter, remote_port, local_ip, verify_vnc_path,
                remote_ips=remote_ips)
            # If we are doing x509 Authentication, then setup the certificates
            if use_x509_auth:
                listener.set_x509_certificates(
                    ca_certs, server_cert, server_key)
            _VNC_REMOTE_PORT_TO_LISTENER[remote_port] = listener

            listener.start()

    return remote_port


def _run_proc(cmd):
    """Simple wrapper to run a process.

    Will return the return code along with the stdout and stderr.  It is the
    decision of the caller if it wishes to honor or ignore the return code.

    :return: The return code, stdout and stderr from the command.
    """
    process = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               close_fds=True, env=None)
    process.wait()
    stdout, stderr = process.communicate()
    # Convert the stdout/stderr output from a byte-string to a unicode-string
    # so it doesn't blow up later on anything doing an implicit conversion
    stdout = encodeutils.safe_decode(stdout)
    stderr = encodeutils.safe_decode(stderr)
    return process.returncode, stdout, stderr


def _get_lpar_id(adapter, lpar_uuid):
    lpar_resp = adapter.read(pvm_lpar.LPAR.schema_type, root_id=lpar_uuid,
                             suffix_type='quick', suffix_parm='PartitionID')
    return lpar_resp.body


def _parse_vnc_port(std_out):
    """Parse the VNC port number out of the standard output from mkvterm.

    :return:  The port number parsed otherwise None if no valid port
    """
    # The first line of the std_out should be the VNC port
    line = std_out.splitlines()[0] if std_out else None
    return int(line) if line and line.isdigit() else None


class _VNCSocketListener(threading.Thread):
    """Provides a listener bound to a remote-accessible port for VNC access.

    The VNC sessions set up by mkvterm only allow access from the localhost, so
    this listener provides an additional listener on a remote-accessible port
    to all incoming connections for VNC sessions.

    This listener may be setup by the caller in a way so that there is only a
    single remote port for all VNC sessions or that there is one port per VM.
    This listener will accept incoming connections, establish authentication of
    the requester (if x509 authentication is enabled), and will determine what
    LPAR UUID the request is for and establish connections to the local port
    and setup a repeater to forward the data between the two sides.
    """

    def __init__(self, adapter, remote_port, local_ip, verify_vnc_path,
                 remote_ips=None):
        """Creates the listener bound to a remote-accessible port.

        :param adapter: The pypowervm adapter
        :param remote_port: The port to bind to for remote connections.
        :param local_ip: The IP address to bind the VNC server to. This would
                         be the IP of the management network on the system.
        :param verify_vnc_path: Boolean to determine whether we verify the
                                vnc_path.
        :param remote_ips: (Optional, Default: None) A binding to only accept
                           clients that are from a specific list of IP
                           addresses through. Default is None, and therefore
                           will allow any remote IP to connect.
        """
        super(_VNCSocketListener, self).__init__()

        self.adapter = adapter
        self.remote_port = remote_port
        self.local_ip = local_ip
        self.verify_vnc_path = verify_vnc_path
        self.remote_ips = remote_ips
        self.x509_certs = None

        self.alive = True
        self.vnc_killer = None

    def set_x509_certificates(self, ca_certs=None,
                              server_cert=None, server_key=None):
        """Set the x509 Certificates to use for TLS authentication.

        :param ca_certs: (Optional, Default: None) Path to CA certificate to
                         use for verifying VNC X509 Authentication.
        :param server_cert: (Optional, Default: None) Path to Server cert
                            to use for verifying VNC X509 Authentication.
        :param server_key: (Optional, Default: None) Path to Server private key
                           to use for verifying VNC X509 Authentication.
        """
        self.x509_certs = dict(
            ca_certs=ca_certs, server_cert=server_cert, server_key=server_key)

    def stop(self):
        """Stops the listener from running."""
        # This will stop listening for all clients
        self.alive = False

        # Remove ourselves from the VNC listeners.
        if self.remote_port in _VNC_REMOTE_PORT_TO_LISTENER:
            del _VNC_REMOTE_PORT_TO_LISTENER[self.remote_port]

    def run(self):
        """Used by the thread to run the listener."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.local_ip, self.remote_port))
        LOG.info(_("VNCSocket Listener Listening on ip=%(ip)s port=%(port)s") %
                 {'ip': self.local_ip, 'port': self.remote_port})
        server.listen(10)

        while self.alive:
            # Listen on the server socket for incoming connections
            s_inputs = select.select([server], [], [], 1)[0]
            for s_input in s_inputs:
                # Establish a new client connection & repeater between the two
                self._new_client(s_input)
        server.close()

    def _new_client(self, server):
        """Listens for a new client.

        :param server: The server socket.
        """
        # This is the socket FROM the client side.  client_addr is a tuple
        # of format ('1.2.3.4', '5678') - ip and port.
        client_socket, client_addr = server.accept()
        LOG.debug("New Client socket accepted client_addr=%s" % client_addr[0])

        # If only select IPs are allowed through, validate
        if (self.remote_ips is not None and
                client_addr[0] not in self.remote_ips):
            # Close the connection, exit.
            client_socket.close()
            return

        # If they gave use a VNC Path to look for in the connection string
        # then we will do that now otherwise just skip over the header info
        if self.verify_vnc_path:
            # Check to ensure that there is output waiting.
            c_input = select.select([client_socket], [], [], 1)[0]

            # If no input, then just assume a close.  We waited a second.
            if not c_input:
                # Assume HTTP 1.1.  All clients should support.  We have no
                # input, so we don't know what protocol they would like.
                client_socket.sendall("HTTP/1.1 400 Bad Request\r\n\r\n")
                client_socket.close()
                return

            # We know we had data waiting.  Receive (at max) the vnc_path
            # string.  All data after this validation string is the
            # actual VNC data.
            lpar_uuid, http_code = self._check_http_connect(client_socket)
            if lpar_uuid:
                # Send back the success message.
                client_socket.sendall("HTTP/%s 200 OK\r\n\r\n" % http_code)
            else:
                # Was not a success, exit.
                client_socket.sendall("HTTP/%s 400 Bad Request\r\n\r\n" %
                                      http_code)
                client_socket.close()
                return
        # If we had no VNC Path to match against, then the local port is
        # going to be the same as the remote port and we need to figure
        # out what the LPAR UUID is for that given local port VNC session
        else:
            lpar_uuid = (k for k, v in _VNC_UUID_TO_LOCAL_PORT.items()
                         if v == self.remote_port).next()

        # Setup the forwarding socket to the local LinuxVNC session
        self._setup_forwarding_socket(lpar_uuid, client_socket)

    def _setup_forwarding_socket(self, lpar_uuid, client_socket):
        """Setup the forwarding socket to the local LinuxVNC session.

        :param lpar_uuid: The UUID of the lpar for which we are forwarding.
        :param client_socket:  The client-side socket to receive data from.
        """
        local_port = _VNC_UUID_TO_LOCAL_PORT.get(lpar_uuid)

        # If for some reason no mapping to a local port, then give up
        if local_port is None:
            client_socket.close()
        # Get the forwarder.  This will be the socket we read FROM the
        # localhost.  When this receives data, it will be sent to the client
        # socket.
        fwd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fwd.connect(('127.0.0.1', local_port))

        # If we were told to enable VeNCrypt using X509 Authentication, do so
        if self.x509_certs is not None:
            ssl_socket = self._enable_x509_authentication(client_socket, fwd)
            # If there was an error enabling SSL, then close the sockets
            if ssl_socket is None:
                client_socket.close()
                fwd.close()
                return
            client_socket = ssl_socket

        # See if we need to start up a new repeater for the given local port
        if local_port not in _VNC_LOCAL_PORT_TO_REPEATER:
            _VNC_LOCAL_PORT_TO_REPEATER[local_port] = _VNCRepeaterServer(
                self.adapter, lpar_uuid, local_port, client_socket, fwd)
            _VNC_LOCAL_PORT_TO_REPEATER[local_port].start()
        else:
            repeater = _VNC_LOCAL_PORT_TO_REPEATER[local_port]
            repeater.add_socket_connection_pair(client_socket, fwd)

    def _enable_x509_authentication(self, client_socket, server_socket):
        """Enables and Handshakes VeNCrypt using X509 Authentication.

        :param client_socket:  The client-side socket to receive data from.
        :param server_socket:  The server-side socket to forward data to.
        :return ssl_socket:  A client-side socket wrappered for SSL or None
                             if there is an error.
        """
        try:
            # First perform the RFB Version negotiation between client/server
            self._version_negotiation(client_socket, server_socket)
            # Next perform the Security Authentication Type Negotiation
            if not self._auth_type_negotiation(client_socket):
                return None
            # Next perform the Security Authentication SubType Negotiation
            if not self._auth_subtype_negotiation(client_socket):
                return None
            # Now that the VeNCrypt handshake is done, do the SSL wrapper
            ca_certs = self.x509_certs.get('ca_certs')
            server_key = self.x509_certs.get('server_key')
            server_cert = self.x509_certs.get('server_cert')
            return ssl.wrap_socket(
                client_socket, server_side=True, ca_certs=ca_certs,
                certfile=server_cert, keyfile=server_key,
                ssl_version=ssl.PROTOCOL_TLSv1_2, cert_reqs=ssl.CERT_REQUIRED)
        # If we got an error, log and handle to not take down the thread
        except Exception as exc:
            LOG.warning(_("Error negotiating SSL for VNC Repeater: %s") % exc)
            LOG.exception(exc)
            return None

    def _version_negotiation(self, client_socket, server_socket):
        """Performs the RFB Version negotiation between client/server.

        :param client_socket:  The client-side socket to receive data from.
        :param server_socket:  The server-side socket to forward data to.
        """
        # Do a pass-thru of the RFB Version negotiation up-front
        # The length of the version is 12, such as 'RFB 003.007\n'
        client_socket.sendall(self._socket_receive(server_socket, 12))
        server_socket.sendall(self._socket_receive(client_socket, 12))
        # Since we are doing our own additional authentication
        # just tell the server we are doing No Authentication (1) to it
        auth_size = self._socket_receive(server_socket, 1)
        self._socket_receive(server_socket, six.byte2int(auth_size))
        server_socket.sendall(six.int2byte(1))

    def _auth_type_negotiation(self, client_socket):
        """Performs the VeNCrypt Authentication Type Negotiation.

        :param client_socket:  The client-side socket to receive data from.
        :return success:  Boolean whether the handshake was successful.
        """
        # Do the VeNCrypt handshake next before establishing SSL
        # Say we only support VeNCrypt (19) authentication version 0.2
        client_socket.sendall(six.int2byte(1))
        client_socket.sendall(six.int2byte(19))
        client_socket.sendall("\x00\x02")
        authtype = self._socket_receive(client_socket, 1)
        # Make sure the Client supports the VeNCrypt (19) authentication
        if len(authtype) < 1 or six.byte2int(authtype) != 19:
            # Send a 1 telling the client the type wasn't accepted
            client_socket.sendall(six.int2byte(1))
            return False
        vers = self._socket_receive(client_socket, 2)
        # Make sure the Client supports at least version 0.2 of it
        if ((len(vers) < 2 or six.byte2int(vers) != 0
             or six.byte2int(vers[1:]) < 2)):
            # Send a 1 telling the client the type wasn't accepted
            client_socket.sendall(six.int2byte(1))
            return False
        # Tell the Client we have accepted the authentication type
        # In this particular case 0 means the type was accepted
        client_socket.sendall(six.int2byte(0))
        return True

    def _auth_subtype_negotiation(self, client_socket):
        """Performs the x509None Authentication Sub-Type Negotiation.

        :param client_socket:  The client-side socket to receive data from.
        :return success:  Boolean whether the handshake was successful.
        """
        # Tell the client the authentication sub-type is x509None (260)
        client_socket.sendall(six.int2byte(1))
        client_socket.sendall(struct.pack('!I', 260))
        subtyp_raw = self._socket_receive(client_socket, 4)
        # Make sure that the client also supports sub-type x509None (260)
        if 260 not in struct.unpack('!I', subtyp_raw):
            # Send a 0 telling the client the sub-type wasn't accepted
            client_socket.sendall(six.int2byte(0))
            return False
        # Tell the Client we have accepted the authentication handshake
        # In this particular case 1 means the sub-type was accepted
        client_socket.sendall(six.int2byte(1))
        return True

    def _socket_receive(self, asocket, bufsize):
        """Helper method to add a timeout on each receive call.

        This method will raise a timeout exception if it takes > 30 seconds.

        :param asocket: The socket to do the receive on.
        :param bufsize: The number of bytes to receive.
        :return data: The data returned from the socket receive.
        """
        # Add a 30 second timeout around the receive so that we don't
        # block forever if for some reason it never received the packet
        if not select.select([asocket], [], [], 30)[0]:
            raise socket.timeout('30 second timeout on handshake receive')
        return asocket.recv(bufsize)

    def _check_http_connect(self, client_socket):
        """Parse the HTTP connect string to find the LPAR UUID.

        :param client_socket: The client socket sending the data.
        :returns lpar_uuid: The LPAR UUID parsed from the connect string.
        :returns http_code: The HTTP Connection code used for the client
                            connection.
        """
        # Get the expected header.
        # We don't know how large the identifier will be, so use 500 as max.
        # If the identifier is less than 500, it will not return as many bytes.
        header_len = len("CONNECT %s HTTP/1.1\r\n\r\n" % ('x' * 500))
        value = client_socket.recv(header_len)

        # Find the HTTP Code (if you can...)
        pat = r'^CONNECT\s+(\S+)\s+HTTP/(.*)\r\n\r\n$'
        res = re.match(pat, value)
        vnc_path = res.groups()[0] if res else None
        http_code = res.groups()[1] if res else '1.1'
        return _VNC_PATH_TO_UUID.get(vnc_path), http_code


class _VNCRepeaterServer(threading.Thread):
    """Repeats a VNC connection from localhost to a given client.

    This class is separated out from the Socket Listener so that there can
    be one thread doing the actual repeating/forwarded of the data for the
    VNC sessions for a single LPAR.  Otherwise if there are sessions to a lot
    of LPAR's with sessions, one overall thread might get overloaded.

    This class will be provided a pair of peer socket connections and will
    listen for data from each of them and forward to the other until the
    connection on one side goes down in which it will close the connection
    to the other side.

    Also, if no connections are open for a given local port VNC session,
    after a 5 minute window it will run rmvterm to close the terminal console
    to clean up sessions that are no longer being used.
    """

    def __init__(self, adapter, lpar_uuid, local_port, client_socket=None,
                 local_socket=None):
        """Creates the repeater.

        :param adapter: The pypowervm adapter
        :param lpar_uuid: Partition UUID.
        :param local_port: The local port bound to by the VNC session.
        :param client_socket: (Optional, Default: None) The socket descriptor
                              of the incoming client connection.
        :param local_socket: (Optional, Default: None) The socket descriptor of
                             the VNC session connection forwarding data to.
        """
        super(_VNCRepeaterServer, self).__init__()

        self.peers = dict()
        self.adapter = adapter
        self.lpar_uuid = lpar_uuid
        self.local_port = local_port
        self.alive = True
        self.vnc_killer = None

        # Add the connection passed into us to the forwarding list
        if client_socket is not None and local_socket is not None:
            self.add_socket_connection_pair(client_socket, local_socket)

    def stop(self):
        """Stops the repeater from running."""
        # This will stop listening for all clients
        self.alive = False

        # Remove ourselves from the VNC listeners.
        if self.local_port in _VNC_LOCAL_PORT_TO_REPEATER:
            del _VNC_LOCAL_PORT_TO_REPEATER[self.local_port]

    def run(self):
        """Used by the thread to run the repeater."""
        while self.alive:
            # Do a select to wait for data on each of the socket connections
            input_list = list(self.peers)
            s_inputs = select.select(input_list, [], [], 1)[0]

            for s_input in s_inputs:
                # At this point, we need to read the data.  We know that data
                # is ready.  However, if that data that is ready is length
                # 0, then we know that we're ready to close this.
                data = s_input.recv(4096)
                if len(data) == 0:
                    self._close_client(s_input)

                    # Note that we have to break here.  We do that because the
                    # peer dictionary has changed with the close.  So the list
                    # to iterate over should be re-evaluated.
                    # The remaining inputs will just be picked up on the next
                    # pass, so nothing to worry about.
                    break

                # Just process the data.
                self.peers[s_input].send(data)

        # At this point, force a close on all remaining inputs.
        for input_socket in self.peers:
            input_socket.close()

    def add_socket_connection_pair(self, client_socket, local_socket):
        """Adds the pair of socket connections to the list to forward data for.

        :param client_socket: The client-side incoming socket.
        :param local_socket: The local socket for the VNC session.
        """
        self.peers[local_socket] = client_socket
        self.peers[client_socket] = local_socket
        # If for some reason the VNC was being killed, abort it
        if self.vnc_killer is not None:
            self.vnc_killer.abort()
            self.vnc_killer = None

    def _close_client(self, s_input):
        """Closes down a client.

        :param s_input: The socket that has received a close.
        """
        # Close the sockets
        peer = self.peers[s_input]
        peer.close()
        s_input.close()

        # And remove from the peer list, so that we've removed all pointers to
        # them
        del self.peers[peer]
        del self.peers[s_input]

        # If this was the last port, close the local connection
        if len(self.peers) == 0:
            self.vnc_killer = _VNCKiller(self.adapter, self.lpar_uuid)
            self.vnc_killer.start()


class _VNCKiller(threading.Thread):
    """The VNC Killer is a thread that will eventually close the VNC.

    The VNC Repeater could run indefinitely, whether clients are connected to
    it or not.  This class will wait a period of time (5 minutes) and if
    the abort has not been called, will fully close the vterm.

    This is used in orchestration with the VNCRepeaterServer.  The intention
    is, if the user quickly navigates off the VNC, they can come back without
    losing their whole session.  But if they wait up to 5 minutes, then the
    session will be closed out and the memory will be reclaimed.
    """

    def __init__(self, adapter, lpar_uuid):
        super(_VNCKiller, self).__init__()
        self.adapter = adapter
        self.lpar_uuid = lpar_uuid
        self._abort = False

    def abort(self):
        """Call to stop the killer from completing its job."""
        self._abort = True

    def run(self):
        count = 0

        # Wait up to 5 minutes to see if any new negotiations came in
        while count < 300 and not self._abort:
            time.sleep(1)
            if self._abort:
                break
            count += 1

        if not self._abort:
            _close_vterm_local(self.adapter, self.lpar_uuid)
