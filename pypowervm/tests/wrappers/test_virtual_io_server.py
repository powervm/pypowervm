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

import mock

import unittest

from pypowervm import adapter as adpt
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.virtual_io_server as vios


class TestVIOSWrapper(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    def test_get_ip_addresses(self):
        expected_ips = ('9.1.2.4', '10.10.10.5')
        self.assertEqual(expected_ips, self.dwrap.ip_addresses)

    def test_license_accept(self):
        self.assertTrue(self.dwrap.is_license_accepted)

    def test_is_running(self):
        self.assertTrue(self.dwrap.is_running)

    def test_is_rmc_active(self):
        self.assertTrue(self.dwrap.is_rmc_active)

    def test_hdisk_reserve_policy_found(self):
        # Most are NoReserve; look for the only one that's SinglePath to make
        # sure we're actually searching rather than picking first/last/random
        found_policy = self.dwrap.hdisk_reserve_policy(
            '6005076300838041300000000000002B')
        self.assertEqual('SinglePath', found_policy)

    def test_hdisk_reserve_policy_notfound(self):
        # Most are NoReserve; look for the only one that's SinglePath to make
        # sure we're actually searching rather than picking first/last/random
        found_policy = self.dwrap.hdisk_reserve_policy('Bogus')
        self.assertIsNone(found_policy)

    def test_hdisk_from_uuid_found(self):
        found_name = self.dwrap.hdisk_from_uuid(
            '01M0lCTTIxNDUyNEM2MDA1MDc2MzAwODM4MDQxMzAwMDAwMDAwMDAwMDhCNQ==')
        self.assertEqual('hdisk7', found_name)

    def test_hdisk_from_uuid_notfound(self):
        found_name = self.dwrap.hdisk_from_uuid('Bogus')
        self.assertIsNone(found_name)

    def test_seas(self):
        self.assertEqual(1, len(self.dwrap.seas))
        sea = self.dwrap.seas[0]
        self.assertEqual(1, sea.pvid)
        self.assertEqual(1, len(sea.addl_adpts))

    def test_trunks(self):
        self.assertEqual(3, len(self.dwrap.trunk_adapters))
        self.assertEqual(1, self.dwrap.trunk_adapters[0].pvid)
        self.assertEqual(4094, self.dwrap.trunk_adapters[1].pvid)
        self.assertEqual(4093, self.dwrap.trunk_adapters[2].pvid)

    def test_derive_orphan_trunk_adapters(self):
        orphans = self.dwrap.derive_orphan_trunk_adapters()
        self.assertEqual(1, len(orphans))
        self.assertEqual(4093, orphans[0].pvid)


class TestViosMappings(twrap.TestWrapper):

    file = 'fake_vios_mappings.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.virtual_io_server._crt_related_href')
    def test_crt_scsi_mapping_vopt(self, mock_href, mock_adpt):
        """Validation that the element is correct."""
        mock_href.return_value = adpt.Element(vios.MAP_CLIENT_LPAR,
                                              attrib={'href': 'href',
                                                      'rel': 'related'})
        vmap = vios.crt_scsi_map_to_vopt(mock_adpt, 'host_uuid',
                                         'client_lpar_uuid', 'media_name')
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap._element)
        self.assertEqual(vios._NEW_CLIENT_ADAPTER.tag,
                         vmap.find('ClientAdapter').tag)
        self.assertEqual(vios._NEW_SERVER_ADAPTER.tag,
                         vmap.find('ServerAdapter').tag)
        self.assertEqual('media_name',
                         vmap.findtext('./Storage/VirtualOpticalMedia'
                                       '/MediaName'))

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.wrappers.virtual_io_server._crt_related_href')
    def test_crt_scsi_mapping_vdisk(self, mock_href, mock_adpt):
        """Validation that the element is correct."""
        mock_href.return_value = adpt.Element(vios.MAP_CLIENT_LPAR,
                                              attrib={'href': 'href',
                                                      'rel': 'related'})
        vmap = vios.crt_scsi_map_to_vdisk(mock_adpt, 'host_uuid',
                                          'client_lpar_uuid', 'disk_name')
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap._element)
        self.assertEqual(vios._NEW_CLIENT_ADAPTER.tag,
                         vmap.find('ClientAdapter').tag)
        self.assertEqual(vios._NEW_SERVER_ADAPTER.tag,
                         vmap.find('ServerAdapter').tag)
        self.assertEqual('disk_name',
                         vmap.findtext('./Storage/VirtualDisk/DiskName'))

    def test_get_scsi_mappings(self):
        mappings = self.dwrap.scsi_mappings

        # Ensure that at least one adapter has a client LPAR & storage
        found_client_uri = False
        static_map = None
        for mapping in mappings:
            if (mapping.client_lpar_href and
                    mapping.backing_storage is not None):
                found_client_uri = True
                static_map = mapping
        self.assertTrue(found_client_uri)

        # We'll use the previous mapping as a baseline for further validation
        self.assertIsNotNone(static_map.client_adapter)
        self.assertIsNotNone(static_map.backing_storage)
        self.assertIsNotNone(static_map.server_adapter)

        # Deeper check on each of these.
        ca = static_map.client_adapter
        self.assertIsNotNone(ca.lpar_id)
        self.assertTrue(ca.is_varied_on)
        self.assertIsNotNone(ca.slot_number)
        self.assertIsNotNone(ca.loc_code)
        self.assertEqual(ca.side, 'Client')

        sa = static_map.server_adapter
        self.assertIsNotNone(sa.name)
        self.assertIsNotNone(sa.backing_dev_name)
        self.assertIsNotNone(sa.udid)
        self.assertEqual(sa.side, 'Server')
        self.assertTrue(sa.is_varied_on)
        self.assertIsNotNone(sa.slot_number)
        self.assertIsNotNone(sa.loc_code)

        # Try copying the map and adding it in
        new_map = copy.deepcopy(static_map)
        orig_size = len(mappings)
        mappings.append(new_map)
        self.assertEqual(len(mappings), orig_size + 1)
        self.assertEqual(len(self.dwrap.scsi_mappings), orig_size + 1)

        mappings.remove(new_map)
        self.dwrap.scsi_mappings = mappings
        self.assertEqual(len(self.dwrap.scsi_mappings), orig_size)

    def test_vfc_mappings(self):
        mappings = self.dwrap.vfc_mappings

        # Ensure that at least one adapter has a client LPAR
        found_client_uri = False
        static_map = None
        for mapping in mappings:
            if mapping.client_lpar_href:
                found_client_uri = True
                static_map = mapping
        self.assertTrue(found_client_uri)

        # We'll use the previous mapping as a baseline for further validation
        self.assertIsNotNone(static_map.client_adapter)
        self.assertIsNotNone(static_map.backing_port)
        self.assertIsNotNone(static_map.server_adapter)

        # Deeper check on each of these.
        ca = static_map.client_adapter
        self.assertIsNotNone(ca.wwpns)
        self.assertIsNotNone(ca.lpar_id)
        self.assertTrue(ca.is_varied_on)
        self.assertIsNotNone(ca.slot_number)
        self.assertIsNotNone(ca.loc_code)
        self.assertEqual(ca.side, 'Client')

        bp = static_map.backing_port
        self.assertIsNotNone(bp.loc_code)
        self.assertIsNotNone(bp.name)
        self.assertIsNotNone(bp.udid)
        self.assertIsNotNone(bp.wwpn)
        self.assertIsNotNone(bp.available_ports)
        self.assertIsNotNone(bp.total_ports)

        sa = static_map.server_adapter
        self.assertIsNotNone(sa.name)
        self.assertIsNotNone(sa.map_port)
        self.assertIsNotNone(sa.udid)
        self.assertEqual(sa.side, 'Server')
        self.assertTrue(sa.is_varied_on)
        self.assertIsNotNone(sa.slot_number)
        self.assertIsNotNone(sa.loc_code)

        # Try copying the map and adding it in
        new_map = copy.deepcopy(static_map)
        orig_size = len(mappings)
        mappings.append(new_map)
        self.assertEqual(len(mappings), orig_size + 1)
        self.assertEqual(len(self.dwrap.vfc_mappings), orig_size + 1)

        mappings.remove(new_map)
        self.dwrap.vfc_mappings = mappings
        self.assertEqual(len(self.dwrap.vfc_mappings), orig_size)

if __name__ == "__main__":
    unittest.main()
