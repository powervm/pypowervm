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

import os

from pypowervm.jobs import cna
from pypowervm.tests.wrappers.util import pvmhttp

import unittest


VSWITCH_FILE = 'cna_vswitches.txt'
VNET_FILE = 'fake_virtual_network_feed.txt'


class TestCNA(unittest.TestCase):
    """Unit Tests for creating Client Network Adapters."""

    @mock.patch('pypowervm.jobs.cna._find_or_create_vnet')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_crt_cna(self, mock_adpt, mock_vnet_find):
        """Tests the creation of Client Network Adapters."""
        # First need to load in the various test responses.
        vs = self._load_file(VSWITCH_FILE)
        mock_adpt.read.return_value = vs

        # Create a side effect that can validate the input into the create
        # call.
        def validate_of_create(*kargs, **kwargs):
            self.assertIsNotNone(kargs[0])
            self.assertEqual('LogicalPartition', kargs[1])
            self.assertEqual('fake_lpar', kwargs.get('root_id'))
            self.assertEqual('ClientNetworkAdapter', kwargs.get('child_type'))
            return mock.MagicMock()
        mock_adpt.create.side_effect = validate_of_create

        n_cna = cna.crt_cna(mock_adpt, 'fake_host', 'fake_lpar', 5)
        self.assertIsNotNone(n_cna)

    @mock.patch('pypowervm.adapter.Adapter')
    def test_find_or_create_vnet(self, mock_adpt):
        """Tests that the virtual network can be found/created."""
        vn = pvmhttp.load_pvm_resp(VNET_FILE).get_response()
        mock_adpt.read.return_value = vn

        fake_vs = mock.MagicMock()
        fake_vs.switch_id = 0
        fake_vs.name = 'ETHERNET0'

        host_uuid = '67dca605-3923-34da-bd8f-26a378fc817f'
        uri = ('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
               '67dca605-3923-34da-bd8f-26a378fc817f/VirtualSwitch/'
               'ec8aaa54-9837-3c23-a541-a4e4be3ae489')

        # This should find a vnet.
        vnet_resp = cna._find_or_create_vnet(mock_adpt, host_uuid, '2227',
                                             fake_vs, uri)
        self.assertIsNotNone(vnet_resp)

        # Now flip to a CNA that requires a create...
        mock_adpt.create.return_value = mock.MagicMock()
        vnet_resp = cna._find_or_create_vnet(mock_adpt, host_uuid, '2228',
                                             fake_vs, uri)
        self.assertIsNotNone(vnet_resp)
        self.assertEqual(1, mock_adpt.create.call_count)

    def _load_file(self, file_name):
        """Helper method to load the responses from a given location."""
        data_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(data_dir, 'data')
        file_path = os.path.join(data_dir, file_name)
        return pvmhttp.load_pvm_resp(file_path).get_response()
