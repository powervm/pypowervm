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

import unittest

from pypowervm.tests.wrappers.util import pvmhttp
from pypowervm.wrappers import pcm_pref

_HTTPRESP_FILE = "pcm_pref.txt"


class TestPCM(unittest.TestCase):

    def setUp(self):
        super(TestPCM, self).setUp()

        http_resp = pvmhttp.load_pvm_resp(_HTTPRESP_FILE)
        self.assertIsNotNone(http_resp, "Could not load %s " %
                             _HTTPRESP_FILE)

        self.pcm_wraps = pcm_pref.PcmPref.wrap(http_resp.response)
        self.pcm_wrap = self.pcm_wraps[0]

    def test_pcm(self):
        self.assertEqual('dev-system-6', self.pcm_wrap.system_name)

        # Test enable getters when all are loaded and False
        self.assertFalse(self.pcm_wrap.ltm_enabled)
        self.assertFalse(self.pcm_wrap.aggregation_enabled)
        self.assertFalse(self.pcm_wrap.stm_enabled)
        self.assertFalse(self.pcm_wrap.compute_ltm_enabled)

        # Set all to True and test.
        self.pcm_wrap.ltm_enabled = True
        self.assertTrue(self.pcm_wrap.ltm_enabled)

        self.pcm_wrap.aggregation_enabled = True
        self.assertTrue(self.pcm_wrap.aggregation_enabled)

        self.pcm_wrap.stm_enabled = True
        self.assertTrue(self.pcm_wrap.stm_enabled)

        self.pcm_wrap.compute_ltm_enabled = True
        self.assertTrue(self.pcm_wrap.compute_ltm_enabled)
