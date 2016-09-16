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

import pypowervm.adapter as adpt
import pypowervm.const as c
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.storage as pvm_stor
import pypowervm.wrappers.virtual_io_server as vios


class TestVIOSWrapper(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

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

    def test_mover_service_partition(self):
        self.assertTrue(self.dwrap.is_mover_service_partition)
        self.dwrap.is_mover_service_partition = False
        self.assertFalse(self.dwrap.is_mover_service_partition)

    def test_rmc_ip(self):
        self.assertEqual('9.1.2.5', self.dwrap.rmc_ip)

    def test_license_accept(self):
        self.assertTrue(self.dwrap.is_license_accepted)

    def test_vnic_capabilities(self):
        self.assertTrue(self.dwrap.vnic_capable)
        self.assertTrue(self.dwrap.vnic_failover_capable)

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
        self.assertTrue(vmap.client_adapter._get_val_bool(
            'UseNextAvailableSlotID'))
        self.assertEqual(vmap.server_adapter.side, 'Server')
        # Validate the exact XML of the server adapter: ensure proper ordering.
        self.assertEqual(
            '<uom:ServerAdapter xmlns:uom="http://www.ibm.com/xmlns/systems/po'
            'wer/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata>'
            '<uom:Atom/></uom:Metadata><uom:AdapterType>Server</uom:AdapterTyp'
            'e><uom:UseNextAvailableSlotID>true</uom:UseNextAvailableSlotID></'
            'uom:ServerAdapter>'.encode('utf-8'),
            vmap.server_adapter.toxmlstring())
        # If the slot number is None then REST will assign the first available.
        self.assertIsNone(vmap.client_adapter.lpar_slot_num)
        self.assertIsNone(vmap.target_dev)
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
        self.assertIsNone(vmap2.client_adapter.lpar_slot_num)
        self.assertIsNone(vmap2.target_dev)
        self.assertEqual('media_name2', vmap2.backing_storage.media_name)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.VOptMedia)

        # Clone to a different device type
        vdisk = pvm_stor.VDisk.bld_ref(self.adpt, 'disk_name')
        vmap3 = vios.VSCSIMapping.bld_from_existing(
            vmap, vdisk, lpar_slot_num=6, lua='vdisk_lua')
        self.assertIsNotNone(vmap3)
        self.assertIsNotNone(vmap3.element)
        # Validate the exact XML of the client adapter: ensure proper ordering.
        self.assertEqual(
            '<uom:ClientAdapter xmlns:uom="http://www.ibm.com/xmlns/systems/po'
            'wer/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata>'
            '<uom:Atom/></uom:Metadata><uom:AdapterType>Client</uom:AdapterTyp'
            'e><uom:UseNextAvailableSlotID>false</uom:UseNextAvailableSlotID><'
            'uom:VirtualSlotNumber>6</uom:VirtualSlotNumber></uom:ClientAdapte'
            'r>'.encode('utf-8'), vmap3.client_adapter.toxmlstring())
        self.assertEqual('Client', vmap3.client_adapter.side)
        # Specifying 'lua' builds the appropriate type of target dev...
        self.assertIsInstance(vmap3.target_dev, pvm_stor.VDiskTargetDev)
        # ...with the correct LUA
        self.assertEqual('vdisk_lua', vmap3.target_dev.lua)
        self.assertEqual(6, vmap3.client_adapter.lpar_slot_num)
        # Assert this is set to False when specifying the slot number
        # and building from an existing mapping
        self.assertFalse(vmap3.client_adapter._get_val_bool(
            'UseNextAvailableSlotID'))
        self.assertEqual('Server', vmap3.server_adapter.side)
        self.assertEqual('disk_name', vmap3.backing_storage.name)
        self.assertEqual('a_link', vmap3.client_lpar_href)
        self.assertIsInstance(vmap3.backing_storage, pvm_stor.VDisk)

    def test_bld_scsi_mapping_vdisk(self):
        """Validation that the element is correct."""
        vdisk = pvm_stor.VDisk.bld_ref(self.adpt, 'disk_name')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', vdisk,
                                     lpar_slot_num=5, lua='vdisk_lua')
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap.element)
        self.assertEqual('Client', vmap.client_adapter.side)
        self.assertIsInstance(vmap.target_dev, pvm_stor.VDiskTargetDev)
        self.assertEqual('vdisk_lua', vmap.target_dev.lua)
        self.assertEqual(5, vmap.client_adapter.lpar_slot_num)
        # Assert that we set this to False when specifying the slot number
        self.assertFalse(vmap.client_adapter._get_val_bool(
            'UseNextAvailableSlotID'))
        self.assertEqual('Server', vmap.server_adapter.side)
        self.assertEqual('disk_name', vmap.backing_storage.name)
        self.assertEqual('a_link', vmap.client_lpar_href)
        self.assertIsInstance(vmap.backing_storage, pvm_stor.VDisk)

        # Test cloning
        vdisk2 = pvm_stor.VDisk.bld_ref(self.adpt, 'disk_name2')
        vmap2 = vios.VSCSIMapping.bld_from_existing(vmap, vdisk2,
                                                    lpar_slot_num=6)
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual('Client', vmap2.client_adapter.side)
        # Cloning without specifying 'lua' doesn't clone the target dev
        self.assertIsNone(vmap2.target_dev)
        self.assertEqual(6, vmap2.client_adapter.lpar_slot_num)
        self.assertFalse(vmap2.client_adapter._get_val_bool(
            'UseNextAvailableSlotID'))
        self.assertEqual('Server', vmap2.server_adapter.side)
        self.assertEqual('disk_name2', vmap2.backing_storage.name)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.VDisk)

    def test_bld_scsi_mapping_lu(self):
        """Validation that the element is correct."""
        lu = pvm_stor.LU.bld_ref(self.adpt, 'disk_name', 'udid')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', lu,
                                     lpar_slot_num=5)
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap.element)
        self.assertEqual('Client', vmap.client_adapter.side)
        self.assertIsNone(vmap.target_dev)
        self.assertEqual(5, vmap.client_adapter.lpar_slot_num)
        self.assertEqual('Server', vmap.server_adapter.side)
        self.assertEqual('disk_name', vmap.backing_storage.name)
        self.assertEqual('udid', vmap.backing_storage.udid)
        self.assertEqual('a_link', vmap.client_lpar_href)
        self.assertIsInstance(vmap.backing_storage, pvm_stor.LU)

        # Test cloning
        lu2 = pvm_stor.LU.bld_ref(self.adpt, 'disk_name2', 'udid2')
        vmap2 = vios.VSCSIMapping.bld_from_existing(vmap, lu2, lua='lu_lua')
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual('Client', vmap2.client_adapter.side)
        self.assertEqual(5, vmap2.client_adapter.lpar_slot_num)
        self.assertIsInstance(vmap2.target_dev, pvm_stor.LUTargetDev)
        self.assertEqual('lu_lua', vmap2.target_dev.lua)
        self.assertEqual('Server', vmap2.server_adapter.side)
        self.assertEqual('disk_name2', vmap2.backing_storage.name)
        self.assertEqual('udid2', vmap2.backing_storage.udid)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.LU)

    def test_bld_scsi_mapping_pv(self):
        """Validation that the element is correct."""
        pv = pvm_stor.PV.bld(self.adpt, 'disk_name', 'udid')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', pv,
                                     lpar_slot_num=5, target_name='fake_name')
        self.assertIsNotNone(vmap)
        self.assertIsNotNone(vmap.element)
        self.assertEqual('Client', vmap.client_adapter.side)
        self.assertEqual(5, vmap.client_adapter.lpar_slot_num)
        self.assertEqual('Server', vmap.server_adapter.side)
        self.assertEqual('disk_name', vmap.backing_storage.name)
        self.assertEqual('a_link', vmap.client_lpar_href)
        self.assertEqual('fake_name', vmap.target_dev.name)
        self.assertIsInstance(vmap.backing_storage, pvm_stor.PV)

        # Test cloning
        pv2 = pvm_stor.PV.bld(self.adpt, 'disk_name2', 'udid2')
        vmap2 = vios.VSCSIMapping.bld_from_existing(
            vmap, pv2, lpar_slot_num=6, lua='pv_lua')
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual('Client', vmap2.client_adapter.side)
        self.assertEqual(6, vmap2.client_adapter.lpar_slot_num)
        self.assertIsInstance(vmap2.target_dev, pvm_stor.PVTargetDev)
        self.assertEqual('pv_lua', vmap2.target_dev.lua)
        self.assertEqual('Server', vmap2.server_adapter.side)
        self.assertEqual('disk_name2', vmap2.backing_storage.name)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertIsNone(vmap2.target_dev.name)
        self.assertIsInstance(vmap2.backing_storage, pvm_stor.PV)

        # Test empty target_dev_type
        pv3 = pvm_stor.PV.bld(self.adpt, 'disk_name3', 'udid3')
        vmap3 = vios.VSCSIMapping.bld_from_existing(
            vmap, pv3, lpar_slot_num=6)
        self.assertIsNone(vmap3.target_dev)

    def test_clone_scsi_mapping_no_storage(self):
        """Clone a VSCSI mapping with no storage element."""
        pv = pvm_stor.PV.bld(self.adpt, 'disk_name', 'udid')
        vmap = vios.VSCSIMapping.bld(self.adpt, 'host_uuid',
                                     'client_lpar_uuid', pv,
                                     lpar_slot_num=5)
        vmap2 = vios.VSCSIMapping.bld_from_existing(vmap, None)
        self.assertIsNotNone(vmap2)
        self.assertIsNotNone(vmap2.element)
        self.assertEqual('Client', vmap2.client_adapter.side)
        self.assertEqual('Server', vmap2.server_adapter.side)
        self.assertEqual('a_link', vmap2.client_lpar_href)
        self.assertEqual(5, vmap2.client_adapter.lpar_slot_num)
        self.assertIsNone(vmap.target_dev)
        self.assertIsNone(vmap2.backing_storage)
        # Illegal to specify target dev properties without backing storage.
        self.assertRaises(ValueError, vios.VSCSIMapping.bld_from_existing,
                          vmap, None, lua='bogus')

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

    def test_bld_vfc_mapping_with_slot(self):
        mapping = vios.VFCMapping.bld(self.adpt, 'host_uuid',
                                      'client_lpar_uuid', 'fcs0',
                                      client_wwpns=['aa', 'bb'],
                                      lpar_slot_num=3)
        self.assertIsNotNone(mapping)

        # Validate the FC Backing port
        self.assertIsNotNone(mapping.backing_port)

        # Validate the Server Adapter
        self.assertIsNotNone(mapping.server_adapter)

        # Validate the Client Adapter
        self.assertIsNotNone(mapping.client_adapter)
        self.assertEqual(['AA', 'BB'], mapping.client_adapter.wwpns)
        # verify the slot number
        self.assertEqual(3, mapping.client_adapter.lpar_slot_num)
        # Assert that we set this to False when specifying the slot number
        self.assertFalse(mapping.client_adapter._get_val_bool(
            'UseNextAvailableSlotID'))

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


class TestVSCSIBus(twrap.TestWrapper):
    file = 'vscsibus_feed.txt'
    wrapper_class_to_test = vios.VSCSIBus

    def test_props(self):
        self.assertEqual(4, len(self.entries))
        bus = self.dwrap
        self.assertEqual('1f25efc1-a42b-3384-85e7-f37158f46615', bus.uuid)
        self.assertEqual(
            'http://localhost:12080/rest/api/uom/ManagedSystem/1cab7366-6b73-3'
            '42c-9f43-ddfeb9f8edd3/LogicalPartition/3DFF2EF5-6F99-4C29-B655-EE'
            '57DF1B64C6', bus.client_lpar_href)
        self.assertEqual(5, bus.client_adapter.lpar_id)
        self.assertEqual(2, bus.client_adapter.lpar_slot_num)
        self.assertEqual(5, bus.server_adapter.lpar_id)
        self.assertEqual(2, bus.server_adapter.lpar_slot_num)
        map1, map2 = bus.mappings
        self.assertIsInstance(map1.backing_storage, pvm_stor.PV)
        self.assertEqual('hdisk10', map1.backing_storage.name)
        self.assertIsInstance(map1.target_dev, pvm_stor.PVTargetDev)
        self.assertEqual('0x8100000000000000', map1.target_dev.lua)
        self.assertIsInstance(map2.backing_storage, pvm_stor.VOptMedia)
        self.assertEqual('cfg_My_OS_Image_V_3dff2ef5_000000.iso',
                         map2.backing_storage.name)
        self.assertIsInstance(map2.target_dev, pvm_stor.VOptTargetDev)
        self.assertEqual('0x8200000000000000', map2.target_dev.lua)

    def test_bld(self):
        self.adpt.build_href.return_value = 'href'
        # Default slot number (use next available)
        bus = vios.VSCSIBus.bld(self.adpt, 'client_lpar_uuid')
        self.adpt.build_href.assert_called_once_with(
            'LogicalPartition', 'client_lpar_uuid', xag=[])
        self.assertEqual('href', bus.client_lpar_href)
        self.assertTrue(bus.client_adapter._get_val_bool(
            pvm_stor._VADPT_NEXT_SLOT))
        self.assertIsNotNone(bus.server_adapter)
        self.assertEqual([], bus.mappings)
        # Specify slot number
        bus = vios.VSCSIBus.bld(self.adpt, 'client_lpar_uuid',
                                lpar_slot_num=42)
        self.assertFalse(bus.client_adapter._get_val_bool(
            pvm_stor._VADPT_NEXT_SLOT))
        self.assertEqual(42, bus.client_adapter.lpar_slot_num)

    def test_bld_from_existing(self):
        bus = vios.VSCSIBus.bld_from_existing(self.dwrap)
        self.assertEqual(
            'http://localhost:12080/rest/api/uom/ManagedSystem/1cab7366-6b73-3'
            '42c-9f43-ddfeb9f8edd3/LogicalPartition/3DFF2EF5-6F99-4C29-B655-EE'
            '57DF1B64C6', bus.client_lpar_href)
        self.assertEqual(5, bus.client_adapter.lpar_id)
        self.assertEqual(2, bus.client_adapter.lpar_slot_num)
        self.assertEqual(5, bus.server_adapter.lpar_id)
        self.assertEqual(2, bus.server_adapter.lpar_slot_num)
        self.assertEqual([], bus.mappings)

    def test_mappings(self):
        # No LUA
        lu1 = pvm_stor.LU.bld_ref(self.adpt, 'lu1', 'lu_udid1')
        std1 = vios.STDev.bld(self.adpt, lu1)
        self.assertIsInstance(std1.backing_storage, pvm_stor.LU)
        self.assertEqual('lu1', std1.backing_storage.name)
        self.assertIsNone(std1.target_dev)
        # With LUA
        vdisk1 = pvm_stor.VDisk.bld_ref(self.adpt, 'vdisk1')
        std2 = vios.STDev.bld(self.adpt, vdisk1, lua='vdisk1_lua')
        self.assertIsInstance(std2.backing_storage, pvm_stor.VDisk)
        self.assertEqual('vdisk1', std2.backing_storage.name)
        self.assertIsInstance(std2.target_dev, pvm_stor.VDiskTargetDev)
        self.assertEqual('vdisk1_lua', std2.target_dev.lua)
        # Add 'em to a bus
        bus = self.dwrap
        self.assertEqual(2, len(bus.mappings))
        bus.mappings.extend((std1, std2))
        self.assertEqual(4, len(bus.mappings))
        self.assertEqual('lu1', bus.mappings[2].backing_storage.name)
        self.assertEqual('vdisk1', bus.mappings[3].backing_storage.name)
        # Replace bus mappings
        bus.mappings = [std2, std1]
        self.assertEqual(2, len(bus.mappings))
        self.assertEqual('vdisk1', bus.mappings[0].backing_storage.name)
        self.assertEqual('lu1', bus.mappings[1].backing_storage.name)


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
        self.assertEqual(826, self.io_slot.pci_subsys_dev_id)
        self.assertEqual(4116, self.io_slot.pci_mfg_id)
        self.assertEqual(1, self.io_slot.pci_rev_id)
        self.assertEqual(4116, self.io_slot.pci_vendor_id)
        self.assertEqual(4116, self.io_slot.pci_subsys_vendor_id)
        self.assertEqual(553713674, self.io_slot.drc_index)
        self.assertEqual('U78AB.001.WZSJBM3-P1-T9',
                         self.io_slot.drc_name)
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

    @mock.patch('warnings.warn')
    def test_io_adpt(self, mock_warn):
        self.assertEqual('553713674', self.io_slot.io_adapter.id)
        # Verify deprecation warning on IOSlot.adapter
        self.assertEqual('553713674', self.io_slot.adapter.id)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)

    def test_bld(self):
        new_slot = bp.IOSlot.bld(self.adpt, True, 12345678)
        self.assertEqual(False, new_slot.required)
        self.assertEqual(True, new_slot.bus_grp_required)
        self.assertEqual(12345678, new_slot.drc_index)


class TestGenericIOAdapter(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

    def setUp(self):
        super(TestGenericIOAdapter, self).setUp()
        self.io_adpt = self.dwrap.io_config.io_slots[0].io_adapter

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
        self.io_adpt = self.dwrap.io_config.io_slots[2].io_adapter

    def test_attrs(self):
        desc = '8 Gigabit PCI Express Dual Port Fibre Channel Adapter'

        self.assertEqual('553714177', self.io_adpt.id)
        self.assertEqual(desc, self.io_adpt.description)
        self.assertEqual('U78AB.001.WZSJBM3-P1-C2', self.io_adpt.dev_name)
        self.assertEqual('U78AB.001.WZSJBM3-P1-C2',
                         self.io_adpt.drc_name)
        self.assertEqual('C2', self.io_adpt.phys_loc_code)
        self.assertIsInstance(self.io_adpt, bp.PhysFCAdapter)

    def test_fc_ports(self):
        self.assertEqual(2, len(self.io_adpt.fc_ports))


class TestPhysFCPort(twrap.TestWrapper):

    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

    def setUp(self):
        super(TestPhysFCPort, self).setUp()
        self.io_port1 = self.dwrap.io_config.io_slots[2].io_adapter.fc_ports[0]
        self.io_port2 = self.dwrap.io_config.io_slots[2].io_adapter.fc_ports[1]

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


class TestFeed3(twrap.TestWrapper):
    """Tests that specifically need fake_vios_feed3.txt"""
    file = 'fake_vios_feed3.txt'
    wrapper_class_to_test = vios.VIOS

    def test_vivify_io_adpts_for_link_agg(self):
        """Vivifying FreeIOAdaptersForLinkAggregation adds the Network xag."""
        # The first VIOS doesn't have FreeIOAdapters...
        vwrp = self.dwrap
        self.assertIsNone(vwrp._find(vios._VIO_FREE_IO_ADPTS_FOR_LNAGG))
        # Vivify it - should be empty
        self.assertEqual([], vwrp.io_adpts_for_link_agg)
        # Now it's in there
        elem = vwrp._find(vios._VIO_FREE_IO_ADPTS_FOR_LNAGG)
        self.assertIsNotNone(elem)
        # Got the right xag
        self.assertEqual(c.XAG.VIO_NET, elem.attrib['group'])

    @mock.patch('warnings.warn')
    def test_xags(self, mock_warn):
        """Test deprecated extented attribute groups on the VIOS class.

        This can be removed once VIOS.xags is removed.
        """
        expected = dict(NETWORK=c.XAG.VIO_NET, STORAGE=c.XAG.VIO_STOR,
                        SCSI_MAPPING=c.XAG.VIO_SMAP, FC_MAPPING=c.XAG.VIO_FMAP)

        for key, val in expected.items():
            # Test class accessor, ensure '.name' works.
            self.assertEqual(val, getattr(vios.VIOS.xags, key).name)
            mock_warn.assert_called_with(mock.ANY, DeprecationWarning)
            mock_warn.reset_mock()
            # Test instance accessor.
            self.assertEqual(val, getattr(self.dwrap.xags, key))
            mock_warn.assert_called_with(mock.ANY, DeprecationWarning)
            mock_warn.reset_mock()

        # And in case getattr(foo, 'bar') actually differs from foo.bar...
        self.assertEqual(c.XAG.VIO_NET, vios.VIOS.xags.NETWORK)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)
        mock_warn.reset_mock()
        # Make sure the equality comparison works the other way
        self.assertEqual(self.dwrap.xags.NETWORK, c.XAG.VIO_NET)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)
        # Test sorting
        self.assertTrue(c.XAG.VIO_NET < self.dwrap.xags.SCSI_MAPPING)
        self.assertTrue(self.dwrap.xags.NETWORK < c.XAG.VIO_SMAP)

if __name__ == "__main__":
    unittest.main()
