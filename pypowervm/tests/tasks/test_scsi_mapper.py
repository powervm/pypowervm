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
        # Mapping LPAR IDs
        self.mock_lpar_id_p = mock.patch('pypowervm.wrappers.storage.'
                                         'VSCSIClientAdapter.lpar_id')
        self.mock_lpar_id = self.mock_lpar_id_p.start()
        self.mock_lpar_id.return_value = 2

        self.mock_client_adpt_p = mock.patch('pypowervm.wrappers.'
                                             'virtual_io_server.VSCSIMapping.'
                                             'client_adapter')
        self.mock_client_adpt = self.mock_client_adpt_p.start()
        self.mock_client_adpt.lpar_id = 2

        # Common Adapter
        self.mock_adpt_p = mock.patch('pypowervm.adapter.Adapter')
        self.mock_adpt = self.mock_adpt_p.start()

        # Fake URI
        self.mock_crt_href_p = mock.patch('pypowervm.wrappers.'
                                          'virtual_io_server.'
                                          'VSCSIMapping._crt_related_href')
        self.mock_crt_href = self.mock_crt_href_p.start()
        self.mock_crt_href.return_value = 'href'

    def tearDown(self):
        unittest.TestCase.tearDown(self)

        # End patching
        self.mock_crt_href_p.stop()
        self.mock_adpt_p.stop()
        self.mock_client_adpt_p.stop()
        self.mock_lpar_id_p.stop()

    def test_mapping(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(5, num_elems)
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

    def test_mapping_new_mapping(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(2, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(4, num_elems)
            num_elems = len(vios_w.scsi_mappings[1].backing_storage_elems)
            self.assertEqual(1, num_elems)
            return vios_w.entry

        self.mock_adpt.update_by_path.side_effect = validate_update

        # Create the new mapping
        mapping = pvm_vios.VSCSIMapping.bld_to_pv(self.mock_adpt, 'host_uuid',
                                                  'client_lpar_uuid',
                                                  'disk_name')

        # Run the code
        scsi_mapper.add_vscsi_mapping(self.mock_adpt, 'fake_vios_uuid',
                                      mapping, fuse_limit=3)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, self.mock_adpt.update_by_path.call_count)

    def test_remove_storage_vopt(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(3, num_elems)
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

    def test_remove_storage_vdisk(self):
        # Mock Data
        self.mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)

        # Validate that the mapping was removed from existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(3, num_elems)
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
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(3, num_elems)
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

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(3, num_elems)
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