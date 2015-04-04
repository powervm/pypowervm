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

import unittest

from pypowervm.tasks import scsi_mapper
from pypowervm.tests.tasks import util as tju
from pypowervm.wrappers import storage as pvm_stor
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIO_MULTI_MAP_FILE = 'vio_multi_vscsi_mapping.txt'


class TestSCSIMapper(unittest.TestCase):

    def setUp(self):
        # Common Adapter
        self.mock_adpt_p = mock.patch('pypowervm.adapter.Adapter')
        self.mock_adpt = self.mock_adpt_p.start()

        # Fake URI
        self.mock_crt_href_p = mock.patch('pypowervm.wrappers.'
                                          'virtual_io_server.'
                                          'VSCSIMapping._crt_related_href')
        self.mock_crt_href = self.mock_crt_href_p.start()
        href = ('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
                'c5d782c7-44e4-3086-ad15-b16fb039d63b/LogicalPartition/'
                '42AD4FD4-DC64-4935-9E29-9B7C6F35AFCC')
        self.mock_crt_href.return_value = href

        # Mock the delay function, by overriding the sleep
        self.mock_delay_p = mock.patch('time.sleep')
        self.mock_delay = self.mock_delay_p.start()

    def tearDown(self):
        unittest.TestCase.tearDown(self)

        # End patching
        self.mock_crt_href_p.stop()
        self.mock_adpt_p.stop()
        self.mock_delay_p.stop()

    def test_mapping(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(5, len(vios_w.scsi_mappings))
            self.assertEqual(vios_w.scsi_mappings[0].client_adapter,
                             vios_w.scsi_mappings[4].client_adapter)
            self.assertEqual(vios_w.scsi_mappings[0].server_adapter,
                             vios_w.scsi_mappings[4].server_adapter)
            return vios_w.entry

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Create the new mapping
        mapping = pvm_vios.VSCSIMapping.bld_to_pv(self.mock_adpt, 'host_uuid',
                                                  'client_lpar_uuid',
                                                  'disk_name')

        # Run the code
        scsi_mapper.add_vscsi_mapping(self.mock_adpt, 'fake_vios_uuid',
                                      mapping)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.mock_adpt.update_by_path.call_count)

    def test_mapping_retry(self):
        """Tests that a mapping function will be retried."""
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

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

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Create the new mapping
        mapping = pvm_vios.VSCSIMapping.bld_to_pv(self.mock_adpt, 'host_uuid',
                                                  'client_lpar_uuid',
                                                  'disk_name')

        # Run the code
        scsi_mapper.add_vscsi_mapping(self.mock_adpt, 'fake_vios_uuid',
                                      mapping)

        # Make sure that our validation code above was invoked
        self.assertEqual(3, self.mock_adpt.update_by_path.call_count)
        self.assertEqual(3, attempt_count)

    def test_mapping_new_mapping(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

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

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Create the new mapping
        mapping = pvm_vios.VSCSIMapping.bld_to_pv(self.mock_adpt, 'host_uuid',
                                                  'client_lpar_uuid',
                                                  'disk_name')

        # Run the code
        scsi_mapper.add_vscsi_mapping(self.mock_adpt, 'fake_vios_uuid',
                                      mapping, fuse_limit=4)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.mock_adpt.update_by_path.call_count)

    def test_remove_storage_vopt(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Run the code
        media_name = 'bldr1_dfe05349_kyleh_config.iso'
        resp = scsi_mapper.remove_vopt_mapping(self.mock_adpt,
                                               'fake_vios_uuid', 2,
                                               media_name=media_name)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.mock_adpt.update_by_path.call_count)
        self.assertEqual(1, len(resp))
        self.assertIsInstance(resp[0], pvm_stor.VOptMedia)

    def test_remove_storage_vopt_retry(self):
        """Tests removing the storage vOpt with multiple retries."""
        # Mock Data.  The retry will call this three times.  They have to
        # be indepdent loads, otherwise the data gets re-used and the remove
        # will not be properly invoked.
        self.mock_adpt.read.side_effect = [tju.load_file(VIO_MULTI_MAP_FILE),
                                           tju.load_file(VIO_MULTI_MAP_FILE),
                                           tju.load_file(VIO_MULTI_MAP_FILE)]

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

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Run the code
        media_name = 'bldr1_dfe05349_kyleh_config.iso'
        resp = scsi_mapper.remove_vopt_mapping(self.mock_adpt,
                                               'fake_vios_uuid', 2,
                                               media_name=media_name)

        # Make sure that our validation code above was invoked
        self.assertEqual(3, self.mock_adpt.update_by_path.call_count)
        self.assertEqual(3, attempt_count)
        self.assertEqual(1, len(resp))
        self.assertIsInstance(resp[0], pvm_stor.VOptMedia)

    def test_remove_storage_vdisk(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Run the code
        resp = scsi_mapper.remove_vdisk_mapping(self.mock_adpt,
                                                'fake_vios_uuid', 2,
                                                disk_names=['Ubuntu1410'])

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.mock_adpt.update_by_path.call_count)
        self.assertEqual(1, len(resp))
        self.assertIsInstance(resp[0], pvm_stor.VDisk)

    def test_remove_storage_lu(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Run the code
        resp = scsi_mapper.remove_lu_mapping(
            self.mock_adpt, 'fake_vios_uuid', 2)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.mock_adpt.update_by_path.call_count)
        self.assertEqual(1, len(resp))
        self.assertIsInstance(resp[0], pvm_stor.LU)

    def test_remove_pv_mapping(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was removed to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(3, len(vios_w.scsi_mappings))
            return vios_w.entry

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Run the code
        resp = scsi_mapper.remove_pv_mapping(self.mock_adpt,
                                             'fake_vios_uuid', 2,
                                             'hdisk10')

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.mock_adpt.update_by_path.call_count)
        self.assertEqual(1, len(resp))
        self.assertIsInstance(resp[0], pvm_stor.PV)
