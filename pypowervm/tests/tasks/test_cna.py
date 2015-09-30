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

import pypowervm.adapter as adp
from pypowervm.tasks import cna
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
import pypowervm.wrappers.entry_wrapper as ewrap
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

    @mock.patch('pypowervm.tasks.cna._find_or_create_vnet')
    def test_crt_cna_new_vswitch(self, mock_vnet_find):
        """Validates the create will also create the vSwitch."""
        # First need to load in the various test responses.
        vs = tju.load_file(VSWITCH_FILE)
        self.adpt.read.return_value = vs

        # Create a side effect that can validate the input into the create
        # call.
        def validate_of_create(*kargs, **kwargs):
            self.assertIsNotNone(kargs[0])
            if 'LogicalPartition' == kargs[1]:
                self.assertEqual('LogicalPartition', kargs[1])
                self.assertEqual('fake_lpar', kwargs.get('root_id'))
                self.assertEqual('ClientNetworkAdapter',
                                 kwargs.get('child_type'))
                return pvm_net.CNA.bld(self.adpt, 1, 'href').entry
            else:
                # Is the vSwitch create
                self.assertEqual('ManagedSystem', kargs[1])
                self.assertEqual('VirtualSwitch', kwargs.get('child_type'))
                # Return a previously created vSwitch...
                return pvm_net.VSwitch.wrap(vs)[0].entry
        self.adpt.create.side_effect = validate_of_create

        n_cna = cna.crt_cna(self.adpt, 'fake_host', 'fake_lpar', 5,
                            vswitch='Temp', crt_vswitch=True)
        self.assertIsNotNone(n_cna)

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
