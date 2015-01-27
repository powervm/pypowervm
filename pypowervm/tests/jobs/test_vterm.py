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

from pypowervm.jobs import vterm

import unittest


class TestVterm(unittest.TestCase):
    """Unit Tests for Close LPAR vterm."""

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.logical_partition.LogicalPartition')
    def test_close_vterm(self, mock_lpar, mock_adpt, mock_run_job):
        """Performs a close LPAR vterm test."""
        vterm.close_vterm(mock_adpt, mock_lpar.uuid)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_adpt.read.call_count)
        mock_run_job.reset_mock()
        mock_adpt.reset_mock()
    