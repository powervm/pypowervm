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
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.virtual_io_server as vios


class TestVIOSWrapper(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    def test_get_ip_addresses(self):
        expected_ips = ('9.1.2.4', '10.10.10.5')
        self.assertEqual(expected_ips, self.dwrap.ip_addresses)

    def test_license_accept(self):
        self.assertEqual(True, self.dwrap.is_license_accepted)

    def test_is_running(self):
        self.assertEqual(True, self.dwrap.is_running)

    def test_is_rmc_active(self):
        self.assertEqual(True, self.dwrap.is_rmc_active)

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

    def test_wwpns(self):
        """Tests the helper methods to get WWPNs more easily."""
        phys_paths = self.dwrap.get_pfc_wwpns()
        self.assertIsNotNone(phys_paths)
        self.assertEqual(2, len(phys_paths))

        virt_paths = self.dwrap.get_vfc_wwpns()
        self.assertIsNotNone(virt_paths)
        self.assertEqual(2, len(virt_paths))
        self.assertEqual(2, len(virt_paths[0]))
        self.assertEqual(2, len(virt_paths[1]))


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
        self.assertIsNotNone(bp.npiv_available_ports)
        self.assertIsNotNone(bp.npiv_total_ports)

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


class TestPartitionIOConfiguration(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    def setUp(self):
        super(TestPartitionIOConfiguration, self).setUp()
        self.io_config = self.dwrap.io_config

    def test_max_slots(self):
        self.assertEqual(80, self.io_config.max_virtual_slots)

    def test_io_slots(self):
        # IO Slots are typically associated with the VIOS.  Further testing
        # driven there.
        self.assertIsNotNone(self.io_config.io_slots)
        self.assertEqual(3, len(self.io_config.io_slots))


class TestIOSlots(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    def setUp(self):
        super(TestIOSlots, self).setUp()
        self.io_slot = self.dwrap.io_config.io_slots[0]

    def test_attrs(self):
        self.assertEqual('PCI-E SAS Controller', self.io_slot.description)
        self.assertEqual('U78AB.001.WZSJBM3', self.io_slot.phys_loc)
        self.assertEqual('825', self.io_slot.pc_adpt_id)
        self.assertEqual('260', self.io_slot.pci_class)
        self.assertEqual('825', self.io_slot.pci_dev_id)
        self.assertEqual('825', self.io_slot.pci_subsys_dev_id)
        self.assertEqual('4116', self.io_slot.pci_mfg_id)
        self.assertEqual('1', self.io_slot.pci_rev_id)
        self.assertEqual('4116', self.io_slot.pci_vendor_id)
        self.assertEqual('4116', self.io_slot.pci_subsys_vendor_id)

    def test_io_adpt(self):
        self.assertIsNotNone(self.io_slot.adapter)


class TestGenericIOAdapter(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    def setUp(self):
        super(TestGenericIOAdapter, self).setUp()
        self.io_adpt = self.dwrap.io_config.io_slots[0].adapter

    def test_attrs(self):
        self.assertEqual('553713674', self.io_adpt.id)
        self.assertEqual('PCI-E SAS Controller', self.io_adpt.description)
        self.assertEqual('PCI-E SAS Controller', self.io_adpt.dev_name)
        self.assertEqual('U78AB.001.WZSJBM3-P1-T9',
                         self.io_adpt.dyn_reconfig_conn_name)
        self.assertEqual('T9', self.io_adpt.phys_loc_code)
        self.assertFalse(isinstance(self.io_adpt, lpar.PhysFCAdapter))


class TestPhysFCAdapter(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    def setUp(self):
        super(TestPhysFCAdapter, self).setUp()
        self.io_adpt = self.dwrap.io_config.io_slots[2].adapter

    def test_attrs(self):
        desc = '8 Gigabit PCI Express Dual Port Fibre Channel Adapter'

        self.assertEqual('553714177', self.io_adpt.id)
        self.assertEqual(desc, self.io_adpt.description)
        self.assertEqual(desc, self.io_adpt.dev_name)
        self.assertEqual('U78AB.001.WZSJBM3-P1-C2',
                         self.io_adpt.dyn_reconfig_conn_name)
        self.assertEqual('C2', self.io_adpt.phys_loc_code)
        self.assertTrue(isinstance(self.io_adpt, lpar.PhysFCAdapter))

    def test_fc_ports(self):
        self.assertEqual(2, len(self.io_adpt.fc_ports))


class TestPhysFCPort(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VirtualIOServer

    def setUp(self):
        super(TestPhysFCPort, self).setUp()
        self.io_port1 = self.dwrap.io_config.io_slots[2].adapter.fc_ports[0]
        self.io_port2 = self.dwrap.io_config.io_slots[2].adapter.fc_ports[1]

    def test_attrs(self):
        self.assertEqual('U78AB.001.WZSJBM3-P1-C2-T2', self.io_port1.loc_code)
        self.assertEqual('fcs1', self.io_port1.name)
        self.assertEqual('1aU78AB.001.WZSJBM3-P1-C2-T2', self.io_port1.udid)
        self.assertEqual('10000090FA1B6303', self.io_port1.wwpn)
        self.assertEqual(0, self.io_port1.npiv_available_ports)
        self.assertEqual(0, self.io_port1.npiv_total_ports)

        self.assertEqual('U78AB.001.WZSJBM3-P1-C2-T1', self.io_port2.loc_code)
        self.assertEqual('fcs0', self.io_port2.name)
        self.assertEqual('1aU78AB.001.WZSJBM3-P1-C2-T1', self.io_port2.udid)
        self.assertEqual('10000090FA1B6302', self.io_port2.wwpn)
        self.assertEqual(64, self.io_port2.npiv_available_ports)
        self.assertEqual(64, self.io_port2.npiv_total_ports)

if __name__ == "__main__":
    unittest.main()
