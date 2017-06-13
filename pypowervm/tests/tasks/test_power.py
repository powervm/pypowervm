# Copyright 2014, 2017 IBM Corp.
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

import fixtures
import mock
import testtools

import pypowervm.exceptions as pexc
from pypowervm.tasks import power
import pypowervm.tasks.power_opts as popts
import pypowervm.tests.test_fixtures as fx
import pypowervm.wrappers.base_partition as pvm_bp
import pypowervm.wrappers.logical_partition as pvm_lpar


class TestPower(testtools.TestCase):
    def setUp(self):
        super(TestPower, self).setUp()

        self.adpt = self.useFixture(fx.AdapterFx()).adpt

        # Make it easier to validate job params: create_job_parameter returns a
        # simple 'name=value' string.
        mock_crt_jparm = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.job.Job.create_job_parameter')).mock
        mock_crt_jparm.side_effect = (
            lambda name, value, cdata=False: '%s=%s' % (name, value))

        # Patch Job.wrap to return a mocked Job wrapper
        mock_job = mock.Mock()
        self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.job.Job.wrap')).mock.return_value = mock_job
        self.run_job = mock_job.run_job

    def validate_run(self, part, ex_suff="PowerOff", ex_parms=None,
                     ex_timeout=1800, ex_synch=True, result='', nxt=None):
        """Return side effect method to validate Adapter.read and Job.run_job.

        :param part: (Mock) partition wrapper.
        :param ex_suff: Expected Job suffix - "PowerOn" or "PowerOff"
        :param ex_parms: Set of expected JobParameter 'name=value' strings.
        :param ex_timeout: Expected timeout (int, seconds).
        :param ex_synch: Expected value of the 'synchronous' flag.
        :param result: The desired result of the run_job call.  May be None
                       (the run_job call "succeeded") or an instance of an
                       exception to be raised (either JobRequestTimedOut or
                       JobRequestFailed).
        :param nxt: When chaining side effects, pass the method to be assigned
                    to the run_job side effect after this side effect runs.
                    Typically the return from another validate_run() call.
        :return: A method suitable for assigning to self.run_job.side_effect.
        """
        def run_job_seff(uuid, job_parms=None, timeout=None, synchronous=None):
            # We fetched the Job template with the correct bits of the
            # partition wrapper and the correct suffix
            self.adpt.read.assert_called_once_with(
                part.schema_type, part.uuid, suffix_type='do',
                suffix_parm=ex_suff)
            # Reset for subsequent runs
            self.adpt.reset_mock()
            self.assertEqual(part.uuid, uuid)
            # JobParameter order doesn't matter
            self.assertEqual(ex_parms or set(), set(job_parms))
            self.assertEqual(ex_timeout, timeout)
            self.assertEqual(ex_synch, synchronous)
            if nxt:
                self.run_job.side_effect = nxt
            if result:
                raise result
        return run_job_seff

    @staticmethod
    def etimeout():
        """Returns a JobRequestTimedOut exception."""
        return pexc.JobRequestTimedOut(operation_name='foo', seconds=1800)

    @staticmethod
    def efail(error='error'):
        """Returns a JobRequestFailed exception."""
        return pexc.JobRequestFailed(operation_name='foo', error=error)

    def mock_partition(self, env=pvm_bp.LPARType.AIXLINUX,
                       rmc_state=pvm_bp.RMCState.ACTIVE, mgmt=False):
        """Returns a mocked partition with the specified properties."""
        return mock.Mock(adapter=self.adpt, env=env, rmc_state=rmc_state,
                         is_mgmt_partition=mgmt)

    def test_pwrop_start(self):
        """Test PowerOp.start."""
        part = self.mock_partition()

        # Default params, success
        self.run_job.side_effect = self.validate_run(part, ex_suff="PowerOn")
        power.PowerOp.start(part)
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Additional params, timeout
        self.run_job.side_effect = self.validate_run(
            part, ex_suff="PowerOn", ex_parms={'foo=bar', 'one=two'},
            result=self.etimeout())
        self.assertRaises(
            pexc.VMPowerOnTimeout, power.PowerOp.start, part,
            opts=popts.PowerOnOpts(legacy_add_parms={'foo': 'bar',
                                                     'one': 'two'}))
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Asynchronous, failure
        self.run_job.side_effect = self.validate_run(
            part, ex_suff="PowerOn", ex_synch=False, result=self.efail())
        self.assertRaises(pexc.VMPowerOnFailure, power.PowerOp.start, part,
                          synchronous=False)
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Specified timeout, already on
        self.run_job.side_effect = self.validate_run(
            part, ex_suff="PowerOn", ex_timeout=10,
            result=self.efail('HSCL3681'))
        power.PowerOp.start(part, timeout=10)
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

    def test_pwrop_stop(self):
        """Test PowerOp.stop."""
        # If RMC is down, VSP normal - make sure the 'immediate' flag goes away
        part = self.mock_partition(rmc_state=pvm_bp.RMCState.INACTIVE)
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=shutdown'})
        power.PowerOp.stop(
            part, opts=popts.PowerOffOpts().immediate().soft_detect(part))
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Default parameters - the method figures out whether to do OS shutdown
        part = self.mock_partition()
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=osshutdown', 'immediate=true'})
        power.PowerOp.stop(
            part, opts=popts.PowerOffOpts().immediate().soft_detect(part))
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Non-default optional params ignored, timeout
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=osshutdown', 'immediate=true',
                            'restart=true'},
            ex_timeout=100, ex_synch=False, result=self.etimeout())
        self.assertRaises(
            pexc.VMPowerOffTimeout, power.PowerOp.stop, part,
            opts=popts.PowerOffOpts(legacy_add_parms={
                'one': 1, 'foo': 'bar'}).os_immediate().restart(),
            timeout=100, synchronous=False)
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # VSP normal, fail
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=shutdown'},
            result=self.efail())
        self.assertRaises(
            pexc.VMPowerOffFailure, power.PowerOp.stop, part,
            opts=popts.PowerOffOpts().vsp_normal())
        self.assertEqual(1, self.run_job.call_count)

    def test_pwrop_stop_no_rmc(self):
        """Test PowerOp.stop with bad RMC state."""
        part = self.mock_partition(rmc_state=pvm_bp.RMCState.INACTIVE)
        self.assertRaises(pexc.OSShutdownNoRMC, power.PowerOp.stop,
                          part, opts=popts.PowerOffOpts().os_normal())
        self.run_job.assert_not_called()

    def test_pwron(self):
        """Test the power_on method."""
        lpar = self.mock_partition()
        self.run_job.side_effect = self.validate_run(lpar, "PowerOn")
        power.power_on(lpar, None)
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Try optional parameters
        self.run_job.side_effect = self.validate_run(
            lpar, "PowerOn", ex_parms={
                'bootmode=sms', 'iIPLsource=a', 'remove_optical_name=testVopt',
                'remove_optical_time=30'}, ex_synch=False)
        power.power_on(
            lpar, None, add_parms={
                power.BootMode.KEY: power.BootMode.SMS,
                pvm_lpar.IPLSrc.KEY: pvm_lpar.IPLSrc.A,
                power.RemoveOptical.KEY_TIME: 30,
                power.RemoveOptical.KEY_NAME: 'testVopt'},
            synchronous=False)
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Job timeout, IBMi, implicit remove_optical_time
        ibmi = self.mock_partition(env=pvm_bp.LPARType.OS400)
        self.run_job.side_effect = self.validate_run(
            ibmi, "PowerOn", ex_parms={'remove_optical_name=test',
                                       'remove_optical_time=0'},
            result=self.etimeout())
        self.assertRaises(pexc.VMPowerOnTimeout, power.power_on, ibmi, None,
                          add_parms=power.RemoveOptical.bld_map(name="test"))

        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Job failure, VIOS partition, explicit remove_optical_time
        vios = self.mock_partition(env=pvm_bp.LPARType.VIOS)
        self.run_job.side_effect = self.validate_run(
            vios, "PowerOn", ex_parms={'remove_optical_name=test2',
                                       'remove_optical_time=25'},
            result=self.efail())
        self.assertRaises(
            pexc.VMPowerOnFailure, power.power_on, vios, None,
            add_parms=power.RemoveOptical.bld_map(name="test2", time=25))

        self.assertEqual(1, self.run_job.call_count)

    def test_pwron_already_on(self):
        """PowerOn when the system is already powered on."""
        part = self.mock_partition()
        for prefix in power._ALREADY_POWERED_ON_ERRS:
            self.run_job.side_effect = self.validate_run(
                part, ex_suff="PowerOn", result=self.efail(
                    error="Something %s Something else" % prefix))
            power.power_on(part, None)
            self.assertEqual(1, self.run_job.call_count)
            self.run_job.reset_mock()

    def test_pwroff_force_immed(self):
        """Test power_off with force_immediate=Force.TRUE."""
        # PowerOff with force-immediate works the same regardless of partition
        # type, RMC state, or management partition status.
        for env in (pvm_bp.LPARType.OS400, pvm_bp.LPARType.AIXLINUX,
                    pvm_bp.LPARType.VIOS):
            for rmc in (pvm_bp.RMCState.ACTIVE, pvm_bp.RMCState.BUSY,
                        pvm_bp.RMCState.INACTIVE):
                for mgmt in (True, False):
                    part = self.mock_partition(env=env, rmc_state=rmc,
                                               mgmt=mgmt)
                    self.run_job.side_effect = self.validate_run(
                        part, ex_parms={'operation=shutdown',
                                        'immediate=true'})
                    power.power_off(part, None,
                                    force_immediate=power.Force.TRUE)
                    self.assertEqual(1, self.run_job.call_count)
                    self.run_job.reset_mock()

        # Restart, timeout, additional params ignored
        part = self.mock_partition()
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=shutdown', 'immediate=true',
                            'restart=true'},
            ex_timeout=10, result=self.etimeout())
        self.assertRaises(pexc.VMPowerOffTimeout, power.power_off, part, None,
                          force_immediate=power.Force.TRUE, restart=True,
                          timeout=10, add_parms=dict(one=1))
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # Failure
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=shutdown', 'immediate=true'},
            result=self.efail())
        self.assertRaises(pexc.VMPowerOffFailure, power.power_off, part, None,
                          force_immediate=power.Force.TRUE)
        self.assertEqual(1, self.run_job.call_count)

    def test_pwroff_soft_ibmi_norm(self):
        """Soft PowerOff flow, IBMi, normal (no immediate)."""
        part = self.mock_partition(env=pvm_bp.LPARType.OS400)
        # This works the same whether intervening Job exceptions are Timeout or
        # Failure.
        for exc in (self.etimeout(), self.efail()):
            self.run_job.side_effect = (
                # OS normal
                self.validate_run(
                    part, ex_parms={'operation=osshutdown'}, ex_timeout=100,
                    result=exc,
                    # OS immediate (timeout is defaulted from this point)
                    nxt=self.validate_run(
                        part, ex_parms={'operation=osshutdown',
                                        'immediate=true'}, result=exc,
                        # VSP normal
                        nxt=self.validate_run(
                            part, ex_parms={'operation=shutdown'}, result=exc,
                            # VSP hard (default timeout)
                            nxt=self.validate_run(
                                part, ex_parms={
                                    'operation=shutdown', 'immediate=true'}))))
            )
            # Run it
            power.power_off(part, None, timeout=100)
            self.assertEqual(4, self.run_job.call_count)
            self.run_job.reset_mock()

        # If one of the interim calls succeeds, the operation succeeds.
        self.run_job.side_effect = (
            # OS normal
            self.validate_run(
                part, ex_parms={'operation=osshutdown'}, result=self.efail(),
                # OS immediate (timeout is defaulted from this point)
                nxt=self.validate_run(
                    part, ex_parms={'operation=osshutdown', 'immediate=true'},
                    result=self.etimeout(),
                    # VSP normal - succeeds
                    nxt=self.validate_run(
                        part, ex_parms={'operation=shutdown'},
                        # Not reached
                        nxt=self.fail))))
        power.power_off(part, None)
        self.assertEqual(3, self.run_job.call_count)

    def test_pwroff_soft_standard_timeout(self):
        """Soft PowerOff flow, non-IBMi, with timeout."""
        # When OS shutdown times out, go straight to VSP hard.
        part = self.mock_partition()
        self.run_job.side_effect = (
            # OS normal.  Non-IBMi always adds immediate.
            self.validate_run(
                part, ex_parms={'operation=osshutdown', 'immediate=true'},
                ex_timeout=100, result=self.etimeout(),
                # VSP hard
                nxt=self.validate_run(
                    part, ex_parms={'operation=shutdown', 'immediate=true'}))
        )
        # Run it
        power.power_off(part, None, timeout=100)
        self.assertEqual(2, self.run_job.call_count)

        self.run_job.reset_mock()

        # Same if invoked with immediate.  But since we're running again, add
        # restart and another param; make sure restart comes through but the
        # bogus one is ignored.
        self.run_job.side_effect = (
            # OS immediate (non-IBMi always adds immediate).
            self.validate_run(
                part, ex_parms={'operation=osshutdown', 'immediate=true',
                                'restart=true'},
                ex_timeout=200, result=self.etimeout(),
                # VSP hard
                nxt=self.validate_run(
                    part, ex_parms={'operation=shutdown', 'immediate=true',
                                    'restart=true'}))
        )
        # Run it
        power.power_off(part, None, timeout=200, restart=True,
                        add_parms={'foo': 'bar'})
        self.assertEqual(2, self.run_job.call_count)

    def test_pwroff_soft_no_retry(self):
        """Soft PowerOff, no retry."""
        # When OS shutdown fails with NO_RETRY, fail (no soft flow)
        # IBMi
        part = self.mock_partition(env=pvm_bp.LPARType.OS400)
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=osshutdown'}, result=self.efail())
        self.assertRaises(pexc.VMPowerOffFailure, power.power_off, part, None,
                          force_immediate=power.Force.NO_RETRY)
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # non-IBMi
        part = self.mock_partition()
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=osshutdown', 'immediate=true'},
            result=self.efail())
        self.assertRaises(pexc.VMPowerOffFailure, power.power_off, part, None,
                          force_immediate=power.Force.NO_RETRY)
        self.assertEqual(1, self.run_job.call_count)

    def test_pwroff_soft_standard_fail(self):
        """Soft PowerOff flow, non-IBMi, with Job failure."""
        # When OS shutdown fails (non-timeout), we try VSP normal first.
        part = self.mock_partition()
        self.run_job.side_effect = (
            # OS immediate (non-IBMi always adds immediate).
            # Make sure restart percolates through, bogus params ignored.
            self.validate_run(
                part, ex_parms={'operation=osshutdown', 'immediate=true',
                                'restart=true'},
                ex_timeout=300, result=self.efail(),
                # VSP normal, timeout reset to default
                nxt=self.validate_run(
                    part, ex_parms={
                        'operation=shutdown', 'restart=true'},
                    result=self.efail(),
                    # VSP hard
                    nxt=self.validate_run(
                        part, ex_parms={'operation=shutdown', 'immediate=true',
                                        'restart=true'})))
        )
        power.power_off(part, None, timeout=300, restart=True,
                        add_parms={'foo': 'bar'})
        self.assertEqual(3, self.run_job.call_count)

    def test_pwroff_soft_standard_no_rmc_no_retry(self):
        """Non-IBMi soft PowerOff does VSP normal if RMC is down; no retry."""
        # Behavior is the same for INACTIVE or BUSY
        for rmc in (pvm_bp.RMCState.INACTIVE, pvm_bp.RMCState.BUSY):
            part = self.mock_partition(rmc_state=rmc)
            self.run_job.side_effect = self.validate_run(
                part, ex_parms={'operation=shutdown'}, result=self.efail())
            self.assertRaises(
                pexc.VMPowerOffFailure, power.power_off, part, None,
                force_immediate=power.Force.NO_RETRY)
            self.assertEqual(1, self.run_job.call_count)

            self.run_job.reset_mock()

            # Job timeout & failure do the same (except for final exception).
            self.run_job.side_effect = self.validate_run(
                part, ex_parms={'operation=shutdown'}, result=self.etimeout())
            self.assertRaises(
                pexc.VMPowerOffTimeout, power.power_off, part, None,
                force_immediate=power.Force.NO_RETRY)
            self.assertEqual(1, self.run_job.call_count)

            self.run_job.reset_mock()

    def test_pwroff_already_off(self):
        """PowerOff when the system is already powered off."""
        part = self.mock_partition()
        for prefix in power._ALREADY_POWERED_OFF_ERRS:
            self.run_job.side_effect = self.validate_run(
                part, ex_parms={'operation=osshutdown', 'immediate=true'},
                result=self.efail(error="Foo %s bar" % prefix))
            power.power_off(part, None)
            self.assertEqual(1, self.run_job.call_count)

            self.run_job.reset_mock()

            # If restart was specified, this is a failure.  (Force, to KISS)
            self.run_job.side_effect = self.validate_run(
                part, ex_parms={'operation=shutdown', 'immediate=true',
                                'restart=true'},
                result=self.efail(error="Foo %s bar" % prefix))
            self.assertRaises(pexc.VMPowerOffFailure, power.power_off, part,
                              None, restart=True,
                              force_immediate=power.Force.TRUE)
            self.assertEqual(1, self.run_job.call_count)

            self.run_job.reset_mock()

    def test_pwroff_new_opts(self):
        """Test power_off where add_parms is PowerOffOpts (not legacy)."""
        part = self.mock_partition()

        # VSP hard
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=shutdown', 'immediate=true'})
        power.power_off(part, None, add_parms=popts.PowerOffOpts().vsp_hard())
        self.assertEqual(1, self.run_job.call_count)

        self.run_job.reset_mock()

        # VSP normal
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=shutdown'})
        power.power_off(part, None,
                        add_parms=popts.PowerOffOpts().vsp_normal())

        self.run_job.reset_mock()

        # OS immediate
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=osshutdown', 'immediate=true'})
        power.power_off(part, None,
                        add_parms=popts.PowerOffOpts().os_immediate())

        self.run_job.reset_mock()

        # OS normal
        self.run_job.side_effect = self.validate_run(
            part, ex_parms={'operation=osshutdown'})
        power.power_off(part, None, add_parms=popts.PowerOffOpts().os_normal())

    @mock.patch('pypowervm.tasks.power._power_off_progressive')
    def test_pwroff_progressive(self, mock_prog_internal):
        # The internal _power_off_progressive is exercised via the existing
        # tests for power_off. This test just ensures the public
        # power_off_progressive calls it appropriately.

        # Default kwargs
        power.power_off_progressive('part')
        mock_prog_internal.assert_called_once_with(
            'part', 1800, False, ibmi_immed=False)

        mock_prog_internal.reset_mock()

        # Non-default kwargs
        power.power_off_progressive('part', restart=True, ibmi_immed=True,
                                    timeout=10)
        mock_prog_internal.assert_called_once_with(
            'part', 10, True, ibmi_immed=True)
