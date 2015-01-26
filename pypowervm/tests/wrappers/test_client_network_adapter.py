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

from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.client_network_adapter as cna

CNA_FILE = 'fake_cna.txt'


class TestClientNetworkAdapterWrapper(unittest.TestCase):

    def setUp(self):
        super(TestClientNetworkAdapterWrapper, self).setUp()

        cna_resp = pvmhttp.load_pvm_resp(CNA_FILE).get_response()
        self.cna = cna.ClientNetworkAdapter.load_from_response(cna_resp)
        self.assertIsNotNone(self.cna.etag)

    def tearDown(self):
        super(TestClientNetworkAdapterWrapper, self).tearDown()

    def test_standard_crt(self):
        """Tests a standard create of the CNA."""
        test = cna.crt_cna(1, "fake_vs")
        self.assertEqual('fake_vs',
                         test.find('AssociatedVirtualSwitch/link')
                             .attrib['href'])
        self.assertEqual('false',
                         test.find(cna.VADPT_TAGGED_VLAN_SUPPORT).text)
        self.assertIsNone(test.find(cna.VADPT_TAGGED_VLANS))
        self.assertIsNotNone(test.find('UseNextAvailableSlotID'))
        self.assertEqual('true',
                         test.find('UseNextAvailableSlotID').text)
        self.assertIsNone(test.find(cna.VADPT_MAC_ADDR))
        self.assertEqual('1', test.find(cna.VADPT_PVID).text)

    def test_unique_crt(self):
        """Tests the create path with a non-standard flow for the CNA."""
        test = cna.crt_cna(5, "fake_vs", mac_addr="aa:bb:cc:dd:ee:ff",
                           slot_num=5, addl_tagged_vlans='6 7 8 9')
        self.assertEqual('fake_vs',
                         test.find('AssociatedVirtualSwitch/link')
                             .attrib['href'])
        self.assertEqual('true',
                         test.find(cna.VADPT_TAGGED_VLAN_SUPPORT).text)
        self.assertEqual('6 7 8 9',
                         test.find(cna.VADPT_TAGGED_VLANS).text)
        self.assertEqual('5', test.find(cna.VADPT_SLOT_NUM).text)
        self.assertIsNone(test.find('UseNextAvailableSlotID'))
        self.assertIsNotNone(test.find(cna.VADPT_MAC_ADDR))
        self.assertEqual("AABBCCDDEEFF", test.find(cna.VADPT_MAC_ADDR).text)
        self.assertEqual('5', test.find(cna.VADPT_PVID).text)

    def test_attrs(self):
        """Test getting the attributes."""
        self.assertEqual(32, self.cna.slot)
        self.assertEqual("FAD4433ED120", self.cna.mac)
        self.assertEqual(100, self.cna.pvid)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/LogicalPartition/'
                         '0A68CFAB-F62B-46D4-A6A0-F4EBE0264AD5/'
                         'ClientNetworkAdapter/'
                         '6445b54b-b9dc-3bc2-b1d3-f8cc22ba95b8',
                         self.cna.href)
        self.assertEqual('U8246.L2C.0604C7A-V24-C32',
                         self.cna.loc_code)
        self.assertEqual([53, 54, 55], self.cna.tagged_vlans)
        self.assertEqual(True, self.cna.is_tagged_vlan_supported)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '726e9cb3-6576-3df5-ab60-40893d51d074/VirtualSwitch/'
                         '9e42d4a9-9725-3007-9932-d85374ebf5cf',
                         self.cna.vswitch_uri)

    def test_tagged_vlan_modification(self):
        """Tests that the tagged vlans can be modified."""
        # Update via getter and Actionable List
        tags = self.cna.tagged_vlans
        tags.append(56)
        self.assertEqual(4, len(self.cna.tagged_vlans))
        tags.remove(56)
        self.assertEqual(3, len(self.cna.tagged_vlans))

        # Update via setter
        self.cna.tagged_vlans = [1, 2, 3]
        self.assertEqual([1, 2, 3], self.cna.tagged_vlans)
        self.cna.tagged_vlans = []
        self.assertEqual([], self.cna.tagged_vlans)
        self.cna.tagged_vlans = [53, 54, 55]

        # Try the tagged vlan support
        self.cna.is_tagged_vlan_supported = False
        self.assertFalse(self.cna.is_tagged_vlan_supported)
        self.cna.is_tagged_vlan_supported = True

    def test_mac_set(self):
        orig_mac = self.cna.mac
        mac = "AA:bb:CC:dd:ee:ff"
        self.cna.mac = mac
        self.assertEqual("AABBCCDDEEFF", self.cna.mac)
        self.cna.mac = orig_mac

    def test_get_slot(self):
        """Test getting the VirtualSlotID."""
        self.assertEqual(32, self.cna.slot)

    def test_get_mac(self):
        """Test that we can get the mac address."""
        self.assertEqual("FAD4433ED120", self.cna.mac)

    def test_pvid(self):
        """Test that the PVID returns properly."""
        self.assertEqual(100, self.cna.pvid)
        self.cna.pvid = 101
        self.assertEqual(101, self.cna.pvid)
        self.cna.pvid = 100

    def test_vswitch_uri(self):
        orig_uri = self.cna.vswitch_uri
        self.cna.vswitch_uri = 'test'
        self.assertEqual('test', self.cna.vswitch_uri)
        self.cna.vswitch_uri = orig_uri

if __name__ == "__main__":
    unittest.main()
