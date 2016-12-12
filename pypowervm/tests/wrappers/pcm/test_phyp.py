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

"""Tests for the raw PHYP long term metrics."""

import testtools

from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers.pcm import phyp as pcm_phyp

PHYP_DATA = 'phyp_pcm_data.txt'


class TestPhypLTM(testtools.TestCase):

    def setUp(self):
        super(TestPhypLTM, self).setUp()

        self.raw_json = pvmhttp.PVMFile(PHYP_DATA).body

    def test_parse(self):
        info = pcm_phyp.PhypInfo(self.raw_json)
        self.assertIsNotNone(info)

        # Validate the info
        self.assertEqual('1.3.0', info.info.version)
        self.assertEqual('Raw', info.info.metric_type)
        self.assertEqual('LTM', info.info.monitoring_type)
        self.assertEqual('8247-22L*2125D4A', info.info.mtms)
        self.assertEqual('dev-4', info.info.name)

        # Validate some samples
        sample = info.sample
        self.assertEqual(806297258933150.0, sample.time_based_cycles)
        self.assertEqual(0, sample.status)
        self.assertEqual(u'2015-05-27T08:17:45+0000', sample.time_stamp)

        # Firmware
        self.assertEqual(58599310268,
                         sample.system_firmware.utilized_proc_cycles)
        self.assertEqual(4096, sample.system_firmware.assigned_mem)

        # Shared Proc Pool
        spp_list = sample.shared_proc_pools
        self.assertEqual(1, len(spp_list))
        self.assertEqual(0, spp_list[0].id)
        self.assertEqual('DefaultPool', spp_list[0].name)
        self.assertEqual(1.6125945162342e+16, spp_list[0].assigned_proc_cycles)
        self.assertEqual(683011326288, spp_list[0].utilized_pool_cycles)
        self.assertEqual(20, spp_list[0].max_proc_units)
        self.assertEqual(18, spp_list[0].borrowed_pool_proc_units)

        # Processor
        self.assertEqual(20, sample.processor.total_proc_units)
        self.assertEqual(20, sample.processor.configurable_proc_units)
        self.assertEqual(18.9, sample.processor.available_proc_units)
        self.assertEqual(512000000, sample.processor.proc_cycles_per_sec)

        # Memory
        self.assertEqual(65536, sample.memory.total_mem)
        self.assertEqual(32512, sample.memory.available_mem)
        self.assertEqual(65536, sample.memory.configurable_mem)

        # LPARs
        self.assertEqual(5, len(sample.lpars))

        # First LPAR shouldn't have network or storage (inactive)
        bad_lpar = sample.lpars[0]
        self.assertEqual(6, bad_lpar.id)
        self.assertEqual('2545BCC5-BAE8-4414-AD49-EAFC2DEE2546', bad_lpar.uuid)
        self.assertEqual('aixlinux', bad_lpar.type)
        self.assertEqual('fkh4-99b8fdca-kyleh', bad_lpar.name)
        self.assertEqual('Not Activated', bad_lpar.state)
        self.assertEqual(100, bad_lpar.affinity_score)
        self.assertIsNotNone(bad_lpar.memory)
        self.assertIsNotNone(bad_lpar.processor)
        self.assertEqual(None, bad_lpar.network)
        self.assertEqual(None, bad_lpar.storage)

        # Last LPAR should have network and storage
        good_lpar = sample.lpars[4]

        # VM Memory
        self.assertEqual(20480, good_lpar.memory.logical_mem)
        self.assertEqual(20480, good_lpar.memory.backed_physical_mem)

        # VM Processor
        self.assertEqual(0, good_lpar.processor.pool_id)
        self.assertEqual('uncap', good_lpar.processor.mode)
        self.assertEqual(4, good_lpar.processor.virt_procs)
        self.assertEqual(.4, good_lpar.processor.proc_units)
        self.assertEqual(128, good_lpar.processor.weight)
        self.assertEqual(1765629232513,
                         good_lpar.processor.entitled_proc_cycles)
        self.assertEqual(264619289721,
                         good_lpar.processor.util_cap_proc_cycles)
        self.assertEqual(641419282, good_lpar.processor.util_uncap_proc_cycles)
        self.assertEqual(0, good_lpar.processor.idle_proc_cycles)
        self.assertEqual(0, good_lpar.processor.donated_proc_cycles)
        self.assertEqual(0, good_lpar.processor.time_wait_dispatch)
        self.assertEqual(160866895489, good_lpar.processor.total_instructions)
        self.assertEqual(193139925064,
                         good_lpar.processor.total_inst_exec_time)

        # VM Vea
        vea = good_lpar.network.veas[0]
        self.assertEqual(2227, vea.vlan_id)
        self.assertEqual(0, vea.vswitch_id)
        self.assertEqual('U8247.22L.2125D4A-V2-C2', vea.physical_location)
        self.assertEqual(True, vea.is_pvid)
        self.assertEqual(10, vea.received_packets)
        self.assertEqual(100, vea.sent_packets)
        self.assertEqual(5, vea.dropped_packets)
        self.assertEqual(100, vea.sent_bytes)
        self.assertEqual(10000, vea.received_bytes)
        self.assertEqual(0, vea.received_physical_packets)
        self.assertEqual(0, vea.sent_physical_packets)
        self.assertEqual(0, vea.dropped_physical_packets)
        self.assertEqual(0, vea.sent_physical_bytes)
        self.assertEqual(0, vea.received_physical_bytes)

        # TODO(thorst) Test SR-IOV

        # VM storage
        stor = good_lpar.storage.v_stor_adpts[0]
        self.assertEqual('U8247.22L.2125D4A-V2-C3', stor.physical_location)
        self.assertEqual(1, stor.vios_id)
        self.assertEqual(1000, stor.vios_slot)

        # Test that VFC adapter has been parsed.
        self.assertIsNotNone(good_lpar.storage.v_fc_adpts)
        self.assertEqual(2, len(good_lpar.storage.v_fc_adpts))
        # Test 1st VFC adapter
        vfc_adpt = good_lpar.storage.v_fc_adpts[0]
        self.assertEqual('U8247.22L.2125D4A-V2-C2',
                         vfc_adpt.physical_location)
        self.assertEqual(2, vfc_adpt.vios_id)
        self.assertEqual(2, len(vfc_adpt.wwpn_pair))
        self.assertIn(13857705835384867080, vfc_adpt.wwpn_pair)
        self.assertIn(13857705835384867081, vfc_adpt.wwpn_pair)
        # Test 2nd VFC adapter
        vfc_adpt = good_lpar.storage.v_fc_adpts[1]
        self.assertEqual('U8247.22L.2125D4A-V2-C3',
                         vfc_adpt.physical_location)
        self.assertEqual(1, vfc_adpt.vios_id)
        self.assertEqual(2, len(vfc_adpt.wwpn_pair))
        self.assertIn(13857705835384867082, vfc_adpt.wwpn_pair)
        self.assertIn(13857705835384867083, vfc_adpt.wwpn_pair)

        # TODO(thorst) Test vfc
