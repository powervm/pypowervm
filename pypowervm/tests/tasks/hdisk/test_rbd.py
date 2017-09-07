# Copyright 2017 IBM Corp.
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
from pypowervm.tasks.hdisk import _rbd as rbd
import pypowervm.tests.test_fixtures as fx
from pypowervm.wrappers import job


class TestRbd(testtools.TestCase):

    def setUp(self):
        super(TestRbd, self).setUp()
        entry = ent.Entry({}, ent.Element('Dummy', None), None)
        self.mock_job = job.Job(entry)
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_rbd_exists(self, mock_job_res, mock_run_job, mock_job_w,
                        mock_job_p):
        mock_job_w.return_value = self.mock_job
        mock_uuid = 'uuid'
        mock_name = 'pool/image'
        mock_parm = mock.MagicMock()
        mock_job_p.return_value = mock_parm
        args = ['VirtualIOServer', mock_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': ('RBDExists')}
        mock_job_res.return_value = {'exists': 'true'}
        self.assertTrue(rbd.rbd_exists(self.adpt, mock_uuid, mock_name))

        self.adpt.read.assert_called_once_with(*args, **kwargs)
        mock_run_job.assert_called_once_with(mock_uuid, job_parms=[mock_parm],
                                             timeout=120)
        mock_job_p.assert_any_call('name', mock_name)
        self.assertEqual(1, mock_run_job.call_count)
        mock_job_res.return_value = {'exists': 'false'}
        mock_job_p.return_value = mock_parm
        self.assertFalse(rbd.rbd_exists(self.adpt, mock_uuid, mock_name))
