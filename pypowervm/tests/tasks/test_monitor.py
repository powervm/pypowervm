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

import os

import mock
import testtools

from pypowervm import entities as pvm_e
from pypowervm.tasks import monitor as pvm_t_mon
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
        self.adpt.read_by_href.return_value = tju.load_file('ltm_feed.txt')
        feed = pvm_t_mon.query_ltm_feed(self.adpt, 'host_uuid')

        # Make sure the feed is correct.
        self.assertEqual(130, len(feed))

        # Make sure each element is a LTMMetric
        for mon in feed:
            self.assertIsInstance(mon, pvm_mon.LTMMetrics)

        self.assertEqual(1, self.adpt.read_by_href.call_count)

    def test_ensure_ltm_monitors(self):
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
        dirname = os.path.dirname(__file__)
        file_name = os.path.join(dirname, path)
        return pvmhttp.PVMFile(file_name).body

    def test_parse_to_vm_metrics(self):
        vios_resp = self._load('../wrappers/pcm/data/vios_data.txt')
        phyp_resp = self._load('../wrappers/pcm/data/phyp_data.txt')

        mock_phyp = mock.MagicMock()
        mock_vioses = [mock.MagicMock()]

        self.adpt.read_by_href.side_effect = [phyp_resp, vios_resp]

        pvm_t_mon.vm_metrics(self.adpt, mock_phyp, mock_vioses)
        pass
