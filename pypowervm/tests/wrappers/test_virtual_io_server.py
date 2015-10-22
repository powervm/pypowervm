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
import unittest

import mock

import pypowervm.adapter as adpt
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.storage as pvm_stor
import pypowervm.wrappers.virtual_io_server as vios


class TestVIOSWrapper(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

    def test_xag_hash(self):
        self.assertEqual(hash('ViosNetwork'), hash(vios.VIOS.xags.NETWORK))
        self.assertEqual(hash('ViosStorage'), hash(vios.VIOS.xags.STORAGE))
        self.assertEqual(hash('ViosSCSIMapping'),
                         hash(vios.VIOS.xags.SCSI_MAPPING))
        self.assertEqual(hash('ViosFCMapping'),
                         hash(vios.VIOS.xags.FC_MAPPING))

    def test_update_timeout(self):
        self.adpt.update_by_path.return_value = self.dwrap.entry
        self.assertEqual(self.dwrap.entry, self.dwrap.update().entry)
        self.adpt.update_by_path.assert_called_with(self.dwrap, None, mock.ANY,
                                                    timeout=3600)
        self.assertEqual(self.dwrap.entry, self.dwrap.update(timeout=42).entry)
        self.adpt.update_by_path.assert_called_with(self.dwrap, None, mock.ANY,
                                                    timeout=42)
        # If the session is configured for longer...
        self.adpt.session.timeout = 10000
        self.assertEqual(self.dwrap.entry, self.dwrap.update().entry)
        # ...default to the longer value.
        self.adpt.update_by_path.assert_called_with(self.dwrap, None, mock.ANY,
                                                    timeout=10000)
        # But explicit timeout can still be set.
        self.assertEqual(self.dwrap.entry, self.dwrap.update(timeout=42).entry)
        self.adpt.update_by_path.assert_called_with(self.dwrap, None, mock.ANY,
                                                    timeout=42)

    def test_get_ip_addresses(self):
        expected_ips = ('9.1.2.4', '10.10.10.5')
        self.assertEqual(expected_ips, self.dwrap.ip_addresses)

    def test_rmc_ip(self):
        self.assertEqual('9.1.2.5', self.dwrap.rmc_ip)

    def test_license_accept(self):
        self.assertTrue(self.dwrap.is_license_accepted)

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
        for virt_path in virt_paths:
            self.assertEqual(2, len(virt_path))

        self.assertEqual(1, len(self.dwrap.get_active_pfc_wwpns()))
        self.assertEqual('10000090FA1B6302',
                         self.dwrap.get_active_pfc_wwpns()[0])

    def test_pfc_ports(self):
        """Tests that the physical FC ports can be gathered."""
        ports = self.dwrap.pfc_ports
        self.assertIsNotNone(ports)
        self.assertEqual(2, len(ports))

        # Validate attributes on one.
        self.assertEqual('U78AB.001.WZSJBM3-P1-C2-T2', ports[0].loc_code)
        self.assertEqual('fcs1', ports[0].name)
        self.assertEqual('1aU78AB.001.WZSJBM3-P1-C2-T2', ports[0].udid)
        self.assertEqual('10000090FA1B6303', ports[0].wwpn)
        self.assertEqual(0, ports[0].npiv_available_ports)
        self.assertEqual(0, ports[0].npiv_total_ports)

    def test_phys_vols(self):
        """Tests that the physical volumes can be gathered."""
        phys_vols = self.dwrap.phys_vols
        self.assertIsNotNone(phys_vols)
        self.assertEqual(11, len(phys_vols))

        # Validate attributes on one.
        self.assertEqual(phys_vols[0].description, 'SAS Disk Drive')
        self.assertEqual(phys_vols[0].udid,
                         '01M0lCTU1CRjI2MDBSQzUwMDAwMzk0NzgzQTUyQjg=')
        self.assertEqual(phys_vols[0].capacity, 572325)
        self.assertEqual(phys_vols[0].name, 'hdisk0')
        self.assertEqual(phys_vols[0].state, 'active')


class TestViosMappings(twrap.TestWrapper):

    file = 'fake_vios_mappings.txt'
    wrapper_class_to_test = vios.VIOS
    mock_adapter_fx_args = {}

    def setUp(self):
        super(TestViosMappings, self).setUp()
        self.adpt.build_href.return_value = "a_link"

    def test_bld_scsi_mapping_vopt(self):
        """Validation that the element is correct."""
        vopt = pvm_stor.VOptMedia.bld_ref(self.adpt, 'media_name')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', vopt)
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap.element)
        self.assertEqual(vmap.client_adapter.side, 'Client')
        self.assertEqual(vmap.server_adapter.side, 'Server')
        self.assertEqual('media_name', vmap.backing_storage.media_name)
        self.assertEqual('a_link', vmap.client_lpar_href)
        self.assertIsInstance(vmap.backing_storage, pvm_stor.VOptMedia)

        # Test the cloning
        vopt2 = pvm_stor.VOptMedia.bld_ref(self.adpt, 'media_name2')
        vmap2 = vios.VSCSIMapping.bld_from_existing(vmap, vopt2)
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual(vmap2.client_adapter.side, 'Client')
        self.assertEqual(vmap2.server_adapter.side, 'Server')
        self.assertEqual('media_name2', vmap2.backing_storage.media_name)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.VOptMedia)

        # Clone to a different device type
        vdisk = pvm_stor.VDisk.bld_ref(self.adpt, 'disk_name')
        vmap3 = vios.VSCSIMapping.bld_from_existing(vmap, vdisk)
        self.assertIsNotNone(vmap3)
        self.assertIsNotNone(vmap3.element)
        self.assertEqual('Client', vmap3.client_adapter.side)
        self.assertEqual('Server', vmap3.server_adapter.side)
        self.assertEqual('disk_name', vmap3.backing_storage.name)
        self.assertEqual('a_link', vmap3.client_lpar_href)
        self.assertIsInstance(vmap3.backing_storage, pvm_stor.VDisk)

    def test_bld_scsi_mapping_vdisk(self):
        """Validation that the element is correct."""
        vdisk = pvm_stor.VDisk.bld_ref(self.adpt, 'disk_name')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', vdisk)
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap.element)
        self.assertEqual('Client', vmap.client_adapter.side)
        self.assertEqual('Server', vmap.server_adapter.side)
        self.assertEqual('disk_name', vmap.backing_storage.name)
        self.assertEqual('a_link', vmap.client_lpar_href)
        self.assertIsInstance(vmap.backing_storage, pvm_stor.VDisk)

        # Test cloning
        vdisk2 = pvm_stor.VDisk.bld_ref(self.adpt, 'disk_name2')
        vmap2 = vios.VSCSIMapping.bld_from_existing(vmap, vdisk2)
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual('Client', vmap2.client_adapter.side)
        self.assertEqual('Server', vmap2.server_adapter.side)
        self.assertEqual('disk_name2', vmap2.backing_storage.name)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.VDisk)

    def test_bld_scsi_mapping_lu(self):
        """Validation that the element is correct."""
        lu = pvm_stor.LU.bld_ref(self.adpt, 'disk_name', 'udid')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', lu)
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap.element)
        self.assertEqual('Client', vmap.client_adapter.side)
        self.assertEqual('Server', vmap.server_adapter.side)
        self.assertEqual('disk_name', vmap.backing_storage.name)
        self.assertEqual('udid', vmap.backing_storage.udid)
        self.assertEqual('a_link', vmap.client_lpar_href)
        self.assertIsInstance(vmap.backing_storage, pvm_stor.LU)

        # Test cloning
        lu2 = pvm_stor.LU.bld_ref(self.adpt, 'disk_name2', 'udid2')
        vmap2 = vios.VSCSIMapping.bld_from_existing(vmap, lu2)
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual('Client', vmap2.client_adapter.side)
        self.assertEqual('Server', vmap2.server_adapter.side)
        self.assertEqual('disk_name2', vmap2.backing_storage.name)
        self.assertEqual('udid2', vmap2.backing_storage.udid)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.LU)

    def test_bld_scsi_mapping_pv(self):
        """Validation that the element is correct."""
        pv = pvm_stor.PV.bld(self.adpt, 'disk_name', 'udid')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', pv)
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap.element)
        self.assertEqual('Client', vmap.client_adapter.side)
        self.assertEqual('Server', vmap.server_adapter.side)
        self.assertEqual('disk_name', vmap.backing_storage.name)
        self.assertEqual('a_link', vmap.client_lpar_href)
        self.assertIsInstance(vmap.backing_storage, pvm_stor.PV)

        # Test cloning
        pv2 = pvm_stor.PV.bld(self.adpt, 'disk_name2', 'udid2')
        vmap2 = vios.VSCSIMapping.bld_from_existing(vmap, pv2)
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual('Client', vmap2.client_adapter.side)
        self.assertEqual('Server', vmap2.server_adapter.side)
        self.assertEqual('disk_name2', vmap2.backing_storage.name)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.PV)

    def test_get_scsi_mappings(self):
        mappings = self.dwrap.scsi_mappings

        # Ensure that at least one adapter has a client LPAR & storage
        found_client_uri = False
        static_map = None
        for mapping in mappings:
            if mapping.client_lpar_href and mapping.backing_storage:
                found_client_uri = True
                static_map = mapping
        self.assertTrue(found_client_uri)

        # We'll use the previous mapping as a baseline for further validation
        self.assertIsNotNone(static_map.client_adapter)
        self.assertIsNotNone(static_map.backing_storage)
        self.assertIsNotNone(static_map.server_adapter)

        # Deeper check on each of these.
        ca = static_map.client_adapter
        self.assertEqual(5, ca.lpar_id)
        self.assertEqual(1, ca.vios_id)
        self.assertTrue(ca.is_varied_on)
        self.assertIsNotNone(ca.lpar_slot_num)
        self.assertIsNotNone(ca.vios_slot_num)
        self.assertIsNotNone(ca.loc_code)
        self.assertEqual(ca.side, 'Client')

        sa = static_map.server_adapter
        self.assertEqual(10, sa.lpar_id)
        self.assertEqual(1, sa.vios_id)
        self.assertIsNotNone(sa.name)
        self.assertIsNotNone(sa.backing_dev_name)
        self.assertIsNotNone(sa.udid)
        self.assertEqual(sa.side, 'Server')
        self.assertTrue(sa.is_varied_on)
        self.assertIsNotNone(sa.lpar_slot_num)
        self.assertIsNotNone(sa.vios_slot_num)
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
        self.assertIsNotNone(ca.vios_id)
        self.assertTrue(ca.is_varied_on)
        self.assertIsNotNone(ca.lpar_slot_num)
        self.assertIsNotNone(ca.vios_slot_num)
        self.assertIsNotNone(ca.loc_code)
        self.assertEqual(ca.side, 'Client')

        bport = static_map.backing_port
        self.assertIsNotNone(bport.loc_code)
        self.assertIsNotNone(bport.name)
        self.assertIsNotNone(bport.udid)
        self.assertIsNotNone(bport.wwpn)
        self.assertIsNotNone(bport.npiv_available_ports)
        self.assertIsNotNone(bport.npiv_total_ports)

        sa = static_map.server_adapter
        self.assertIsNotNone(sa.name)
        self.assertIsNotNone(sa.map_port)
        self.assertIsNotNone(sa.udid)
        self.assertEqual(sa.side, 'Server')
        self.assertTrue(sa.is_varied_on)
        self.assertIsNotNone(sa.lpar_slot_num)
        self.assertIsNotNone(sa.vios_slot_num)
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

    def test_bld_vfc_mapping(self):
        mapping = vios.VFCMapping.bld(self.adpt, 'host_uuid',
                                      'client_lpar_uuid', 'fcs0', ['aa', 'bb'])
        self.assertIsNotNone(mapping)

        # Validate the FC Backing port
        self.assertIsNotNone(mapping.backing_port)

        # Validate the Server Adapter
        self.assertIsNotNone(mapping.server_adapter)

        # Validate the Client Adapter
        self.assertIsNotNone(mapping.client_adapter)
        self.assertEqual(['AA', 'BB'], mapping.client_adapter.wwpns)

    def test_bld_scsi_mapping_from_existing(self):
        def map_has_pieces(smap, lpar_href=True, client_adapter=True,
                           server_adapter=True, storage=True,
                           target_device=True):
            def has_piece(piece, has_it):
                if has_it:
                    self.assertIsNotNone(piece)
                else:
                    self.assertIsNone(piece)
            has_piece(smap.client_lpar_href, lpar_href)
            has_piece(smap.client_adapter, client_adapter)
            has_piece(smap.server_adapter, server_adapter)
            has_piece(smap.backing_storage, storage)
            has_piece(smap.element.find('TargetDevice'), target_device)
        stg = pvm_stor.VDisk.bld_ref(self.adpt, 'disk_name')
        smaps = self.dwrap.scsi_mappings
        # 0 has only ServerAdapter
        sm = smaps[0]
        map_has_pieces(sm, lpar_href=False, client_adapter=False,
                       storage=False, target_device=False)
        smclone = vios.VSCSIMapping.bld_from_existing(sm, stg)
        map_has_pieces(smclone, lpar_href=False, client_adapter=False,
                       target_device=False)
        self.assertEqual(stg, smclone.backing_storage)
        # 1 has ServerAdapter, Storage, and TargetDevice
        sm = smaps[1]
        map_has_pieces(sm, lpar_href=False, client_adapter=False)
        self.assertNotEqual(stg, sm.backing_storage)
        smclone = vios.VSCSIMapping.bld_from_existing(sm, stg)
        # Target device *disappears*
        map_has_pieces(smclone, lpar_href=False, client_adapter=False,
                       target_device=False)
        self.assertEqual(stg, smclone.backing_storage)
        # 3 has AssociatedLogicalPartition, ClientAdapter, ServerAdapter.
        sm = smaps[3]
        map_has_pieces(sm, storage=False, target_device=False)
        smclone = vios.VSCSIMapping.bld_from_existing(sm, stg)
        map_has_pieces(smclone, target_device=False)
        self.assertEqual(stg, smclone.backing_storage)
        # 12 has everything
        sm = smaps[12]
        map_has_pieces(sm)
        self.assertNotEqual(stg, sm.backing_storage)
        smclone = vios.VSCSIMapping.bld_from_existing(sm, stg)
        # Target device *disappears*
        map_has_pieces(smclone, target_device=False)
        self.assertEqual(stg, smclone.backing_storage)
        # Everything else cloned okay
        self.assertEqual(sm.client_lpar_href, smclone.client_lpar_href)
        self.assertEqual(sm.client_adapter, smclone.client_adapter)
        self.assertEqual(sm.server_adapter, smclone.server_adapter)


class TestCrtRelatedHref(unittest.TestCase):
    @mock.patch('pypowervm.adapter.Session')
    def test_crt_related_href(self, mock_sess):
        """Tests to make sure that related elements are well formed."""
        mock_sess.dest = 'root'
        adapter = adpt.Adapter(mock_sess)
        href = vios.VStorageMapping.crt_related_href(adapter, 'host', 'lpar')
        self.assertEqual('root/rest/api/uom/ManagedSystem/host/'
                         'LogicalPartition/lpar', href)


class TestPartitionIOConfiguration(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

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
    wrapper_class_to_test = vios.VIOS

    def setUp(self):
        super(TestIOSlots, self).setUp()
        self.io_slot = self.dwrap.io_config.io_slots[0]

    def test_attrs(self):
        self.assertEqual('PCI-E SAS Controller', self.io_slot.description)
        self.assertEqual('U78AB.001.WZSJBM3', self.io_slot.phys_loc)
        self.assertEqual(825, self.io_slot.pc_adpt_id)
        self.assertEqual(260, self.io_slot.pci_class)
        self.assertEqual(825, self.io_slot.pci_dev_id)
        self.assertEqual(825, self.io_slot.pci_subsys_dev_id)
        self.assertEqual(4116, self.io_slot.pci_mfg_id)
        self.assertEqual(1, self.io_slot.pci_rev_id)
        self.assertEqual(4116, self.io_slot.pci_vendor_id)
        self.assertEqual(4116, self.io_slot.pci_subsys_vendor_id)
        self.assertEqual(553713674, self.io_slot.pci_subsys_drc_index)
        self.assertEqual('U78AB.001.WZSJBM3-P1-T9',
                         self.io_slot.pci_subsys_drc_name)
        self.assertEqual(False, self.io_slot.bus_grp_required)
        self.assertEqual(False, self.io_slot.required)

    def test_io_slots_setter(self):
        old_len = len(self.dwrap.io_config.io_slots)
        new_io_slots = self.dwrap.io_config.io_slots[:]
        deleted_slot = new_io_slots[1]
        del new_io_slots[1]
        self.dwrap.io_config.io_slots = new_io_slots
        self.assertEqual(old_len - 1, len(self.dwrap.io_config.io_slots))
        self.assertNotIn(deleted_slot, self.dwrap.io_config.io_slots)

    def test_io_adpt(self):
        self.assertIsNotNone(self.io_slot.adapter)

    def test_bld(self):
        new_slot = bp.IOSlot.bld(self.adpt, True, 12345678)
        self.assertEqual(False, new_slot.required)
        self.assertEqual(True, new_slot.bus_grp_required)
        self.assertEqual(12345678, new_slot.pci_subsys_drc_index)


class TestGenericIOAdapter(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

    def setUp(self):
        super(TestGenericIOAdapter, self).setUp()
        self.io_adpt = self.dwrap.io_config.io_slots[0].adapter

    def test_attrs(self):
        self.assertEqual('553713674', self.io_adpt.id)
        self.assertEqual('PCI-E SAS Controller', self.io_adpt.description)
        self.assertEqual('U78AB.001.WZSJBM3-P1-T9',
                         self.io_adpt.dev_name)
        self.assertEqual('U78AB.001.WZSJBM3-P1-T9',
                         self.io_adpt.drc_name)
        self.assertEqual('T9', self.io_adpt.phys_loc_code)
        self.assertFalse(isinstance(self.io_adpt, bp.PhysFCAdapter))


class TestPhysFCAdapter(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

    def setUp(self):
        super(TestPhysFCAdapter, self).setUp()
        self.io_adpt = self.dwrap.io_config.io_slots[2].adapter

    def test_attrs(self):
        desc = '8 Gigabit PCI Express Dual Port Fibre Channel Adapter'

        self.assertEqual('553714177', self.io_adpt.id)
        self.assertEqual(desc, self.io_adpt.description)
        self.assertEqual('U78AB.001.WZSJBM3-P1-C2', self.io_adpt.dev_name)
        self.assertEqual('U78AB.001.WZSJBM3-P1-C2',
                         self.io_adpt.drc_name)
        self.assertEqual('C2', self.io_adpt.phys_loc_code)
        self.assertTrue(isinstance(self.io_adpt, bp.PhysFCAdapter))

    def test_fc_ports(self):
        self.assertEqual(2, len(self.io_adpt.fc_ports))


class TestPhysFCPort(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

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


class TestIOAdapterChoices(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

    def setUp(self):
        super(TestIOAdapterChoices, self).setUp()
        self.io_adpts = self.dwrap.io_adpts_for_link_agg

    def test_adapter_choices(self):
        self.assertEqual(len(self.io_adpts), 3)
        self.assertEqual(self.io_adpts[0].id, '1')
        self.assertEqual(
            self.io_adpts[0].description,
            '4-Port Gigabit Ethernet PCI-Express Adapter (e414571614102004)')
        self.assertEqual(self.io_adpts[0].dev_name, 'ent3')
        self.assertEqual(self.io_adpts[0].dev_type, 'physicalEthernetAdpter')
        self.assertEqual(self.io_adpts[0].drc_name,
                         'U78AB.001.WZSJBM3-P1-C7-T4')
        self.assertEqual(self.io_adpts[0].phys_loc_code,
                         'U78AB.001.WZSJBM3-P1-C7-T4')
        self.assertEqual(self.io_adpts[0].udid,
                         '13U78AB.001.WZSJBM3-P1-C7-T4')

if __name__ == "__main__":
    unittest.main()
