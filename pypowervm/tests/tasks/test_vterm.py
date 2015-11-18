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
        mock_get_lpar_id.return_value = '4'
        std_out = '5903'
        std_err = ('VNC is started on port 5903 for localhost access '
                   'only.  Use \'rmvterm --id 4\' to close it.')
        mock_run_proc.return_value = (std_out, std_err)

        resp = vterm.open_localhost_vnc_vterm(self.adpt, 'lpar_uuid')

        mock_run_proc.assert_called_once_with(['mkvterm', '--id', '4', '--vnc',
                                               '--local'])
        self.assertEqual(5903, resp)

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_open_vnc_vterm_second_pass(self, mock_run_proc, mock_get_lpar_id):
        """Validates the output from the mkvterm if a vterm is active."""
        mock_get_lpar_id.return_value = '4'
        std_out = '5903'
        std_err = ('\nVNC server is already started on port 5903. Use '
                   '\'rmvterm --id 4\' to close it.')
        mock_run_proc.return_value = (std_out, std_err)

        resp = vterm.open_localhost_vnc_vterm(self.adpt, 'lpar_uuid')

        mock_run_proc.assert_called_once_with(['mkvterm', '--id', '4', '--vnc',
                                               '--local'])
        self.assertEqual(5903, resp)

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    def test_close_vterm_local(self, mock_run_proc, mock_get_lpar_id):
        mock_get_lpar_id.return_value = '2'
        vterm._close_vterm_local(self.adpt, '5')
        mock_run_proc.assert_called_once_with(['rmvterm', '--id', '2'])


class TestVNCRepeaterServer(testtools.TestCase):
    """Unit Tests for _VNCRepeaterServer vterm."""

    def setUp(self):
        super(TestVNCRepeaterServer, self).setUp()
        self.adpt = self.useFixture(
            fx.AdapterFx(traits=fx.LocalPVMTraits)).adpt
        self.srv = vterm._VNCRepeaterServer(
            'uuid', '1.2.3.4', '5800', remote_ips=['1.2.3.5'],
            validation_check='check', validation_success='success',
            validation_fail='fail')

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
        mock_srv.accept.return_value = mock_c_sock, ['1.2.3.5']
        mock_c_sock.recv.return_value = 'check'
        peers = {}

        self.srv._new_client(mock_srv, peers)

        mock_c_sock.sendall.assert_called_once_with('success')
        mock_s_sock.connect.assert_called_once_with(('127.0.0.1', '5800'))
        self.assertEqual({mock_c_sock: mock_s_sock, mock_s_sock: mock_c_sock},
                         peers)

    def test_new_client_bad_ip(self):
        """Tests that a new client will be rejected if a bad IP."""
        mock_srv = mock.MagicMock()
        mock_c_sock = mock.MagicMock()
        mock_srv.accept.return_value = mock_c_sock, ['1.2.3.4']
        peers = {}

        self.srv._new_client(mock_srv, peers)

        self.assertEqual(peers, {})
        self.assertEqual(1, mock_c_sock.close.call_count)

    @mock.patch('select.select')
    def test_new_client_validation_checks(self, mock_select):
        mock_srv = mock.MagicMock()
        mock_c_sock = mock.MagicMock()
        mock_select.return_value = None, None, None
        mock_srv.accept.return_value = mock_c_sock, ['1.2.3.5']
        peers = {}

        # This mock has no 'socket ready'.
        self.srv._new_client(mock_srv, peers)
        self.assertEqual(peers, {})
        mock_c_sock.sendall.assert_called_with('fail')
        self.assertEqual(1, mock_c_sock.close.call_count)

        # Reset the select so that the validation check fails
        mock_c_sock.reset_mock()
        mock_select.return_value = [mock_c_sock], None, None
        mock_c_sock.recv.return_value = 'bad_check'
        self.srv._new_client(mock_srv, peers)
        self.assertEqual(peers, {})
        mock_c_sock.sendall.assert_called_with('fail')
        self.assertEqual(1, mock_c_sock.close.call_count)

    def test_close_client(self):
        client, server = mock.Mock(), mock.Mock()
        peers = {client: server, server: client}

        self.srv._close_client(client, peers)

        self.assertTrue(client.close.called)
        self.assertTrue(server.close.called)
        self.assertEqual({}, peers)

    @mock.patch('pypowervm.tasks.vterm._VNCRepeaterServer._new_client')
    @mock.patch('select.select')
    @mock.patch('socket.socket')
    def test_run_new_client(self, mock_socket, mock_select, mock_new_client):
        mock_server = mock.MagicMock()
        mock_socket.return_value = mock_server
        mock_client_peer, mock_server_peer = mock.MagicMock(), mock.MagicMock()
        mock_client_peer.recv.return_value = 'data'

        # Used to make sure we don't loop indefinitely.
        bad_select = mock.MagicMock()
        bad_select.recv.side_effect = Exception('Invalid Loop Call')

        # Mocks how data is received.  First is a new client.  Second is data
        # from client.  Last should never happen.
        mock_select.side_effect = [([mock_server], [], []),
                                   ([mock_client_peer], [], []),
                                   ([bad_select], [], [])]

        def new_client(server, peers):
            peers[mock_client_peer] = mock_server_peer
            peers[mock_server_peer] = mock_client_peer

        mock_new_client.side_effect = new_client

        def send_data(data):
            self.assertEqual('data', data)
            self.srv.alive = False

        mock_server_peer.send.side_effect = send_data

        # If this runs...we've pretty much validated.  Because it will end.
        # If it doesn't end...the fail in the 'select' side effect shoudl catch
        # it.
        self.srv.run()

        # Make sure the close was called on all of the sockets.
        self.assertTrue(mock_server.close.called)
        self.assertTrue(mock_client_peer.close.called)
        self.assertTrue(mock_server_peer.close.called)
