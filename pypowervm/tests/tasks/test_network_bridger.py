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

import mock
import testtools

from pypowervm import adapter as adpt
import pypowervm.entities as ent
from pypowervm import exceptions as pvm_exc
from pypowervm.tasks import network_bridger as net_br
from pypowervm.tests import fixtures
from pypowervm.tests.wrappers.util import pvmhttp
from pypowervm.wrappers import network as pvm_net

MGR_NET_BR_FILE = 'nbbr_network_bridge.txt'
MGR_VNET_FILE = 'nbbr_virtual_network.txt'
MGR_VSW_FILE = 'nbbr_virtual_switch.txt'


class TestNetworkBridger(testtools.TestCase):
    """General tests for the Network Bridger superclass.

    Subclasses of Network Bridgers should extend this class.
    """

    def setUp(self):
        super(TestNetworkBridger, self).setUp()

        # Find directory for response files
        data_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(data_dir, 'data')

        def resp(file_name):
            file_path = os.path.join(data_dir, file_name)
            return pvmhttp.load_pvm_resp(file_path).get_response()

        self.mgr_nbr_resp = resp(MGR_NET_BR_FILE)
        self.mgr_vnet_resp = resp(MGR_VNET_FILE)
        self.mgr_vsw_resp = resp(MGR_VSW_FILE)

        self.adpt = self.useFixture(fixtures.AdapterFx()).adpt
        self.adpt.traits = self.useFixture(fixtures.LocalPVMTraitsFx).traits

        self.host_uuid = 'c5d782c7-44e4-3086-ad15-b16fb039d63b'
        self.nb_uuid = 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151'

    def test_ensure_vlan_on_nb(self):
        """This does a happy path test.  Assumes VLAN on NB already.

        No subclass invocation.
        """
        self.adpt.read.return_value = self.mgr_nbr_resp
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 2227)
        self.assertEqual(1, self.adpt.read.call_count)

    def test_is_arbitrary_vid(self):
        nbs = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)
        bridger = net_br.NetworkBridger(self.adpt, self.host_uuid)
        self.assertTrue(bridger._is_arbitrary_vid(4094, nbs))
        self.assertFalse(bridger._is_arbitrary_vid(2227, nbs))

    def test_find_new_arbitrary_vid(self):
        nbs = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)
        bridger = net_br.NetworkBridger(self.adpt, self.host_uuid)
        self.assertEqual(4093, bridger._find_new_arbitrary_vid(nbs))
        self.assertEqual(4092, bridger._find_new_arbitrary_vid(nbs,
                                                               others=[4093]))

    def test_find_vswitch(self):
        self.adpt.read.return_value = self.mgr_vsw_resp
        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        v = bridger._find_vswitch('0')
        self.assertIsNotNone(v)
        self.assertEqual(0, v.switch_id)

    def test_remove_vlan_from_nb_bad_vid(self):
        """Attempt to remove a VID that can't be taken off NB."""
        # Mock Data
        self.adpt.read.return_value = self.mgr_nbr_resp

        # Should fail if fail_if_pvid set to True
        self.assertRaises(pvm_exc.PvidOfNetworkBridgeError,
                          net_br.remove_vlan_from_nb, self.adpt,
                          self.host_uuid, self.nb_uuid, 2227, True)

        # Should not fail if fail_if_pvid set to False, but shouldn't call
        # update either.
        net_br.remove_vlan_from_nb(self.adpt, self.host_uuid, self.nb_uuid,
                                   2227)
        self.assertEqual(0, self.adpt.update.call_count)


class TestNetworkBridgerVNet(TestNetworkBridger):
    """General tests for the network bridge super class and the VNet impl."""

    def setUp(self):
        super(TestNetworkBridgerVNet, self).setUp()

        # Make sure that we run through the vnet aware flow.
        self.adpt.traits = self.useFixture(fixtures.RemoteHMCTraitsFx).traits

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_reassign_arbitrary_vid')
    @mock.patch('pypowervm.wrappers.network.NetBridge.supports_vlan')
    def test_ensure_vlan_on_nb_reassign(self, mock_support_vlan,
                                        mock_reassign):
        """Validates that after update, we support the VLAN."""
        # Have the response
        self.adpt.read.return_value = self.mgr_nbr_resp

        # First call, say that we don't support the VLAN (which is true).
        # Second call, fake out that we now do.
        mock_support_vlan.side_effect = [False, True]

        # Invoke
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 4094)
        self.assertEqual(2, self.adpt.read.call_count)
        self.assertEqual(1, mock_reassign.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_vlan(self, mock_arb_vid, mock_find_vnet):
        """Validates new VLAN on existing Load Group."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_vnet = mock.MagicMock()
        mock_vnet.related_href = 'fake_href'
        mock_find_vnet.return_value = mock_vnet

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            nb = kargs[0]
            self.assertIsNotNone(nb)
            self.assertEqual(1,
                             len(nb.load_grps[0].vnet_uri_list))
            self.assertEqual(2,
                             len(nb.load_grps[1].vnet_uri_list))
            self.assertEqual(self.nb_uuid, nb.uuid)

            return nb.entry

        self.adpt.update_by_path.side_effect = validate_of_update_nb

        # Invoke
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 2000)

        # Validate the calls
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_is_arbitrary_vid')
    def test_ensure_vlans_on_nb_new_vlan(self, mock_arb_vid, mock_find_vnet):
        """Validates new VLAN on existing Load Group."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_vnet = mock.MagicMock()
        mock_vnet.related_href = 'fake_href'
        mock_find_vnet.return_value = mock_vnet

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            nb = kargs[0]
            self.assertEqual(1, len(nb.load_grps[0].vnet_uri_list))
            self.assertEqual(2, len(nb.load_grps[1].vnet_uri_list))
            self.assertEqual(self.nb_uuid, nb.uuid)
            return nb.entry

        self.adpt.update_by_path.side_effect = validate_of_update_nb

        # Invoke.  VLAN 2227 should be on there already.
        net_br.ensure_vlans_on_nb(self.adpt, self.host_uuid,
                                  self.nb_uuid, [2227, 2000])

        # Validate the calls
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_available_ld_grp')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_lg(self, mock_arb_vid, mock_avail_lg,
                                      mock_find_vnet):
        """Validates new VLAN on new Load Group."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_avail_lg.return_value = None

        # Make the fake virtual networks (the new, then the arb vid)
        mock_vnet = mock.MagicMock()
        mock_vnet.related_href = 'fake_href'
        mock_vnet_avid = mock.MagicMock()
        mock_vnet_avid.related_href = 'fake_avid_href'
        mock_find_vnet.side_effect = [mock_vnet, mock_vnet_avid]

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            nb = kargs[0]
            self.assertIsNotNone(nb)
            self.assertEqual(1, len(nb.load_grps[0].vnet_uri_list))
            self.assertEqual(2, len(nb.load_grps[2].vnet_uri_list))
            self.assertEqual(self.nb_uuid, nb.uuid)
            return nb.entry

        self.adpt.update_by_path.side_effect = validate_of_update_nb

        # Invoke
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 2000)

        # Validate the calls
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_vswitch')
    def test_reassign_arbitrary_vid(self, mock_vsw, mock_find_vnet):
        vnet = pvm_net.VNet._bld().entry
        resp1 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {},
                              self.adpt.traits)
        resp1.feed = ent.Feed({}, [vnet])
        self.adpt.read.return_value = resp1
        self.adpt.read_by_href.return_value = vnet
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)[0]
        resp2 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {},
                              self.adpt.traits)
        resp2.entry = nb.entry
        self.adpt.update.return_value = resp2

        vsw = pvm_net.VSwitch.wrap(self.mgr_vsw_resp)[0]
        mock_vsw.return_value = vsw

        mock_find_vnet.return_value = mock.MagicMock()
        mock_find_vnet.return_value.related_href = 'other'

        # Make this function return itself.
        def return_self(*kargs, **kwargs):
            return kargs[0].entry

        self.adpt.update_by_path.side_effect = return_self

        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        bridger._reassign_arbitrary_vid(4094, 4093, nb)

        # Make sure the mocks were called
        self.assertEqual(1, mock_find_vnet.call_count)
        self.assertEqual(2, self.adpt.update_by_path.call_count)

    def test_remove_vlan_from_nb(self):
        """Happy path testing of the remove VLAN from NB."""
        # Mock Data
        self.adpt.read.return_value = self.mgr_nbr_resp

        def validate_update(*kargs, **kwargs):
            # Make sure the load groups are down to just 1 now.
            nb = kargs[0]
            self.assertEqual(1, len(nb.load_grps))
            return nb.entry

        self.adpt.update_by_path.side_effect = validate_update

        net_br.remove_vlan_from_nb(self.adpt, self.host_uuid, self.nb_uuid,
                                   1000)
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_find_or_create_vnet(self):
        """Validates that a vnet is created (and deleted) as part of find."""
        # Load the data
        vnets = pvm_net.VNet.wrap(self.mgr_vnet_resp)
        vsw = pvm_net.VSwitch.wrap(self.mgr_vsw_resp)[0]

        # Set up the mock create
        resp = pvm_net.VNet.bld('FakeName', 4094, vsw.href, True)
        mock_resp = mock.MagicMock()
        mock_resp.entry = resp.entry
        self.adpt.create.return_value = mock_resp

        # Run the code
        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        ret_val = bridger._find_or_create_vnet(vnets, 4094, vsw)

        # Equality check
        self.assertEqual(4094, ret_val.vlan)
        self.assertTrue(ret_val.tagged)

        # Make sure the delete was called
        self.assertEqual(1, self.adpt.delete_by_href.call_count)

    def test_find_available_lb(self):
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)
        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        lg = bridger._find_available_ld_grp(nb[0])
        self.assertIsNotNone(lg)


class TestNetworkBridgerTA(TestNetworkBridger):
    """General tests for the network bridge super class and the VNet impl."""

    def setUp(self):
        super(TestNetworkBridgerTA, self).setUp()

        # Make sure that we run through the vnet aware flow.
        self.adpt.traits = self.useFixture(fixtures.LocalPVMTraitsFx).traits

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_reassign_arbitrary_vid')
    @mock.patch('pypowervm.wrappers.network.NetBridge.supports_vlan')
    def test_ensure_vlan_on_nb_reassign(self, mock_support_vlan,
                                        mock_reassign):
        """Validates that after update, we support the VLAN."""
        # Have the response
        self.adpt.read.return_value = self.mgr_nbr_resp

        # First call, say that we don't support the VLAN (which is true).
        # Second call, fake out that we now do.
        mock_support_vlan.side_effect = [False, True]

        # Invoke
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 4094)
        self.assertEqual(2, self.adpt.read.call_count)
        self.assertEqual(1, mock_reassign.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_vlan(self, mock_arb_vid):
        """Validates new VLAN on existing Trunk Adapter."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            nb = kargs[0]
            self.assertIsNotNone(nb)
            self.assertEqual(0,
                             len(nb.seas[0].primary_adpt.tagged_vlans))
            self.assertEqual(2,
                             len(nb.seas[0].addl_adpts[0].tagged_vlans))
            self.assertEqual(self.nb_uuid, nb.uuid)

            return nb.entry

        self.adpt.update_by_path.side_effect = validate_of_update_nb

        # Invoke
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 2000)

        # Validate the calls
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_is_arbitrary_vid')
    def test_ensure_vlans_on_nb_new_vlan(self, mock_arb_vid):
        """Validates new VLAN on existing Load Group."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            nb = kargs[0]
            self.assertEqual(0, len(nb.seas[0].primary_adpt.tagged_vlans))
            self.assertEqual(2, len(nb.seas[0].addl_adpts[0].tagged_vlans))
            self.assertEqual(self.nb_uuid, nb.uuid)
            return nb.entry

        self.adpt.update_by_path.side_effect = validate_of_update_nb

        # Invoke.  VLAN 2227 should be on there already.
        net_br.ensure_vlans_on_nb(self.adpt, self.host_uuid,
                                  self.nb_uuid, [2227, 2000])

        # Validate the calls
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_find_available_trunks')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_trunk(self, mock_arb_vid,
                                         mock_avail_trunks):
        """Validates new VLAN on new Load Group."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_avail_trunks.return_value = None

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            nb = kargs[0]
            self.assertIsNotNone(nb)
            self.assertEqual(0, len(nb.seas[0].primary_adpt.tagged_vlans))
            self.assertEqual(2, len(nb.seas[0].addl_adpts))
            self.assertEqual(self.nb_uuid, nb.uuid)
            return nb.entry

        self.adpt.update_by_path.side_effect = validate_of_update_nb

        # Invoke
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 2000)

        # Validate the calls
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_find_vswitch')
    def test_reassign_arbitrary_vid(self, mock_vsw):
        vnet = pvm_net.VNet._bld().entry
        resp1 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {},
                              self.adpt.traits)
        resp1.feed = ent.Feed({}, [vnet])
        self.adpt.read.return_value = resp1
        self.adpt.read_by_href.return_value = vnet
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)[0]
        resp2 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {},
                              self.adpt.traits)
        resp2.entry = nb.entry
        self.adpt.update.return_value = resp2

        vsw = pvm_net.VSwitch.wrap(self.mgr_vsw_resp)[0]
        mock_vsw.return_value = vsw

        # Make this function return itself.
        def return_self(*kargs, **kwargs):
            nb_wrap = pvm_net.NetBridge.wrap(kargs[0].entry)
            self.assertEqual(4093,
                             nb_wrap.seas[0].addl_adpts[0].pvid)

            return kargs[0].entry

        self.adpt.update_by_path.side_effect = return_self

        bridger = net_br.NetworkBridgerTA(self.adpt, self.host_uuid)
        bridger._reassign_arbitrary_vid(4094, 4093, nb)

        # Make sure the mocks were called.  Only one update needed.
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_remove_vlan_from_nb(self):
        """Happy path testing of the remove VLAN from NB."""
        # Mock Data
        self.adpt.read.return_value = self.mgr_nbr_resp

        def validate_update(*kargs, **kwargs):
            # Make sure the load groups are down to just 1 now.
            nb = kargs[0]
            self.assertEqual(0, len(nb.seas[0].addl_adpts))
            return nb.entry

        self.adpt.update_by_path.side_effect = validate_update

        net_br.remove_vlan_from_nb(self.adpt, self.host_uuid, self.nb_uuid,
                                   1000)
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_find_available_trunks(self):
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)
        bridger = net_br.NetworkBridgerTA(self.adpt, self.host_uuid)
        trunks = bridger._find_available_trunks(nb[0])
        self.assertIsNotNone(trunks)
