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
LPAR_UUID = '42AD4FD4-DC64-4935-9E29-9B7C6F35AFCC'


class TestSCSIMapper(testtools.TestCase):

    def setUp(self):
        super(TestSCSIMapper, self).setUp()
        # Common Adapter
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

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

    def test_mapping(self):
        # Mock Data
        vio_resp = tju.load_file(VIO_MULTI_MAP_FILE, self.adpt)
        self.adpt.read.return_value = vio_resp

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(5, len(vios_w.scsi_mappings))
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
        vios_wrap = pvm_vios.VIOS.wrap(vio_resp)
        self.adpt.update_by_path.reset_mock()
        self.adpt.read.reset_mock()
        scsi_mapper.add_vscsi_mapping('host_uuid', vios_wrap, LPAR_UUID, pv)
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
                self.assertEqual(5, len(vios_w.scsi_mappings))
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
        # Mock Data
        self.adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE,
                                                    self.adpt)

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(5, len(vios_w.scsi_mappings))

            # Make sure that the adapters do not match
            self.assertNotEqual(vios_w.scsi_mappings[0].client_adapter,
                                vios_w.scsi_mappings[4].client_adapter)
            self.assertNotEqual(vios_w.scsi_mappings[0].server_adapter,
                                vios_w.scsi_mappings[4].server_adapter)

            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Create the new storage dev
        pv = pvm_stor.PV.bld(self.adpt, 'pv_name', 'pv_udid')

        # Run the code
        scsi_mapper.add_vscsi_mapping('host_uuid', 'vios_uuid', LPAR_UUID,
                                      pv, fuse_limit=4)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_remove_storage_vopt(self):
        # Mock Data
        self.adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE,
                                                    self.adpt)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
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

        # Now do it again, but passing the vios wrapper and the client UUID
        vios_wrap = pvm_vios.VIOS.wrap(
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt))
        self.adpt.update_by_path.reset_mock()
        self.adpt.read.reset_mock()
        vios, remel = scsi_mapper.remove_vopt_mapping(
            self.adpt, vios_wrap, LPAR_UUID, media_name=media_name)
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VOptMedia)
        # But the VIOS was not "looked up"
        self.assertEqual(0, self.adpt.read.call_count)

    def test_remove_storage_vopt_no_name_specified(self):
        # Mock Data
        self.adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE,
                                                    self.adpt)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_vopt_mapping(
            self.adpt, 'fake_vios_uuid', 2, media_name=None)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VOptMedia)

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
                self.assertEqual(3, len(vios_w.scsi_mappings))
                return vios_w.entry
            else:
                tju.raiseRetryException()

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        media_name = 'bldr1_dfe05349_kyleh_config.iso'
        vios, remel = scsi_mapper.remove_vopt_mapping(
            self.adpt, 'fake_vios_uuid', 2, media_name=media_name)

        # Make sure that our validation code above was invoked
        self.assertEqual(3, self.adpt.update_by_path.call_count)
        self.assertEqual(3, attempt_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VOptMedia)

    def test_remove_storage_vdisk(self):
        # Mock Data
        self.adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE,
                                                    self.adpt)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_vdisk_mapping(
            self.adpt, 'fake_vios_uuid', 2, disk_names=['Ubuntu1410'])

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.VDisk)

    def test_remove_storage_lu(self):
        # Mock Data
        self.adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE,
                                                    self.adpt)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_lu_mapping(
            self.adpt, 'fake_vios_uuid', 2)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.LU)

    def test_remove_pv_mapping(self):
        # Mock Data
        self.adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE,
                                                    self.adpt)

        # Validate that the mapping was removed to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.adpt.update_by_path.side_effect = validate_update

        # Run the code
        vios, remel = scsi_mapper.remove_pv_mapping(
            self.adpt, 'fake_vios_uuid', 2, 'hdisk10')

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.adpt.update_by_path.call_count)
        self.assertEqual(1, len(remel))
        self.assertIsInstance(remel[0], pvm_stor.PV)

    def test_find_maps(self):
        """find_maps() tests not covered elsewhere."""
        maps = pvm_vios.VIOS.wrap(
            tju.load_file(VIO_MULTI_MAP_FILE, self.adpt)).scsi_mappings
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
        matches = scsi_mapper.find_maps(maps, LPAR_UUID[:36] + '0')
        self.assertEqual(0, len(matches))
        # Specific storage element generates match func for that element.
        matches = scsi_mapper.find_maps(maps, 2,
                                        stg_elem=maps[2].backing_storage)
        self.assertEqual(1, len(matches))
        self.assertEqual(maps[2], matches[0])
