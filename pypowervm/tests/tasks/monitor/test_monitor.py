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
import os

import mock
import testtools

from pypowervm import entities as pvm_e
from pypowervm.tasks.monitor import util as pvm_t_mon
from pypowervm.tests.tasks import util as tju
from pypowervm.tests import test_fixtures as fx
from pypowervm.tests.wrappers.util import pvmhttp
from pypowervm.wrappers import monitor as pvm_mon


class TestMonitors(testtools.TestCase):

    def setUp(self):
        super(TestMonitors, self).setUp()

        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemoteHMCTraits))
        self.adpt = self.adptfx.adpt

    def test_query_ltm_feed(self):
        self.adpt.read_by_path.return_value = tju.load_file('ltm_feed.txt')
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
        resp = tju.load_file('pcm_pref_feed.txt')
        self.adpt.read_by_href.return_value = resp

        # Create a side effect that can validate the input to the update
        def validate_of_update(*kargs, **kwargs):
            element = kargs[0]
            etag = kargs[1]
            self.assertIsNotNone(element)
            self.assertEqual('1430365985674', etag)

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
        pvm_t_mon.ensure_ltm_monitors(self.adpt, 'host_uuid')

        # Make sure the update was in fact invoked though
        self.assertEqual(1, self.adpt.update.call_count)

    def _load(self, path):
        """Loads a file."""
        dirname = os.path.dirname(__file__)
        file_name = os.path.join(dirname, path)
        return pvmhttp.PVMFile(file_name).body

    def test_parse_to_vm_metrics(self):
        """Verifies the parsing to LPAR metrics."""
        vios_resp = self._load('../../wrappers/pcm/data/vios_data.txt')
        phyp_resp = self._load('../../wrappers/pcm/data/phyp_data.txt')

        mock_phyp = mock.MagicMock()
        mock_phyp.body = phyp_resp
        mock_vios = mock.MagicMock()
        mock_vios.body = vios_resp

        self.adpt.read_by_href.side_effect = [mock_phyp, mock_vios]

        metrics = pvm_t_mon.vm_metrics(self.adpt, mock.MagicMock(),
                                       [mock.MagicMock()])
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
        self.assertIsNone(metric.storage)
        self.assertIsNone(metric.network)


class TestMetricsCache(testtools.TestCase):
    """Validates the LparMetricCache."""

    def setUp(self):
        super(TestMetricsCache, self).setUp()

        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemoteHMCTraits))
        self.adpt = self.adptfx.adpt

    @mock.patch('pypowervm.tasks.monitor.util.vm_metrics')
    @mock.patch('pypowervm.tasks.monitor.util.query_ltm_feed')
    @mock.patch('pypowervm.tasks.monitor.util.ensure_ltm_monitors')
    def test_parse_current_feed(self, mock_ensure_monitor, mock_ltm_feed,
                                mock_vm_metrics):
        # Build cache with original mock
        metric_cache = pvm_t_mon.LparMetricCache(self.adpt, 'host_uuid',
                                                 refresh_delta=.25)

        # Set up the return data.
        mock_phyp_metric = mock.MagicMock()
        mock_phyp_metric.category = 'phyp'
        mock_phyp_metric.updated_datetime = 1

        mock_phyp2_metric = mock.MagicMock()
        mock_phyp2_metric.category = 'phyp'
        mock_phyp2_metric.updated_datetime = 2

        mock_vio1_metric = mock.MagicMock()
        mock_vio1_metric.category = 'vios_1'
        mock_vio1_metric.updated_datetime = 1

        mock_vio2_metric = mock.MagicMock()
        mock_vio2_metric.category = 'vios_1'
        mock_vio2_metric.updated_datetime = 2

        mock_vio3_metric = mock.MagicMock()
        mock_vio3_metric.category = 'vios_3'
        mock_vio3_metric.updated_datetime = 2

        # Reset as this was invoked once up front.
        mock_ltm_feed.reset_mock()
        mock_ltm_feed.return_value = [mock_phyp_metric, mock_phyp2_metric,
                                      mock_vio1_metric, mock_vio2_metric,
                                      mock_vio3_metric]

        # Set up a validate
        def validate_read(adpt, latest_phyp, vios_metrics):
            self.assertEqual(2, len(vios_metrics))
            self.assertEqual([mock_vio2_metric, mock_vio3_metric],
                             vios_metrics)
            self.assertEqual(mock_phyp2_metric, latest_phyp)
        mock_vm_metrics.side_effect = validate_read

        resp_date, resp_response = metric_cache._parse_current_feed()
        self.assertIsNotNone(resp_date)

    @mock.patch('pypowervm.tasks.monitor.util.vm_metrics')
    @mock.patch('pypowervm.tasks.monitor.util.query_ltm_feed')
    @mock.patch('pypowervm.tasks.monitor.util.ensure_ltm_monitors')
    def test_parse_current_feed_no_data(self, mock_ensure_monitor,
                                        mock_ltm_feed, mock_vm_metrics):
        # Build cache with original mock
        metric_cache = pvm_t_mon.LparMetricCache(self.adpt, 'host_uuid',
                                                 refresh_delta=.25)

        # Set up the return data.
        mock_vio3_metric = mock.MagicMock()
        mock_vio3_metric.category = 'vios_3'
        mock_vio3_metric.updated_datetime = 2

        # Reset as this was invoked once up front.
        mock_ltm_feed.reset_mock()
        mock_ltm_feed.return_value = [mock_vio3_metric]

        # Call the system.
        resp_date, resp_response = metric_cache._parse_current_feed()
        self.assertIsNotNone(resp_date)
        self.assertIsNone(resp_response)

    @mock.patch('pypowervm.tasks.monitor.util.LparMetricCache.'
                '_parse_current_feed')
    @mock.patch('pypowervm.tasks.monitor.util.ensure_ltm_monitors')
    def test_refresh(self, mock_ensure_monitor, mock_parse):
        ret1 = None
        ret2 = {'lpar_uuid': 2}
        ret3 = {'lpar_uuid': 3}

        date_ret1 = datetime.datetime.now()
        date_ret2 = date_ret1 + datetime.timedelta(milliseconds=250)
        date_ret3 = date_ret2 + datetime.timedelta(milliseconds=250)

        mock_parse.side_effect = [(date_ret1, ret1), (date_ret2, ret2),
                                  (date_ret3, ret3)]

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
