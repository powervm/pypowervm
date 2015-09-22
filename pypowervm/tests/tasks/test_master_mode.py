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
from pypowervm.tasks import master_mode as m_mode
import pypowervm.tests.tasks.util as u
import pypowervm.tests.test_fixtures as fx


class TestMasterMode(testtools.TestCase):
    """Unit Tests for master mode request and release."""

    def setUp(self):
        super(TestMasterMode, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        mock_resp = mock.MagicMock()
        mock_resp.entry = ent.Entry(
            {}, ent.Element('Dummy', self.adpt), self.adpt)
        self.adpt.read.return_value = mock_resp
        self.msys_w = mock.MagicMock()
        self.msys_w.adapter = self.adpt
        self.msys_w.uuid = '1234'

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_request_master(self, mock_run_job):
        mock_run_job.side_effect = u.get_parm_checker(
            self, '1234', [(m_mode.CO_MGMT_MASTER_STATUS,
                            m_mode.MasterMode.NORMAL)], exp_timeout=1800)
        m_mode.request_master(self.msys_w)
        self.adpt.read.assert_called_once_with('ManagedSystem', '1234',
                                               suffix_parm='RequestMaster',
                                               suffix_type='do')
        self.adpt.reset_mock()
        mock_run_job.reset_mock()

        # Test temp mode
        mock_run_job.side_effect = u.get_parm_checker(
            self, '1234', [(m_mode.CO_MGMT_MASTER_STATUS,
                            m_mode.MasterMode.TEMP)], exp_timeout=1800)
        m_mode.request_master(self.msys_w, mode=m_mode.MasterMode.TEMP)
        self.adpt.read.assert_called_once_with('ManagedSystem', '1234',
                                               suffix_parm='RequestMaster',
                                               suffix_type='do')

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_release_master(self, mock_run_job):
        m_mode.release_master(self.msys_w)
        self.adpt.read.assert_called_once_with('ManagedSystem', '1234',
                                               suffix_parm='ReleaseMaster',
                                               suffix_type='do')
        mock_run_job.assert_called_once_with('1234', timeout=1800)
