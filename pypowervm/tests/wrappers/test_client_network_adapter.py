# Copyright 2014, 2015 IBM Corp.
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

import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.network as net


class TestCNAWrapper(twrap.TestWrapper):

    file = 'fake_cna.txt'
    wrapper_class_to_test = net.CNA

    def setUp(self):
        super(TestCNAWrapper, self).setUp()
        self.assertIsNotNone(self.entries.etag)

    def test_standard_crt(self):
        """Tests a standard create of the CNA."""
        test = net.CNA.new(1, "fake_vs")
        self.assertEqual('fake_vs', test.vswitch_uri)
        self.assertFalse(test.is_tagged_vlan_supported)
        self.assertEqual([], test.tagged_vlans)
        self.assertIsNotNone(test.use_next_avail_slot_id)
        self.assertTrue(test.use_next_avail_slot_id)
        self.assertIsNone(test.mac)
        self.assertEqual(1, test.pvid)

    def test_unique_crt(self):
        """Tests the create path with a non-standard flow for the CNA."""
        test = net.CNA.new(5, "fake_vs", mac_addr="aa:bb:cc:dd:ee:ff",
                           slot_num=5, addl_tagged_vlans=[6, 7, 8, 9])
        self.assertEqual('fake_vs', test.vswitch_uri)
        self.assertTrue(test.is_tagged_vlan_supported)
        self.assertEqual([6, 7, 8, 9], test.tagged_vlans)
        self.assertEqual(5, test.slot)
        self.assertFalse(test.use_next_avail_slot_id)
        self.assertIsNotNone(test.mac)
        self.assertEqual("AABBCCDDEEFF", test.mac)
        self.assertEqual(5, test.pvid)

    def test_attrs(self):
        """Test getting the attributes."""
        self.assertEqual(32, self.entries.slot)
        self.assertEqual("FAD4433ED120", self.entries.mac)
        self.assertEqual(100, self.entries.pvid)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/LogicalPartition/'
                         '0A68CFAB-F62B-46D4-A6A0-F4EBE0264AD5/'
                         'ClientNetworkAdapter/'
                         '6445b54b-b9dc-3bc2-b1d3-f8cc22ba95b8',
                         self.entries.href)
        self.assertEqual('U8246.L2C.0604C7A-V24-C32',
                         self.entries.loc_code)
        self.assertEqual([53, 54, 55], self.entries.tagged_vlans)
        self.assertEqual(True, self.entries.is_tagged_vlan_supported)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '726e9cb3-6576-3df5-ab60-40893d51d074/VirtualSwitch/'
                         '9e42d4a9-9725-3007-9932-d85374ebf5cf',
                         self.entries.vswitch_uri)

    def test_tagged_vlan_modification(self):
        """Tests that the tagged vlans can be modified."""
        # Update via getter and Actionable List
        tags = self.entries.tagged_vlans
        tags.append(56)
        self.assertEqual(4, len(self.entries.tagged_vlans))
        tags.remove(56)
        self.assertEqual(3, len(self.entries.tagged_vlans))

        # Update via setter
        self.entries.tagged_vlans = [1, 2, 3]
        self.assertEqual([1, 2, 3], self.entries.tagged_vlans)
        self.entries.tagged_vlans = []
        self.assertEqual([], self.entries.tagged_vlans)
        self.entries.tagged_vlans = [53, 54, 55]

        # Try the tagged vlan support
        self.entries.is_tagged_vlan_supported = False
        self.assertFalse(self.entries.is_tagged_vlan_supported)
        self.entries.is_tagged_vlan_supported = True

    def test_mac_set(self):
        orig_mac = self.entries.mac
        mac = "AA:bb:CC:dd:ee:ff"
        self.entries.mac = mac
        self.assertEqual("AABBCCDDEEFF", self.entries.mac)
        self.entries.mac = orig_mac

    def test_get_slot(self):
        """Test getting the VirtualSlotID."""
        self.assertEqual(32, self.entries.slot)

    def test_get_mac(self):
        """Test that we can get the mac address."""
        self.assertEqual("FAD4433ED120", self.entries.mac)

    def test_pvid(self):
        """Test that the PVID returns properly."""
        self.assertEqual(100, self.entries.pvid)
        self.entries.pvid = 101
        self.assertEqual(101, self.entries.pvid)
        self.entries.pvid = 100

    def test_vswitch_uri(self):
        orig_uri = self.entries.vswitch_uri
        self.entries.vswitch_uri = 'test'
        self.assertEqual('test', self.entries.vswitch_uri)
        self.entries.vswitch_uri = orig_uri

if __name__ == "__main__":
    unittest.main()
