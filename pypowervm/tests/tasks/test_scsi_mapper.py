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

from pypowervm.tasks import scsi_mapper
from pypowervm.tests.tasks import util as tju
from pypowervm.tests import test_fixtures as fx
from pypowervm.wrappers import storage as pvm_stor
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIO_MULTI_MAP_FILE = 'vio_multi_vscsi_mapping.txt'
VIO_MULTI_MAP_FILE2 = 'fake_vios_mappings.txt'
LPAR_UUID = '42AD4FD4-DC64-4935-9E29-9B7C6F35AFCC'


class TestSCSIMapper(testtools.TestCase):

    def setUp(self):
        super(TestSCSIMapper, self).setUp()
        # Common Adapter
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        # Don't really sleep
        self.useFixture(fx.SleepFx())

        # Fake URI
        mock_crt_href_p = mock.patch('pypowervm.wrappers.virtual_io_server.'
                                     'VSCSIMapping.crt_related_href')
        self.mock_crt_href = mock_crt_href_p.start()
        self.addCleanup(mock_crt_href_p.stop)
        href = ('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                'c5d782c7-44e4-3086-ad15-b16fb039d63b/LogicalPartition/' +
                LPAR_UUID)
        self.mock_crt_href.return_value = href

        # Mock the delay function, by overriding the sleep
        mock_delay_p = mock.patch('time.sleep')
        self.mock_delay = mock_delay_p.start()
        self.addCleanup(mock_delay_p.stop)

        self.v1resp = tju.load_file(VIO_MULTI_MAP_FILE, self.adpt)
        self.v1wrap = pvm_vios.VIOS.wrap(self.v1resp)
        self.v2resp = tju.load_file(VIO_MULTI_MAP_FILE2, self.adpt)
        self.v2wrap = pvm_vios.VIOS.wrap(self.v2resp)

    def test_mapping(self):
        # Mock Data
        self.adpt.read.return_value = self.v1resp

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(6, len(vios_w.scsi_mappings))
            self.assertEqual(vios_w.scsi_mappings[0].client_adapter,
                             vios_w.scsi_mappings[4].client_adapter)
            self.assertEqual(vios_w.scsi_mappings[0].server_adapter,
                             vios_w.scsi_mappings[4].server_adapter)
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Create the new storage dev
        pv = pvm_stor.PV.bld(self.adpt, 'pv_name', 'pv_udid')

        # Run the code
        scsi_mapper.add_vscsi_mapping('host_uuid', 'vios_uuid', LPAR_UUID,
                                      pv)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        # And the VIOS was "looked up"
        self.assertEqual(1, self.adpt.read.call_count)

        # Now do it again, but passing the vios wrapper
        self.adpt.update_by_path.reset_mock()
        self.adpt.read.reset_mock()
        scsi_mapper.add_vscsi_mapping('host_uuid', self.v1wrap, LPAR_UUID, pv)
        # Since the mapping already existed, our update mock was not called
        self.assertEqual(0, self.adpt.update_by_path.call_count)
        # And the VIOS was not "looked up"
        self.assertEqual(0, self.adpt.read.call_count)

    def test_mapping_retry(self):
        """Tests that a mapping function will be retried."""
        # Mock Data.  Need to load this once per retry, or else the mappings
        # get appended with each other.
        self.adpt.read.side_effect = [
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt),
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt),
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt)]

        global attempt_count
        attempt_count = 0

        # Validate that the mapping was added to existing.  First few times
        # through loop, force a retry exception
        def validate_update(*kargs, **kwargs):
            global attempt_count
            attempt_count += 1

            if attempt_count == 3:
                vios_w = kargs[0]
                self.assertEqual(6, len(vios_w.scsi_mappings))
                return vios_w.entry
            else:
                tju.raiseRetryException()

        self.adpt.update_by_path.side_effect = validate_update

        # Create the new storage dev
        pv = pvm_stor.PV.bld(self.adpt, 'pv_name', 'pv_udid')

        # Run the code
        scsi_mapper.add_vscsi_mapping('host_uuid', 'vios_uuid', LPAR_UUID,
                                      pv)

        # Make sure that our validation code above was invoked
        self.assertEqual(3, self.adpt.update_by_path.call_count)
        self.assertEqual(3, attempt_count)

    def test_mapping_new_mapping(self):
        """Fuse limit, slot number, LUA via add_vscsi_mapping."""
        # Mock Data
        self.adpt.read.return_value = self.v1resp

        # Validate that the mapping was added to existing
        def validate_update(*args, **kwargs):
            vios_w = args[0]
            self.assertEqual(6, len(vios_w.scsi_mappings))

            new_map = vios_w.scsi_mappings[5]
            # Make sure that the adapters do not match
            self.assertNotEqual(vios_w.scsi_mappings[0].client_adapter,
                                new_map.client_adapter)
            self.assertNotEqual(vios_w.scsi_mappings[0].server_adapter,
                                new_map.server_adapter)
            # Make sure we got the right slot number and LUA
            self.assertEqual(23, new_map.client_adapter.lpar_slot_num)
            self.assertEqual('the_lua', new_map.target_dev.lua)
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Create the new storage dev
        pv = pvm_stor.PV.bld(self.adpt, 'pv_name', 'pv_udid')

        # Run the code
        # While we're here, make sure lpar_slot_num and lua go through.  This
        # validates those kwargs in build_vscsi_mapping too.
        scsi_mapper.add_vscsi_mapping(
            'host_uuid', 'vios_uuid', LPAR_UUID, pv, fuse_limit=5,
            lpar_slot_num=23, lua='the_lua')

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_add_map(self):
        """Tests the add_map method."""
        pv = pvm_stor.PV.bld(self.adpt, 'pv_name', 'pv_udid')

        scsi_map = scsi_mapper.build_vscsi_mapping('host_uuid', self.v1wrap,
                                                   LPAR_UUID, pv,
                                                   lpar_slot_num=23)

        # Get the original count
        orig_mappings = len(self.v1wrap.scsi_mappings)

        # Add the actual mapping
        resp1 = scsi_mapper.add_map(self.v1wrap, scsi_map)
        self.assertIsNotNone(resp1)
        self.assertIsInstance(resp1, pvm_vios.VSCSIMapping)

        # Assert that the desired client slot number was set
        self.assertEqual(resp1.client_adapter.lpar_slot_num, 23)

        # The mapping should return as None, as it is already there.
        resp2 = scsi_mapper.add_map(self.v1wrap, scsi_map)
        self.assertIsNone(resp2)

        # Make sure only one was added.
        self.assertEqual(orig_mappings + 1, len(self.v1wrap.scsi_mappings))

        # Now make sure the mapping added can be found
        found = scsi_mapper.find_maps(self.v1wrap.scsi_mappings, LPAR_UUID,
                                      stg_elem=pv)
        self.assertEqual(1, len(found))
        self.assertEqual(scsi_map, found[0])

    def test_remove_storage_vopt(self):
        # Mock Data
        self.adpt.read.return_value = self.v1resp

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(4, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        media_name = 'bldr1_dfe05349_kyleh_config.iso'
        vios, remel = scsi_mapper.remove_vopt_mapping(
            self.adpt, 'fake_vios_uuid', 2, media_name=media_name)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VOptMedia)
        # And the VIOS was "looked up"
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(self.v1resp.atom, vios.entry)

        # Now do it again, but passing the vios wrapper and the client UUID.
        # Match by UDID this time.
        media_udid = '0ebldr1_dfe05349_kyleh_config.iso'
        vios_wrap = pvm_vios.VIOS.wrap(
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt))
        self.adpt.update_by_path.reset_mock()
        self.adpt.read.reset_mock()
        vios, remel = scsi_mapper.remove_vopt_mapping(
            self.adpt, vios_wrap, LPAR_UUID, udid=media_udid)
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VOptMedia)
        # But the VIOS was not "looked up"
        self.assertEqual(0, self.adpt.read.call_count)
        self.assertEqual(vios_wrap.entry, vios.entry)

    def test_remove_storage_vopt_no_name_specified(self):
        # Mock Data
        self.adpt.read.return_value = self.v1resp

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(4, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_vopt_mapping(
            self.adpt, 'fake_vios_uuid', 2, media_name=None)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VOptMedia)
        self.assertEqual(self.v1resp.atom, vios.entry)

    def test_remove_storage_vopt_retry(self):
        """Tests removing the storage vOpt with multiple retries."""
        # Mock Data.  The retry will call this three times.  They have to
        # be indepdent loads, otherwise the data gets re-used and the remove
        # will not be properly invoked.
        self.adpt.read.side_effect = [
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt),
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt),
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt)]

        global attempt_count
        attempt_count = 0

        # Validate that the mapping was removed from existing.  First few
        # loops, force a retry
        def validate_update(*kargs, **kwargs):
            global attempt_count
            attempt_count += 1

            if attempt_count == 3:
                vios_w = kargs[0]
                self.assertEqual(4, len(vios_w.scsi_mappings))
                return vios_w.entry
            else:
                tju.raiseRetryException()

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        media_name = 'bldr1_dfe05349_kyleh_config.iso'
        remel = scsi_mapper.remove_vopt_mapping(
            self.adpt, 'fake_vios_uuid', 2, media_name=media_name)[1]

        # Make sure that our validation code above was invoked
        self.assertEqual(3, self.adpt.update_by_path.call_count)
        self.assertEqual(3, attempt_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VOptMedia)

    def _test_remove_storage_vdisk(self, *args, **kwargs):
        """Helper to test remove_storage_vdisk with various arguments."""
        # Mock Data
        self.adpt.read.return_value = self.v1resp

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwa):
            vios_w = kargs[0]
            self.assertEqual(4, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_vdisk_mapping(*args, **kwargs)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VDisk)
        self.assertEqual(self.v1resp.atom, vios.entry)

    def test_remove_storage_vdisk_name(self):
        self._test_remove_storage_vdisk(
            self.adpt, 'fake_vios_uuid', 2, disk_names=['Ubuntu1410'])

    def test_remove_storage_vdisk_udid(self):
        self._test_remove_storage_vdisk(
            self.adpt, 'fake_vios_uuid', 2,
            udids=['0300025d4a00007a000000014b36d9deaf.1'])

    def _test_remove_storage_lu(self, *args, **kwargs):
        # Mock Data
        self.adpt.read.return_value = self.v1resp

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwa):
            vios_w = kargs[0]
            self.assertEqual(4, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_lu_mapping(*args, **kwargs)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.LU)
        self.assertEqual(self.v1resp.atom, vios.entry)

    def test_remove_storage_lu_all(self):
        self._test_remove_storage_lu(self.adpt, 'fake_vios_uuid', 2)

    def test_remove_storage_lu_udid(self):
        self._test_remove_storage_lu(
            self.adpt, 'fake_vios_uuid', 2,
            udids=['270c88f8e2d36711e490ce40f2e95daf30a6d61c0dee5ec6f6a011b300'
                   'b9d0830d'])

    def _test_remove_pv_mapping(self, *args, **kwargs):
        # Mock Data
        self.adpt.read.return_value = self.v1resp

        # Validate that the mapping was removed to existing
        def validate_update(*kargs, **kwa):
            vios_w = kargs[0]
            self.assertEqual(4, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_pv_mapping(*args, **kwargs)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.PV)
        self.assertEqual(self.v1resp.atom, vios.entry)

    def test_remove_pv_mapping_name(self):
        self._test_remove_pv_mapping(self.adpt, 'fake_vios_uuid', 2, 'hdisk10')

    def test_remove_pv_mapping_udid(self):
        self._test_remove_pv_mapping(
            self.adpt, 'fake_vios_uuid', 2, None,
            udid='01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDA2MA'
                 '==')

    def test_detach_storage(self):
        """Detach storage from some mappings."""
        # In v1wrap, all five maps are associated with LPAR 2
        num_matches = 5
        self.assertEqual(num_matches, len(self.v1wrap.scsi_mappings))
        # Beforehand, four of them have storage and one does not.
        self.assertEqual(4, len(
            [sm.backing_storage for sm in self.v1wrap.scsi_mappings
             if sm.backing_storage is not None]))
        removals = scsi_mapper.detach_storage(self.v1wrap, 2)
        # The number of mappings is the same afterwards.
        self.assertEqual(num_matches, len(self.v1wrap.scsi_mappings))
        # But now the mappings have no storage
        for smap in self.v1wrap.scsi_mappings:
            self.assertIsNone(smap.backing_storage)
        # The return list contains all the mappings
        self.assertEqual(num_matches, len(removals))
        # The return list members contain the storage (the four that had it
        # beforehand).
        self.assertEqual(4, len([sm.backing_storage for sm in removals
                                 if sm .backing_storage is not None]))

        # In v2wrap, there are four VOptMedia mappings
        num_matches = 4
        match_class = pvm_stor.VOptMedia
        # Number of mappings should be the same before and after.
        len_before = len(self.v2wrap.scsi_mappings)
        self.assertEqual(
            num_matches, len([1 for sm in self.v2wrap.scsi_mappings
                              if isinstance(sm.backing_storage, match_class)]))
        removals = scsi_mapper.detach_storage(
            self.v2wrap, None, match_func=scsi_mapper.gen_match_func(
                match_class))
        self.assertEqual(num_matches, len(removals))
        # The number of mappings is the same as beforehand.
        self.assertEqual(len_before, len(self.v2wrap.scsi_mappings))
        # Now there should be no mappings with VOptMedia
        self.assertEqual(
            0, len([1 for sm in self.v2wrap.scsi_mappings
                    if isinstance(sm.backing_storage, match_class)]))
        # The removals contain the storage
        self.assertEqual(
            num_matches, len([1 for sm in removals
                              if isinstance(sm.backing_storage, match_class)]))

    def test_find_maps(self):
        """find_maps() tests not covered elsewhere."""
        maps = self.v1wrap.scsi_mappings
        # Specifying both match_func and stg_elem raises ValueError
        self.assertRaises(ValueError, scsi_mapper.find_maps, maps, 1,
                          match_func=isinstance, stg_elem='foo')
        # Omitting match_func and stg_elem matches all entries with specified
        # LPAR ID.
        # For LPAR ID 2, that should be all of 'em.
        matches = scsi_mapper.find_maps(maps, 2)
        self.assertEqual(len(maps), len(matches))
        for exp, act in zip(maps, matches):
            self.assertEqual(exp, act)
        # For the right LPAR UUID, that should be all of 'em.
        matches = scsi_mapper.find_maps(maps, LPAR_UUID)
        self.assertEqual(len(maps), len(matches))
        for exp, act in zip(maps, matches):
            self.assertEqual(exp, act)
        # For the wrong LPAR ID, it should be none of 'em.
        matches = scsi_mapper.find_maps(maps, 1)
        self.assertEqual(0, len(matches))
        # For the wrong LPAR UUID, it should be none of 'em.
        matches = scsi_mapper.find_maps(maps, LPAR_UUID[:35] + '0')
        self.assertEqual(0, len(matches))
        # Specific storage element generates match func for that element.
        matches = scsi_mapper.find_maps(maps, 2,
                                        stg_elem=maps[2].backing_storage)
        self.assertEqual(1, len(matches))
        self.assertEqual(maps[2], matches[0])
        # Test find maps when client lpar id is not specified and backing
        # storage is given
        matches = scsi_mapper.find_maps(maps, None,
                                        stg_elem=maps[2].backing_storage)
        self.assertEqual(1, len(matches))
        self.assertEqual(maps[2], matches[0])

        # All the mappings in VIO_MULTI_MAP_FILE are "complete".  Now play with
        # some that aren't.
        maps = self.v2wrap.scsi_mappings
        # Map 0 has only a server adapter.  We should find it if we specify the
        # LPAR ID...
        matches = scsi_mapper.find_maps(maps, 27, include_orphans=True)
        self.assertEqual(maps[0], matches[0])
        # ...but only if allowing orphans
        matches = scsi_mapper.find_maps(maps, 27, include_orphans=False)
        self.assertEqual(0, len(matches))
        # Matching by LPAR UUID.  Maps 12, 25, and 26 have this UUID...
        uuid = '0C0A6EBE-7BF4-4707-8780-A140F349E42E'
        matches = scsi_mapper.find_maps(maps, uuid, include_orphans=True)
        self.assertEqual(3, len(matches))
        self.assertEqual(maps[12], matches[0])
        self.assertEqual(maps[25], matches[1])
        self.assertEqual(maps[26], matches[2])
        # ...but 25 is an orphan (no client adapter).
        uuid = '0C0A6EBE-7BF4-4707-8780-A140F349E42E'
        matches = scsi_mapper.find_maps(maps, uuid)
        self.assertEqual(2, len(matches))
        self.assertEqual(maps[12], matches[0])
        self.assertEqual(maps[26], matches[1])

    def test_separate_mappings(self):
        client_href = ('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                       '726e9cb3-6576-3df5-ab60-40893d51d074/LogicalPartition/'
                       '0C0A6EBE-7BF4-4707-8780-A140F349E42E')
        sep = scsi_mapper._separate_mappings(self.v2wrap, client_href)
        self.assertEqual(2, len(sep))
        self.assertEqual(
            {'1eU8246.L2C.0604C7A-V1-C13', '1eU8246.L2C.0604C7A-V1-C25'},
            set(sep.keys()))
        self.assertEqual(sep['1eU8246.L2C.0604C7A-V1-C13'][0],
                         self.v2wrap.scsi_mappings[-1])

    def test_index_mappings(self):
        idx = scsi_mapper.index_mappings(self.v2wrap.scsi_mappings)

        self.assertEqual({
            'by-lpar-id', 'by-lpar-uuid', 'by-storage-udid'}, set(idx.keys()))

        exp_lpar_ids = ('2', '5', '6', '7', '10', '11', '12', '13', '14', '15',
                        '16', '17', '18', '19', '20', '21', '22', '23', '24',
                        '27', '28', '29', '33', '35', '36', '39', '40')
        self.assertEqual(set(exp_lpar_ids), set(idx['by-lpar-id'].keys()))
        # Each mapping has a different LPAR ID, so each LPAR ID only has one
        # mapping
        for lpar_id in exp_lpar_ids:
            maplist = idx['by-lpar-id'][lpar_id]
            self.assertEqual(1, len(maplist))
            self.assertIsInstance(maplist[0], pvm_vios.VSCSIMapping)
            self.assertEqual(lpar_id, str(maplist[0].server_adapter.lpar_id))

        # Not all mappings have client_lpar_href, so this list is shorter.
        exp_lpar_uuids = ('0C0A6EBE-7BF4-4707-8780-A140F349E42E',
                          '0FB69DD7-4B93-4C09-8916-8BC9821ABAAC',
                          '263EE77B-AD6E-4920-981A-4B7D245B8571',
                          '292ACAF5-C96B-447A-8C7E-7503D80AA33E',
                          '32AA6AA5-CCE6-4523-860C-0852455036BE',
                          '3CE30EC6-C98A-4A58-A764-09DAC7C324BC',
                          '615C9134-243D-4A11-93EB-C0556664B761',
                          '7CFDD55B-E0D7-4B8C-8254-9305E31BB1DC')
        self.assertEqual(set(exp_lpar_uuids), set(idx['by-lpar-uuid'].keys()))
        # Of ten mappings with client_lpar_href, three have the same UUID.
        for lpar_uuid in exp_lpar_uuids:
            maplist = idx['by-lpar-uuid'][lpar_uuid]
            for smap in maplist:
                self.assertIsInstance(smap, pvm_vios.VSCSIMapping)
                self.assertTrue(smap.client_lpar_href.endswith(lpar_uuid))
            if lpar_uuid == '0C0A6EBE-7BF4-4707-8780-A140F349E42E':
                self.assertEqual(3, len(maplist))
            else:
                self.assertEqual(1, len(maplist))

        # Only five mappings have storage, and all are different
        self.assertEqual(5, len(idx['by-storage-udid'].keys()))
        for sudid in idx['by-storage-udid']:
            self.assertEqual(1, len(idx['by-storage-udid'][sudid]))

    def test_gen_match_func(self):
        """Tests for gen_match_func."""

        # Class must match
        mfunc = scsi_mapper.gen_match_func(str)
        self.assertFalse(mfunc(1))
        self.assertTrue(mfunc('foo'))

        # Match names
        elem = mock.Mock()
        elem.name = 'foo'
        # 'False' names/prefixes ignored
        mfunc = scsi_mapper.gen_match_func(mock.Mock, names=[])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, prefixes=[])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, names=[], prefixes=[])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, names=['bar', 'baz'])
        self.assertFalse(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, names=['bar', 'foobar',
                                                             'baz'])
        self.assertFalse(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock,
                                           names=['bar', 'foo', 'baz'])
        self.assertTrue(mfunc(elem))

        # Prefixes are ignored if names specified
        mfunc = scsi_mapper.gen_match_func(mock.Mock, prefixes='x',
                                           names=['bar', 'foo', 'baz'])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, names=['bar', 'baz'],
                                           prefixes=['f'])
        self.assertFalse(mfunc(elem))

        # Prefixes
        mfunc = scsi_mapper.gen_match_func(mock.Mock, prefixes=['f'])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, prefixes=['foo'])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, prefixes=['foo', 'x'])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, prefixes=['x'])
        self.assertFalse(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, prefixes=['xfoo', 'foox',
                                                                'xfoox'])
        self.assertFalse(mfunc(elem))

        # Alternate key for the name property
        elem = mock.Mock(alt_name='foo')
        mfunc = scsi_mapper.gen_match_func(mock.Mock, name_prop='alt_name',
                                           names=[])
        self.assertTrue(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, names=['bar', 'baz'])
        self.assertFalse(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, name_prop='alt_name',
                                           names=['bar', 'baz'])
        self.assertFalse(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock,
                                           names=['bar', 'foo', 'baz'])
        self.assertFalse(mfunc(elem))
        mfunc = scsi_mapper.gen_match_func(mock.Mock, name_prop='alt_name',
                                           names=['bar', 'foo', 'baz'])
        self.assertTrue(mfunc(elem))
