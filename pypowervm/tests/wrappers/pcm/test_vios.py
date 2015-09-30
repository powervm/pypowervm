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

"""Tests for the raw VIOS long term metrics."""

import testtools

from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers.pcm import vios as pcm_vios

VIOS_DATA = 'vios_pcm_data.txt'


class TestViosLTM(testtools.TestCase):

    def setUp(self):
        super(TestViosLTM, self).setUp()

        self.raw_json = pvmhttp.PVMFile(VIOS_DATA).body

    def test_parse(self):
        info = pcm_vios.ViosInfo(self.raw_json)
        self.assertIsNotNone(info)

        # Validate the info
        self.assertEqual('1.0.0', info.info.version)
        self.assertEqual('Raw', info.info.metric_type)
        self.assertEqual('LTM', info.info.monitoring_type)
        self.assertEqual('8247-22L*2125D4A', info.info.mtms)

        # Validate some samples
        sample = info.sample
        self.assertEqual(u'2015-05-27T00:22:00+0000', sample.time_stamp)
        self.assertEqual(1, sample.id)
        self.assertEqual('IOServer - SN2125D4A', sample.name)

        # Validate Memory
        self.assertEqual(1715, sample.mem.utilized_mem)

        # Validate the Network
        self.assertEqual(6, len(sample.network.adpts))
        self.assertEqual(1, len(sample.network.seas))

        phys_dev = sample.network.adpts[1]
        self.assertEqual('ent0', phys_dev.name)
        self.assertEqual('physical', phys_dev.type)
        self.assertEqual('U78CB.001.WZS007Y-P1-C10-T1',
                         phys_dev.physical_location)
        self.assertEqual(1703083, phys_dev.received_packets)
        self.assertEqual(65801, phys_dev.sent_packets)
        self.assertEqual(0, phys_dev.dropped_packets)
        self.assertEqual(187004823, phys_dev.received_bytes)
        self.assertEqual(71198950, phys_dev.sent_bytes)

        # SEA validation
        sea = sample.network.seas[0]
        self.assertEqual('ent6', sea.name)
        self.assertEqual('sea', sea.type)
        self.assertEqual('U8247.22L.2125D4A-V1-C12-T1', sea.physical_location)
        self.assertEqual(0, sea.received_packets)
        self.assertEqual(0, sea.sent_packets)
        self.assertEqual(0, sea.dropped_packets)
        self.assertEqual(0, sea.received_bytes)
        self.assertEqual(0, sea.sent_bytes)
        self.assertEqual(['ent3', 'ent5'], sea.bridged_adpts)

        # Storage - FC Validation
        fc = sample.storage.fc_adpts[0]
        self.assertEqual('fcs0', fc.name)
        self.assertEqual('21000024ff649104', fc.wwpn)
        self.assertEqual('U78CB.001.WZS007Y-P1-C3-T1', fc.physical_location)
        self.assertEqual(0, fc.num_reads)
        self.assertEqual(0, fc.num_writes)
        self.assertEqual(0, fc.read_bytes)
        self.assertEqual(0, fc.write_bytes)
        self.assertEqual(8, fc.running_speed)

        # VFC Validation
        vfc = sample.storage.fc_adpts[1].ports[0]
        self.assertEqual("vfc1", vfc.name)
        self.assertEqual("21000024ff649159", vfc.wwpn)
        self.assertEqual(1234, vfc.num_reads)
        self.assertEqual(1235, vfc.num_writes)
        self.assertEqual(184184, vfc.read_bytes)
        self.assertEqual(138523, vfc.write_bytes)
        self.assertEqual(8, vfc.running_speed)
        self.assertEqual("U78CB.001.WZS007Y-P1-C3-T2000",
                         vfc.physical_location)

        # Physical Adpt Validation
        padpt = sample.storage.phys_adpts[0]
        self.assertEqual('sissas0', padpt.name)
        self.assertEqual('U78CB.001.WZS007Y-P1-C14-T1',
                         padpt.physical_location)
        self.assertEqual(1089692, padpt.num_reads)
        self.assertEqual(1288936, padpt.num_writes)
        self.assertEqual(557922304, padpt.read_bytes)
        self.assertEqual(659935232, padpt.write_bytes)
        self.assertEqual('sas', padpt.type)

        # Storage Virtual Adapter Validation
        vadpt = sample.storage.virt_adpts[0]
        self.assertEqual('vhost5', vadpt.name)
        self.assertEqual('U8247.22L.2125D4A-V1-C7', vadpt.physical_location)
        self.assertEqual(0, vadpt.num_reads)
        self.assertEqual(1, vadpt.num_writes)
        self.assertEqual(0, vadpt.read_bytes)
        self.assertEqual(512, vadpt.write_bytes)
        self.assertEqual('virtual', vadpt.type)

        # SSP Validation
        ssp = sample.storage.ssps[0]
        self.assertEqual('ssp1', ssp.name)
        self.assertEqual(["sissas0"], ssp.pool_disks)
        self.assertEqual(12346, ssp.num_reads)
        self.assertEqual(17542, ssp.num_writes)
        self.assertEqual(18352435, ssp.total_space)
        self.assertEqual(123452, ssp.used_space)
        self.assertEqual(123825, ssp.read_bytes)
        self.assertEqual(375322, ssp.write_bytes)
