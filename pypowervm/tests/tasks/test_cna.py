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

from pypowervm import adapter as adp
from pypowervm import exceptions as exc
from pypowervm.tasks import cna
from pypowervm.tests.tasks import util as tju
from pypowervm.tests import test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers import entry_wrapper as ewrap
from pypowervm.wrappers import logical_partition as pvm_lpar
from pypowervm.wrappers import network as pvm_net

VSWITCH_FILE = 'fake_vswitch_feed.txt'
VNET_FILE = 'fake_virtual_network_feed.txt'


class TestCNA(testtools.TestCase):
    """Unit Tests for creating Client Network Adapters."""

    def setUp(self):
        super(TestCNA, self).setUp()
        # Adapter with HMCish Traits
        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemoteHMCTraits))
        self.adpt = self.adptfx.adpt

    @mock.patch('pypowervm.tasks.cna._find_or_create_vnet')
    def test_crt_cna(self, mock_vnet_find):
        """Tests the creation of Client Network Adapters."""
        # First need to load in the various test responses.
        vs = tju.load_file(VSWITCH_FILE)
        self.adpt.read.return_value = vs

        # Create a side effect that can validate the input into the create
        # call.
        def validate_of_create(*kargs, **kwargs):
            self.assertIsNotNone(kargs[0])
            self.assertEqual('LogicalPartition', kargs[1])
            self.assertEqual('fake_lpar', kwargs.get('root_id'))
            self.assertEqual('ClientNetworkAdapter', kwargs.get('child_type'))
            return pvm_net.CNA.bld(self.adpt, 1, 'href').entry
        self.adpt.create.side_effect = validate_of_create

        n_cna = cna.crt_cna(self.adpt, 'fake_host', 'fake_lpar', 5)
        self.assertIsNotNone(n_cna)
        self.assertIsInstance(n_cna, pvm_net.CNA)
        self.assertEqual(1, mock_vnet_find.call_count)

    @mock.patch('pypowervm.tasks.cna._find_or_create_vnet')
    def test_crt_cna_no_vnet_crt(self, mock_vnet_find):
        """Tests the creation of Client Network Adapters.

        The virtual network creation shouldn't be done in this flow.
        """
        # First need to load in the various test responses.
        vs = tju.load_file(VSWITCH_FILE)
        self.adpt.read.return_value = vs
        # PVMish Traits
        self.adptfx.set_traits(fx.LocalPVMTraits)

        # Create a side effect that can validate the input into the create
        # call.
        def validate_of_create(*kargs, **kwargs):
            self.assertIsNotNone(kargs[0])
            self.assertEqual('LogicalPartition', kargs[1])
            self.assertEqual('fake_lpar', kwargs.get('root_id'))
            self.assertEqual('ClientNetworkAdapter', kwargs.get('child_type'))
            return pvm_net.CNA.bld(self.adpt, 1, 'href').entry
        self.adpt.create.side_effect = validate_of_create

        n_cna = cna.crt_cna(self.adpt, 'fake_host', 'fake_lpar', 5)
        self.assertIsNotNone(n_cna)
        self.assertIsInstance(n_cna, pvm_net.CNA)
        self.assertEqual(0, mock_vnet_find.call_count)

    def test_find_or_create_vswitch(self):
        """Validates that a vswitch can be created."""
        # First need to load in the various test responses.
        vs = tju.load_file(VSWITCH_FILE)
        self.adpt.read.return_value = vs

        # Create a side effect that can validate the input into the create
        # call.
        def validate_of_create(*kargs, **kwargs):
            self.assertIsNotNone(kargs[0])
            # Is the vSwitch create
            self.assertEqual('ManagedSystem', kargs[1])
            self.assertEqual('VirtualSwitch', kwargs.get('child_type'))
            # Return a previously created vSwitch...
            return pvm_net.VSwitch.wrap(vs)[0].entry
        self.adpt.create.side_effect = validate_of_create

        vswitch_w = cna._find_or_create_vswitch(self.adpt, 'fake_host',
                                                'Temp', True)
        self.assertIsNotNone(vswitch_w)

        # Make sure that if the create flag is set to false, an error is thrown
        # when the vswitch can't be found.
        self.assertRaises(exc.Error, cna._find_or_create_vswitch, self.adpt,
                          'fake_host', 'Temp', False)

    def test_find_or_create_vnet(self):
        """Tests that the virtual network can be found/created."""
        vn = pvmhttp.load_pvm_resp(VNET_FILE).get_response()
        self.adpt.read.return_value = vn

        fake_vs = mock.Mock()
        fake_vs.switch_id = 0
        fake_vs.name = 'ETHERNET0'

        host_uuid = '67dca605-3923-34da-bd8f-26a378fc817f'
        fake_vs.related_href = ('https://9.1.2.3:12443/rest/api/uom/'
                                'ManagedSystem/'
                                '67dca605-3923-34da-bd8f-26a378fc817f/'
                                'VirtualSwitch/'
                                'ec8aaa54-9837-3c23-a541-a4e4be3ae489')

        # This should find a vnet.
        vnet_resp = cna._find_or_create_vnet(self.adpt, host_uuid, '2227',
                                             fake_vs)
        self.assertIsNotNone(vnet_resp)

        # Now flip to a CNA that requires a create...
        resp = adp.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp.entry = ewrap.EntryWrapper._bld(
            self.adpt, tag='VirtualNetwork').entry
        self.adpt.create.return_value = resp
        vnet_resp = cna._find_or_create_vnet(self.adpt, host_uuid, '2228',
                                             fake_vs)
        self.assertIsNotNone(vnet_resp)
        self.assertEqual(1, self.adpt.create.call_count)

    def test_find_free_vlan(self):
        """Tests that a free VLAN can be found."""
        vn = pvmhttp.load_pvm_resp(VNET_FILE).get_response()
        self.adpt.read.return_value = vn

        # Mock data specific to the VNET File
        host_uuid = '67dca605-3923-34da-bd8f-26a378fc817f'
        fake_vs = mock.Mock()
        fake_vs.name = 'ETHERNET0'
        fake_vs.related_href = ('https://9.1.2.3:12443/rest/api/uom/'
                                'ManagedSystem/'
                                '67dca605-3923-34da-bd8f-26a378fc817f/'
                                'VirtualSwitch/'
                                'ec8aaa54-9837-3c23-a541-a4e4be3ae489')

        self.assertEqual(1, cna._find_free_vlan(self.adpt, host_uuid, fake_vs))

    @mock.patch('pypowervm.wrappers.network.VNet.wrap')
    def test_find_free_vlan_mocked(self, mock_vnet_wrap):
        """Uses lots of mock data for a find vlan."""
        self.adpt.read.return_value = mock.Mock()

        # Helper function to build the vnets.
        def build_mock_vnets(max_vlan, vswitch_uri):
            vnets = []
            for x in range(1, max_vlan + 1):
                vnets.append(mock.Mock(vlan=x,
                                       associated_switch_uri=vswitch_uri))
            return vnets

        mock_vswitch = mock.Mock(related_href='test_vs')

        # Test when all the vnet's are on a single switch.
        mock_nets = build_mock_vnets(3000, 'test_vs')
        mock_vnet_wrap.return_value = mock_nets
        self.assertEqual(3001, cna._find_free_vlan(self.adpt, 'host_uuid',
                                                   mock_vswitch))

        # Test with multiple switches.  The second vswitch with a higher vlan
        # should not impact the vswitch we're searching for.
        mock_nets = (build_mock_vnets(2000, 'test_vs') +
                     build_mock_vnets(4000, 'test_vs2'))
        mock_vnet_wrap.return_value = mock_nets
        self.assertEqual(2001, cna._find_free_vlan(self.adpt, 'host_uuid',
                                                   mock_vswitch))

    @mock.patch('pypowervm.wrappers.network.CNA.bld')
    @mock.patch('pypowervm.tasks.cna._find_free_vlan')
    @mock.patch('pypowervm.tasks.cna._find_or_create_vswitch')
    def test_crt_p2p_cna(
            self, mock_find_or_create_vswitch, mock_find_free_vlan,
            mock_cna_bld):
        """Tests the crt_p2p_cna."""
        mock_vswitch = mock.Mock(related_href='vswitch_href')

        mock_find_or_create_vswitch.return_value = mock_vswitch
        mock_find_free_vlan.return_value = 2050

        mock_cna, mock_trunk = mock.MagicMock(), mock.MagicMock()
        mock_cna_bld.side_effect = [mock_cna, mock_trunk]

        client_adpt, trunk_adpts = cna.crt_p2p_cna(
            self.adpt, 'host_uuid', 'lpar_uuid', ['src_io_host_uuids'],
            mock_vswitch, crt_vswitch=True, mac_addr='aabbccddeeff')

        # Make sure the client and trunk were 'built'
        mock_cna_bld.assert_any_call(self.adpt, 2050, 'vswitch_href',
                                     mac_addr='aabbccddeeff')
        mock_cna_bld.assert_any_call(self.adpt, 2050, 'vswitch_href',
                                     trunk_pri=1)

        # Make sure they were then created
        self.assertIsNotNone(client_adpt)
        self.assertEqual(1, len(trunk_adpts))
        mock_cna.create.assert_called_once_with(
            parent_type=pvm_lpar.LPAR, parent_uuid='lpar_uuid')
        mock_trunk.create.assert_called_once_with(
            parent_type=pvm_lpar.LPAR, parent_uuid='src_io_host_uuids')
