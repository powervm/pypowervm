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

"""Test for the monitoring functions."""

import datetime

import mock
import testtools

from pypowervm import entities as pvm_e
from pypowervm.tasks.monitor import util as pvm_t_mon
from pypowervm.tests.tasks import util as tju
from pypowervm.tests import test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers import monitor as pvm_mon
from pypowervm.wrappers.pcm import lpar as pvm_mon_lpar
from pypowervm.wrappers.pcm import phyp as pvm_mon_phyp
from pypowervm.wrappers.pcm import vios as pvm_mon_vios


PHYP_DATA = 'phyp_pcm_data.txt'
VIOS_DATA = 'vios_pcm_data.txt'
LPAR_DATA = 'lpar_pcm_data.txt'
LTM_FEED = 'ltm_feed2.txt'


class TestMonitors(testtools.TestCase):

    def setUp(self):
        super(TestMonitors, self).setUp()

        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemoteHMCTraits))
        self.adpt = self.adptfx.adpt

    def test_query_ltm_feed(self):
        self.adpt.read_by_path.return_value = tju.load_file(LTM_FEED)
        feed = pvm_t_mon.query_ltm_feed(self.adpt, 'host_uuid')

        # Make sure the feed is correct.  Our sample data has 130 elements
        # in the feed.
        self.assertEqual(130, len(feed))

        # Make sure each element is a LTMMetric
        for mon in feed:
            self.assertIsInstance(mon, pvm_mon.LTMMetrics)

        self.assertEqual(1, self.adpt.read_by_path.call_count)

    def test_ensure_ltm_monitors(self):
        """Verifies that the LTM monitors can be turned on."""
        resp = tju.load_file('pcm_pref.txt')
        self.adpt.read_by_href.return_value = resp

        # Create a side effect that can validate the input to the update
        def validate_of_update(*kargs, **kwargs):
            element = kargs[0]
            etag = kargs[1]
            self.assertIsNotNone(element)
            self.assertEqual('-215935973', etag)

            # Wrap the element so we can validate it.
            pref = pvm_mon.PcmPref.wrap(pvm_e.Entry({'etag': etag},
                                                    element, self.adpt))

            self.assertFalse(pref.compute_ltm_enabled)
            self.assertTrue(pref.ltm_enabled)
            self.assertFalse(pref.stm_enabled)
            self.assertFalse(pref.aggregation_enabled)
            return element
        self.adpt.update.side_effect = validate_of_update

        # This will invoke the validate_of_update
        pvm_t_mon.ensure_ltm_monitors(self.adpt, 'host_uuid')

        # Make sure the update was in fact invoked though
        self.assertEqual(1, self.adpt.update.call_count)

    def test_ensure_ltm_monitors_non_default(self):
        """Verifies that the LTM monitors with different default inputs"""
        resp = tju.load_file('pcm_pref.txt')
        self.adpt.read_by_href.return_value = resp

        # Create a side effect that can validate the input to the update
        def validate_of_update(*kargs, **kwargs):
            element = kargs[0]
            etag = kargs[1]
            self.assertIsNotNone(element)

            # Wrap the element so we can validate it.
            pref = pvm_mon.PcmPref.wrap(pvm_e.Entry({'etag': etag},
                                                    element, self.adpt))

            self.assertTrue(pref.compute_ltm_enabled)
            self.assertTrue(pref.ltm_enabled)
            self.assertFalse(pref.stm_enabled)
            self.assertTrue(pref.aggregation_enabled)
            return element
        self.adpt.update.side_effect = validate_of_update

        # This will invoke the validate_of_update
        pvm_t_mon.ensure_ltm_monitors(self.adpt, 'host_uuid', compute_ltm=True,
                                      override_to_default=True)

        # Make sure the update was in fact invoked though
        self.assertEqual(1, self.adpt.update.call_count)

    def _load(self, file_name):
        """Loads a file."""
        return pvmhttp.PVMFile(file_name).body

    def test_parse_to_vm_metrics(self):
        """Verifies the parsing to LPAR metrics."""
        phyp_resp = self._load(PHYP_DATA)
        phyp_data = pvm_mon_phyp.PhypInfo(phyp_resp)

        vios_resp = self._load(VIOS_DATA)
        vios_data = pvm_mon_vios.ViosInfo(vios_resp)

        lpar_resp = self._load(LPAR_DATA)
        lpar_data = pvm_mon_lpar.LparInfo(lpar_resp)

        metrics = pvm_t_mon.vm_metrics(phyp_data, [vios_data], lpar_data)
        self.assertIsNotNone(metrics)

        # In the test data, there are 5 LPARs total.
        self.assertEqual(5, len(metrics.keys()))

        # Validate a metric with live data
        good_vm = '42AD4FD4-DC64-4935-9E29-9B7C6F35AFCC'
        metric = metrics.get(good_vm)
        self.assertIsNotNone(metric)

        self.assertIsNotNone(metric.network)
        self.assertIsNotNone(metric.storage)
        self.assertIsNotNone(metric.processor)
        self.assertIsNotNone(metric.memory)

        # Memory validation
        self.assertEqual(20480, metric.memory.logical_mem)
        self.assertEqual(20480, metric.memory.backed_physical_mem)
        self.assertEqual(80, metric.memory.pct_real_mem_avbl)
        self.assertEqual(1024, metric.memory.total_pg_count)
        self.assertEqual(512, metric.memory.free_pg_count)
        self.assertEqual(1048576, metric.memory.real_mem_size_bytes)
        self.assertEqual(61, metric.memory.pct_real_mem_free)
        self.assertEqual(25, metric.memory.vm_pg_out_rate)

        # Processor validation
        self.assertEqual(0, metric.processor.pool_id)
        self.assertEqual('uncap', metric.processor.mode)
        self.assertEqual(4, metric.processor.virt_procs)
        self.assertEqual(.4, metric.processor.proc_units)

        # Network validation
        self.assertEqual(1, len(metric.network.cnas))
        cna = metric.network.cnas[0]
        self.assertEqual(2227, cna.vlan_id)
        self.assertEqual(0, cna.vswitch_id)
        self.assertEqual('U8247.22L.2125D4A-V2-C2', cna.physical_location)
        self.assertEqual(10, cna.received_packets)
        self.assertEqual(100, cna.sent_packets)
        self.assertEqual(5, cna.dropped_packets)
        self.assertEqual(100, cna.sent_bytes)
        self.assertEqual(10000, cna.received_bytes)

        # Storage validation
        self.assertEqual(1, len(metric.storage.virt_adpts))
        self.assertEqual(0, len(metric.storage.vfc_adpts))
        vadpt = metric.storage.virt_adpts[0]
        self.assertEqual('virtual', vadpt.type)
        self.assertEqual('vhost0', vadpt.name)
        self.assertEqual('U8247.22L.2125D4A-V1-C1000', vadpt.physical_location)
        self.assertEqual(1074, vadpt.num_reads)
        self.assertEqual(1075, vadpt.num_writes)
        self.assertEqual(549888, vadpt.read_bytes)
        self.assertEqual(550400, vadpt.write_bytes)

        # Validate a metric for a system that was powered off.
        bad_vm = '3B0237F9-26F1-41C7-BE57-A08C9452AD9D'
        metric = metrics.get(bad_vm)
        self.assertIsNotNone(metric)

        self.assertIsNotNone(metric.processor)
        self.assertIsNotNone(metric.memory)
        # For powered off VM, OS specific memory metrics are None
        self.assertIsNone(metric.memory.pct_real_mem_avbl)
        self.assertIsNone(metric.memory.total_pg_count)
        self.assertIsNone(metric.memory.free_pg_count)
        self.assertIsNone(metric.memory.active_pg_count)
        self.assertIsNone(metric.memory.real_mem_size_bytes)
        # For powered off VM, the free memory is 100 percent.
        self.assertEqual(100, metric.memory.pct_real_mem_free)
        # For powered off VM, the page in/out rate is 0.
        self.assertEqual(0, metric.memory.vm_pg_out_rate)
        self.assertIsNone(metric.storage)
        self.assertIsNone(metric.network)

        # Take a VM which has entry in phyp data but not in PCM Lpar data.
        # Assert that it has been correctly parsed and memory metrics
        # are set to default values.
        vm_in_phyp_not_in_lpar_pcm = '66A2E886-D05D-42F4-87E0-C3BA02CF7C7E'
        metric = metrics.get(vm_in_phyp_not_in_lpar_pcm)
        self.assertIsNotNone(metric)
        self.assertIsNotNone(metric.processor)
        self.assertIsNotNone(metric.memory)
        self.assertEqual(.2, metric.processor.proc_units)
        self.assertEqual(0, metric.memory.pct_real_mem_free)
        self.assertEqual(-1, metric.memory.vm_pg_in_rate)

    def test_vm_metrics_no_phyp_data(self):
        self.assertEqual({}, pvm_t_mon.vm_metrics(None, [], None))

    @mock.patch('pypowervm.tasks.monitor.util.query_ltm_feed')
    def test_latest_stats(self, mock_ltm_feed):
        # Set up the return data.
        mock_phyp_metric = mock.MagicMock()
        mock_phyp_metric.category = 'phyp'
        mock_phyp_metric.updated_datetime = 1
        mock_phyp_metric.link = 'bad'

        mock_phyp2_metric = mock.MagicMock()
        mock_phyp2_metric.category = 'phyp'
        mock_phyp2_metric.updated_datetime = 2
        mock_phyp2_metric.link = 'phyp'

        mock_vio1_metric = mock.MagicMock()
        mock_vio1_metric.category = 'vios_1'
        mock_vio1_metric.updated_datetime = 1
        mock_vio1_metric.link = 'bad'

        mock_vio2_metric = mock.MagicMock()
        mock_vio2_metric.category = 'vios_1'
        mock_vio2_metric.updated_datetime = 2
        mock_vio2_metric.link = 'vio'

        mock_vio3_metric = mock.MagicMock()
        mock_vio3_metric.category = 'vios_3'
        mock_vio3_metric.updated_datetime = 2
        mock_vio3_metric.link = 'vio'

        mock_lpar1_metric = mock.MagicMock()
        mock_lpar1_metric.category = 'lpar'
        mock_lpar1_metric.updated_datetime = 2
        mock_lpar1_metric.link = 'lpar'

        # Reset as this was invoked once up front.
        mock_ltm_feed.reset_mock()
        mock_ltm_feed.return_value = [mock_phyp_metric, mock_phyp2_metric,
                                      mock_vio1_metric, mock_vio2_metric,
                                      mock_vio3_metric, mock_lpar1_metric]

        # Data for the responses.
        phyp_resp = self._load(PHYP_DATA)
        vios_resp = self._load(VIOS_DATA)

        def validate_read(link, xag=None):
            resp = mock.MagicMock()
            if link == 'phyp':
                resp.body = phyp_resp
                return resp
            elif link == 'vio':
                resp.body = vios_resp
                return resp
            elif link == 'lpar':
                resp.body = self._load(LPAR_DATA)
                return resp
            else:
                self.fail()

        self.adpt.read_by_href.side_effect = validate_read

        resp_date, resp_phyp, resp_vioses, resp_lpars = (
            pvm_t_mon.latest_stats(self.adpt, mock.Mock()))
        self.assertIsNotNone(resp_phyp)
        self.assertIsInstance(resp_phyp, pvm_mon_phyp.PhypInfo)
        self.assertEqual(2, len(resp_vioses))
        self.assertIsInstance(resp_vioses[0], pvm_mon_vios.ViosInfo)
        self.assertIsInstance(resp_vioses[1], pvm_mon_vios.ViosInfo)
        self.assertEqual(6, len(resp_lpars.lpars_util))
        self.assertIsInstance(resp_lpars, pvm_mon_lpar.LparInfo)

        # Invoke again, but set to ignore vioses
        resp_date, resp_phyp, resp_vioses, resp_lpars = (
            pvm_t_mon.latest_stats(self.adpt, mock.Mock(), include_vio=False))
        self.assertIsNotNone(resp_phyp)
        self.assertIsInstance(resp_phyp, pvm_mon_phyp.PhypInfo)
        self.assertEqual(0, len(resp_vioses))

    @mock.patch('pypowervm.tasks.monitor.util.vm_metrics')
    @mock.patch('pypowervm.tasks.monitor.util.query_ltm_feed')
    def test_latest_stats_no_data(self, mock_ltm_feed, mock_vm_metrics):
        # Set up the return data.
        mock_vio3_metric = mock.MagicMock()
        mock_vio3_metric.category = 'vios_3'
        mock_vio3_metric.updated_datetime = 2

        # Reset as this was invoked once up front.
        mock_ltm_feed.reset_mock()
        mock_ltm_feed.return_value = [mock_vio3_metric]

        # Call the system.
        resp_date, resp_phyp, resp_vios, resp_lpars = (
            pvm_t_mon.latest_stats(mock.Mock(), mock.Mock()))
        self.assertIsNotNone(resp_date)
        self.assertIsNone(resp_phyp)
        self.assertIsNone(resp_vios)
        self.assertIsNone(resp_lpars)


class TestMetricsCache(testtools.TestCase):
    """Validates the LparMetricCache."""

    def setUp(self):
        super(TestMetricsCache, self).setUp()

        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemoteHMCTraits))
        self.adpt = self.adptfx.adpt

    @mock.patch('pypowervm.tasks.monitor.util.vm_metrics')
    @mock.patch('pypowervm.tasks.monitor.util.latest_stats')
    @mock.patch('pypowervm.tasks.monitor.util.ensure_ltm_monitors')
    def test_refresh(self, mock_ensure_monitor, mock_stats,
                     mock_vm_metrics):
        ret1 = None
        ret2 = {'lpar_uuid': 2}
        ret3 = {'lpar_uuid': 3}

        date_ret1 = datetime.datetime.now()
        date_ret2 = date_ret1 + datetime.timedelta(milliseconds=250)
        date_ret3 = date_ret2 + datetime.timedelta(milliseconds=250)

        mock_stats.side_effect = [
            (date_ret1, mock.Mock(), mock.Mock(), mock.Mock()),
            (date_ret2, mock.Mock(), mock.Mock(), mock.Mock()),
            (date_ret3, mock.Mock(), mock.Mock(), mock.Mock())]
        mock_vm_metrics.side_effect = [ret1, ret2, ret3]

        # Creation invokes the refresh once automatically.
        metric_cache = pvm_t_mon.LparMetricCache(self.adpt, 'host_uuid',
                                                 refresh_delta=.25)

        # Make sure the current and prev are none.
        self.assertEqual(date_ret1, metric_cache.cur_date)
        self.assertIsNone(metric_cache.cur_metric)
        self.assertIsNone(metric_cache.prev_date)
        self.assertIsNone(metric_cache.prev_metric)

        # The current metric should detect that it hasn't been enough time
        # and pass us none.
        cur_date, cur_metric = metric_cache.get_latest_metric('lpar_uuid')
        self.assertEqual(date_ret1, cur_date)
        self.assertIsNone(cur_metric)
        prev_date, prev_metric = metric_cache.get_previous_metric('lpar_uuid')
        self.assertIsNone(prev_date)
        self.assertIsNone(prev_metric)

        # Force the update by stating we're older than we are.
        pre_date = metric_cache.cur_date - datetime.timedelta(milliseconds=250)
        metric_cache.cur_date = pre_date

        # Verify that we've incremented
        cur_date, cur_metric = metric_cache.get_latest_metric('lpar_uuid')
        self.assertEqual(date_ret2, cur_date)
        self.assertEqual(2, cur_metric)
        prev_date, prev_metric = metric_cache.get_previous_metric('lpar_uuid')
        self.assertEqual(pre_date, prev_date)
        self.assertIsNone(prev_metric)

        # Verify that if we set the date to now, we don't increment
        metric_cache.cur_date = datetime.datetime.now()
        cur_date, cur_metric = metric_cache.get_latest_metric('lpar_uuid')
        self.assertEqual(2, cur_metric)
        prev_date, prev_metric = metric_cache.get_previous_metric('lpar_uuid')
        self.assertEqual(pre_date, prev_date)
        self.assertIsNone(prev_metric)

        # Delay one more time.  Make sure the previous values are now set.
        pre_date = metric_cache.cur_date - datetime.timedelta(milliseconds=250)
        metric_cache.cur_date = pre_date

        cur_date, cur_metric = metric_cache.get_latest_metric('lpar_uuid')
        self.assertEqual(date_ret3, cur_date)
        self.assertEqual(3, cur_metric)
        prev_date, prev_metric = metric_cache.get_previous_metric('lpar_uuid')
        self.assertEqual(pre_date, prev_date)
        self.assertEqual(2, prev_metric)
