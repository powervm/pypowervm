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

import unittest

import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.managed_system as ms


class TestSRIOVAdapter(twrap.TestWrapper):

    file = 'sys_with_sriov.txt'
    wrapper_class_to_test = ms.System

    def setUp(self):
        super(TestSRIOVAdapter, self).setUp()
        self.sriovs = self.dwrap.asio_config.sriov_adapters

    def test_list(self):
        self.assertEqual(3, len(self.sriovs))
        for sriov in self.sriovs:
            self.assertIsInstance(sriov, card.SRIOVAdapter)

    def test_attrs(self):
        desc = 'PCIe2 4-port (10Gb FCoE & 1GbE) SR&RJ45 Adapter'

        self.assertEqual('553713696', self.sriovs[0].id)
        self.assertEqual(desc, self.sriovs[0].description)
        self.assertEqual('U78C7.001.RCH0004-P1-C8',
                         self.sriovs[0].phys_loc_code)

    def test_mode(self):
        self.assertEqual('Sriov', self.sriovs[0].mode)
        # Test setter
        self.sriovs[0].mode = 'unknown'
        self.assertEqual('unknown', self.sriovs[0].mode)

    def test_state(self):
        self.assertEqual('Running', self.sriovs[0].state)

    def test_physical_ports(self):
        adapter = self.sriovs[0]

        phyports = adapter.phys_ports()
        self.assertEqual(4, len(phyports))

        self.assertEqual(None, phyports[0].label)
        phyports[0].label = 'updatedlabel'
        self.assertEqual('updatedlabel', phyports[0].label)

        self.assertEqual('U78C7.001.RCH0004-P1-C8-T1', phyports[0].loc_code)

        self.assertEqual(0, phyports[0].port_id)

        self.assertEqual(None, phyports[0].sublabel)
        phyports[0].sublabel = 'updatedsublabel'
        self.assertEqual('updatedsublabel', phyports[0].sublabel)

        self.assertEqual(True, phyports[0].link_status)

        self.assertEqual(20, phyports[0].cfg_max_ports)
        phyports[0].cfg_max_ports = 40
        self.assertEqual(40, phyports[0].cfg_max_ports)

        self.assertEqual(200, phyports[0].min_granularity)

        self.assertEqual(20, phyports[0].supp_max_ports)

        self.assertEqual('2.0%', phyports[0].allocated_capacity)
        phyports[0].allocated_capacity = '4.0%'
        self.assertEqual('4.0%', phyports[0].allocated_capacity)

        self.assertEqual(None, phyports[2].label)
        phyports[2].label = 'updatedlabel'
        self.assertEqual('updatedlabel', phyports[0].label)

        self.assertEqual('U78C7.001.RCH0004-P1-C8-T3', phyports[2].loc_code)

        self.assertEqual(2, phyports[2].port_id)

        self.assertEqual(None, phyports[2].sublabel)
        phyports[2].sublabel = 'updatedsublabel'
        self.assertEqual('updatedsublabel', phyports[2].sublabel)

        self.assertEqual(True, phyports[2].link_status)

        self.assertEqual(4, phyports[2].cfg_max_ports)
        phyports[2].cfg_max_ports = 40
        self.assertEqual(40, phyports[2].cfg_max_ports)

        self.assertEqual(200, phyports[2].min_granularity)

        self.assertEqual(4, phyports[2].supp_max_ports)

        self.assertEqual('2.0%', phyports[2].allocated_capacity)
        phyports[2].allocated_capacity = '4.0%'
        self.assertEqual('4.0%', phyports[2].allocated_capacity)

if __name__ == "__main__":
    unittest.main()
