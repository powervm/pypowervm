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

    def test_ids(self):
        """Test .id and .sriov_adap_id."""
        # AdapterID inherited from IOAdapter
        self.assertEqual('553713696', self.sriovs[0].id)
        self.assertEqual(1, self.sriovs[0].sriov_adap_id)

        self.assertEqual('553713680', self.sriovs[1].id)
        self.assertIsNone(self.sriovs[1].sriov_adap_id)

    def test_mode(self):
        self.assertEqual('Sriov', self.sriovs[0].mode)
        # Test setter
        self.sriovs[0].mode = 'unknown'
        self.assertEqual('unknown', self.sriovs[0].mode)

    def test_state(self):
        self.assertEqual('Running', self.sriovs[0].state)

    def test_physical_ports(self):
        adapter = self.sriovs[0]

        phyports = adapter.phys_ports
        self.assertEqual(4, len(phyports))

        # Get converged and ethernet physical ports each
        conv_port, eth_port = self.sriovs[0].phys_ports[:3:2]

        # Converged physical ports test
        self.assertEqual(None, conv_port.label)
        conv_port.label = 'updatedlabel'
        self.assertEqual('updatedlabel', conv_port.label)

        self.assertEqual('U78C7.001.RCH0004-P1-C8-T1', conv_port.loc_code)

        self.assertEqual(0, conv_port.port_id)

        self.assertEqual(None, conv_port.sublabel)
        conv_port.sublabel = 'updatedsublabel'
        self.assertEqual('updatedsublabel', conv_port.sublabel)

        self.assertEqual(True, conv_port.link_status)

        self.assertEqual(20, conv_port.cfg_max_lps)
        conv_port.cfg_max_lps = 40
        self.assertEqual(40, conv_port.cfg_max_lps)

        self.assertEqual(200, conv_port.min_granularity)

        self.assertEqual(20, conv_port.supp_max_lps)

        self.assertEqual(0.02, conv_port.allocated_capacity)

        # Ethernet physical ports test
        self.assertEqual(None, eth_port.label)
        eth_port.label = 'updatedlabel'
        self.assertEqual('updatedlabel', eth_port.label)

        self.assertEqual('U78C7.001.RCH0004-P1-C8-T3', eth_port.loc_code)

        self.assertEqual(2, eth_port.port_id)

        self.assertEqual(None, eth_port.sublabel)
        eth_port.sublabel = 'updatedsublabel'
        self.assertEqual('updatedsublabel', eth_port.sublabel)

        self.assertEqual(True, eth_port.link_status)

        self.assertEqual(4, eth_port.cfg_max_lps)
        eth_port.cfg_max_lps = 40
        self.assertEqual(40, eth_port.cfg_max_lps)

        self.assertEqual(200, eth_port.min_granularity)

        self.assertEqual(4, eth_port.supp_max_lps)

        self.assertEqual(0.02, eth_port.allocated_capacity)

if __name__ == "__main__":
    unittest.main()
