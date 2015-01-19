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

import mock

import unittest

from pypowervm import adapter as adpt
from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.virtual_io_server as vios


VIOS_FILE = 'fake_vios_ssp_npiv.txt'
VIOS_MAPPINGS_FILE = 'fake_vios_mappings.txt'


class TestVIOSWrapper(unittest.TestCase):

    _vios_resp = None

    def setUp(self):
        super(TestVIOSWrapper, self).setUp()
        if TestVIOSWrapper._vios_resp:
            self.vios_resp = TestVIOSWrapper._vios_resp
            return
        TestVIOSWrapper._vios_resp = pvmhttp.load_pvm_resp(
            VIOS_FILE).get_response()
        self.vios_resp = TestVIOSWrapper._vios_resp

    def test_get_ip_addresses(self):
        vios_wrapper = vios.VirtualIOServer(self.vios_resp.entry)
        expected_ips = ['9.1.2.4', '10.10.10.5']
        self.assertEqual(expected_ips, vios_wrapper.get_ip_addresses())

    def test_license_accept(self):
        vios_wrapper = vios.VirtualIOServer(self.vios_resp.entry)
        self.assertEqual(True, vios_wrapper.is_license_accepted)

    def test_is_running(self):
        vios_wrapper = vios.VirtualIOServer(self.vios_resp.entry)
        self.assertEqual(True, vios_wrapper.is_running)

    def test_is_rmc_active(self):
        vios_wrapper = vios.VirtualIOServer(self.vios_resp.entry)
        self.assertEqual(True, vios_wrapper.is_rmc_active)


class TestViosMappings(unittest.TestCase):

    def setUp(self):
        super(TestViosMappings, self).setUp()
        self.vio_res = pvmhttp.load_pvm_resp(VIOS_MAPPINGS_FILE).get_response()
        self.vios_obj = vios.VirtualIOServer(self.vio_res.entry)

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
        self.assertEqual(vmap.attrib['group'], 'ViosSCSIMapping')
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
        self.assertEqual(vmap.attrib['group'], 'ViosSCSIMapping')
        self.assertEqual(vios._NEW_CLIENT_ADAPTER.tag,
                         vmap.find('ClientAdapter').tag)
        self.assertEqual(vios._NEW_SERVER_ADAPTER.tag,
                         vmap.find('ServerAdapter').tag)
        self.assertEqual('disk_name',
                         vmap.findtext('./Storage/VirtualDisk/DiskName'))

    def test_get_scsi_mappings(self):
        mappings = self.vios_obj.get_scsi_mappings()

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

    def test_get_vfc_mappings(self):
        mappings = self.vios_obj.get_vfc_mappings()

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

if __name__ == "__main__":
    unittest.main()
