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

import testtools

from pypowervm.tests.wrappers.util import pvmhttp
from pypowervm.wrappers.pcm import vios as pcm_vios


class TestPhypLTM(testtools.TestCase):

    def setUp(self):
        super(TestPhypLTM, self).setUp()

        dirname = os.path.dirname(__file__)
        file_name = os.path.join(dirname, 'data', 'vios_data.txt')
        self.raw_json = pvmhttp.PVMFile(file_name).body

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
        self.assertEqual('1', sample.id)
        self.assertEqual('IOServer - SN2125D4A', sample.name)

        # Validate Memory
        self.assertEqual(1715, sample.mem.utilized_mem)

        # Validate the Network
        self.assertEqual(6, len(sample.network.adpts))
        self.assertEqual(1, len(sample.network.seas))

        phys_dev = sample.network.adpts[1]
        self.assertEqual('ent0', phys_dev.id)
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
        self.assertEqual('ent6', sea.id)
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
        self.assertEqual('fcs0', fc.id)
        self.assertEqual('21000024ff649104', fc.wwpn)
        self.assertEqual('U78CB.001.WZS007Y-P1-C3-T1', fc.physical_location)
        self.assertEqual(0, fc.num_of_reads)
        self.assertEqual(0, fc.num_of_writes)
        self.assertEqual(0, fc.read_bytes)
        self.assertEqual(0, fc.write_bytes)
        self.assertEqual(8, fc.running_speed)

        # Physical Adpt Validation
        padpt = sample.storage.phys_adpts[0]
        self.assertEqual('sissas0', padpt.id)
        self.assertEqual('U78CB.001.WZS007Y-P1-C14-T1',
                         padpt.physical_location)
        self.assertEqual(1089692, padpt.num_of_reads)
        self.assertEqual(1288936, padpt.num_of_writes)
        self.assertEqual(557922304, padpt.read_bytes)
        self.assertEqual(659935232, padpt.write_bytes)
        self.assertEqual('sas', padpt.type)

        # Storage Virtual Adapter Validation
        vadpt = sample.storage.virt_adpts[0]
        self.assertEqual('vhost5', vadpt.id)
        self.assertEqual('U8247.22L.2125D4A-V1-C7', vadpt.physical_location)
        self.assertEqual(0, vadpt.num_of_reads)
        self.assertEqual(1, vadpt.num_of_writes)
        self.assertEqual(0, vadpt.read_bytes)
        self.assertEqual(512, vadpt.write_bytes)
        self.assertEqual('virtual', vadpt.type)
