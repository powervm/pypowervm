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


class TestCNA(unittest.TestCase):
    """Unit Tests for creating Client Network Adapters."""

    @mock.patch('pypowervm.adapter.Adapter')
    def test_crt_cna(self, mock_adpt):
        """Tests the creation of Client Network Adapters."""
        # First need to load in the various test responses.
        vs = self._load_file(VSWITCH_FILE)
        mock_adpt.read.return_value = vs

        # Create a side effect that can validate the input into the create
        # call.
        def validate_of_create(*kargs, **kwargs):
            self.assertIsNotNone(kargs[0])
            self.assertEqual('ManagedSystem', kargs[1])
            self.assertEqual('fake_host', kargs[2])
            self.assertEqual('ClientNetworkAdapter', kargs[3])
            return mock.MagicMock()
        mock_adpt.create.side_effect = validate_of_create

        n_cna = cna.crt_cna(mock_adpt, 'fake_host', 'fake_lpar', 5)
        self.assertIsNotNone(n_cna)

    def _load_file(self, file_name):
        """Helper method to load the responses from a given location."""
        data_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(data_dir, 'data')
        file_path = os.path.join(data_dir, file_name)
        return pvmhttp.load_pvm_resp(file_path).get_response()
