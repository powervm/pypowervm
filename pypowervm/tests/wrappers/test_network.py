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

import mock

import pypowervm.const as pc
import pypowervm.tests.test_fixtures as fx
import pypowervm.tests.test_utils.pvmhttp as pvmhttp
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.network as net
import pypowervm.wrappers.virtual_io_server as vios

NET_BRIDGE_FILE = 'fake_network_bridge.txt'
VSWITCH_FEED_FILE = 'fake_vswitch_feed.txt'


class TestVNetwork(twrap.TestWrapper):

    file = 'fake_virtual_network_feed.txt'
    wrapper_class_to_test = net.VNet

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
        """Tests the method that returns a VNet ElementWrapper."""
        vn_w = net.VNet.bld(None, 'name', 10, 'vswitch_uri', True)
        self.assertEqual('name', vn_w.name)
        self.assertEqual(10, vn_w.vlan)
        self.assertTrue(vn_w.tagged)

    def test_wrapper_class(self):
        self.assertEqual(net.VNet.schema_type, 'VirtualNetwork')
        self.assertEqual(net.VNet.schema_ns, pc.UOM_NS)
        self.assertTrue(net.VNet.has_metadata)
        self.assertEqual(net.VNet.default_attrib, pc.DEFAULT_SCHEMA_ATTR)


class TestVSwitch(twrap.TestWrapper):

    file = 'fake_vswitch_feed.txt'
    wrapper_class_to_test = net.VSwitch

    def test_bld(self):
        """Tests that the vSwitch element can be built."""
        vs = net.VSwitch.bld(None, 'Test')
        self.assertEqual('Test', vs.name)
        self.assertEqual(net.VSwitchMode.VEB, vs.mode)
        self.assertListEqual([], vs.vnet_uri_list)

        vs = net.VSwitch.bld(None, 'Test', net.VSwitchMode.VEPA)
        self.assertEqual('Test', vs.name)
        self.assertEqual(net.VSwitchMode.VEPA, vs.mode)
        self.assertListEqual([], vs.vnet_uri_list)

    def test_feed(self):
        """Tests the feed of virtual switches."""
        vswitches = net.VSwitch.wrap(self.resp)
        self.assertTrue(len(vswitches) >= 1)
        for vswitch in vswitches:
            self.assertIsNotNone(vswitch.etag)

    def test_data(self):
        self.assertEqual('ETHERNET0', self.dwrap.name)
        self.assertEqual(0, self.dwrap.switch_id)
        self.assertEqual('Veb', self.dwrap.mode)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '4abca7ff-3710-3160-b9e4-cb4456c33f43/VirtualSwitch/'
                         '4d9735ae-feaf-32c2-a1bc-102026df9168?group=None',
                         self.dwrap.href)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '4abca7ff-3710-3160-b9e4-cb4456c33f43/VirtualSwitch/'
                         '4d9735ae-feaf-32c2-a1bc-102026df9168',
                         self.dwrap.related_href)

    def test_wrapper_class(self):
        self.assertEqual(net.VSwitch.schema_type, 'VirtualSwitch')
        self.assertEqual(net.VSwitch.schema_ns, pc.UOM_NS)
        self.assertTrue(net.VSwitch.has_metadata)
        self.assertEqual(net.VSwitch.default_attrib, pc.DEFAULT_SCHEMA_ATTR)

    def test_set_mode(self):
        """Tests that the vSwitch element can have the mode set."""
        vs = net.VSwitch.bld(None, 'Test')
        self.assertEqual(net.VSwitchMode.VEB, vs.mode)
        vs.mode = net.VSwitchMode.VEPA
        self.assertEqual(net.VSwitchMode.VEPA, vs.mode)
        vs.mode = net.VSwitchMode.VEB
        self.assertEqual(net.VSwitchMode.VEB, vs.mode)


class TestLoadGroup(unittest.TestCase):
    def test_wrapper_class(self):
        self.assertEqual(net.LoadGroup.schema_type, 'LoadGroup')
        self.assertEqual(net.LoadGroup.schema_ns, pc.UOM_NS)
        self.assertTrue(net.LoadGroup.has_metadata)
        self.assertEqual(net.LoadGroup.default_attrib, pc.DEFAULT_SCHEMA_ATTR)


class TestTrunkAdapter(unittest.TestCase):
    def test_wrapper_class(self):
        self.assertEqual(net.TrunkAdapter.schema_type, 'TrunkAdapter')
        self.assertEqual(net.TrunkAdapter.schema_ns, pc.UOM_NS)
        self.assertFalse(net.TrunkAdapter.has_metadata)
        self.assertEqual(net.TrunkAdapter.default_attrib,
                         pc.DEFAULT_SCHEMA_ATTR)


class TestSEA(unittest.TestCase):
    def test_wrapper_class(self):
        self.assertEqual(net.SEA.schema_type, 'SharedEthernetAdapter')
        self.assertEqual(net.SEA.schema_ns, pc.UOM_NS)
        self.assertTrue(net.SEA.has_metadata)
        self.assertEqual(net.SEA.default_attrib, pc.DEFAULT_SCHEMA_ATTR)


class TestNetBridge(unittest.TestCase):
    def test_wrapper_class(self):
        self.assertEqual(net.NetBridge.schema_type, 'NetworkBridge')
        self.assertEqual(net.NetBridge.schema_ns, pc.UOM_NS)
        self.assertTrue(net.NetBridge.has_metadata)
        self.assertEqual(net.NetBridge.default_attrib, pc.DEFAULT_SCHEMA_ATTR)


class TestNetwork(twrap.TestWrapper):

    file = 'fake_network_bridge.txt'
    wrapper_class_to_test = net.NetBridge
    mock_adapter_fx_args = dict(traits=fx.LocalPVMTraits)

    def set_vnet(self, aware):
        # Since they're all references through the same adapter, setting traits
        # on dwrap's element's adapter ought to affect all sub-elements, etc.
        self.adptfx.set_traits(fx.RemoteHMCTraits if aware
                               else fx.RemotePVMTraits)

    def test_pvid(self):
        self.assertEqual(1, self.dwrap.pvid)

    def test_configuration_state(self):
        self.assertEqual(net.SEAState.CONFIGURED,
                         self.dwrap.seas[0].configuration_state)

    def test_load_balance(self):
        self.assertTrue(self.dwrap.load_balance)

    def test_uuid(self):
        self.assertEqual(
            '764f3423-04c5-3b96-95a3-4764065400bd', self.dwrap.uuid)

    def test_vnet_uri_list(self):
        uri_list = self.dwrap.vnet_uri_list
        self.assertEqual(13, len(uri_list))
        self.assertEqual('http', uri_list[0][:4])

    def test_contrl_channel(self):
        vios_file = pvmhttp.PVMFile('fake_vios_feed.txt')

        vios_resp = pvmhttp.PVMResp(pvmfile=vios_file).get_response()
        vios_wrap = vios.VIOS.wrap(vios_resp.feed.entries[0])

        self.assertEqual('ent5', vios_wrap.seas[0].control_channel)

    def test_contrl_channel_id(self):
        self.assertEqual(99, self.dwrap.control_channel_id)

    def test_crt_net_bridge(self):
        vswitch_file = pvmhttp.PVMFile('fake_vswitch_feed.txt')

        vswitch_resp = pvmhttp.PVMResp(pvmfile=vswitch_file).get_response()
        vsw_wrap = net.VSwitch.wrap(vswitch_resp.feed.entries[0])

        # Create mocked data
        nb = net.NetBridge.bld(self.adpt, pvid=1,
                               vios_to_backing_adpts=[('vio_href1', 'ent0'),
                                                      ('vio_href2', 'ent2')],
                               vswitch=vsw_wrap, load_balance=True)

        self.assertIsNotNone(nb)
        self.assertEqual(1, nb.pvid)
        self.assertEqual(2, len(nb.seas))
        self.assertEqual(0, len(nb.load_grps))
        self.assertTrue(nb.load_balance)

        # First SEA.  Should be the primary
        sea1 = nb.seas[0]
        self.assertIsNotNone(sea1)
        self.assertEqual(1, sea1.pvid)
        self.assertEqual('vio_href1', sea1.vio_uri)
        self.assertEqual('ent0', sea1.backing_device.dev_name)
        self.assertTrue(sea1.is_primary)

        # Validate the trunk.
        ta = sea1.primary_adpt
        self.assertTrue(ta._required)
        self.assertEqual(1, ta.pvid)
        self.assertFalse(ta.has_tag_support)
        self.assertEqual(vsw_wrap.switch_id, ta.vswitch_id)
        self.assertEqual(1, ta.trunk_pri)
        self.assertEqual(vsw_wrap.related_href, ta.associated_vswitch_uri)

        # Check that the second SEA is similar but not primary.
        sea2 = nb.seas[1]
        self.assertIsNotNone(sea2)
        self.assertEqual(1, sea2.pvid)
        self.assertEqual('vio_href2', sea2.vio_uri)
        self.assertEqual('ent2', sea2.backing_device.dev_name)
        self.assertFalse(sea2.is_primary)
        self.assertIsNone(sea2.ha_mode)

        # Validate the second SEA trunk.
        ta = sea2.primary_adpt
        self.assertTrue(ta._required)
        self.assertEqual(1, ta.pvid)
        self.assertFalse(ta.has_tag_support)
        self.assertEqual(vsw_wrap.switch_id, ta.vswitch_id)
        self.assertEqual(2, ta.trunk_pri)
        self.assertEqual(vsw_wrap.related_href, ta.associated_vswitch_uri)

    def test_crt_sea(self):
        vswitch_file = pvmhttp.PVMFile('fake_vswitch_feed.txt')

        vswitch_resp = pvmhttp.PVMResp(pvmfile=vswitch_file).get_response()
        vsw_wrap = net.VSwitch.wrap(vswitch_resp.feed.entries[0])

        # Create mocked data
        sea = net.SEA.bld(self.adpt, pvid=1, vios_href='127.0.0.1',
                          adpt_name='ent0', vswitch=vsw_wrap)

        self.assertIsNotNone(sea)
        self.assertEqual(1, sea.pvid)
        self.assertEqual('127.0.0.1', sea.vio_uri)
        self.assertEqual('ent0',
                         sea.backing_device.dev_name)

        ta = sea.primary_adpt
        self.assertTrue(ta._required)
        self.assertEqual(1, ta.pvid)
        self.assertFalse(ta.has_tag_support)
        self.assertEqual(vsw_wrap.switch_id, ta.vswitch_id)
        self.assertEqual(1, ta.trunk_pri)
        self.assertEqual(vsw_wrap.related_href, ta.associated_vswitch_uri)

    def test_crt_trunk_adapter(self):
        vswitch_file = pvmhttp.PVMFile('fake_vswitch_feed.txt')

        vswitch_resp = pvmhttp.PVMResp(pvmfile=vswitch_file).get_response()
        vsw_wrap = net.VSwitch.wrap(vswitch_resp.feed.entries[0])

        # Create mocked data
        ta = net.TrunkAdapter.bld(self.adpt, pvid=1, vlan_ids=[1, 2, 3],
                                  vswitch=vsw_wrap)

        self.assertIsNotNone(ta)
        self.assertTrue(ta._required)
        self.assertEqual(1, ta.pvid)
        self.assertEqual([1, 2, 3], ta.tagged_vlans)
        self.assertTrue(ta.has_tag_support)
        self.assertEqual(vsw_wrap.switch_id, ta.vswitch_id)
        self.assertEqual(1, ta.trunk_pri)
        self.assertEqual(vsw_wrap.related_href, ta.associated_vswitch_uri)

        # Try adding a VLAN to the trunk adapter.
        ta.tagged_vlans.append(4)
        self.assertEqual([1, 2, 3, 4], ta.tagged_vlans)

    def test_crt_load_group(self):
        # Create my mocked data
        uri_list = ['a', 'b', 'c']
        pvid = 1
        lg = net.LoadGroup.bld(self.adpt, pvid, uri_list)

        # Validate the data back
        self.assertIsNotNone(lg)
        self.assertEqual(1, lg.pvid)
        self.assertEqual(3, len(lg.vnet_uri_list))
        self.assertEqual('a', lg.vnet_uri_list[0])
        self.assertEqual('b', lg.vnet_uri_list[1])
        self.assertEqual('c', lg.vnet_uri_list[2])

    def test_load_groups(self):
        prim_ld_grp = self.dwrap.load_grps[0]
        self.assertIsNotNone(prim_ld_grp)
        self.assertEqual(1, prim_ld_grp.pvid)
        self.assertEqual(1, len(prim_ld_grp.trunk_adapters))
        self.assertEqual('U8246.L2C.0604C7A-V4-C2',
                         prim_ld_grp.trunk_adapters[0].loc_code)
        self.assertEqual(4, prim_ld_grp.trunk_adapters[0].vios_id)

        addl_ld_grps = self.dwrap.load_grps[1:]
        self.assertIsNotNone(addl_ld_grps)
        self.assertEqual(1, len(addl_ld_grps))

        self.assertEqual(
            12, len(addl_ld_grps[0].vnet_uri_list))
        addl_ld_grps[0].vnet_uri_list.append('fake_uri')
        self.assertEqual(
            13, len(addl_ld_grps[0].vnet_uri_list))
        addl_ld_grps[0].vnet_uri_list.remove('fake_uri')
        self.assertEqual(
            12, len(addl_ld_grps[0].vnet_uri_list))

        # Make sure that the reference to the Network Bridge is there.
        self.assertEqual(self.dwrap, prim_ld_grp._nb_root)

    def test_load_group_modification(self):
        """Verifies that the callbacks to the Network Bridge work.

        When modifying the Virtual Network list in the Load Group, those
        updates should be reflected back into the Network Bridge.
        """
        orig_len = len(self.dwrap.vnet_uri_list)
        ld_grp = self.dwrap.load_grps[0]
        lg_vnets = ld_grp.vnet_uri_list
        first_vnet = lg_vnets[0]
        lg_vnets.remove(first_vnet)

        self.assertEqual(orig_len - 1,
                         len(self.dwrap.vnet_uri_list))

    def test_sea_modification(self):
        """Verifies that the SEA can have a Trunk Adapter added to it."""
        vswitch_file = pvmhttp.PVMFile('fake_vswitch_feed.txt')

        vswitch_resp = pvmhttp.PVMResp(pvmfile=vswitch_file).get_response()
        vsw_wrap = net.VSwitch.wrap(vswitch_resp.feed.entries[0])

        # Create mocked data
        ta = net.TrunkAdapter.bld(
            self.adpt, pvid=1, vlan_ids=[1, 2, 3], vswitch=vsw_wrap)
        self.assertEqual(1, len(self.dwrap.seas[0].addl_adpts))
        self.dwrap.seas[0].addl_adpts.append(ta)
        self.assertEqual(2, len(self.dwrap.seas[0].addl_adpts))

        # Check that the total trunks is now three elements
        self.assertEqual(3, len(self.dwrap.seas[0]._get_trunks()))

    def test_supports_vlan(self):
        """Tests the supports_vlan method."""
        # Both styles should produce similar results.
        vnet_paths = [False, True]
        for use_vnet in vnet_paths:
            self.set_vnet(use_vnet)
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

    def test_supports_vlan_no_vnet(self):
        """Tests that a VLAN change affects trunks, not vnets."""
        self.dwrap.seas[0].primary_adpt.tagged_vlans.append(128)
        self.set_vnet(False)
        self.assertTrue(self.dwrap.supports_vlan(128))
        self.set_vnet(True)
        self.assertFalse(self.dwrap.supports_vlan(128))

    def test_no_primary_adpt(self):
        """Tests rare case that SEA has no primary adapter."""
        # Test to make sure None reference error is not hit
        self.assertIsNone(self.dwrap.seas[1].primary_adpt)
        self.assertEqual(self.dwrap.seas[1].addl_adpts, [])
        self.assertFalse(self.dwrap.seas[1].contains_device('abcd'))
        ct_ch = self.dwrap.seas[1].control_channel
        self.assertTrue(self.dwrap.seas[1].contains_device(ct_ch))

    def test_vswitch_id(self):
        """Tests that the pass thru of the vswitch id works."""
        self.assertEqual(2, self.dwrap.vswitch_id)

    def test_arbitrary_pvids(self):
        self.set_vnet(False)
        self.assertEqual([4094], self.dwrap.arbitrary_pvids)
        self.set_vnet(True)
        self.assertEqual([4094], self.dwrap.arbitrary_pvids)

    def test_list_vlans(self):
        # Both styles should produce similar results.
        vnet_paths = [False, True]
        for use_vnet in vnet_paths:
            self.set_vnet(use_vnet)

            # 1 is the PVID.  4094 is the arbitrary (only one arbitrary)
            val = set(self.dwrap.list_vlans())
            self.assertEqual({100, 150, 175, 200, 250, 300, 333, 350, 900,
                              1001, 2227, 2228, 1}, val)

            val = set(self.dwrap.list_vlans(pvid=False, arbitrary=True))
            self.assertEqual({4094, 100, 150, 175, 200, 250, 300, 333, 350,
                              900, 1001, 2227, 2228}, val)

            val = set(self.dwrap.list_vlans(pvid=False))
            self.assertEqual({100, 150, 175, 200, 250, 300, 333, 350, 900,
                              1001, 2227, 2228}, val)

            val = set(self.dwrap.list_vlans(arbitrary=True))
            self.assertEqual({1, 4094, 100, 150, 175, 200, 250, 300, 333, 350,
                              900, 1001, 2227, 2228}, val)

    def test_list_vlan_no_vnet(self):
        """Tests that a VLAN change affects trunks, not vnets."""
        self.dwrap.seas[0].primary_adpt.tagged_vlans.append(128)
        self.set_vnet(False)
        self.assertIn(128, self.dwrap.list_vlans())
        self.set_vnet(True)
        self.assertNotIn(128, self.dwrap.list_vlans())

    def test_seas(self):
        self.assertEqual(2, len(self.dwrap.seas))

        sea = self.dwrap.seas[0]

        # Test some properties
        self.assertEqual(1, sea.pvid)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '726e9cb3-6576-3df5-ab60-40893d51d074/VirtualIOServer'
                         '/691019AF-506A-4896-AADE-607E21FA93EE',
                         sea.vio_uri)
        self.assertEqual('ent8', sea.dev_name)
        self.assertEqual(net.HAMode.DISABLED, sea.ha_mode)

        new_sea = copy.deepcopy(sea)
        self.dwrap.seas.append(new_sea)

        self.assertEqual(3, len(self.dwrap.seas))

        sea_copy = copy.copy(self.dwrap.seas)
        sea_copy.remove(new_sea)
        self.dwrap.seas = sea_copy
        self.assertEqual(2, len(self.dwrap.seas))

        # Test the 'contains_device' method within the SEA.
        self.assertTrue(new_sea.contains_device('ent5'))
        self.assertFalse(new_sea.contains_device('ent2'))

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

    def test_varied_on(self):
        self.assertEqual(2, len(self.dwrap.seas))

        sea = self.dwrap.seas[0]

        # Try the varied_on property
        prim_t = sea.primary_adpt
        self.assertTrue(prim_t.varied_on)


class TestCNAWrapper(twrap.TestWrapper):

    file = 'fake_cna.txt'
    wrapper_class_to_test = net.CNA
    mock_adapter_fx_args = dict(traits=fx.LocalPVMTraits)

    def setUp(self):
        super(TestCNAWrapper, self).setUp()
        self.assertIsNotNone(self.entries.etag)

    def test_standard_crt(self):
        """Tests a standard create of the CNA."""
        test = net.CNA.bld(self.adpt, 1, "fake_vs")
        self.assertEqual('fake_vs', test.vswitch_uri)
        self.assertFalse(test.is_tagged_vlan_supported)
        self.assertEqual([], test.tagged_vlans)
        self.assertIsNotNone(test._use_next_avail_slot_id)
        self.assertTrue(test._use_next_avail_slot_id)
        self.assertIsNone(test.mac)
        self.assertIsNone(test.vsi_type_id)
        self.assertIsNone(test.vsi_type_version)
        self.assertIsNone(test.vsi_type_manager_id)
        self.assertIsNone(test.vswitch_id)
        self.assertEqual(1, test.pvid)
        self.assertNotIn(net._TA_TRUNK_PRI, str(test.toxmlstring()))
        self.assertFalse(test.is_trunk)
        self.assertIsNone(test.trunk_pri)
        self.assertFalse(test.enabled)

    def test_trunk_crt(self):
        """Tests a standard create of the CNA."""
        test = net.CNA.bld(self.adpt, 1, "fake_vs", trunk_pri=2)
        self.assertEqual('fake_vs', test.vswitch_uri)
        self.assertFalse(test.is_tagged_vlan_supported)
        self.assertEqual([], test.tagged_vlans)
        self.assertIsNotNone(test._use_next_avail_slot_id)
        self.assertTrue(test._use_next_avail_slot_id)
        self.assertIsNone(test.mac)
        self.assertIsNone(test.vsi_type_id)
        self.assertIsNone(test.vsi_type_version)
        self.assertIsNone(test.vsi_type_manager_id)
        self.assertIsNone(test.vswitch_id)
        self.assertEqual(1, test.pvid)
        self.assertIn(net._TA_TRUNK_PRI, str(test.toxmlstring()))
        self.assertTrue(test.is_trunk)
        self.assertEqual(test.trunk_pri, 2)

    def test_unique_crt(self):
        """Tests the create path with a non-standard flow for the CNA."""
        test = net.CNA.bld(
            self.adpt, 5, "fake_vs", mac_addr="aa:bb:cc:dd:ee:ff", slot_num=5,
            addl_tagged_vlans=[6, 7, 8, 9])
        self.assertEqual('fake_vs', test.vswitch_uri)
        self.assertTrue(test.is_tagged_vlan_supported)
        self.assertEqual([6, 7, 8, 9], test.tagged_vlans)
        self.assertEqual(5, test.slot)
        self.assertFalse(test._use_next_avail_slot_id)
        self.assertIsNotNone(test.mac)
        self.assertEqual("AABBCCDDEEFF", test.mac)
        self.assertEqual(5, test.pvid)
        self.assertIsNone(test.vsi_type_id)
        self.assertIsNone(test.vsi_type_version)
        self.assertIsNone(test.vsi_type_manager_id)
        self.assertIsNone(test.vswitch_id)
        self.assertNotIn(net._TA_TRUNK_PRI, str(test.toxmlstring()))
        self.assertFalse(test.is_trunk)
        self.assertIsNone(test.trunk_pri)

    def test_unasi_field(self):
        """UseNextAvailable(High)SlotID field is (not) used, as appropriate."""
        mock_vswitch = mock.Mock()
        mock_vswitch.related_href = 'href'
        # Do TrunkAdapter as well as CNA here
        # Traits fixture starts off "PVM" - should use High
        cna = net.CNA.bld(self.adpt, 1, "fake_vs")
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertIsNotNone(cna._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertTrue(cna._use_next_avail_slot_id)
        ta = net.TrunkAdapter.bld(self.adpt, 1, [], mock_vswitch)
        self.assertIsNone(ta._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertIsNotNone(ta._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertEqual('Unknown', ta.dev_name)

        # When slot specified, no UseNextAvailable(High)SlotID
        cna = net.CNA.bld(self.adpt, 1, "fake_vs", slot_num=1)
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertFalse(cna._use_next_avail_slot_id)

        # Swap to HMC - should *not* use High
        self.adptfx.set_traits(fx.RemoteHMCTraits)
        cna = net.CNA.bld(self.adpt, 1, "fake_vs")
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertIsNotNone(cna._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertTrue(cna._use_next_avail_slot_id)
        ta = net.TrunkAdapter.bld(self.adpt, 1, [], mock_vswitch)
        self.assertIsNone(ta._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertIsNotNone(ta._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertEqual('Unknown', cna.dev_name)

        # When slot specified, no UseNextAvailable(High)SlotID
        cna = net.CNA.bld(self.adpt, 1, "fake_vs", slot_num=1)
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertFalse(cna._use_next_avail_slot_id)

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.create')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR.get')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
    def test_cna_create(self, mock_vget, mock_lget, mock_ewrap_create):
        """CNA.create hack that mucks with UseNextAvailable(High)SlotID."""
        lpar_parent = mock.Mock(env=bp.LPARType.AIXLINUX,
                                is_mgmt_partition=False)
        vios_parent = mock.Mock(env=bp.LPARType.VIOS, is_mgmt_partition=False)
        mgmt_parent = mock.Mock(env=bp.LPARType.AIXLINUX,
                                is_mgmt_partition=True)
        sde_parent = mock.Mock(env=bp.LPARType.VIOS, is_mgmt_partition=True)

        # Exception paths for invalid parent spec
        cna = net.CNA.bld(self.adpt, 1, 'href')
        self.assertRaises(ValueError, cna.create)
        self.assertRaises(ValueError, cna.create, parent_type='foo')
        self.assertRaises(ValueError, cna.create, parent_uuid='foo')
        mock_ewrap_create.assert_not_called()
        mock_vget.assert_not_called()
        mock_lget.assert_not_called()

        # No parent, string parent_type gets converted.  Validate element
        # twiddling for VIOS and mgmt
        mock_lget.return_value = mgmt_parent
        mock_vget.return_value = vios_parent
        for ptyp, mck in ((lpar.LPAR, mock_lget), (vios.VIOS, mock_vget)):
            cna = net.CNA.bld(self.adpt, 1, 'href')
            self.assertEqual(
                mock_ewrap_create.return_value,
                cna.create(parent_type=ptyp.schema_type, parent_uuid='puuid'))
            mock_ewrap_create.assert_called_once_with(
                parent_type=ptyp, parent_uuid='puuid', timeout=-1,
                parent=mck.return_value)
            # One mck should get called in each loop
            mck.assert_called_once_with(self.adpt, uuid='puuid')
            # Element should get twiddled each time
            self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
            self.assertIsNotNone(cna._find(net._USE_NEXT_AVAIL_SLOT))
            self.assertTrue(cna._use_next_avail_slot_id)

            mock_ewrap_create.reset_mock()

        mock_lget.reset_mock()
        mock_vget.reset_mock()

        # No parent, wrapper parent_type, element twiddling for SDE (VIOS+mgmt)
        mock_vget.return_value = sde_parent
        cna = net.CNA.bld(self.adpt, 1, 'href')
        self.assertEqual(
            mock_ewrap_create.return_value,
            cna.create(parent_type=vios.VIOS, parent_uuid='puuid'))
        mock_ewrap_create.assert_called_once_with(
            parent_type=vios.VIOS, parent_uuid='puuid', timeout=-1,
            parent=mock_vget.return_value)
        mock_vget.assert_called_once_with(self.adpt, uuid='puuid')
        mock_lget.assert_not_called()
        # Element should get twiddled.
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertIsNotNone(cna._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertTrue(cna._use_next_avail_slot_id)

        mock_ewrap_create.reset_mock()
        mock_vget.reset_mock()

        # Parent specified, no element twiddling for plain LPAR
        cna = net.CNA.bld(self.adpt, 1, 'href')
        self.assertEqual(mock_ewrap_create.return_value,
                         cna.create(parent=lpar_parent))
        mock_ewrap_create.assert_called_once_with(
            parent_type=None, parent_uuid=None, timeout=-1, parent=lpar_parent)
        mock_vget.assert_not_called()
        mock_lget.assert_not_called()
        # Element should not get twiddled.
        self.assertIsNotNone(cna._find(net._USE_NEXT_AVAIL_HIGH_SLOT))
        self.assertIsNone(cna._find(net._USE_NEXT_AVAIL_SLOT))
        self.assertTrue(cna._use_next_avail_slot_id)

        mock_ewrap_create.reset_mock()

        # If slot specified, we skip the whole hack
        self.adptfx.set_traits(fx.RemoteHMCTraits)
        cna = net.CNA.bld(self.adpt, 1, 'href', slot_num=1)
        self.assertEqual(mock_ewrap_create.return_value,
                         cna.create(parent_type='ptyp', parent_uuid='puuid'))
        mock_ewrap_create.assert_called_once_with(
            parent_type='ptyp', parent_uuid='puuid', timeout=-1, parent=None)
        mock_vget.assert_not_called()
        mock_lget.assert_not_called()

        mock_ewrap_create.reset_mock()

        # For HMC, we skip the whole hack
        self.adptfx.set_traits(fx.RemoteHMCTraits)
        cna = net.CNA.bld(self.adpt, 1, 'href')
        self.assertEqual(mock_ewrap_create.return_value,
                         cna.create(parent_type='ptyp', parent_uuid='puuid'))
        mock_ewrap_create.assert_called_once_with(
            parent_type='ptyp', parent_uuid='puuid', timeout=-1, parent=None)
        mock_vget.assert_not_called()
        mock_lget.assert_not_called()

    def test_attrs(self):
        """Test getting the attributes."""
        self.assertEqual(32, self.dwrap.slot)
        self.assertEqual("FAD4433ED120", self.dwrap.mac)
        self.assertEqual(100, self.dwrap.pvid)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/LogicalPartition/'
                         '0A68CFAB-F62B-46D4-A6A0-F4EBE0264AD5/'
                         'ClientNetworkAdapter/'
                         '6445b54b-b9dc-3bc2-b1d3-f8cc22ba95b8',
                         self.dwrap.href)
        self.assertEqual('U8246.L2C.0604C7A-V24-C32',
                         self.dwrap.loc_code)
        self.assertEqual([53, 54, 55], self.dwrap.tagged_vlans)
        self.assertTrue(self.dwrap.is_tagged_vlan_supported)
        self.assertEqual('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                         '726e9cb3-6576-3df5-ab60-40893d51d074/VirtualSwitch/'
                         '9e42d4a9-9725-3007-9932-d85374ebf5cf',
                         self.dwrap.vswitch_uri)
        self.assertEqual(0, self.dwrap.vswitch_id)
        self.assertEqual('VSITID', self.dwrap.vsi_type_id)
        self.assertEqual('77.99', self.dwrap.vsi_type_version)
        self.assertEqual('VSIMID', self.dwrap.vsi_type_manager_id)

    def test_tagged_vlan_modification(self):
        """Tests that the tagged vlans can be modified."""
        # Update via getter and Actionable List
        tags = self.dwrap.tagged_vlans
        tags.append(56)
        self.assertEqual(4, len(self.dwrap.tagged_vlans))
        tags.remove(56)
        self.assertEqual(3, len(self.dwrap.tagged_vlans))

        # Update via setter
        self.dwrap.tagged_vlans = [1, 2, 3]
        self.assertEqual([1, 2, 3], self.dwrap.tagged_vlans)
        self.dwrap.tagged_vlans = []
        self.assertEqual([], self.dwrap.tagged_vlans)
        self.dwrap.tagged_vlans = [53, 54, 55]

        # Try the tagged vlan support
        self.dwrap.is_tagged_vlan_supported = False
        self.assertFalse(self.dwrap.is_tagged_vlan_supported)
        self.dwrap.is_tagged_vlan_supported = True

    def test_mac_set(self):
        orig_mac = self.dwrap.mac
        mac = "AA:bb:CC:dd:ee:ff"
        self.dwrap.mac = mac
        self.assertEqual("AABBCCDDEEFF", self.dwrap.mac)
        self.dwrap.mac = orig_mac

    def test_get_slot(self):
        """Test getting the VirtualSlotID."""
        self.assertEqual(32, self.dwrap.slot)

    def test_get_mac(self):
        """Test that we can get the mac address."""
        self.assertEqual("FAD4433ED120", self.dwrap.mac)

    def test_pvid(self):
        """Test that the PVID returns properly."""
        self.assertEqual(100, self.dwrap.pvid)
        self.dwrap.pvid = 101
        self.assertEqual(101, self.dwrap.pvid)
        self.dwrap.pvid = 100

    def test_vswitch_uri(self):
        orig_uri = self.dwrap.vswitch_uri
        self.dwrap.vswitch_uri = 'test'
        self.assertEqual('test', self.dwrap.vswitch_uri)
        self.dwrap.vswitch_uri = orig_uri

    def test_wrapper_class(self):
        self.assertEqual(net.CNA.schema_type, 'ClientNetworkAdapter')
        self.assertEqual(net.CNA.schema_ns, pc.UOM_NS)
        self.assertTrue(net.CNA.has_metadata)
        self.assertEqual(net.CNA.default_attrib, pc.DEFAULT_SCHEMA_ATTR)

    def test_get_trunk_pri(self):
        """Test that we can get the trunk priority."""
        self.assertEqual(1, self.dwrap.trunk_pri)

    def test_set_trunk_pri(self):
        """Test that we can set the trunk priority."""
        self.assertEqual(1, self.dwrap.trunk_pri)
        self.dwrap._trunk_pri(2)
        self.assertEqual(2, self.dwrap.trunk_pri)

    def test_is_trunk(self):
        """Test that we can get if this adapter is a trunk."""
        self.assertTrue(self.dwrap.is_trunk)
        self.dwrap._trunk_pri(None)
        self.assertFalse(self.dwrap.is_trunk)

    def test_lpar_id(self):
        """Test that we can get the local partition id."""
        self.assertEqual(3, self.dwrap.lpar_id)

    def test_set_dev_name(self):
        """Test that we can set the device name."""
        self.assertEqual('Unknown', self.dwrap.dev_name)
        self.dwrap._dev_name('tap-01234')
        self.assertEqual('tap-01234', self.dwrap.dev_name)

    def test_enabled(self):
        """Test that we disable/enable."""
        self.assertTrue(self.dwrap.enabled)
        self.dwrap.enabled = False
        self.assertFalse(self.dwrap.enabled)
        self.dwrap.enabled = True
        self.assertTrue(self.dwrap.enabled)

if __name__ == "__main__":
    unittest.main()
