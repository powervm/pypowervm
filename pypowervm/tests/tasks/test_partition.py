# Copyright 2016 IBM Corp.
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

"""Tests for pypowervm.tasks.partition."""

import mock

import pypowervm.exceptions as ex
import pypowervm.tasks.partition as tpar
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.logical_partition as lpar


class TestPartition(twrap.TestWrapper):
    file = 'lpar.txt'
    wrapper_class_to_test = lpar.LPAR

    def test_get_mgmt(self):
        """Test get_mgmt_partition()."""
        self.adpt.read.return_value = self.resp
        mgmt_w = tpar.get_mgmt_partition(self.adpt)
        self.assertTrue(mgmt_w.is_mgmt_partition)
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', mgmt_w.uuid)
        with mock.patch(
                'pypowervm.wrappers.logical_partition.LPAR.is_mgmt_partition',
                return_value=False):
            self.assertRaises(ex.ManagementPartitionNotFoundException,
                              tpar.get_mgmt_partition, self.adpt)

    @mock.patch('pypowervm.wrappers.logical_partition.LPAR.search')
    @mock.patch('pypowervm.util.my_partition_id')
    def test_get_me(self, mock_my_id, mock_search):
        """Test get_this_partition()."""
        # Good path - one hit
        mock_search.return_value = [self.dwrap]
        mock_my_id.return_value = 9
        my_w = tpar.get_this_partition(self.adpt)
        self.assertEqual(9, my_w.id)
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', my_w.uuid)
        mock_search.assert_called_with(self.adpt, id=9)

        # Bad path - multiple hits
        mock_search.return_value = self.entries
        self.assertRaises(ex.ThisPartitionNotFoundException,
                          tpar.get_this_partition, self.adpt)

        # Bad path - no hits
        mock_search.return_value = []
        self.assertRaises(ex.ThisPartitionNotFoundException,
                          tpar.get_this_partition, self.adpt)
