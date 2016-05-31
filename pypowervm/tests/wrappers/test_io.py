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
import pypowervm.wrappers.io as io
import pypowervm.wrappers.managed_system as ms


class TestSRIOVAdapter(twrap.TestWrapper):

    file = 'sys_with_sriov.txt'
    wrapper_class_to_test = ms.System

    def setUp(self):
        super(TestSRIOVAdapter, self).setUp()
        self.io_adpt = self.dwrap.asio_config.sriov_adapters[0]

    def test_attrs(self):
        desc = 'PCIe2 4-port (10Gb FCoE & 1GbE) SR&RJ45 Adapter'

        self.assertEqual('553713680', self.io_adpt.id)
        self.assertEqual(desc, self.io_adpt.description)
        self.assertEqual('U78CB.001.WZS06RG-P1-C7',
                         self.io_adpt.phys_loc_code)
        self.assertIsInstance(self.io_adpt, io.SRIOVAdapter)

    def test_mode(self):
        self.assertEqual('Dedicated', self.io_adpt.mode)
        # Test setter
        self.io_adpt.mode = 'unknown'
        self.assertEqual('unknown', self.io_adpt.mode)

    def test_state(self):
        self.assertEqual('NotConfigured', self.io_adpt.state)

if __name__ == "__main__":
    unittest.main()
