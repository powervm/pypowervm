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
from pypowervm.tasks.hdisk import _iscsi as iscsi
import pypowervm.tests.test_fixtures as fx
from pypowervm.wrappers import job


class TestIscsi(testtools.TestCase):

    def setUp(self):
        super(TestIscsi, self).setUp()
        entry = ent.Entry({}, ent.Element('Dummy', None), None)
        self.mock_job = job.Job(entry)
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_discover_iscsi(self, mock_job_res, mock_job_p, mock_run_job,
                            mock_job_w):
        mock_job_w.return_value = self.mock_job
        mock_host_ip = '10.0.0.1'
        mock_user = 'username'
        mock_pass = 'password'
        mock_iqn = 'fake_iqn'
        mock_uuid = 'uuid'
        args = ['VirtualIOServer', mock_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': ('ISCSIDiscovery')}
        mock_job_res.return_value = {'DEV_OUTPUT': '["fake_iqn devName udid"]'}
        device_name, udid = iscsi.discover_iscsi(
            self.adpt, mock_host_ip, mock_user, mock_pass, mock_iqn, mock_uuid)

        self.adpt.read.assert_called_once_with(*args, **kwargs)
        mock_job_p.assert_any_call('hostIP', mock_host_ip)
        mock_job_p.assert_any_call('user', mock_user)
        mock_job_p.assert_any_call('password', mock_pass)
        self.assertEqual('devName', device_name)
        self.assertEqual('udid', udid)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(4, mock_job_p.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_discover_initiator(self, mock_job_res, mock_run_job, mock_job_w):
        mock_job_w.return_value = self.mock_job
        mock_uuid = 'uuid'
        args = ['VirtualIOServer', mock_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': ('ISCSIDiscovery')}
        mock_job_res.return_value = {'InitiatorName': 'fake_iqn'}
        initiator = iscsi.discover_iscsi_initiator(self.adpt, mock_uuid)

        self.adpt.read.assert_called_once_with(*args, **kwargs)
        self.assertEqual('fake_iqn', initiator)
        self.assertEqual(1, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_remove_iscsi(self, mock_job_res, mock_run_job, mock_job_w,
                          mock_job_p):
        mock_job_w.return_value = self.mock_job
        mock_uuid = 'uuid'
        mock_iqn = 'fake_iqn'
        mock_parm = mock.MagicMock()
        mock_job_p.return_value = mock_parm
        args = ['VirtualIOServer', mock_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': ('ISCSILogout')}
        iscsi.remove_iscsi(self.adpt, mock_iqn, mock_uuid)

        self.adpt.read.assert_called_once_with(*args, **kwargs)
        mock_run_job.assert_called_once_with(mock_uuid, job_parms=[mock_parm],
                                             timeout=120)
        mock_job_p.assert_any_call('targetIQN', mock_iqn)
        self.assertEqual(1, mock_run_job.call_count)
