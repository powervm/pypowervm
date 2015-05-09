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
    """Unit Tests for Close LPAR vterm."""

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
    @mock.patch('pypowervm.tasks.vterm._has_vnc_running')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    @mock.patch('pypowervm.tasks.vterm._check_for_tty')
    def test_open_vnc_vterm(self, mock_check_tty, mock_run_proc,
                            mock_vnc_running, mock_get_lpar_id):
        mock_check_tty.return_value = None
        mock_vnc_running.return_value = []
        mock_get_lpar_id.return_value = '1'

        # 1 - rmvterm
        # 2 - openvt
        # 3 - linuxvnc
        mock_run_proc.side_effect = [(None, None), (None, '/asdf/tty4'),
                                     (None, None)]

        vterm.open_vnc_vterm(self.adpt, 'lpar_uuid')

        mock_check_tty.assert_called_with('1')
        mock_vnc_running.assert_called_with('4', 5904, listen_ip='127.0.0.1')

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._has_vnc_running')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    @mock.patch('pypowervm.tasks.vterm._check_for_tty')
    def test_open_vnc_vterm_existing_tty(self, mock_check_tty, mock_run_proc,
                                         mock_vnc_running, mock_get_lpar_id):
        mock_check_tty.return_value = '5'
        mock_vnc_running.return_value = ['running!']
        mock_get_lpar_id.return_value = '1'

        vterm.open_vnc_vterm(self.adpt, 'lpar_uuid')

        mock_check_tty.assert_called_with('1')
        mock_vnc_running.assert_called_with('5', 5905, listen_ip='127.0.0.1')
        self.assertEqual(0, mock_run_proc.call_count)

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._has_vnc_running')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    @mock.patch('pypowervm.tasks.vterm._check_for_tty')
    def test_close_vterm_local(self, mock_check_tty, mock_run_proc,
                               mock_vnc_running, mock_get_lpar_id):
        self.close_vt_local_test(vterm._close_vterm_local, mock_check_tty,
                                 mock_run_proc, mock_vnc_running,
                                 mock_get_lpar_id)

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('pypowervm.tasks.vterm._has_vnc_running')
    @mock.patch('pypowervm.tasks.vterm._run_proc')
    @mock.patch('pypowervm.tasks.vterm._check_for_tty')
    def test_close_vterm(self, mock_check_tty, mock_run_proc, mock_vnc_running,
                         mock_get_lpar_id):
        # Will run down the local path
        self.close_vt_local_test(vterm.close_vterm, mock_check_tty,
                                 mock_run_proc, mock_vnc_running,
                                 mock_get_lpar_id)

    def close_vt_local_test(self, func, mock_check_tty, mock_run_proc,
                            mock_vnc_running, mock_get_lpar_id):
        # Mock
        mock_get_lpar_id.return_value = '5'
        mock_check_tty.return_value = '2'

        proc = mock.MagicMock()
        mock_vnc_running.return_value = [proc]

        # Execute
        func(self.adpt, "lpar_uuid")

        # Validate
        mock_check_tty.assert_called_with('5')
        mock_vnc_running.assert_called_with('2', 5902)
        self.assertEqual(1, proc.kill.call_count)
        mock_run_proc.assert_called_with(['sudo', 'rmvtermutil', '--id', '5'])

    @mock.patch('psutil.process_iter')
    def test_check_for_tty(self, mock_proc_iter):
        # Mock
        bad_proc = self.proc(['notmvt', '--id', '5'], terminal='/proc/tty5')
        bad_proc2 = self.proc(['/sbin/mkvtermutil', '--id', '5'])
        good_proc = self.proc(['/sbin/mkvtermutil', '--id', '5'],
                              terminal='/proc/tty6')
        mock_proc_iter.return_value = [bad_proc, bad_proc2, good_proc]

        # Execute
        self.assertEqual('6', vterm._check_for_tty('5'))
        self.assertEqual(None, vterm._check_for_tty('6'))

    @mock.patch('psutil.process_iter')
    def test_has_vnc_running(self, mock_proc_iter):
        # Mock
        proc1 = self.proc(['linuxvnc', '3', '-rfbport', '10', '-listen',
                           '172.0.0.1'])
        proc2 = self.proc(['linuxvnc', '3', '-rfbport', '11'])
        proc3 = self.proc(['linuxvnc', '3', '-rfbport', '11', '-listen',
                           '127.0.0.1'])
        mock_proc_iter.return_value = [proc1, proc2, proc3]

        # Execute
        self.assertEqual(2, len(vterm._has_vnc_running('3', '11')))
        self.assertEqual(1, len(vterm._has_vnc_running('3', '11',
                                                       listen_ip='127.0.0.1')))
        self.assertEqual(0, len(vterm._has_vnc_running('3', '11',
                                                       listen_ip='172.0.0.1')))

    def proc(self, cmdline, terminal=None):
        process = mock.MagicMock()
        process.cmdline = cmdline
        process.terminal = terminal
        return process
