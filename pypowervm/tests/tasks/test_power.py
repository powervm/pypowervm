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
from pypowervm.tests import test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
from pypowervm import util as u
from pypowervm.wrappers import base_partition as pvm_bp
from pypowervm.wrappers import logical_partition as pvm_lpar
from pypowervm.wrappers import storage as pvm_stor


class TestPower(testtools.TestCase):
    """Unit Tests for Instance Power On/Off."""

    def setUp(self):
        super(TestPower, self).setUp()
        mock_resp = mock.MagicMock()
        mock_resp.entry = ent.Entry({}, ent.Element('Dummy', None), None)
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.adpt.read.return_value = mock_resp

        def resp(file_name):
            return pvmhttp.load_pvm_resp(
                file_name, adapter=self.adpt).get_response()

        self.vfc_client_adpt_resp = resp('vfc_client_adapter_feed.txt')

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR')
    @mock.patch('pypowervm.tasks.power.power_off_vfcs')
    def test_power_on_off(self, mock_vfc_off, mock_lpar, mock_job_p,
                          mock_run_job):
        """Performs a simple set of Power On/Off Tests."""
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

        # Try optional parameters
        power.power_on(mock_lpar, '1111',
                       add_parms=dict(bootmode=power.BootMode.SMS))
        mock_vfc_off.assert_called_once_with(mock_lpar, fail_if_invalid=False)
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        self.assertTrue(power.BootMode.SMS in str(mock_job_p.call_args))

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
                       add_parms=dict(bootmode=power.BootMode.SMS))
        self.assertEqual(1, mock_run_job.call_count)
        self.assertEqual(1, mock_job_p.call_count)
        self.assertTrue(power.BootMode.SMS in str(mock_job_p.call_args))

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

    @mock.patch('pypowervm.tasks.power._power_vfcs')
    def test_power_off_vfcs(self, mock_vfcs):
        # No failure path
        part = mock.Mock()
        power.power_off_vfcs(part)
        mock_vfcs.assert_called_once_with(part, pvm_stor.WWPNStatus.LOGGED_OUT,
                                          failure_error=None)

        # Path that would pass in the failure.
        mock_vfcs.reset_mock()
        power.power_off_vfcs(part, fail_if_invalid=True)
        mock_vfcs.assert_called_once_with(part, pvm_stor.WWPNStatus.LOGGED_OUT,
                                          failure_error=pexc.VFCPowerOffFailed)

    @mock.patch('pypowervm.tasks.power._power_vfcs')
    def test_power_on_vfcs(self, mock_vfcs):
        # No failure path
        part = mock.Mock()
        power.power_on_vfcs(part, {'wwpn'})
        mock_vfcs.assert_called_once_with(
            part, pvm_stor.WWPNStatus.LOGGED_IN, wwpns={'wwpn'},
            failure_error=None)

        # Path that would pass in the failure.
        mock_vfcs.reset_mock()
        power.power_on_vfcs(part, {'wwpn2'}, fail_if_invalid=True)
        mock_vfcs.assert_called_once_with(
            part, pvm_stor.WWPNStatus.LOGGED_IN, wwpns={'wwpn2'},
            failure_error=pexc.VFCPowerOnFailed)

    def test_power_vfcs_bad_input(self):
        """Tests the _power_vfcs when invalid input is passed in."""
        # Test scenarios where we are passing in something other than a LPAR
        not_lpar = mock.Mock()
        self.assertRaises(
            pexc.VFCPowerOffFailed, power._power_vfcs, not_lpar,
            pvm_stor.WWPNStatus.LOGGED_OUT, wwpns=['abcdef1234567890'],
            failure_error=pexc.VFCPowerOffFailed)
        self.assertFalse(power._power_vfcs(
            not_lpar, pvm_stor.WWPNStatus.LOGGED_OUT,
            wwpns=['abcdef1234567890']))

        # Test where we pass in an Activate LPAR
        active_lpar = mock.Mock(spec=pvm_lpar.LPAR,
                                state=pvm_bp.LPARState.MIGRATING_RUNNING)
        self.assertRaises(
            pexc.VFCPowerOffFailed, power._power_vfcs, active_lpar,
            pvm_stor.WWPNStatus.LOGGED_OUT, wwpns=['abcdef1234567890'],
            failure_error=pexc.VFCPowerOffFailed)
        self.assertFalse(power._power_vfcs(
            active_lpar, pvm_stor.WWPNStatus.LOGGED_OUT,
            wwpns=['abcdef1234567890']))

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    def test_power_vfcs(self, mock_update):
        # Mock data
        self.adpt.read.return_value = self.vfc_client_adpt_resp
        inactive_lpar = mock.Mock(spec=pvm_lpar.LPAR,
                                  state=pvm_bp.LPARState.NOT_ACTIVATED,
                                  adapter=self.adpt)

        # Some should be set to logged in, some will be left as unknown.
        logged_in_wwpns = {'c05076087cba0169', 'C05076087CBA016C'}
        unknown_wwpns = {'c05076087cba0168', 'C05076087CBA016D'}
        s_logged_in_wwpns = [u.sanitize_wwpn_for_api(x)
                             for x in logged_in_wwpns]
        s_unknown_wwpns = [u.sanitize_wwpn_for_api(x) for x in unknown_wwpns]

        # The update method will be called.  As part of this, we simply want
        # to validate that the wwpn_status was properly configured.
        def validate_update(entry, etag, path, timeout=0):
            # The entry passed in will be the VFCClientAdapter.  Validate
            # the WWPNs.
            self.assertEqual(2, len(entry.nport_logins))
            for n_port in entry.nport_logins:
                if n_port.wwpn in s_logged_in_wwpns:
                    self.assertEqual(pvm_stor.WWPNStatus.LOGGED_IN,
                                     n_port.wwpn_status)
                elif n_port.wwpn in s_unknown_wwpns:
                    self.assertEqual(pvm_stor.WWPNStatus.UNKNOWN,
                                     n_port.wwpn_status)
                else:
                    self.fail("Unknown WWPN")
            return entry.entry
        mock_update.side_effect = validate_update

        resp = power._power_vfcs(inactive_lpar, pvm_stor.WWPNStatus.LOGGED_IN,
                                 wwpns=logged_in_wwpns)
        self.assertTrue(resp)
        self.assertTrue(mock_update.called)
