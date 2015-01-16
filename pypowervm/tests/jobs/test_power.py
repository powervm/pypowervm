# Copyright 2014, 2015 IBM Corp.
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

from pypowervm import exceptions as pexc
from pypowervm.jobs import power

import unittest


class TestPower(unittest.TestCase):
    """Unit Tests for Instance Power On/Off."""

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.logical_partition.LogicalPartition')
    def test_power_on_off(self, mock_lpar, mock_adpt, mock_job_p,
                          mock_run_job):
        """Performs a simple set of Power On/Off Tests."""
        power._power_on_off(mock_adpt, mock_lpar, 'PowerOn', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(0, mock_job_p.call_count)
        self.assertEqual(1, mock_adpt.invalidate_cache_elem.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()
        mock_adpt.reset_mock()

        # Try a power off
        power._power_on_off(mock_adpt, mock_lpar, 'PowerOff', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(2, mock_job_p.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try a power off when the RMC state is active
        mock_lpar.check_dlpar_connectivity.return_value = ['Bah', 'active']
        power._power_on_off(mock_adpt, mock_lpar, 'PowerOff', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_lpar.reset_mock()
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try a more complex power off
        power._power_on_off(mock_adpt, mock_lpar, 'PowerOff', '1111',
                            force_immediate=True, restart=True, timeout=100)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(3, mock_job_p.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.logical_partition.LogicalPartition')
    def test_power_off_timeout_retry(self, mock_lpar, mock_adpt, mock_job_p,
                                     mock_run_job):
        """Validate that when first power off times out, re-run."""
        mock_lpar.check_dlpar_connectivity.return_value = ['Bah', 'active']
        mock_run_job.side_effect = pexc.JobRequestTimedOut(
            operation_name='PowerOff', seconds=60)

        # Invoke the run, should power off graceful, fail, then force off
        # and fail again.
        self.assertRaises(pexc.VMPowerOffFailure,
                          power._power_on_off,
                          mock_adpt, mock_lpar, 'PowerOff', '1111')

        # It should have been called twice, once for the elegant power
        # off, and another for the immediate power off
        self.assertEqual(2, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.logical_partition.LogicalPartition')
    def test_power_off_job_failure(self, mock_lpar, mock_adpt, mock_job_p,
                                   mock_run_job):
        """Validates a power off job request failure."""
        mock_lpar.check_dlpar_connectivity.return_value = ['Bah', 'active']
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOff', operation_name='HSCL0DB4')

        # Invoke the run, should power off graceful, fail, then force off
        # and fail again.
        self.assertRaises(pexc.VMPowerOffFailure,
                          power._power_on_off,
                          mock_adpt, mock_lpar, 'PowerOff', '1111')

        # This specific error should cause a retry.
        self.assertEqual(2, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.logical_partition.LogicalPartition')
    def test_power_off_sysoff(self, mock_lpar, mock_adpt, mock_job_p,
                              mock_run_job):
        """Validates a power off job when system is already off."""
        mock_lpar.check_dlpar_connectivity.return_value = ['Bah', 'active']
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOff', operation_name='HSCL1558')

        # Invoke the run the job, but succeed because it is already powered off
        power._power_on_off(mock_adpt, mock_lpar, 'PowerOff', '1111')

        # This specific error should cause a retry.
        self.assertEqual(1, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.logical_partition.LogicalPartition')
    def test_power_on_syson(self, mock_lpar, mock_adpt, mock_job_p,
                            mock_run_job):
        """Validates a power on job when system is already on."""
        mock_lpar.check_dlpar_connectivity.return_value = ['Bah', 'active']
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOn', operation_name='HSCL3681')

        # Invoke the run the job, but succeed because it is already powered off
        power._power_on_off(mock_adpt, mock_lpar, 'PowerOn', '1111')

        # This specific error should cause a retry.
        self.assertEqual(1, mock_run_job.call_count)
