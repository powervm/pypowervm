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

import mock
import six
import testtools

import pypowervm.entities as ent
import pypowervm.exceptions as pexc
from pypowervm.tasks import vterm
import pypowervm.tests.test_fixtures as fx


class TestVterm(testtools.TestCase):
    """Unit Tests for LPAR vterm."""

    def setUp(self):
        super(TestVterm, self).setUp()
        self.adpt = self.useFixture(
            fx.AdapterFx(traits=fx.LocalPVMTraits)).adpt

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_close_vterm_non_local(self, mock_run_job):
        """Performs a close LPAR vterm test."""
        mock_resp = mock.MagicMock()
        mock_resp.entry = ent.Entry(
            {}, ent.Element('Dummy', self.adpt), self.adpt)
        self.adpt.read.return_value = mock_resp
        vterm._close_vterm_non_local(self.adpt, '12345')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, self.adpt.read.call_count)
        # test exception path
        mock_run_job.side_effect = pexc.LPARNotFound(
            lpar_name='12345')
        self.assertRaises(pexc.LPARNotFound,
                          vterm._close_vterm_non_local, self.adpt, '12345')
        mock_run_job.reset_mock()

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_open_vnc_vterm(self, mock_run_proc, mock_get_lpar_id):
        """Validates the output from the mkvterm if a vterm is not active."""
        mock_get_lpar_id.return_value = '4'
        std_out = '5903'
        std_err = ('VNC is started on port 5903 for localhost access '
                   'only.  Use \'rmvterm --id 4\' to close it.')
        mock_run_proc.return_value = (0, std_out, std_err)

        resp = vterm.open_localhost_vnc_vterm(self.adpt, 'lpar_uuid')

        mock_run_proc.assert_called_once_with(['mkvterm', '--id', '4', '--vnc',
                                               '--local'])
        self.assertEqual(5903, resp)

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_open_vnc_vterm_existing(self, mock_run_proc, mock_get_lpar_id):
        """Validates the output from the mkvterm if a VNC vterm is active."""
        mock_get_lpar_id.return_value = '4'
        std_out = '5903'
        std_err = ('\nVNC server is already started on port 5903. Use '
                   '\'rmvterm --id 4\' to close it.')
        mock_run_proc.return_value = (3, std_out, std_err)

        resp = vterm.open_localhost_vnc_vterm(self.adpt, 'lpar_uuid')

        mock_run_proc.assert_called_once_with(['mkvterm', '--id', '4', '--vnc',
                                               '--local'])
        self.assertEqual(5903, resp)

    @mock.patch('subprocess.Popen')
    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    def test_open_vnc_vterm_nonascii(self, mock_get_lpar_id, mock_popen):
        """Validates errors in non-ascii encodings are handled properly"""
        proc_mock = mock.Mock(returncode=3)
        mock_get_lpar_id.return_value = '4'
        mock_popen.return_value = proc_mock
        proc_mock.communicate.return_value = ('', '\xd0\x92')
        # Make sure we don't get some sort of encoding error on a failure case
        self.assertRaises(pexc.VNCBasedTerminalFailedToOpen,
                          vterm.open_localhost_vnc_vterm, self.adpt, '1', True)

    @mock.patch('pypowervm.tasks.vterm.close_vterm')
    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_open_vnc_vterm_nonvnc_force(self, mock_run_proc,
                                         mock_get_lpar_id, mock_close):
        """Validates the output from mkvterm if non-vnc active and force."""
        mock_get_lpar_id.return_value = '4'
        std_out_1 = ""
        std_err_1 = ("The vterm is currently in use by process 120352.  "
                     "Use 'rmvterm --id 4' to close it.")
        std_out_2 = '5903'
        std_err_2 = ('VNC is started on port 5903 for localhost access '
                     'only.  Use \'rmvterm --id 4\' to close it.')
        mock_run_proc.side_effect = [(3, std_out_1, std_err_1),
                                     (0, std_out_2, std_err_2)]

        resp = vterm.open_localhost_vnc_vterm(self.adpt, 'lpar_uuid',
                                              force=True)

        # Validation
        mock_close.assert_called_once_with(self.adpt, 'lpar_uuid')
        mock_run_proc.assert_any_call(['mkvterm', '--id', '4', '--vnc',
                                       '--local'])
        self.assertEqual(2, mock_run_proc.call_count)
        self.assertEqual(5903, resp)

    @mock.patch('pypowervm.tasks.vterm.close_vterm')
    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_open_vnc_vterm_nonvnc_noforce(self, mock_run_proc,
                                           mock_get_lpar_id, mock_close):
        """Validates the output from mkvterm if non-vnc active and no force."""
        mock_get_lpar_id.return_value = '4'
        std_out = ""
        std_err = ("The vterm is currently in use by process 120352.  "
                   "Use 'rmvterm --id 4' to close it.")
        mock_run_proc.return_value = (3, std_out, std_err)

        self.assertRaises(pexc.VNCBasedTerminalFailedToOpen,
                          vterm.open_localhost_vnc_vterm, self.adpt,
                          'lpar_uuid')

        # Validation
        mock_close.assert_not_called()
        mock_run_proc.assert_called_with(['mkvterm', '--id', '4', '--vnc',
                                          '--local'])
        self.assertEqual(1, mock_run_proc.call_count)

    @mock.patch('pypowervm.tasks.vterm.close_vterm')
    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_open_vnc_vterm_force_bad_error(self, mock_run_proc,
                                            mock_get_lpar_id, mock_close):
        """Validates the output from mkvterm if force but unexpected error."""
        mock_get_lpar_id.return_value = '4'
        std_out = ""
        std_err = ("The mkvterm command failed for an unexpected reason")
        mock_run_proc.return_value = (2, std_out, std_err)

        self.assertRaises(pexc.VNCBasedTerminalFailedToOpen,
                          vterm.open_localhost_vnc_vterm, self.adpt,
                          'lpar_uuid', force=True)

        # Validation
        mock_close.assert_not_called()
        mock_run_proc.assert_called_with(['mkvterm', '--id', '4', '--vnc',
                                          '--local'])
        self.assertEqual(1, mock_run_proc.call_count)

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_close_vterm_local(self, mock_run_proc, mock_get_lpar_id):
        mock_get_lpar_id.return_value = '2'
        vterm._close_vterm_local(self.adpt, '5')
        mock_run_proc.assert_called_once_with(['rmvterm', '--id', '2'])


class TestVNCSocketListener(testtools.TestCase):
    """Unit Tests for _VNCSocketListener vterm."""

    def setUp(self):
        super(TestVNCSocketListener, self).setUp()
        self.adpt = self.useFixture(
            fx.AdapterFx(traits=fx.LocalPVMTraits)).adpt

        self.srv = vterm._VNCSocketListener(
            self.adpt, '5901', '1.2.3.4', True, remote_ips=['1.2.3.5'])
        self.rptr = vterm._VNCRepeaterServer(self.adpt, 'uuid', '5800')

        vterm._VNC_LOCAL_PORT_TO_REPEATER['5800'] = self.rptr
        vterm._VNC_PATH_TO_UUID['path'] = 'uuid'
        vterm._VNC_PATH_TO_UUID['test'] = 'uuid'
        vterm._VNC_UUID_TO_LOCAL_PORT['uuid'] = '5800'

    def tearDown(self):
        """Tear down the Session instance."""

        vterm._VNC_PATH_TO_UUID['path'] = None
        vterm._VNC_PATH_TO_UUID['test'] = None
        vterm._VNC_UUID_TO_LOCAL_PORT['1.2.3.4'] = None
        vterm._VNC_LOCAL_PORT_TO_REPEATER['5800'] = None
        self.rptr = None

        super(TestVNCSocketListener, self).tearDown()

    def test_stop(self):
        self.assertTrue(self.srv.alive)
        self.srv.stop()
        self.assertFalse(self.srv.alive)

    @mock.patch('select.select')
    @mock.patch('socket.socket')
    def test_new_client(self, mock_sock, mock_select):
        mock_srv = mock.MagicMock()
        mock_s_sock, mock_c_sock = mock.MagicMock(), mock.MagicMock()
        mock_sock.return_value = mock_s_sock
        mock_select.return_value = [mock_c_sock], None, None
        mock_srv.accept.return_value = mock_c_sock, ('1.2.3.5', '40675')
        mock_c_sock.recv.return_value = "CONNECT path HTTP/1.8\r\n\r\n"

        self.srv._new_client(mock_srv)

        mock_c_sock.sendall.assert_called_once_with(
            "HTTP/1.8 200 OK\r\n\r\n")
        mock_s_sock.connect.assert_called_once_with(('127.0.0.1', '5800'))

        self.assertEqual({mock_c_sock: mock_s_sock, mock_s_sock: mock_c_sock},
                         self.rptr.peers)

    def test_check_http_connect(self):
        sock = mock.MagicMock()
        sock.recv.return_value = "INVALID"
        uuid, http_code = self.srv._check_http_connect(sock)
        self.assertIsNone(uuid)
        self.assertEqual('1.1', http_code)

        # Test a good string
        sock.reset_mock()
        sock.recv.return_value = 'CONNECT test HTTP/2.0\r\n\r\n'
        uuid, http_code = self.srv._check_http_connect(sock)
        self.assertEqual('uuid', uuid)
        self.assertEqual('2.0', http_code)

    def test_new_client_bad_ip(self):
        """Tests that a new client will be rejected if a bad IP."""
        mock_srv = mock.MagicMock()
        mock_c_sock = mock.MagicMock()
        mock_srv.accept.return_value = mock_c_sock, ('1.2.3.8', '40675')

        self.srv._new_client(mock_srv)

        self.assertEqual(self.rptr.peers, {})
        self.assertEqual(1, mock_c_sock.close.call_count)

    @mock.patch('select.select')
    def test_new_client_validation_checks(self, mock_select):
        mock_srv = mock.MagicMock()
        mock_c_sock = mock.MagicMock()
        mock_select.return_value = None, None, None
        mock_srv.accept.return_value = mock_c_sock, ('1.2.3.5', '40675')

        # This mock has no 'socket ready'.
        self.srv._new_client(mock_srv)
        self.assertEqual(self.rptr.peers, {})
        mock_c_sock.sendall.assert_called_with(
            "HTTP/1.1 400 Bad Request\r\n\r\n")
        self.assertEqual(1, mock_c_sock.close.call_count)

        # Reset the select so that the validation check fails
        mock_c_sock.reset_mock()
        mock_select.return_value = [mock_c_sock], None, None
        mock_c_sock.recv.return_value = 'bad_check'
        self.srv._new_client(mock_srv)
        self.assertEqual(self.rptr.peers, {})
        mock_c_sock.sendall.assert_called_with(
            "HTTP/1.1 400 Bad Request\r\n\r\n")
        self.assertEqual(1, mock_c_sock.close.call_count)

    @mock.patch('pypowervm.tasks.vterm._close_vterm_local')
    def test_close_client(self, mock_close):
        client, server = mock.Mock(), mock.Mock()
        self.rptr.add_socket_connection_pair(client, server)
        with mock.patch('time.sleep'):
            self.rptr._close_client(client)

            self.assertTrue(client.close.called)
            self.assertTrue(server.close.called)
            self.assertEqual({}, self.rptr.peers)

            # Get the killer off the thread and wait for it to complete.
            self.rptr.vnc_killer.join()
            mock_close.assert_called_once_with(self.adpt, 'uuid')

    @mock.patch('pypowervm.tasks.vterm._VNCSocketListener._new_client')
    @mock.patch('select.select')
    @mock.patch('socket.socket')
    def test_run_new_client(self, mock_socket, mock_select, mock_new_client):
        mock_server = mock.MagicMock()
        mock_socket.return_value = mock_server
        mock_server.count = 0

        # Used to make sure we don't loop indefinitely.
        bad_select = mock.MagicMock()

        # Since we are only listening on the server socket, we will have it
        # return that same socket the first 2 times, and then also return a
        # bad socket just to make sure we appropriately broke out before then
        mock_select.side_effect = [([mock_server], [], []),
                                   ([mock_server], [], []),
                                   ([bad_select], [], [])]

        def new_client(server):
            # Keep track of a counter so we make sure we break out of the
            # loop after the 2nd call to make sure it works twice at least
            if server.count == 1:
                self.srv.alive = False
            # We are setting alive to false after the 2nd
            # so we want to make sure it doesn't get here
            if server == bad_select:
                raise Exception('Invalid Loop Call')
            server.count += 1

        mock_new_client.side_effect = new_client

        # If this runs...we've pretty much validated.  Because it will end.
        # If it doesn't end...the fail in the 'select' side effect shoudl catch
        # it.
        self.srv.run()

        # Make sure the close was called on all of the sockets.
        self.assertTrue(mock_server.close.called)

        # Make sure the select was called with a timeout.
        mock_select.assert_called_with(mock.ANY, mock.ANY, mock.ANY, 1)

    @mock.patch('select.select')
    @mock.patch('ssl.wrap_socket', mock.Mock())
    def test_enable_x509_authentication(self, mock_select):
        mock_select.return_value = [mock.Mock()], None, None
        csock, ssock = _FakeSocket(), _FakeSocket()
        ssock.recv_buffer = b'RFB 003.008\n\x01\x01'
        csock.recv_buffer = b'RFB 003.007\n\x13\x00\x02\x00\x00\x01\x04'
        # Test the method to do the handshake to enable VeNCrypt Authentication
        self.srv.set_x509_certificates('cacert1', 'cert1', 'key1')
        nsock = self.srv._enable_x509_authentication(csock, ssock)
        # Make sure that we didn't get an error and the TLS Socket was created
        self.assertIsNotNone(nsock, 'The TLS Socket was not created')
        # Verify that the data sent to the Client Socket matches expected
        csocksnd = b'RFB 003.008\n\x01\x13\x00\x02\x00\x01\x00\x00\x01\x04\x01'
        self.assertEqual(csock.send_buffer, csocksnd,
                         'Did not send to the client socket what was expected')
        # Verify that the data sent to the Server Socket matches expected
        self.assertEqual(ssock.send_buffer, b'RFB 003.007\n\x01',
                         'Did not send to the server socket what was expected')

    @mock.patch('select.select')
    def test_enable_x509_authentication_bad_auth_type(self, mock_select):
        mock_select.return_value = [mock.Mock()], None, None
        csock, ssock = _FakeSocket(), _FakeSocket()
        ssock.recv_buffer = b'RFB 003.008\n\x01\x01'
        csock.recv_buffer = b'RFB 003.007\n\x14\x00\x02\x00\x00\x01\x04'
        # Test the method to do the handshake to enable VeNCrypt Authentication
        self.srv.set_x509_certificates('cacert1', 'cert1', 'key1')
        nsock = self.srv._enable_x509_authentication(csock, ssock)
        # Make sure that we got an error and it didn't create the TLS Socket
        self.assertIsNone(nsock, 'Expected an error validating auth type')
        # Verify that the data sent to the Client Socket matches expected
        csocksnd = b'RFB 003.008\n\x01\x13\x00\x02\x01'
        self.assertEqual(csock.send_buffer, csocksnd,
                         'Did not send to the client socket what was expected')

    @mock.patch('select.select')
    def test_enable_x509_authentication_bad_auth_version(self, mock_select):
        mock_select.return_value = [mock.Mock()], None, None
        csock, ssock = _FakeSocket(), _FakeSocket()
        ssock.recv_buffer = b'RFB 003.008\n\x01\x01'
        csock.recv_buffer = b'RFB 003.007\n\x13\x00\x01\x00\x00\x01\x04'
        # Test the method to do the handshake to enable VeNCrypt Authentication
        self.srv.set_x509_certificates('cacert1', 'cert1', 'key1')
        nsock = self.srv._enable_x509_authentication(csock, ssock)
        # Make sure that we got an error and it didn't create the TLS Socket
        self.assertIsNone(nsock, 'Expected an error validating auth version')
        # Verify that the data sent to the Client Socket matches expected
        csocksnd = b'RFB 003.008\n\x01\x13\x00\x02\x01'
        self.assertEqual(csock.send_buffer, csocksnd,
                         'Did not send to the client socket what was expected')

    @mock.patch('select.select')
    def test_enable_x509_authentication_bad_auth_subtype(self, mock_select):
        mock_select.return_value = [mock.Mock()], None, None
        csock, ssock = _FakeSocket(), _FakeSocket()
        ssock.recv_buffer = b'RFB 003.008\n\x01\x01'
        csock.recv_buffer = b'RFB 003.007\n\x13\x00\x02\x00\x00\x01\x03'
        # Test the method to do the handshake to enable VeNCrypt Authentication
        self.srv.set_x509_certificates('cacert1', 'cert1', 'key1')
        nsock = self.srv._enable_x509_authentication(csock, ssock)
        # Make sure that we got an error and it didn't create the TLS Socket
        self.assertIsNone(nsock, 'Expected an error validating auth sub-type')
        # Verify that the data sent to the Client Socket matches expected
        csocksnd = b'RFB 003.008\n\x01\x13\x00\x02\x00\x01\x00\x00\x01\x04\x00'
        self.assertEqual(csock.send_buffer, csocksnd,
                         'Did not send to the client socket what was expected')


class _FakeSocket(object):

    def __init__(self):
        self.recv_buffer, self.send_buffer = b'', b''
        self.recv_bytes, self.send_bytes = 0, 0

    def recv(self, bufsize):
        bufsize = bufsize if isinstance(bufsize, int) else ord(bufsize)
        chunk = self.recv_buffer[self.recv_bytes:self.recv_bytes+bufsize]
        if not isinstance(chunk, six.binary_type):
            chunk = six.binary_type(chunk, 'utf-8')
        self.recv_bytes += bufsize
        return chunk

    def sendall(self, string):
        if not isinstance(string, six.binary_type):
            string = six.binary_type(string, 'utf-8')
        self.send_buffer += string
        self.send_bytes += len(string)
