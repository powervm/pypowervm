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
import testtools

import pypowervm.entities as ent
from pypowervm import exceptions as pexc
from pypowervm.tasks import power
import pypowervm.tests.test_fixtures as fx
from pypowervm.wrappers import base_partition as pvm_bp
from pypowervm.wrappers import logical_partition as pvm_lpar


class TestPower(testtools.TestCase):
    """Unit Tests for Instance Power On/Off."""

    def setUp(self):
        super(TestPower, self).setUp()
        mock_resp = mock.MagicMock()
        mock_resp.entry = ent.Entry({}, ent.Element('Dummy', None), None)
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.adpt.read.return_value = mock_resp

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR')
    def test_power_on_off(self, mock_lpar, mock_job_p, mock_run_job):
        """Performs a simple set of Power On/Off Tests."""
        def run_job_mock(**kwargs1):
            """Produce a run_job method that validates the given kwarg values.

            E.g. run_job_mock(foo='bar') will produce a mock run_job that
            asserts its foo argument is 'bar'.
            """
            def run_job(*args, **kwargs2):
                for key, val in kwargs1.items():
                    self.assertEqual(val, kwargs2[key])
            return run_job

        mock_lpar.adapter = self.adpt
        power._power_on_off(mock_lpar, 'PowerOn', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(0, mock_job_p.call_count)
        self.assertEqual(1, self.adpt.invalidate_cache_elem.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()
        self.adpt.reset_mock()

        # Try a power off
        power._power_on_off(mock_lpar, 'PowerOff', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(2, mock_job_p.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try a power off when the RMC state is active
        mock_lpar.rmc_state = pvm_bp.RMCState.ACTIVE
        power._power_on_off(mock_lpar, 'PowerOff', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_lpar.reset_mock()
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try a power off of IBMi
        mock_lpar.rmc_state = pvm_bp.RMCState.INACTIVE
        mock_lpar.env = pvm_bp.LPARType.OS400
        mock_lpar.ref_code = '00000000'
        power._power_on_off(mock_lpar, 'PowerOff', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_job_p.assert_called_with('operation', 'osshutdown')
        mock_lpar.reset_mock()
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try a more complex power off
        power._power_on_off(mock_lpar, 'PowerOff', '1111',
                            force_immediate=True, restart=True, timeout=100)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(3, mock_job_p.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        mock_run_job.side_effect = run_job_mock(synchronous=True)
        # Try optional parameters
        power.power_on(mock_lpar, '1111',
                       add_parms={power.BootMode.KEY: power.BootMode.SMS})
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_job_p.assert_called_with(power.BootMode.KEY, power.BootMode.SMS)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        power.power_on(mock_lpar, '1111', add_parms={
            pvm_lpar.IPLSrc.KEY: pvm_lpar.IPLSrc.A}, synchronous=True)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_job_p.assert_called_with(pvm_lpar.IPLSrc.KEY, pvm_lpar.IPLSrc.A)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        mock_run_job.side_effect = run_job_mock(synchronous=False)
        power.power_on(mock_lpar, '1111', add_parms={
            power.KeylockPos.KEY: power.KeylockPos.MANUAL}, synchronous=False)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_job_p.assert_called_with(power.KeylockPos.KEY,
                                      power.KeylockPos.MANUAL)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR')
    def test_power_off_timeout_retry(self, mock_lpar, mock_job_p,
                                     mock_run_job):
        """Validate that when first power off times out, re-run."""
        mock_lpar.adapter = self.adpt
        mock_lpar.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestTimedOut(
            operation_name='PowerOff', seconds=60)

        # Invoke the run, should power off graceful, fail, then force off
        # and fail again.
        self.assertRaises(pexc.VMPowerOffFailure,
                          power._power_on_off, mock_lpar, 'PowerOff', '1111')

        # It should have been called twice, once for the elegant power
        # off, and another for the immediate power off
        self.assertEqual(2, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR')
    def test_power_off_job_failure(self, mock_lpar, mock_job_p, mock_run_job):
        """Validates a power off job request failure."""
        mock_lpar.adapter = self.adpt
        mock_lpar.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOff', operation_name='HSCL0DB4')

        # Invoke the run, should power off graceful, fail, then force off
        # and fail again.
        self.assertRaises(pexc.VMPowerOffFailure,
                          power._power_on_off, mock_lpar, 'PowerOff', '1111')

        # This specific error should cause a retry.
        self.assertEqual(2, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR')
    def test_power_off_sysoff(self, mock_lpar, mock_job_p, mock_run_job):
        """Validates a power off job when system is already off."""
        mock_lpar.adapter = self.adpt
        mock_lpar.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOff', operation_name='HSCL1558')

        # Invoke the run the job, but succeed because it is already powered off
        power._power_on_off(mock_lpar, 'PowerOff', '1111')

        # This specific error should cause a retry.
        self.assertEqual(1, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR')
    def test_power_on_syson(self, mock_lpar, mock_job_p, mock_run_job):
        """Validates a power on job when system is already on."""
        mock_lpar.adapter = self.adpt
        mock_lpar.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOn', operation_name='HSCL3681')

        # Invoke the run the job, but succeed because it is already powered off
        power._power_on_off(mock_lpar, 'PowerOn', '1111')

        # This specific error should cause a retry.
        self.assertEqual(1, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS')
    def test_power_on_off_vios(self, mock_vios, mock_job_p, mock_run_job):
        """Performs a simple set of Power On/Off Tests."""
        mock_vios.adapter = self.adpt
        power._power_on_off(mock_vios, 'PowerOn', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(0, mock_job_p.call_count)
        self.assertEqual(1, self.adpt.invalidate_cache_elem.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()
        self.adpt.reset_mock()

        # Try a power off
        power._power_on_off(mock_vios, 'PowerOff', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(2, mock_job_p.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try a power off when the RMC state is active
        mock_vios.rmc_state = pvm_bp.RMCState.ACTIVE
        power._power_on_off(mock_vios, 'PowerOff', '1111')
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_vios.reset_mock()
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try a more complex power off
        power._power_on_off(mock_vios, 'PowerOff', '1111',
                            force_immediate=True, restart=True, timeout=100)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(3, mock_job_p.call_count)
        mock_run_job.reset_mock()
        mock_job_p.reset_mock()

        # Try optional parameters
        power.power_on(mock_vios, '1111',
                       add_parms={power.BootMode.KEY: power.BootMode.SMS})
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        mock_job_p.assert_called_with(power.BootMode.KEY, power.BootMode.SMS)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS')
    def test_power_off_timeout_retry_vios(self, mock_vios, mock_job_p,
                                          mock_run_job):
        """Validate that when first power off times out, re-run."""
        mock_vios.adapter = self.adpt
        mock_vios.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestTimedOut(
            operation_name='PowerOff', seconds=60)

        # Invoke the run, should power off graceful, fail, then force off
        # and fail again.
        self.assertRaises(pexc.VMPowerOffFailure,
                          power._power_on_off, mock_vios, 'PowerOff', '1111')

        # It should have been called twice, once for the elegant power
        # off, and another for the immediate power off
        self.assertEqual(2, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS')
    def test_power_off_job_failure_vios(self, mock_vios,
                                        mock_job_p, mock_run_job):
        """Validates a power off job request failure."""
        mock_vios.adapter = self.adpt
        mock_vios.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOff', operation_name='HSCL0DB4')

        # Invoke the run, should power off graceful, fail, then force off
        # and fail again.
        self.assertRaises(pexc.VMPowerOffFailure,
                          power._power_on_off, mock_vios, 'PowerOff', '1111')

        # This specific error should cause a retry.
        self.assertEqual(2, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS')
    def test_power_off_sysoff_vios(self, mock_vios, mock_job_p, mock_run_job):
        """Validates a power off job when system is already off."""
        mock_vios.adapter = self.adpt
        mock_vios.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOff', operation_name='HSCL1558')

        # Invoke the run the job, but succeed because it is already powered off
        power._power_on_off(mock_vios, 'PowerOff', '1111')

        # This specific error should cause a retry.
        self.assertEqual(1, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS')
    def test_power_on_syson_vios(self, mock_vios, mock_job_p, mock_run_job):
        """Validates a power on job when system is already on."""
        mock_vios.adapter = self.adpt
        mock_vios.rmc_state = pvm_bp.RMCState.ACTIVE
        mock_run_job.side_effect = pexc.JobRequestFailed(
            error='PowerOn', operation_name='HSCL3681')

        # Invoke the run the job, but succeed because it is already powered off
        power._power_on_off(mock_vios, 'PowerOn', '1111')

        # This specific error should cause a retry.
        self.assertEqual(1, mock_run_job.call_count)
