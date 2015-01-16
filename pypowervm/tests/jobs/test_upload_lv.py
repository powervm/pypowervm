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

import os

from pypowervm import exceptions as exc
from pypowervm.jobs import upload_lv
from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.constants as wc

import unittest


VIOS_FILE = 'upload_vios.txt'
UPLOAD_VOL_GRP_ORIG = 'upload_volgrp.txt'
UPLOAD_VOL_GRP_NEW_VDISK = 'upload_volgrp2.txt'


class TestUploadLV(unittest.TestCase):
    """Unit Tests for Instance uploads."""

    def setUp(self):
        self.v_uuid = '14B854F7-42CE-4FF0-BD57-1D117054E701'
        self.vg_uuid = 'b6bdbf1f-eddf-3c81-8801-9859eb6fedcb'

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.jobs.upload_lv._create_file')
    def test_upload_new_vopt(self, mock_create_file, mock_adpt):
        """Tests the uploads of the virtual disks."""

        mock_create_file.return_value = self._fake_meta()

        f_uuid = upload_lv.upload_vopt(mock_adpt, self.v_uuid, None, 'test2',
                                       f_size=50)

        self.assertEqual('FakeText', f_uuid)

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.jobs.upload_lv._create_file')
    def test_upload_new_vdisk(self, mock_create_file, mock_adpt):
        """Tests the uploads of the virtual disks."""

        # First need to load in the various test responses.
        vg_orig = self._load_file(UPLOAD_VOL_GRP_ORIG)
        vg_post_disk_create = self._load_file(UPLOAD_VOL_GRP_NEW_VDISK)

        mock_adpt.read.return_value = vg_orig
        mock_adpt.update.return_value = vg_post_disk_create
        mock_create_file.return_value = self._fake_meta()

        f_uuid, n_vdisk = upload_lv.upload_new_vdisk(mock_adpt, self.v_uuid,
                                                     self.vg_uuid, None,
                                                     'test2', 50, 'abc123')

        mock_create_file.assert_called_once_with(
            mock_adpt, 'test2', wc.BROKERED_DISK_IMAGE, self.v_uuid, f_size=50,
            tdev_udid=n_vdisk.get_udid(), sha_chksum='abc123')
        self.assertEqual('FakeText', f_uuid)
        self.assertEqual('0300f8d6de00004b000000014a54555cd9.3',
                         n_vdisk.get_udid())
        self.assertEqual('test2', n_vdisk.get_name())

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.jobs.upload_lv._create_file')
    def test_upload_new_vdisk_failure(self, mock_create_file, mock_adpt):
        """Tests the failure path for uploading of the virtual disks."""

        # First need to load in the various test responses.
        vg_orig = self._load_file(UPLOAD_VOL_GRP_ORIG)
        vg_post_disk_create = self._load_file(UPLOAD_VOL_GRP_NEW_VDISK)

        mock_adpt.read.return_value = vg_orig
        mock_adpt.update.return_value = vg_post_disk_create
        mock_create_file.return_value = self._fake_meta()

        self.assertRaises(exc.Error,
                          upload_lv.upload_new_vdisk, mock_adpt,
                          self.v_uuid, self.vg_uuid, None, 'test3', 50)

    @mock.patch('pypowervm.adapter.Adapter')
    def test_create_file(self, mock_adpt):
        """Validates that the _create_file builds the Element properly."""
        def validate_in(*args, **kwargs):
            # Validate that the element is built properly
            element = args[0]

            self.assertEqual('chk', element.findtext('SHA256'))
            self.assertEqual('50',
                             element.findtext('ExpectedFileSizeInBytes'))
            self.assertEqual('f_name', element.findtext('Filename'))
            self.assertEqual('application/octet-stream',
                             element.findtext('InternetMediaType'))
            self.assertEqual('f_type',
                             element.findtext('FileEnumType'))
            self.assertEqual('v_uuid',
                             element.findtext('TargetVirtualIOServerUUID'))
            self.assertEqual('tdev_uuid',
                             element.findtext('TargetDeviceUniqueDeviceID'))
            return mock.MagicMock()
        mock_adpt.create.side_effect = validate_in

        upload_lv._create_file(mock_adpt, 'f_name', 'f_type', 'v_uuid',
                               'chk', 50, 'tdev_uuid')
        self.assertTrue(mock_adpt.create.called)

    def _load_file(self, file_name):
        """Helper method to load the responses from a given location."""
        data_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(data_dir, 'data')
        file_path = os.path.join(data_dir, file_name)
        return pvmhttp.load_pvm_resp(file_path).get_response()

    def _fake_meta(self):
        """Returns a fake meta class for the _create_file mock."""
        class FakeMeta():
            def findtext(self, text):
                return "FakeText"
        return FakeMeta()
