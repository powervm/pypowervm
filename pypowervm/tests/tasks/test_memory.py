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
from pypowervm.tasks import memory
import pypowervm.tests.test_fixtures as fx
from pypowervm.wrappers import job


class TestMemory(testtools.TestCase):
    """Unit Tests for Memory tasks."""

    def setUp(self):
        super(TestMemory, self).setUp()
        entry = ent.Entry({}, ent.Element('Dummy', None), None)
        self.mock_job = job.Job(entry)
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_calculate_memory_overhead_on_host(self, mock_job_dict_res,
                                               mock_job_p,
                                               mock_run_job,
                                               mock_job_w):
        """Performs a simple set of calculate_memory_overhead_on_host tests."""

        def _reset_mocks():
            mock_job_w.reset_mock()
            mock_job_p.reset_mock()
            mock_run_job.reset_mock()
            mock_job_dict_res.reset_mock()

        def raise_exc_se():
            raise Exception

        mock_job_w.return_value = self.mock_job
        mock_host_uuid = '1234'
        args = ['ManagedSystem', mock_host_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': ('QueryReservedMemory'
                                                       'RequiredForPartition')}

        # test empty job results dictionary with defaults
        mock_job_dict_res.return_value = {'RequiredMemory': None,
                                          'CurrentAvailableSystemMemory': None}
        overhead, avail = (memory.
                           calculate_memory_overhead_on_host(self.adpt,
                                                             mock_host_uuid))
        self.adpt.read.assert_called_once_with(*args, **kwargs)
        self.assertEqual(1, mock_job_w.call_count)
        self.assertEqual(6, mock_job_p.call_count)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_dict_res.call_count)
        self.assertEqual(512, overhead)
        self.assertEqual(None, avail)
        _reset_mocks()

        # test with desired mem and non empty job results dict
        mock_job_dict_res.return_value = {'RequiredMemory': 1024,
                                          'CurrentAvailableSystemMemory':
                                          32768}
        reserved_mem_data = {'desired_mem': 768, 'num_virt_eth_adapters': 2}
        kwargs2 = {'reserved_mem_data': reserved_mem_data}
        overhead, avail = (memory.
                           calculate_memory_overhead_on_host(self.adpt,
                                                             mock_host_uuid,
                                                             **kwargs2))
        self.assertEqual(6, mock_job_p.call_count)
        self.assertEqual((1024-768), overhead)
        self.assertEqual(32768, avail)
        _reset_mocks()

        # test defaults when run_job fails
        mock_run_job.side_effect = raise_exc_se
        overhead, avail = (memory.
                           calculate_memory_overhead_on_host(self.adpt,
                                                             mock_host_uuid))
        mock_job_p.assert_any_call('LogicalPartitionEnvironment',
                                   'AIX/Linux')
        mock_job_p.assert_any_call('DesiredMemory', '512')
        mock_job_p.assert_any_call('MaximumMemory', '32768')
        mock_job_p.assert_any_call('NumberOfVirtualEthernetAdapter', '2')
        mock_job_p.assert_any_call('NumberOfVirtualSCSIAdapter', '1')
        mock_job_p.assert_any_call('NumberOfVirtualFibreChannelAdapter', '1')
        self.assertEqual(512, overhead)
        self.assertEqual(None, avail)
        self.assertEqual(0, mock_job_dict_res.call_count)
        _reset_mocks()

        # test reserved_mem_data values are created as job params
        reserved_mem_data = {'desired_mem': 2048,
                             'max_mem': 65536,
                             'lpar_env': 'OS400',
                             'num_virt_eth_adapters': 4,
                             'num_vscsi_adapters': 5,
                             'num_vfc_adapters': 6}
        kwargs3 = {'reserved_mem_data': reserved_mem_data}
        overhead, avail = (memory.
                           calculate_memory_overhead_on_host(self.adpt,
                                                             mock_host_uuid,
                                                             **kwargs3))
        mock_job_p.assert_any_call('LogicalPartitionEnvironment',
                                   'OS400')
        mock_job_p.assert_any_call('DesiredMemory', '2048')
        mock_job_p.assert_any_call('MaximumMemory', '65536')
        mock_job_p.assert_any_call('NumberOfVirtualEthernetAdapter', '4')
        mock_job_p.assert_any_call('NumberOfVirtualSCSIAdapter', '5')
        mock_job_p.assert_any_call('NumberOfVirtualFibreChannelAdapter', '6')
        self.assertEqual(512, overhead)
        self.assertEqual(None, avail)
