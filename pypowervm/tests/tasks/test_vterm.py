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
    @mock.patch('subprocess.check_output')
    def test_open_vnc_vterm(self, mock_run_proc, mock_get_lpar_id):
        mock_get_lpar_id.return_value = '4'
        mock_run_proc.return_value = '5903\n'

        resp = vterm.open_localhost_vnc_vterm(self.adpt, 'lpar_uuid')

        mock_run_proc.assert_called_once_with(['mkvterm', '--id', '4', '--vnc',
                                               '--local'])
        self.assertEqual(5903, resp)

    @mock.patch('pypowervm.tasks.vterm._get_lpar_id')
    @mock.patch('subprocess.check_output')
    def test_close_vterm_local(self, mock_run_proc, mock_get_lpar_id):
        mock_get_lpar_id.return_value = '2'
        vterm._close_vterm_local(self.adpt, '5')
        mock_run_proc.assert_called_once_with(['rmvterm', '--id', '2'])

    def proc(self, cmdline, terminal=None):
        process = mock.MagicMock()
        process.cmdline = cmdline
        process.terminal = terminal
        return process
