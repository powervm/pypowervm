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

from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.network as net_br

NET_BRIDGE_FILE = 'fake_network_bridge.txt'
VSWITCH_FEED_FILE = 'fake_vswitch_feed.txt'


class TestVSwitch(unittest.TestCase):

    def setUp(self):
        super(TestVSwitch, self).setUp()
        vswitches = pvmhttp.load_pvm_resp(VSWITCH_FEED_FILE).get_response()
        self.wrapper = net_br.VirtualSwitch(vswitches.feed.entries[0])

    def test_data(self):
        self.assertEqual('ETHERNET0', self.wrapper.name)
        self.assertEqual(0, self.wrapper.switch_id)
        self.assertEqual('Veb', self.wrapper.mode)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '4abca7ff-3710-3160-b9e4-cb4456c33f43/VirtualSwitch/'
                         '4d9735ae-feaf-32c2-a1bc-102026df9168',
                         self.wrapper.href)


class TestNetwork(unittest.TestCase):

    def setUp(self):
        super(TestNetwork, self).setUp()
        self.net_br_resp = pvmhttp.load_pvm_resp(
            NET_BRIDGE_FILE).get_response()
        nb = self.net_br_resp.feed.entries[0]
        self.wrapper = net_br.NetworkBridge(nb)

    def test_pvid(self):
        self.assertEqual(1, self.wrapper.pvid)

    def test_uuid(self):
        self.assertEqual(
            '764f3423-04c5-3b96-95a3-4764065400bd', self.wrapper.uuid)

    def test_virtual_network_uri_list(self):
        uri_list = self.wrapper.get_virtual_network_uri_list()
        self.assertEqual(13, len(uri_list))
        self.assertEqual('http', uri_list[0][:4])

    def test_load_groups(self):
        prim_ld_grp = self.wrapper.prim_load_grp
        self.assertIsNotNone(prim_ld_grp)
        self.assertEqual(1, prim_ld_grp.pvid)
        self.assertEqual(1, len(prim_ld_grp.get_trunk_adapters()))

        addl_ld_grps = self.wrapper.get_addl_load_grps()
        self.assertIsNotNone(addl_ld_grps)
        self.assertEqual(1, len(addl_ld_grps))

        self.assertEqual(
            12, len(addl_ld_grps[0].get_virtual_network_uri_list()))

    def test_supports_vlan(self):
        """Tests the supports_vlan method."""

        # PVID of primary adapter
        self.assertTrue(self.wrapper.supports_vlan(1))
        self.assertTrue(self.wrapper.supports_vlan("1"))

        # PVID of second adapter
        self.assertFalse(self.wrapper.supports_vlan(4094))
        self.assertFalse(self.wrapper.supports_vlan("4094"))

        # Additional VLAN of second adapter.
        self.assertTrue(self.wrapper.supports_vlan(100))
        self.assertTrue(self.wrapper.supports_vlan("100"))
        self.assertTrue(self.wrapper.supports_vlan(2228))
        self.assertTrue(self.wrapper.supports_vlan("2228"))
        self.assertTrue(self.wrapper.supports_vlan(2227))
        self.assertTrue(self.wrapper.supports_vlan("2227"))

        # A VLAN that isn't anywhere
        self.assertFalse(self.wrapper.supports_vlan(123))

    def test_seas(self):
        seas = self.wrapper.get_seas()
        self.assertEqual(1, len(seas))

        sea = seas[0]
        self.assertEqual(1, sea.pvid)

    def test_sea_trunks(self):
        """Tests the trunk adapters on the SEA."""
        sea = self.wrapper.get_seas()[0]

        # The primary adapter testing
        prim_t = sea.primary_adpt
        self.assertIsNotNone(prim_t)
        self.assertEqual(1, prim_t.pvid)
        self.assertFalse(prim_t.has_tag_support())
        self.assertEqual(0, len(prim_t.tagged_vlans))
        self.assertEqual(2, prim_t.vswitch_id)
        self.assertEqual('ent4', prim_t.dev_name)
        self.assertEqual(1, prim_t.trunk_pri)

        # The secondary adapter.
        addl_adpts = sea.get_addl_adpts()
        self.assertIsNotNone(addl_adpts)
        self.assertEqual(1, len(addl_adpts))
        addl_adpt = addl_adpts[0]
        self.assertEqual(4094, addl_adpt.pvid)
        self.assertTrue(addl_adpt.has_tag_support())
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

if __name__ == "__main__":
    unittest.main()
