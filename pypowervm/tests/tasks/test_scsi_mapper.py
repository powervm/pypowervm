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
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIO_MULTI_MAP_FILE = 'vio_multi_vscsi_mapping.txt'


class TestSCSIMapper(unittest.TestCase):

    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIClientAdapter.'
                'lpar_id')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIMapping.'
                '_crt_related_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_mapping(self, mock_adpt, mock_crt_href, mock_lpar_id):
        # Mock Data
        mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)
        mock_crt_href.return_value = 'href'
        mock_lpar_id.return_value = 2

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(3, num_elems)
            return vios_w.entry

        mock_adpt.update_by_path.side_effect = validate_update

        # Create the new mapping
        mapping = pvm_vios.VSCSIMapping.bld_to_pv(mock_adpt, 'host_uuid',
                                                  'client_lpar_uuid',
                                                  'disk_name')

        # Run the code
        scsi_mapper.add_vscsi_mapping(mock_adpt, 'fake_vios_uuid', mapping)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, mock_adpt.update_by_path.call_count)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIClientAdapter.'
                'lpar_id')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIMapping.'
                '_crt_related_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_mapping_new_mapping(self, mock_adpt, mock_crt_href, mock_lpar_id):
        # Mock Data
        mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)
        mock_crt_href.return_value = 'href'
        mock_lpar_id.return_value = 2

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(2, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(2, num_elems)
            num_elems = len(vios_w.scsi_mappings[1].backing_storage_elems)
            self.assertEqual(1, num_elems)
            return vios_w.entry

        mock_adpt.update_by_path.side_effect = validate_update

        # Create the new mapping
        mapping = pvm_vios.VSCSIMapping.bld_to_pv(mock_adpt, 'host_uuid',
                                                  'client_lpar_uuid',
                                                  'disk_name')

        # Run the code
        scsi_mapper.add_vscsi_mapping(mock_adpt, 'fake_vios_uuid', mapping,
                                      fuse_limit=2)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, mock_adpt.update_by_path.call_count)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIMapping.'
                'client_adapter')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIMapping.'
                '_crt_related_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_storage_vopt(self, mock_adpt, mock_crt_href,
                                 mock_client_adpt):
        # Mock Data
        mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)
        mock_crt_href.return_value = 'href'
        mock_client_adpt.lpar_id = 2

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(1, num_elems)
            return vios_w.entry

        mock_adpt.update_by_path.side_effect = validate_update

        # Run the code
        scsi_mapper.remove_vopt_mapping(mock_adpt, 'fake_vios_uuid',
                                        'bldr1_dfe05349_kyleh_config.iso', 2)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, mock_adpt.update_by_path.call_count)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIMapping.'
                'client_adapter')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VSCSIMapping.'
                '_crt_related_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_storage_vdisk(self, mock_adpt, mock_crt_href,
                                  mock_client_adpt):
        # Mock Data
        mock_adpt.read.return_value = tju.load_file(VIO_MULTI_MAP_FILE)
        mock_crt_href.return_value = 'href'
        mock_client_adpt.lpar_id = 2

        # Validate that the mapping was added to existing
        def validate_update(*kargs, **kwargs):
            vios_w = kargs[0]
            self.assertEqual(1, len(vios_w.scsi_mappings))
            num_elems = len(vios_w.scsi_mappings[0].backing_storage_elems)
            self.assertEqual(1, num_elems)
            return vios_w.entry

        mock_adpt.update_by_path.side_effect = validate_update

        # Run the code
        scsi_mapper.remove_vdisk_mapping(mock_adpt, 'fake_vios_uuid',
                                         'Ubuntu1410', 2)

        # Make sure that our validation code above was invoked
        self.assertEqual(1, mock_adpt.update_by_path.call_count)
