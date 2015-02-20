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

import copy
import unittest

import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.network as net_br

NET_BRIDGE_FILE = 'fake_network_bridge.txt'
VSWITCH_FEED_FILE = 'fake_vswitch_feed.txt'


class TestVNetwork(twrap.TestWrapper):

    file = 'fake_virtual_network_feed.txt'
    wrapper_class_to_test = net_br.VirtualNetwork

    def test_vnet(self):
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/'
                         'ManagedSystem/67dca605-3923-34da-bd8f-26a378fc817f/'
                         'VirtualSwitch/ec8aaa54-9837-3c23-a541-a4e4be3ae489',
                         self.dwrap.associated_switch_uri)
        self.assertEqual('VLAN2227-ETHERNET0', self.dwrap.name)
        self.assertEqual(2227, self.dwrap.vlan)
        self.assertEqual(0, self.dwrap.vswitch_id)
        self.assertEqual(False, self.dwrap.tagged)

    def test_name(self):
        self.dwrap.name = 'Test'
        self.assertEqual('Test', self.dwrap.name)

    def test_vnet_new(self):
        """Tests the method that returns a VirtualNetwork ElementWrapper."""
        vn_w = net_br.VirtualNetwork.new_instance('name', 10, 'vswitch_uri',
                                                  True)
        self.assertEqual('name', vn_w.name)
        self.assertEqual(10, vn_w.vlan)
        self.assertTrue(vn_w.tagged)


class TestVSwitch(twrap.TestWrapper):

    file = 'fake_vswitch_feed.txt'
    wrapper_class_to_test = net_br.VirtualSwitch

    def test_feed(self):
        """Tests the feed of virtual switches."""
        vswitches = net_br.VirtualSwitch.load_from_response(self.resp)
        self.assertTrue(len(vswitches) >= 1)
        for vswitch in vswitches:
            self.assertIsNotNone(vswitch.etag)

    def test_data(self):
        self.assertEqual('ETHERNET0', self.dwrap.name)
        self.assertEqual(0, self.dwrap.switch_id)
        self.assertEqual('Veb', self.dwrap.mode)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '4abca7ff-3710-3160-b9e4-cb4456c33f43/VirtualSwitch/'
                         '4d9735ae-feaf-32c2-a1bc-102026df9168',
                         self.dwrap.href)


class TestNetwork(twrap.TestWrapper):

    file = 'fake_network_bridge.txt'
    wrapper_class_to_test = net_br.NetworkBridge

    def test_pvid(self):
        self.assertEqual(1, self.dwrap.pvid)

    def test_uuid(self):
        self.assertEqual(
            '764f3423-04c5-3b96-95a3-4764065400bd', self.dwrap.uuid)

    def test_virtual_network_uri_list(self):
        uri_list = self.dwrap.virtual_network_uri_list
        self.assertEqual(13, len(uri_list))
        self.assertEqual('http', uri_list[0][:4])

    def test_crt_load_group(self):
        # Create my mocked data
        uri_list = ['a', 'b', 'c']
        pvid = 1
        lg = net_br.LoadGroup(net_br.crt_load_group(pvid, uri_list))

        # Validate the data back
        self.assertIsNotNone(lg)
        self.assertEqual(1, lg.pvid)
        self.assertEqual(3, len(lg.virtual_network_uri_list))
        self.assertEqual('a', lg.virtual_network_uri_list[0])
        self.assertEqual('b', lg.virtual_network_uri_list[1])
        self.assertEqual('c', lg.virtual_network_uri_list[2])

    def test_load_groups(self):
        prim_ld_grp = self.dwrap.load_grps[0]
        self.assertIsNotNone(prim_ld_grp)
        self.assertEqual(1, prim_ld_grp.pvid)
        self.assertEqual(1, len(prim_ld_grp.trunk_adapters))

        addl_ld_grps = self.dwrap.load_grps[1:]
        self.assertIsNotNone(addl_ld_grps)
        self.assertEqual(1, len(addl_ld_grps))

        self.assertEqual(
            12, len(addl_ld_grps[0].virtual_network_uri_list))
        addl_ld_grps[0].virtual_network_uri_list.append('fake_uri')
        self.assertEqual(
            13, len(addl_ld_grps[0].virtual_network_uri_list))
        addl_ld_grps[0].virtual_network_uri_list.remove('fake_uri')
        self.assertEqual(
            12, len(addl_ld_grps[0].virtual_network_uri_list))

        # Make sure that the reference to the Network Bridge is there.
        self.assertEqual(self.dwrap, prim_ld_grp._nb_root)

    def test_load_group_modification(self):
        """Verifies that the callbacks to the Network Bridge work.

        When modifying the Virtual Network list in the Load Group, those
        updates should be reflected back into the Network Bridge.
        """
        orig_len = len(self.dwrap.virtual_network_uri_list)
        ld_grp = self.dwrap.load_grps[0]
        lg_vnets = ld_grp.virtual_network_uri_list
        first_vnet = lg_vnets[0]
        lg_vnets.remove(first_vnet)

        self.assertEqual(orig_len - 1,
                         len(self.dwrap.virtual_network_uri_list))

    def test_supports_vlan(self):
        """Tests the supports_vlan method."""

        # PVID of primary adapter
        self.assertTrue(self.dwrap.supports_vlan(1))
        self.assertTrue(self.dwrap.supports_vlan("1"))

        # PVID of second adapter
        self.assertFalse(self.dwrap.supports_vlan(4094))
        self.assertFalse(self.dwrap.supports_vlan("4094"))

        # Additional VLAN of second adapter.
        self.assertTrue(self.dwrap.supports_vlan(100))
        self.assertTrue(self.dwrap.supports_vlan("100"))
        self.assertTrue(self.dwrap.supports_vlan(2228))
        self.assertTrue(self.dwrap.supports_vlan("2228"))
        self.assertTrue(self.dwrap.supports_vlan(2227))
        self.assertTrue(self.dwrap.supports_vlan("2227"))

        # A VLAN that isn't anywhere
        self.assertFalse(self.dwrap.supports_vlan(123))

    def test_vswitch_id(self):
        """Tests that the pass thru of the vswitch id works."""
        self.assertEqual(2, self.dwrap.vswitch_id)

    def test_arbitrary_pvids(self):
        self.assertEqual([4094], self.dwrap.arbitrary_pvids)

    def test_list_vlans(self):
        # 1 is the PVID.  4094 is the arbitrary (only one arbitrary)
        self.assertListEqual([100, 150, 175, 200, 250, 300, 333, 350, 900,
                              1001, 2227, 2228, 1],
                             self.dwrap.list_vlans())
        self.assertListEqual([4094, 100, 150, 175, 200, 250, 300, 333, 350,
                              900, 1001, 2227, 2228],
                             self.dwrap.list_vlans(pvid=False, arbitrary=True))
        self.assertListEqual([100, 150, 175, 200, 250, 300, 333, 350, 900,
                              1001, 2227, 2228],
                             self.dwrap.list_vlans(pvid=False))
        self.assertListEqual([1, 4094, 100, 150, 175, 200, 250, 300, 333, 350,
                              900, 1001, 2227, 2228],
                             self.dwrap.list_vlans(arbitrary=True))

    def test_seas(self):
        self.assertEqual(1, len(self.dwrap.seas))

        sea = self.dwrap.seas[0]

        # Test some properties
        self.assertEqual(1, sea.pvid)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '726e9cb3-6576-3df5-ab60-40893d51d074/VirtualIOServer'
                         '/691019AF-506A-4896-AADE-607E21FA93EE',
                         sea.vio_uri)
        self.assertEqual('ent8', sea.dev_name)

        new_sea = copy.deepcopy(sea)
        self.dwrap.seas.append(new_sea)

        self.assertEqual(2, len(self.dwrap.seas))

        sea_copy = copy.copy(self.dwrap.seas)
        sea_copy.remove(new_sea)
        self.dwrap.seas = sea_copy
        self.assertEqual(1, len(self.dwrap.seas))

    def test_sea_trunks(self):
        """Tests the trunk adapters on the SEA."""
        sea = self.dwrap.seas[0]

        # The primary adapter testing
        prim_t = sea.primary_adpt
        self.assertIsNotNone(prim_t)
        self.assertEqual(1, prim_t.pvid)
        self.assertFalse(prim_t.has_tag_support)
        self.assertEqual(0, len(prim_t.tagged_vlans))
        self.assertEqual(2, prim_t.vswitch_id)
        self.assertEqual('ent4', prim_t.dev_name)
        self.assertEqual(1, prim_t.trunk_pri)

        # The secondary adapter.
        addl_adpts = sea.addl_adpts
        self.assertIsNotNone(addl_adpts)
        self.assertEqual(1, len(addl_adpts))
        addl_adpt = addl_adpts[0]
        self.assertEqual(4094, addl_adpt.pvid)
        self.assertTrue(addl_adpt.has_tag_support)
        self.assertEqual(12, len(addl_adpt.tagged_vlans))
        self.assertEqual(2, addl_adpt.vswitch_id)
        self.assertEqual('ent5', addl_adpt.dev_name)
        self.assertEqual(1, addl_adpt.trunk_pri)

        # Try setting the tagged vlans
        orig_vlans = copy.copy(addl_adpt.tagged_vlans)
        addl_adpt.tagged_vlans.append(5)
        self.assertEqual(13, len(addl_adpt.tagged_vlans))
        addl_adpt.tagged_vlans = [1]
        self.assertEqual(1, len(addl_adpt.tagged_vlans))
        addl_adpt.tagged_vlans = orig_vlans
        self.assertEqual(12, len(addl_adpt.tagged_vlans))

        # Modify the tag support
        addl_adpt.has_tag_support = False
        self.assertFalse(addl_adpt.has_tag_support)
        addl_adpt.has_tag_support = True
        self.assertTrue(addl_adpt.has_tag_support)

if __name__ == "__main__":
    unittest.main()
