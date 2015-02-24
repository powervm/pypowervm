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
import unittest

import mock

from pypowervm import adapter as adpt
from pypowervm import exceptions as pvm_exc
from pypowervm.jobs import network_bridger as net_br
from pypowervm.tests.wrappers.util import pvmhttp
from pypowervm.wrappers import network as pvm_net

MGR_NET_BR_FILE = 'nbbr_network_bridge.txt'
MGR_VNET_FILE = 'nbbr_virtual_network.txt'
MGR_VSW_FILE = 'nbbr_virtual_switch.txt'


class TestNetworkBridger(unittest.TestCase):

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

    def tearDown(self):
        super(TestNetworkBridger, self).tearDown()

    @mock.patch('pypowervm.adapter.Adapter')
    def test_ensure_vlan_on_nb(self, mock_adpt):
        """This does a happy path test.  Assumes VLAN on NB already."""
        mock_adpt.read.return_value = self.mgr_nbr_resp
        net_br.ensure_vlan_on_nb(mock_adpt, 'host_uuid',
                                 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151', 2227)
        self.assertEqual(1, mock_adpt.read.call_count)

    @mock.patch('pypowervm.jobs.network_bridger._reassign_arbitrary_vid')
    @mock.patch('pypowervm.wrappers.network.NetworkBridge.supports_vlan')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_ensure_vlan_on_nb_reassign(self, mock_adpt, mock_support_vlan,
                                        mock_reassign):
        """This does a happy path test.  Assumes VLAN on NB already."""
        # Have the response
        mock_adpt.read.return_value = self.mgr_nbr_resp

        # First call, say that we don't support the VLAN (which is true).
        # Second call, fake out that we now do.
        mock_support_vlan.side_effect = [False, True]

        # Invoke
        net_br.ensure_vlan_on_nb(mock_adpt, 'host_uuid',
                                 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151', 4094)
        self.assertEqual(2, mock_adpt.read.call_count)
        self.assertEqual(1, mock_reassign.call_count)

    @mock.patch('pypowervm.jobs.network_bridger._find_or_create_vnet')
    @mock.patch('pypowervm.jobs.network_bridger._is_arbitrary_vid')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_ensure_vlan_on_nb_new_vlan(self, mock_adpt, mock_arb_vid,
                                        mock_find_vnet):
        """Validates new VLAN on existing Load Group."""
        # Build the responses
        mock_adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_vnet = mock.MagicMock()
        mock_vnet.href = 'fake_href'
        mock_find_vnet.return_value = mock_vnet

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            self.assertEqual('ManagedSystem', kargs[2])
            elem = kargs[0]
            self.assertIsNotNone(elem)
            netbr = pvm_net.NetworkBridge.wrap(adpt.Entry([], elem))
            self.assertEqual(1,
                             len(netbr.load_grps[0].virtual_network_uri_list))
            self.assertEqual(2,
                             len(netbr.load_grps[1].virtual_network_uri_list))

            # Validate the named args
            self.assertEqual('host_uuid', kwargs.get('root_id'))
            self.assertEqual('NetworkBridge', kwargs.get('child_type'))
            self.assertEqual('b6a027a8-5c0b-3ac0-8547-b516f5ba6151',
                             kwargs.get('child_id'))

        mock_adpt.update.side_effect = validate_of_update_nb

        # Invoke
        net_br.ensure_vlan_on_nb(mock_adpt, 'host_uuid',
                                 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151', 2000)

        # Validate the calls
        self.assertEqual(1, mock_adpt.update.call_count)

    @mock.patch('pypowervm.jobs.network_bridger._find_or_create_vnet')
    @mock.patch('pypowervm.jobs.network_bridger._is_arbitrary_vid')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_ensure_vlans_on_nb_new_vlan(self, mock_adpt, mock_arb_vid,
                                         mock_find_vnet):
        """Validates new VLAN on existing Load Group."""
        # Build the responses
        mock_adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_vnet = mock.MagicMock()
        mock_vnet.href = 'fake_href'
        mock_find_vnet.return_value = mock_vnet

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            self.assertEqual('ManagedSystem', kargs[2])
            elem = kargs[0]
            self.assertIsNotNone(elem)
            net_br = pvm_net.NetworkBridge.wrap(adpt.Entry({}, elem))
            self.assertEqual(1,
                             len(net_br.load_grps[0].virtual_network_uri_list))
            self.assertEqual(2,
                             len(net_br.load_grps[1].virtual_network_uri_list))

            # Validate the named args
            self.assertEqual('host_uuid', kwargs.get('root_id'))
            self.assertEqual('NetworkBridge', kwargs.get('child_type'))
            self.assertEqual('b6a027a8-5c0b-3ac0-8547-b516f5ba6151',
                             kwargs.get('child_id'))

        mock_adpt.update.side_effect = validate_of_update_nb

        # Invoke.  VLAN 2227 should be on there already.
        net_br.ensure_vlans_on_nb(mock_adpt, 'host_uuid',
                                  'b6a027a8-5c0b-3ac0-8547-b516f5ba6151',
                                  [2227, 2000])

        # Validate the calls
        self.assertEqual(1, mock_adpt.update.call_count)

    @mock.patch('pypowervm.jobs.network_bridger._find_or_create_vnet')
    @mock.patch('pypowervm.jobs.network_bridger._find_available_ld_grp')
    @mock.patch('pypowervm.jobs.network_bridger._is_arbitrary_vid')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_ensure_vlan_on_nb_new_lg(self, mock_adpt, mock_arb_vid,
                                      mock_avail_lg, mock_find_vnet):
        """Validates new VLAN on new Load Group."""
        # Build the responses
        mock_adpt.read.side_effect = [self.mgr_nbr_resp, self.mgr_vsw_resp,
                                      self.mgr_vnet_resp]
        mock_arb_vid.return_value = False
        mock_avail_lg.return_value = None

        # Make the fake virtual networks (the new, then the arb vid)
        mock_vnet = mock.MagicMock()
        mock_vnet.href = 'fake_href'
        mock_vnet_avid = mock.MagicMock()
        mock_vnet_avid.href = 'fake_avid_href'
        mock_find_vnet.side_effect = [mock_vnet, mock_vnet_avid]

        def validate_of_update_nb(*kargs, **kwargs):
            # Validate args
            self.assertEqual('ManagedSystem', kargs[2])
            elem = kargs[0]
            self.assertIsNotNone(elem)
            netbr = pvm_net.NetworkBridge.wrap(adpt.Entry([], elem))
            self.assertEqual(1,
                             len(netbr.load_grps[0].virtual_network_uri_list))
            self.assertEqual(2,
                             len(netbr.load_grps[2].virtual_network_uri_list))

            # Validate the named args
            self.assertEqual('host_uuid', kwargs.get('root_id'))
            self.assertEqual('NetworkBridge', kwargs.get('child_type'))
            self.assertEqual('b6a027a8-5c0b-3ac0-8547-b516f5ba6151',
                             kwargs.get('child_id'))
            pass

        mock_adpt.update.side_effect = validate_of_update_nb

        # Invoke
        net_br.ensure_vlan_on_nb(mock_adpt, 'host_uuid',
                                 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151', 2000)

        # Validate the calls
        self.assertEqual(1, mock_adpt.update.call_count)

    @mock.patch('pypowervm.adapter.Adapter')
    def test_find_vswitch(self, mock_adpt):
        mock_adpt.read.return_value = self.mgr_vsw_resp
        v = net_br._find_vswitch(mock_adpt,
                                 'c5d782c7-44e4-3086-ad15-b16fb039d63b', '0')
        self.assertIsNotNone(v)
        self.assertEqual(0, v.switch_id)

    def test_find_available_lb(self):
        nb = pvm_net.NetworkBridge.wrap(self.mgr_nbr_resp)
        lg = net_br._find_available_ld_grp(nb[0])
        self.assertIsNotNone(lg)

    @mock.patch('pypowervm.adapter.Adapter')
    def test_find_or_create_vnet(self, mock_adpt):
        """Validates that a vnet is created (and deleted) as part of find."""
        # Load the data
        vnets = pvm_net.VNet.wrap(self.mgr_vnet_resp)
        vsw = pvm_net.VirtualSwitch.wrap(self.mgr_vsw_resp)[0]
        host_uuid = 'c5d782c7-44e4-3086-ad15-b16fb039d63b'

        # Set up the mock create
        resp = pvm_net.VNet(
            name='FakeName', vlan_id=4094, vswitch_uri=vsw.href, tagged=True)
        mock_resp = mock.MagicMock()
        mock_resp.entry = resp._entry
        mock_adpt.create.return_value = mock_resp

        # Run the code
        ret_val = net_br._find_or_create_vnet(mock_adpt, host_uuid, vnets,
                                              4094, vsw)

        # Equality check
        self.assertEqual(4094, ret_val.vlan)
        self.assertEqual(True, ret_val.tagged)

        # Make sure the delete was called
        self.assertEqual(1, mock_adpt.delete_by_href.call_count)

    def test_is_arbitrary_vid(self):
        nbs = pvm_net.NetworkBridge.wrap(self.mgr_nbr_resp)
        self.assertTrue(net_br._is_arbitrary_vid(4094, nbs))
        self.assertFalse(net_br._is_arbitrary_vid(2227, nbs))

    def test_find_new_arbitrary_vid(self):
        nbs = pvm_net.NetworkBridge.wrap(self.mgr_nbr_resp)
        self.assertEqual(4093, net_br._find_new_arbitrary_vid(nbs))
        self.assertEqual(4092, net_br._find_new_arbitrary_vid(nbs,
                                                              others=[4093]))

    @mock.patch('pypowervm.jobs.network_bridger._find_or_create_vnet')
    @mock.patch('pypowervm.jobs.network_bridger._find_vswitch')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_reassign_arbitrary_vid(self, mock_adpt, mock_vsw,
                                    mock_find_vnet):
        vnet = pvm_net.VNet()._entry
        resp1 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp1.feed = adpt.Feed({}, [vnet])
        mock_adpt.read.return_value = resp1
        mock_adpt.read_by_href.return_value = vnet
        nb = pvm_net.NetworkBridge.wrap(self.mgr_nbr_resp)[0]
        resp2 = adpt.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp2.entry = nb._entry
        mock_adpt.update.return_value = resp2
        host_uuid = 'c5d782c7-44e4-3086-ad15-b16fb039d63b'

        vsw = pvm_net.VirtualSwitch.wrap(self.mgr_vsw_resp)[0]
        mock_vsw.return_value = vsw

        mock_find_vnet.return_value = mock.MagicMock()
        mock_find_vnet.return_value.href = 'other'

        net_br._reassign_arbitrary_vid(mock_adpt, host_uuid, 4094, 4093, nb)

        # Make sure the mocks were called
        self.assertEqual(1, mock_find_vnet.call_count)
        self.assertEqual(2, mock_adpt.update.call_count)

    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_vlan_from_nb(self, mock_adpt):
        """Happy path testing of the remove VLAN from NB."""
        # Mock Data
        mock_adpt.read.return_value = self.mgr_nbr_resp
        host_uuid = 'c5d782c7-44e4-3086-ad15-b16fb039d63b'
        nb_uuid = 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151'

        def validate_update(*kargs, **kwargs):
            # Make sure the load groups are down to just 1 now.
            nb = pvm_net.NetworkBridge.wrap(adpt.Entry({}, kargs[0]))
            self.assertEqual(1, len(nb.load_grps))

        mock_adpt.update.side_effect = validate_update

        net_br.remove_vlan_from_nb(mock_adpt, host_uuid, nb_uuid, 1000)
        self.assertEqual(1, mock_adpt.update.call_count)

    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_vlan_from_nb_bad_vid(self, mock_adpt):
        """Attempt to remove a VID that can't be taken off NB."""
        # Mock Data
        mock_adpt.read.return_value = self.mgr_nbr_resp
        host_uuid = 'c5d782c7-44e4-3086-ad15-b16fb039d63b'
        nb_uuid = 'b6a027a8-5c0b-3ac0-8547-b516f5ba6151'

        # Should fail if fail_if_pvid set to True
        self.assertRaises(pvm_exc.PvidOfNetworkBridgeError,
                          net_br.remove_vlan_from_nb, mock_adpt, host_uuid,
                          nb_uuid, 2227, True)

        # Should not fail if fail_if_pvid set to False, but shouldn't call
        # update either.
        net_br.remove_vlan_from_nb(mock_adpt, host_uuid, nb_uuid, 2227)
        self.assertEqual(0, mock_adpt.update.call_count)
