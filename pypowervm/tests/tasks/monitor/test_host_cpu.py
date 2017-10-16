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

import logging
import mock
import testtools

from pypowervm.tasks.monitor import host_cpu
import pypowervm.tests.test_fixtures as pvm_fx

LOG = logging.getLogger(__name__)


class TestHostCPUBase(testtools.TestCase):

    def setUp(self):
        super(TestHostCPUBase, self).setUp()

        # Fixture for the adapter
        self.adpt = self.useFixture(pvm_fx.AdapterFx()).adpt
        ensure_ltm_p = mock.patch(
            'pypowervm.tasks.monitor.util.ensure_ltm_monitors')
        refresh_p = mock.patch(
            'pypowervm.tasks.monitor.util.MetricCache._refresh_if_needed')
        self.mock_ensure_ltm_monitors = ensure_ltm_p.start()
        self.mock_refresh_if_needed = refresh_p.start()
        self.addCleanup(ensure_ltm_p.stop)
        self.addCleanup(refresh_p.stop)


class TestHostCPUFreq(TestHostCPUBase):

    def test_get_cpu_freq(self):
        # _get_cpu_freq() should return an int based on the clock line of the
        # file
        m = mock.mock_open(
            read_data='processor : 12\nclock : 4116.000000MHz\n')
        m.return_value.__iter__ = lambda self: iter(self.readline, '')
        with mock.patch('pypowervm.tasks.monitor.host_cpu.open', m):
            host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        self.assertEqual(host_stats.cpu_freq, 4116)


class TestHostCPUMetricCache(TestHostCPUBase):

    def setUp(self):
        super(TestHostCPUMetricCache, self).setUp()
        get_cpu_freq_p = mock.patch('pypowervm.tasks.monitor.host_cpu.'
                                    'HostCPUMetricCache._get_cpu_freq')
        self.mock_get_cpu_freq = get_cpu_freq_p.start()
        self.addCleanup(get_cpu_freq_p.stop)

    def _get_sample(self, lpar_id, sample):
        for lpar in sample.lpars:
            if lpar.id == lpar_id:
                return lpar
        return None

    def test_refresh(self):
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        host_stats.refresh()
        # Called once in init and once in refesh()
        self.assertEqual(self.mock_refresh_if_needed.call_count, 2)

    @mock.patch('pypowervm.tasks.monitor.host_cpu.HostCPUMetricCache.'
                '_get_fw_cycles_delta')
    @mock.patch('pypowervm.tasks.monitor.host_cpu.HostCPUMetricCache.'
                '_get_total_cycles_delta')
    @mock.patch('pypowervm.tasks.monitor.host_cpu.HostCPUMetricCache.'
                '_gather_user_cycles_delta')
    def test_update_internal_metric(self, mock_user_cycles, mock_total_cycles,
                                    mock_fw_cycles):

        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')

        # Make sure totals are 0 if there is no data.
        host_stats.cur_phyp = None
        host_stats._update_internal_metric()
        self.assertEqual(host_stats.total_cycles, 0)
        self.assertEqual(host_stats.total_user_cycles, 0)
        self.assertEqual(host_stats.total_fw_cycles, 0)

        # Create mock phyp objects to test with
        mock_phyp = mock.MagicMock()
        mock_fw_cycles.return_value = 58599310268
        mock_prev_phyp = mock.MagicMock()

        # Mock methods not currently under test
        mock_user_cycles.return_value = 50
        mock_total_cycles.return_value = 1.6125945178663e+16

        # Make the 'prev' the current...for the first pass
        host_stats.cur_phyp = mock_prev_phyp
        host_stats.prev_phyp = None
        host_stats._update_internal_metric()

        self.assertEqual(host_stats.total_cycles, 1.6125945178663e+16)
        self.assertEqual(host_stats.total_user_cycles, 50)
        self.assertEqual(host_stats.total_fw_cycles, 58599310268)

        # Mock methods not currently under test
        mock_user_cycles.return_value = 30010090000
        mock_total_cycles.return_value = 1.6125945178663e+16

        # Now 'increment' it with a new current/previous
        host_stats.cur_phyp = mock_phyp
        host_stats.prev_phyp = mock_prev_phyp
        mock_user_cycles.return_value = 100000
        host_stats._update_internal_metric()

        # Validate the new values. Note that these values are 'higher' because
        # they are running totals.
        new_fw = 58599310268 * 2
        new_total = 1.6125945178663e+16 * 2
        self.assertEqual(host_stats.total_cycles, new_total)
        self.assertEqual(host_stats.total_user_cycles, 100050)
        self.assertEqual(host_stats.total_fw_cycles, new_fw)

    @mock.patch('pypowervm.tasks.monitor.host_cpu.HostCPUMetricCache.'
                '_get_fw_cycles_delta')
    @mock.patch('pypowervm.tasks.monitor.host_cpu.HostCPUMetricCache.'
                '_get_total_cycles_delta')
    @mock.patch('pypowervm.tasks.monitor.host_cpu.HostCPUMetricCache.'
                '_gather_user_cycles_delta')
    def test_update_internal_metric_bad_total(
            self, mock_user_cycles, mock_tot_cycles, mock_fw_cycles):
        """Validates that if the total cycles are off, we handle."""
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        mock_user_cycles.return_value = 30010090000
        mock_fw_cycles.return_value = 58599310268

        # Mock the total cycles to some really low number.
        mock_tot_cycles.return_value = 5

        # Create mock phyp objects to test with
        mock_phyp = mock.MagicMock()
        mock_prev_phyp = mock.MagicMock()
        mock_phyp.sample.system_firmware.utilized_proc_cycles = 58599310268

        # Run the actual test - 'increment' it with a new current/previous
        host_stats.cur_phyp = mock_phyp
        host_stats.prev_phyp = mock_prev_phyp
        host_stats._update_internal_metric()

        # Validate the results. The total cycles are set to the sum of user
        # and fw when the total is bad.
        self.assertEqual(host_stats.total_cycles, 88609400268)
        self.assertEqual(host_stats.total_user_cycles, 30010090000)
        self.assertEqual(host_stats.total_fw_cycles, 58599310268)

    @mock.patch('pypowervm.tasks.monitor.host_cpu.HostCPUMetricCache.'
                '_delta_proc_cycles')
    def test_gather_user_cycles_delta(self, mock_cycles):
        # Crete objects to test with
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        mock_phyp = mock.MagicMock()
        mock_prev_phyp = mock.MagicMock()

        # Mock methods not currently under test
        mock_cycles.return_value = 15005045000

        # Test that we can run with previous samples and then without.
        host_stats.cur_phyp = mock_phyp
        host_stats.prev_phyp = mock_prev_phyp
        resp = host_stats._gather_user_cycles_delta()
        self.assertEqual(30010090000, resp)

        # Now test if there is no previous sample.  Since there are no previous
        # samples, it will be 0.
        host_stats.prev_phyp = None
        mock_cycles.return_value = 0
        resp = host_stats._gather_user_cycles_delta()
        self.assertEqual(0, resp)

    def test_delta_proc_cycles(self):
        # Create objects to test with
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        mock_phyp, mock_prev_phyp = self._get_mock_phyps()

        # Test that a previous sample allows us to gather the delta across all
        # of the VMs.  This should take into account the scenario where a LPAR
        # is deleted and a new one takes its place (LPAR ID 6)
        delta = host_stats._delta_proc_cycles(mock_phyp.sample.lpars,
                                              mock_prev_phyp.sample.lpars)
        self.assertEqual(10010000000, delta)

        # Now test as if there is no previous data.  This results in 0 as they
        # could have all been LPMs with months of cycles (rather than 30
        # seconds delta).
        delta2 = host_stats._delta_proc_cycles(mock_phyp.sample.lpars, None)
        self.assertEqual(0, delta2)
        self.assertNotEqual(delta2, delta)

        # Test that if previous sample had 0 values, the sample is not
        # considered for evaluation, and resultant delta cycles is 0.
        prev_lpar_sample = mock_prev_phyp.sample.lpars[0].processor
        prev_lpar_sample.util_cap_proc_cycles = 0
        prev_lpar_sample.util_uncap_proc_cycles = 0
        prev_lpar_sample.idle_proc_cycles = 0
        delta3 = host_stats._delta_proc_cycles(mock_phyp.sample.lpars,
                                               mock_prev_phyp.sample.lpars)
        self.assertEqual(0, delta3)

    def test_delta_user_cycles(self):
        # Create objects to test with
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        mock_phyp, mock_prev_phyp = self._get_mock_phyps()
        mock_phyp.sample.lpars[0].processor.util_cap_proc_cycles = 250000
        mock_phyp.sample.lpars[0].processor.util_uncap_proc_cycles = 250000
        mock_phyp.sample.lpars[0].processor.idle_proc_cycles = 500
        mock_prev_phyp.sample.lpars[0].processor.util_cap_proc_cycles = 0
        num = 455000
        mock_prev_phyp.sample.lpars[0].processor.util_uncap_proc_cycles = num
        mock_prev_phyp.sample.lpars[0].processor.idle_proc_cycles = 1000

        # Test that a previous sample allows us to gather just the delta.
        new_elem = self._get_sample(4, mock_phyp.sample)
        old_elem = self._get_sample(4, mock_prev_phyp.sample)
        delta = host_stats._delta_user_cycles(new_elem, old_elem)
        self.assertEqual(45500, delta)

        # Validate the scenario where we don't have a previous.  Should default
        # to 0, given no context of why the previous sample did not have the
        # data.
        delta = host_stats._delta_user_cycles(new_elem, None)
        self.assertEqual(0, delta)

    def test_find_prev_sample(self):
        # Create objects to test with
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        mock_lpar_4A = mock.Mock()
        mock_lpar_4A.configure_mock(id=4, name='A')
        mock_lpar_4A.processor = mock.MagicMock(
            entitled_proc_cycles=500000)
        mock_lpar_6A = mock.Mock()
        mock_lpar_6A.configure_mock(id=6, name='A')
        mock_lpar_6B = mock.Mock()
        mock_lpar_6B.configure_mock(id=6, name='B')
        mock_phyp = mock.MagicMock(sample=mock.MagicMock(lpars=[mock_lpar_4A,
                                                                mock_lpar_6A]))
        mock_prev_phyp = mock.MagicMock(sample=mock.MagicMock(
            lpars=[mock_lpar_4A, mock_lpar_6B]))

        # Sample 6 in the current shouldn't match the previous.  It has the
        # same LPAR ID, but a different name.  This is considered different
        new_elem = self._get_sample(6, mock_phyp.sample)
        prev = host_stats._find_prev_sample(new_elem,
                                            mock_prev_phyp.sample.lpars)
        self.assertIsNone(prev)

        # Lpar 4 should be in the old one.  Match that up.
        new_elem = self._get_sample(4, mock_phyp.sample)
        prev = host_stats._find_prev_sample(new_elem,
                                            mock_prev_phyp.sample.lpars)
        self.assertIsNotNone(prev)
        self.assertEqual(500000, prev.processor.entitled_proc_cycles)

        # Test that we get None back if there are no previous samples
        prev = host_stats._find_prev_sample(new_elem, None)
        self.assertIsNone(prev)

    def test_get_total_cycles(self):
        # Mock objects to test with
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')
        mock_phyp = mock.MagicMock()
        mock_phyp.sample = mock.MagicMock()
        mock_phyp.sample.processor.configurable_proc_units = 5
        mock_phyp.sample.time_based_cycles = 500
        host_stats.cur_phyp = mock_phyp

        # Make sure we get the full system cycles.
        max_cycles = host_stats._get_total_cycles_delta()
        self.assertEqual(2500, max_cycles)

    def test_get_total_cycles_diff_cores(self):
        # Mock objects to test with
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')

        # Latest Sample
        mock_phyp = mock.MagicMock(sample=mock.MagicMock())
        mock_phyp.sample.processor.configurable_proc_units = 48
        mock_phyp.sample.time_based_cycles = 1000
        host_stats.cur_phyp = mock_phyp

        # Earlier sample.  Use a higher proc unit sample
        mock_phyp = mock.MagicMock(sample=mock.MagicMock())
        mock_phyp.sample.processor.configurable_proc_units = 1
        mock_phyp.sample.time_based_cycles = 500
        host_stats.prev_phyp = mock_phyp

        # Make sure we get the full system cycles.
        max_cycles = host_stats._get_total_cycles_delta()
        self.assertEqual(24000, max_cycles)

    def test_get_firmware_cycles(self):
        # Mock objects to test with
        host_stats = host_cpu.HostCPUMetricCache(self.adpt, 'host_uuid')

        # Latest Sample
        mock_phyp = mock.MagicMock(sample=mock.MagicMock())
        mock_phyp.sample.system_firmware.utilized_proc_cycles = 2000
        # Previous Sample
        prev_phyp = mock.MagicMock(sample=mock.MagicMock())
        prev_phyp.sample.system_firmware.utilized_proc_cycles = 1000

        host_stats.cur_phyp = mock_phyp
        host_stats.prev_phyp = prev_phyp
        # Get delta
        delta_firmware_cycles = host_stats._get_fw_cycles_delta()
        self.assertEqual(1000, delta_firmware_cycles)

    def _get_mock_phyps(self):
        """Helper method to return cur_phyp and prev_phyp."""
        mock_lpar_4A = mock.Mock()
        mock_lpar_4A.configure_mock(id=4, name='A')
        mock_lpar_4A.processor = mock.MagicMock(
            util_cap_proc_cycles=5005045000,
            util_uncap_proc_cycles=5005045000,
            idle_proc_cycles=10000)
        mock_lpar_4A_prev = mock.Mock()
        mock_lpar_4A_prev.configure_mock(id=4, name='A')
        mock_lpar_4A_prev.processor = mock.MagicMock(
            util_cap_proc_cycles=40000,
            util_uncap_proc_cycles=40000,
            idle_proc_cycles=0)
        mock_phyp = mock.MagicMock(sample=mock.MagicMock(lpars=[mock_lpar_4A]))
        mock_prev_phyp = mock.MagicMock(
            sample=mock.MagicMock(lpars=[mock_lpar_4A_prev]))
        return mock_phyp, mock_prev_phyp
