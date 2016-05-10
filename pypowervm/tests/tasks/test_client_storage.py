# Copyright 2016 IBM Corp.
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

from pypowervm.tasks import client_storage as clstor
from pypowervm.tests.test_utils import test_wrapper_abc as twrap
from pypowervm.wrappers import virtual_io_server as vios


class TestClientStorage(twrap.TestWrapper):
    file = 'fake_vios_mappings.txt'
    wrapper_class_to_test = vios.VIOS

    def test_udid2scsi(self):
        """Test udid_to_scsi_mapping."""

        maps = self.dwrap.scsi_mappings

        # 2nd mapping has no client adapter
        lpar_id = maps[1].server_adapter.lpar_id
        # Default: ignore orphan
        self.assertIsNone(clstor.udid_to_scsi_mapping(
            self.dwrap, maps[1].backing_storage.udid, lpar_id))
        # Don't ignore orphan
        self.assertEqual(maps[1], clstor.udid_to_scsi_mapping(
            self.dwrap, maps[1].backing_storage.udid, lpar_id,
            ignore_orphan=False))
        # Doesn't work if the LPAR ID is wrong
        self.assertIsNone(clstor.udid_to_scsi_mapping(
            self.dwrap, maps[1].backing_storage.udid, 123,
            ignore_orphan=False))

        # 4th mapping has client adapter but no backing storage
        self.assertIsNone(clstor.udid_to_scsi_mapping(self.dwrap, 'bogus', 22))

    def test_c_wwpn_to_vfc(self):
        """Test c_wwpn_to_vfc_mapping."""
        # Since the first two VFC mappings have no client adapter, this test
        # proves we skip those properly.
        self.assertEqual(self.dwrap.vfc_mappings[5],
                         clstor.c_wwpn_to_vfc_mapping(
                             self.dwrap, 'C05076065A7C02E3'))

        # This works with (limited) craziness in the WWPN format
        self.assertEqual(self.dwrap.vfc_mappings[5],
                         clstor.c_wwpn_to_vfc_mapping(
                             self.dwrap, 'c0:50:76:06:5a:7c:02:e3'))

        # Not found
        self.assertIsNone(clstor.c_wwpn_to_vfc_mapping(
            self.dwrap, 'ab:cd:ef:01:23:45:67:89'))
