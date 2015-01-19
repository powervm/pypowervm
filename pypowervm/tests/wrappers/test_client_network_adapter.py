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
        self.cna = cna.ClientNetworkAdapter(cna_resp.entry)

    def tearDown(self):
        super(TestClientNetworkAdapterWrapper, self).tearDown()

    def test_get_slot(self):
        """Test getting the VirtualSlotID."""
        self.assertEqual(32, self.cna.slot)

    def test_get_mac(self):
        """Test that we can get the mac address."""
        self.assertEqual("FAD4433ED120", self.cna.mac)

    def test_get_pvid(self):
        """Test that the PVID returns properly."""
        self.assertEqual(100, self.cna.pvid)

if __name__ == "__main__":
    unittest.main()
