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

import mock
import testtools

from pypowervm import adapter as adpt
import pypowervm.entities as ent
from pypowervm import exceptions as pvm_exc
from pypowervm.tasks import network_bridger as net_br
import pypowervm.tests.test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import network as pvm_net

MGR_NET_BR_FAILOVER_FILE = 'nbbr_network_bridge_failover.txt'
MGR_NET_BR_FILE = 'nbbr_network_bridge.txt'
MGR_NET_BR_PEER_FILE = 'nbbr_network_bridge_peer.txt'
MGR_VNET_FILE = 'nbbr_virtual_network.txt'
MGR_VSW_FILE = 'nbbr_virtual_switch.txt'
ORPHAN_VIOS_FEED = 'fake_vios_feed.txt'
ORPHAN_CNA_FEED = 'cna_feed.txt'


class TestNetworkBridger(testtools.TestCase):
    """General tests for the Network Bridger superclass.

    Subclasses of Network Bridgers should extend this class.
    """

    def setUp(self):
        super(TestNetworkBridger, self).setUp()

        self.adptfx = self.useFixture(fx.AdapterFx(
            traits=fx.LocalPVMTraits))
        self.adpt = self.adptfx.adpt

        def resp(file_name):
            return pvmhttp.load_pvm_resp(
                file_name, adapter=self.adpt).get_response()

        self.mgr_nbr_resp = resp(MGR_NET_BR_FILE)
        self.mgr_nbr_fo_resp = resp(MGR_NET_BR_FAILOVER_FILE)
        self.mgr_nbr_peer_resp = resp(MGR_NET_BR_PEER_FILE)
        self.mgr_vnet_resp = resp(MGR_VNET_FILE)
        self.mgr_vsw_resp = resp(MGR_VSW_FILE)
        self.orphan_vio_resp = resp(ORPHAN_VIOS_FEED)
        self.orphan_cna_feed = resp(ORPHAN_CNA_FEED)

        self.host_uuid = 'c5d782c7-44e4-3086-ad15-b16fb039d63b'
        self.nb_uuid = 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151'
        self.nb_uuid_peer = '9af89d52-5892-11e5-885d-feff819cdc9f'

    def test_ensure_vlan_on_nb(self):
        """This does a happy path test.  Assumes VLAN on NB already.

        No subclass invocation.
        """
        self.adpt.read.return_value = self.mgr_nbr_resp
        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 2227)
        self.assertEqual(1, self.adpt.read.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger'
                '._validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger'
                '._remove_vlan_from_nb_synch')
    def test_ensure_vlan_on_nb_wrong_peer(self, mock_remove, mock_orphan):
        """Test moving vlan from one peer to another.

        No subclass invocation.
        """
        self.adpt.read.side_effect = [
            self.mgr_nbr_peer_resp, self.mgr_vsw_resp, self.mgr_vnet_resp]

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            nb = kargs[0]
            self.assertEqual(self.nb_uuid, nb.uuid)
            return nb.entry

        self.adpt.update_by_path.side_effect = validate_of_update_nb

        net_br.ensure_vlan_on_nb(self.adpt, self.host_uuid, self.nb_uuid, 1001)
        mock_remove.assert_called_once_with(
            self.nb_uuid_peer, 1001, fail_if_pvid=True, existing_nbs=mock.ANY)

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
                                   '2227')
        self.assertEqual(0, self.adpt.update.call_count)

    def _setup_reassign_arbitrary_vid(self):
        vsw_p = mock.patch('pypowervm.wrappers.network.VSwitch.search')
        self.mock_vsw = vsw_p.start()
        self.addCleanup(vsw_p.stop)
        vnet = pvm_net.VNet._bld(self.adpt).entry
        resp1 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp1.feed = ent.Feed({}, [vnet])
        self.adpt.read.return_value = resp1
        self.adpt.read_by_href.return_value = vnet
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)[0]
        resp2 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp2.entry = nb.entry
        self.adpt.update.return_value = resp2

        vsw = pvm_net.VSwitch.wrap(self.mgr_vsw_resp)[0]
        self.mock_vsw.return_value = vsw
        return nb

    def test_build_orphan_map(self):
        self.adpt.read.side_effect = [self.orphan_vio_resp]
        bridger = net_br.NetworkBridger(self.adpt, self.host_uuid)
        orphan_map = bridger._build_orphan_map()

        expected_map = {
            0: {'nimbus-ch03-p2-vios2': {'ent11': [4092, 2018, 2019]}},
            1: {'nimbus-ch03-p2-vios2': {'ent12': [2800, 2801]}}
        }

        self.assertEqual(expected_map, orphan_map)

    def test_validate_orphan_on_ensure(self):
        """Tests the _validate_orphan_on_ensure method."""
        self.adpt.read.side_effect = [self.orphan_vio_resp]
        bridger = net_br.NetworkBridger(self.adpt, self.host_uuid)

        # Test the Trunk Path - PVID and then an additional
        self.assertRaises(
            pvm_exc.OrphanVLANFoundOnProvision,
            bridger._validate_orphan_on_ensure, 4092, 0)
        self.assertRaises(
            pvm_exc.OrphanVLANFoundOnProvision,
            bridger._validate_orphan_on_ensure, 2018, 0)

        # Different vSwitch
        self.assertRaises(
            pvm_exc.OrphanVLANFoundOnProvision,
            bridger._validate_orphan_on_ensure, 2800, 1)

        # Shouldn't fail on a good vlan
        bridger._validate_orphan_on_ensure(2, 0)
        bridger._validate_orphan_on_ensure(1, 0)
        bridger._validate_orphan_on_ensure(4094, 1)

    def test_get_orphan_vlans(self):
        """Tests the _get_orphan_vlans method."""
        self.adpt.read.side_effect = [self.orphan_vio_resp]
        bridger = net_br.NetworkBridger(self.adpt, self.host_uuid)

        self.assertListEqual([], bridger._get_orphan_vlans(2))
        self.assertListEqual([2018, 2019, 4092],
                             bridger._get_orphan_vlans(0))
        self.assertListEqual([2800, 2801], bridger._get_orphan_vlans(1))


class TestNetworkBridgerVNet(TestNetworkBridger):
    """General tests for the network bridge super class and the VNet impl."""

    def setUp(self):
        super(TestNetworkBridgerVNet, self).setUp()
        self.adptfx.set_traits(fx.RemoteHMCTraits)

    @mock.patch('oslo_concurrency.lockutils.lock')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_get_orphan_vlans')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_reassign_arbitrary_vid')
    @mock.patch('pypowervm.wrappers.network.NetBridge.supports_vlan')
    def test_ensure_vlan_on_nb_reassign(
            self, mock_support_vlan, mock_reassign, mock_orphan_validate,
            mock_orphans, mock_lock):
        """Validates that after update, we support the VLAN."""
        # Have the response
        self.adpt.read.return_value = self.mgr_nbr_resp

        # First call, say that we don't support the VLAN (which is true).
        # Second call, fake out that we now do.
        # Works in pairs, as there are two VLANs we're working through.
        mock_support_vlan.side_effect = [False, False, True, True]
        mock_orphans.return_value = []

        # Invoke
        net_br.ensure_vlans_on_nb(self.adpt, self.host_uuid, self.nb_uuid,
                                  [4093, 4094])
        self.assertEqual(2, self.adpt.read.call_count)
        self.assertEqual(1, mock_reassign.call_count)
        self.assertEqual(1, mock_lock.call_count)

        # Should be called re-assigning 4094 (old) to 4092.  Shouldn't be
        # 4093 as that is also an additional VLAN.
        mock_reassign.assert_called_once_with(4094, 4092, mock.ANY)

    @mock.patch('oslo_concurrency.lockutils.lock')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_vlan(self, mock_arb_vid, mock_find_vnet,
                                        mock_orphan_validate, mock_lock):
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
        self.assertEqual(1, mock_lock.call_count)

    @mock.patch('oslo_concurrency.lockutils.lock')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_is_arbitrary_vid')
    def test_ensure_vlans_on_nb_new_vlan(self, mock_arb_vid, mock_find_vnet,
                                         mock_orphan_validate, mock_lock):
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
        self.assertEqual(1, mock_lock.call_count)

    @mock.patch('oslo_concurrency.lockutils.lock')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_get_orphan_vlans')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_available_ld_grp')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_lg(
            self, mock_arb_vid, mock_avail_lg, mock_find_vnet,
            mock_orphan_validate, mock_orphan_vlans, mock_lock):
        """Validates new VLAN on new Load Group."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_avail_lg.return_value = None
        mock_orphan_vlans.return_value = []

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
        self.assertEqual(1, mock_lock.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_or_create_vnet')
    def test_reassign_arbitrary_vid(self, mock_find_vnet):
        nb = self._setup_reassign_arbitrary_vid()

        mock_find_vnet.return_value = mock.MagicMock()
        mock_find_vnet.return_value.related_href = 'other'

        # Make this function return itself.
        def return_self(*kargs, **kwargs):
            return kargs[0].entry

        self.adpt.update_by_path.side_effect = return_self

        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        bridger._reassign_arbitrary_vid(4094, 4093, nb)

        # Make sure the mocks were called
        self.mock_vsw.assert_called_with(self.adpt, parent_type=pvm_ms.System,
                                         parent_uuid=self.host_uuid,
                                         one_result=True, switch_id=0)
        self.assertEqual(1, mock_find_vnet.call_count)
        self.assertEqual(2, self.adpt.update_by_path.call_count)

    @mock.patch('oslo_concurrency.lockutils.lock')
    def test_remove_vlan_from_nb(self, mock_lock):
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
        self.assertEqual(1, mock_lock.call_count)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerVNET.'
                '_find_vnet_uri_from_lg')
    def test_remove_vlan_from_nb_lb(self, mock_find_vnet):
        """Validates a load balance leaves two total LoadGroups."""
        # Mock Data
        mock_find_vnet.return_value = (
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
            'c5d782c7-44e4-3086-ad15-b16fb039d63b/VirtualNetwork/'
            'e6c0be9f-b974-35f4-855e-2b7192034fae')
        net_bridge = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)[0]
        net_bridge.load_balance = True

        # Run the remove
        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        bridger._remove_vlan_from_nb(net_bridge, 1000)

        # Validate that we still have two load groups
        self.assertEqual(2, len(net_bridge.load_grps))
        self.assertEqual(0, len(net_bridge.load_grps[1].vnet_uri_list))

    def test_find_or_create_vnet(self):
        """Validates that a vnet is created (and deleted) as part of find."""
        # Load the data
        vnets = pvm_net.VNet.wrap(self.mgr_vnet_resp)
        vsw = pvm_net.VSwitch.wrap(self.mgr_vsw_resp)[0]

        # Set up the mock create
        resp = pvm_net.VNet.bld(self.adpt, 'FakeName', 4094, vsw.href, True)
        mock_resp = adpt.Response('rm', 'rp', 200, 'reason', {})
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

    def test_find_available_lg(self):
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)[0]
        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        lg = bridger._find_available_ld_grp(nb)
        self.assertIsNotNone(lg)

    def test_find_available_lg_load_balance(self):
        """Tests finding the Load Group with load balancing enabled."""
        # Set load balancing to True
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_fo_resp)[0]
        nb.load_balance = True
        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)

        # Even though there is a free VEA, it should come back as None.  This
        # is because there is only one free VEA, but we need to balance across
        # two.
        lg = bridger._find_available_ld_grp(nb)
        self.assertIsNone(lg)

    def test_find_available_min_lg(self):
        nb = mock.MagicMock()

        lg_main = mock.MagicMock()
        lg_first_addl = mock.MagicMock()
        lg_first_addl.vnet_uri_list = ['a', 'b', 'c']
        lg_second_addl = mock.MagicMock()
        lg_second_addl.vnet_uri_list = ['e', 'f']
        nb.load_grps = [lg_main, lg_first_addl, lg_second_addl]

        bridger = net_br.NetworkBridgerVNET(self.adpt, self.host_uuid)
        self.assertEqual(lg_second_addl, bridger._find_available_ld_grp(nb))


class TestNetworkBridgerTA(TestNetworkBridger):
    """General tests for the network bridge super class and the VNet impl."""

    def setUp(self):
        super(TestNetworkBridgerTA, self).setUp()
        self.adptfx.set_traits(fx.LocalPVMTraits)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_get_orphan_vlans')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_reassign_arbitrary_vid')
    @mock.patch('pypowervm.wrappers.network.NetBridge.supports_vlan')
    def test_ensure_vlan_on_nb_reassign(
            self, mock_support_vlan, mock_reassign, mock_orphan_validate,
            mock_orphan_vlans):
        """Validates that after update, we support the VLAN."""
        # Have the response
        self.adpt.read.return_value = self.mgr_nbr_resp

        # First call, say that we don't support the VLAN (which is true).
        # Second call, fake out that we now do.
        # Need pairs, as there are two VLANs we are passing in.
        mock_support_vlan.side_effect = [False, False, True, True]
        mock_orphan_vlans.return_value = []

        # Invoke
        net_br.ensure_vlans_on_nb(self.adpt, self.host_uuid, self.nb_uuid,
                                  ['4093', 4094])
        self.assertEqual(2, self.adpt.read.call_count)
        self.assertEqual(1, mock_reassign.call_count)

        # Should be called re-assigning 4094 (old) to 4092.  Shouldn't be
        # 4093 as that is also an additional VLAN.
        mock_reassign.assert_called_once_with(4094, 4092, mock.ANY)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_vlan(self, mock_arb_vid,
                                        mock_orphan_validate):
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

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_is_arbitrary_vid')
    def test_ensure_vlans_on_nb_new_vlan(self, mock_arb_vid,
                                         mock_orphan_validate):
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

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_get_orphan_vlans')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridger.'
                '_validate_orphan_on_ensure')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_find_available_trunks')
    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_is_arbitrary_vid')
    def test_ensure_vlan_on_nb_new_trunk(
            self, mock_arb_vid, mock_avail_trunks, mock_orphan_validate,
            mock_orphan_vlans):
        """Validates new VLAN on new Load Group."""
        # Build the responses
        self.adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_avail_trunks.return_value = None
        mock_orphan_vlans.return_value = []

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

    def test_reassign_arbitrary_vid(self):
        nb = self._setup_reassign_arbitrary_vid()

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
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)[0]
        bridger = net_br.NetworkBridgerTA(self.adpt, self.host_uuid)
        trunks = bridger._find_available_trunks(nb)
        self.assertIsNotNone(trunks)

    def test_find_available_trunks_load_balance(self):
        """Tests finding the trunk with load balancing enabled."""
        # Set load balancing to True
        nb = pvm_net.NetBridge.wrap(self.mgr_nbr_fo_resp)[0]
        nb.load_balance = True
        bridger = net_br.NetworkBridgerTA(self.adpt, self.host_uuid)

        # Even though there is a free VEA, it should come back as None.  This
        # is because there is only one free VEA, but we need to balance across
        # two.
        trunks = bridger._find_available_trunks(nb)
        self.assertIsNone(trunks)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA._trunk_list')
    def test_find_available_min_trunk(self, mock_trunk_list):
        nb = mock.MagicMock()

        trunk_addl = mock.MagicMock()
        trunk_addl.tagged_vlans = ['a', 'b', 'c']
        trunk_addl2 = mock.MagicMock()
        trunk_addl2.tagged_vlans = ['e', 'f']
        trunk_addl3 = mock.MagicMock()
        trunk_addl3.tagged_vlans = ['g', 'h', 'i']

        sea = mock.MagicMock()
        sea.addl_adpts = [trunk_addl, trunk_addl2, trunk_addl3]
        nb.seas = [sea]

        bridger = net_br.NetworkBridgerTA(self.adpt, self.host_uuid)
        bridger._find_available_trunks(nb)

        # Validate the trunk list is called with the second additional adapter
        mock_trunk_list.assert_called_with(nb, trunk_addl2)

    def test_find_peer_trunk(self):
        bridger = net_br.NetworkBridgerTA(self.adpt, self.host_uuid)

        # No failover, shouldn't have a peer
        nbs = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)
        resp = bridger._find_peer_trunk(nbs[0], nbs[0].seas[0].primary_adpt)
        self.assertIsNone(resp)

        # Failover, should have a peer
        nbs = pvm_net.NetBridge.wrap(self.mgr_nbr_fo_resp)
        resp = bridger._find_peer_trunk(nbs[0], nbs[0].seas[0].primary_adpt)
        self.assertEqual(nbs[0].seas[1].primary_adpt, resp)

    @mock.patch('pypowervm.tasks.network_bridger.NetworkBridgerTA.'
                '_reassign_arbitrary_vid')
    def test_remove_vlan_from_nb_arb_vid(self, mock_reassign):
        """Attempt to remove an arbitrary VID off the network bridge."""
        # Mock Data
        self.adpt.read.return_value = self.mgr_nbr_fo_resp

        # Run the remove of the VLAN.  Make sure it is invoked with a new
        # valid arbitrary PVID.
        net_br.remove_vlan_from_nb(self.adpt, self.host_uuid, self.nb_uuid,
                                   '4094')
        self.assertEqual(1, mock_reassign.call_count)
        mock_reassign.assert_called_with(4094, 4093, mock.ANY)

    def test_remove_vlan_from_nb_lb(self):
        """Validates a load balance remove leaves an additional adpt."""
        # Mock Data
        net_bridge = pvm_net.NetBridge.wrap(self.mgr_nbr_resp)[0]
        net_bridge.load_balance = True

        # Run the remove
        bridger = net_br.NetworkBridgerTA(self.adpt, self.host_uuid)
        bridger._remove_vlan_from_nb(net_bridge, 1000)

        # Validate that we left the trunk but no new additional VLANs
        self.assertEqual(1, len(net_bridge.seas[0].addl_adpts))
        self.assertEqual(0, len(net_bridge.seas[0].addl_adpts[0].tagged_vlans))
