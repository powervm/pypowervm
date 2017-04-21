# Copyright 2016 IBM Corp.
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

"""Tests for the raw LPAR long term metrics."""

import json
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers.pcm import lpar as pcm_lpar
import testtools


LPAR_DATA = 'lpar_pcm_data.txt'


class TestLparLTM(testtools.TestCase):

    def setUp(self):
        super(TestLparLTM, self).setUp()
        self.raw_json = pvmhttp.PVMFile(LPAR_DATA).body

    def test_parse(self):
        info = pcm_lpar.LparInfo(self.raw_json)
        self.assertIsNotNone(info)
        # Validate the Lpar metrics.
        # There are metrics for four Lpars.
        self.assertEqual(6, len(info.lpars_util))
        # Get the first Lpar and assert its metrics
        lpar = info.lpars_util[0]
        self.assertEqual("Ubuntu1410", lpar.name)
        self.assertIsNotNone(lpar.memory)
        self.assertEqual(80, lpar.memory.pct_real_mem_avbl)
        self.assertEqual(1024, lpar.memory.total_pg_count)
        self.assertEqual(512, lpar.memory.free_pg_count)
        self.assertEqual(64, lpar.memory.active_pg_count)
        self.assertEqual(1048576, lpar.memory.real_mem_size_bytes)
        self.assertEqual(61, lpar.memory.pct_real_mem_free)
        self.assertEqual(25, lpar.memory.vm_pg_out_rate)
        # Get 3rd(random) VM and assert its metrics
        lpar = info.lpars_util[2]
        self.assertEqual("test_vm3", lpar.name)
        self.assertIsNotNone(lpar.memory)
        self.assertEqual(82, lpar.memory.pct_real_mem_avbl)
        self.assertEqual(4096, lpar.memory.total_pg_count)
        self.assertEqual(2048, lpar.memory.free_pg_count)
        self.assertEqual(256, lpar.memory.active_pg_count)
        self.assertEqual(1048576, lpar.memory.real_mem_size_bytes)
        self.assertEqual(60, lpar.memory.pct_real_mem_free)
        self.assertEqual(0, lpar.memory.vm_pg_out_rate)
        # Assert that we have entries in JSON for VMs which were in error
        metric_json = json.loads(self.raw_json)
        self.assertEqual("3B0237F9-26F1-41C7-BE57-A08C9452AD9D",
                         metric_json['lparUtil'][4]['name'])
        self.assertEqual("vm_inactive_rmc",
                         metric_json['lparUtil'][5]['name'])
        # Assert that powered off VM has 100 percent free memory.
        lpar = info.lpars_util[4]
        self.assertEqual("3B0237F9-26F1-41C7-BE57-A08C9452AD9D", lpar.name)
        self.assertIsNotNone(lpar.memory)
        self.assertIsNone(lpar.memory.pct_real_mem_avbl)
        self.assertIsNone(lpar.memory.total_pg_count)
        self.assertIsNone(lpar.memory.free_pg_count)
        self.assertIsNone(lpar.memory.active_pg_count)
        self.assertIsNone(lpar.memory.real_mem_size_bytes)
        self.assertEqual(100, lpar.memory.pct_real_mem_free)
        # Assert that LPAR with inactive RMC has no free memory.
        lpar = info.lpars_util[5]
        self.assertEqual("vm_inactive_rmc", lpar.name)
        self.assertIsNotNone(lpar.memory)
        self.assertIsNone(lpar.memory.pct_real_mem_avbl)
        self.assertIsNone(lpar.memory.total_pg_count)
        self.assertIsNone(lpar.memory.free_pg_count)
        self.assertIsNone(lpar.memory.active_pg_count)
        self.assertIsNone(lpar.memory.real_mem_size_bytes)
        self.assertEqual(0, lpar.memory.pct_real_mem_free)
