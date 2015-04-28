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

import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
from pypowervm.wrappers import monitor


class TestPCM(twrap.TestWrapper):

    file = 'pcm_pref.txt'
    wrapper_class_to_test = monitor.PcmPref

    def test_pcm(self):
        pcm_wrap = self.entries[0]
        self.assertEqual('dev-system-6', pcm_wrap.system_name)

        # Test enable getters when all are loaded and False
        self.assertFalse(pcm_wrap.ltm_enabled)
        self.assertFalse(pcm_wrap.aggregation_enabled)
        self.assertFalse(pcm_wrap.stm_enabled)
        self.assertFalse(pcm_wrap.compute_ltm_enabled)

        # Set all to True and test.
        pcm_wrap.ltm_enabled = True
        self.assertTrue(pcm_wrap.ltm_enabled)

        pcm_wrap.aggregation_enabled = True
        self.assertTrue(pcm_wrap.aggregation_enabled)

        pcm_wrap.stm_enabled = True
        self.assertTrue(pcm_wrap.stm_enabled)

        pcm_wrap.compute_ltm_enabled = True
        self.assertTrue(pcm_wrap.compute_ltm_enabled)


class TestLongTermMonitorMetrics(twrap.TestWrapper):

    file = 'ltm_feed.txt'
    wrapper_class_to_test = monitor.LongTermMonitorMetrics

    def test_ltm_metrics(self):
        link = ('https://9.1.2.3:12443/rest/api/pcm/ManagedSystem/98498bed'
                '-c78a-3a4f-b90a-4b715418fcb6/RawMetrics/LongTermMonitor/L'
                'TM_8247-22L*1111111_vios_2_20150430T035300+0000.json')

        wrap = self.entries[0]
        self.assertEqual('15161241-b72f-41d5-8154-557ff699fb75', wrap.id)
        self.assertEqual('2015-04-30T03:53:00.000Z', wrap.published)
        self.assertEqual(
            'LTM_8247-22L*1111111_vios_2_20150430T035300+0000.json',
            wrap.title)
        self.assertEqual('2015-04-30T03:53:00.000Z', wrap.updated)
        self.assertEqual('vios_2', wrap.category)
        self.assertEqual(link, wrap.link)

        # Test wrapping just one entry and we should get the same data
        wrap = monitor.LongTermMonitorMetrics.wrap(self.entries[0].entry)
        self.assertEqual(link, wrap.link)


class TestShortTermMonitorMetrics(twrap.TestWrapper):

    file = 'stm_feed.txt'
    wrapper_class_to_test = monitor.LongTermMonitorMetrics

    def test_stm_metrics(self):
        link = ('https://9.1.2.3:12443/rest/api/pcm/ManagedSystem/98498bed'
                '-c78a-3a4f-b90a-4b715418fcb6/RawMetrics/ShortTermMonitor/'
                'STM_8247-22L*1111111_phyp_20150430T061135+0000.json')

        wrap = self.entries[0]
        self.assertEqual('28cb2328-ca14-48ef-a3bd-691debef53dd', wrap.id)
        self.assertEqual('2015-04-30T06:11:35.000Z', wrap.published)
        self.assertEqual(
            'STM_8247-22L*1111111_phyp_20150430T061135+0000.json',
            wrap.title)
        self.assertEqual('2015-04-30T06:11:35.000Z', wrap.updated)
        self.assertEqual('phyp', wrap.category)
        self.assertEqual(link, wrap.link)

        # Test wrapping just one entry and we should get the same data
        wrap = monitor.ShortTermMonitorMetrics.wrap(self.entries[0].entry)
        self.assertEqual(link, wrap.link)
