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

import pypowervm.adapter as adp
import pypowervm.exceptions as exc
import pypowervm.tasks.storage as ts
import pypowervm.tests.tasks.util as tju
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf

import unittest


UPLOAD_VOL_GRP_ORIG = 'upload_volgrp.txt'
UPLOAD_VOL_GRP_NEW_VDISK = 'upload_volgrp2.txt'
UPLOADED_FILE = 'upload_file.txt'


def _mock_update_by_path(ssp, etag, path):
    # Spoof adding UDID and defaulting thinness
    for lu in ssp.logical_units:
        if not lu.udid:
            lu._udid('udid_' + lu.name)
        if lu.is_thin is None:
            lu._is_thin(True)
    resp = adp.Response('meth', 'path', 200, 'reason', {'etag': 'after'})
    resp.entry = ssp.entry
    return resp


class TestUploadLV(unittest.TestCase):
    """Unit Tests for Instance uploads."""

    def setUp(self):
        super(TestUploadLV, self).setUp()
        self.v_uuid = '14B854F7-42CE-4FF0-BD57-1D117054E701'
        self.vg_uuid = 'b6bdbf1f-eddf-3c81-8801-9859eb6fedcb'

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vopt(self, mock_create_file, mock_adpt):
        """Tests the uploads of the virtual disks."""

        mock_create_file.return_value = self._fake_meta()

        f_wrap = ts.upload_vopt(mock_adpt, self.v_uuid, None, 'test2',
                                f_size=50)

        # Test that vopt was 'uploaded'
        mock_adpt.upload_file.assert_called_with(mock.ANY, None)
        self.assertIsNone(f_wrap)

        # Ensure cleanup was called
        mock_adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')

        # Test cleanup failure
        mock_adpt.reset_mock()
        mock_adpt.delete.side_effect = exc.Error('Something bad')
        f_wrap = ts.upload_vopt(mock_adpt, self.v_uuid, None, 'test2',
                                f_size=50)

        mock_adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNotNone(f_wrap)

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vdisk(self, mock_create_file, mock_adpt):
        """Tests the uploads of the virtual disks."""

        # First need to load in the various test responses.
        vg_orig = tju.load_file(UPLOAD_VOL_GRP_ORIG)
        vg_post_crt = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK)

        mock_adpt.read.return_value = vg_orig
        mock_adpt.update_by_path.return_value = vg_post_crt
        mock_create_file.return_value = self._fake_meta()

        n_vdisk, f_wrap = ts.upload_new_vdisk(
            mock_adpt, self.v_uuid, self.vg_uuid, None, 'test2', 50,
            d_size=25, sha_chksum='abc123')

        # Ensure the create file was called
        mock_create_file.assert_called_once_with(
            mock_adpt, 'test2', vf.FTypeEnum.BROKERED_DISK_IMAGE, self.v_uuid,
            f_size=50, tdev_udid='0300f8d6de00004b000000014a54555cd9.3',
            sha_chksum='abc123')

        # Ensure cleanup was called after the upload
        mock_adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNone(f_wrap)
        self.assertIsNotNone(n_vdisk)
        self.assertIsInstance(n_vdisk, stor.VDisk)

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vdisk_failure(self, mock_create_file, mock_adpt):
        """Tests the failure path for uploading of the virtual disks."""

        # First need to load in the various test responses.
        vg_orig = tju.load_file(UPLOAD_VOL_GRP_ORIG)
        vg_post_crt = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK)

        mock_adpt.read.return_value = vg_orig
        mock_adpt.update_by_path.return_value = vg_post_crt
        mock_create_file.return_value = self._fake_meta()

        self.assertRaises(exc.Error, ts.upload_new_vdisk, mock_adpt,
                          self.v_uuid, self.vg_uuid, None, 'test3', 50)

        # Test cleanup failure
        mock_adpt.delete.side_effect = exc.Error('Something bad')
        f_wrap = ts.upload_new_vdisk(mock_adpt, self.v_uuid, self.vg_uuid,
                                     None, 'test2', 50, sha_chksum='abc123')

        mock_adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNotNone(f_wrap)

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_lu(self, mock_create_file, mock_adpt):
        """Tests create/upload of SSP LU."""
        ssp_in = stor.SSP.bld('ssp1', [])
        ssp_in.entry.properties = {'links': {'SELF': [
            '/rest/api/uom/SharedStoragePool/ssp_uuid']}}
        ssp_out = stor.SSP.bld('ssp1', [])
        lu1 = stor.LU.bld('lu1', 123)
        lu1._udid('lu1_udid')
        ssp_out.logical_units = [lu1]
        mock_adpt.update_by_path.return_value = ssp_out.entry
        mock_create_file.return_value = self._fake_meta()

        f_wrap = ts.upload_new_lu(
            mock_adpt, self.v_uuid, ssp_in, None, 'lu1', 123,
            d_size=25, sha_chksum='abc123')

        # Ensure the create file was called
        mock_create_file.assert_called_once_with(
            mock_adpt, 'lu1', vf.FTypeEnum.BROKERED_DISK_IMAGE, self.v_uuid,
            f_size=123, tdev_udid='lu1_udid',
            sha_chksum='abc123')

        # Ensure cleanup was called after the upload
        mock_adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNone(f_wrap)

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
            ret = adp.Response('reqmethod', 'reqpath', 'status', 'reason', {})
            ret.entry = ewrap.EntryWrapper._bld(tag='File').entry
            return ret
        mock_adpt.create.side_effect = validate_in

        ts._create_file(mock_adpt, 'f_name', 'f_type', 'v_uuid', 'chk', 50,
                        'tdev_uuid')
        self.assertTrue(mock_adpt.create.called)

    def _fake_meta(self):
        """Returns a fake meta class for the _create_file mock."""
        resp = tju.load_file(UPLOADED_FILE)
        return vf.File.wrap(resp)


class TestLU(unittest.TestCase):

    def setUp(self):
        self.adp = mock.patch('pypowervm.adapter.Adapter')
        self.adp.update_by_path = _mock_update_by_path
        self.adp.extend_path = lambda x, xag: x
        self.ssp = stor.SSP.bld('ssp1', [])
        for i in range(5):
            lu = stor.LU.bld('lu%d' % i, i+1)
            lu._udid('udid_' + lu.name)
            self.ssp.logical_units.append(lu)
        self.ssp.entry.properties = {
            'links': {'SELF': ['/rest/api/uom/SharedStoragePool/123']}}
        self.ssp._etag = 'before'

    def test_crt_lu(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10)
        self.assertEqual(lu.name, 'lu5')
        self.assertEqual(lu.udid, 'udid_lu5')
        self.assertTrue(lu.is_thin)
        self.assertEqual(ssp.etag, 'after')
        self.assertIn(lu, ssp.logical_units)

    def test_crt_lu_thin(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=True)
        self.assertTrue(lu.is_thin)

    def test_crt_lu_thick(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=False)
        self.assertFalse(lu.is_thin)

    def test_crt_lu_name_conflict(self):
        self.assertRaises(exc.DuplicateLUNameError, ts.crt_lu, self.adp,
                          self.ssp, 'lu1', 5)

    def test_rm_lu_by_lu(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = ts.rm_lu(self.adp, self.ssp, lu=lu)
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_by_name(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = ts.rm_lu(self.adp, self.ssp, name='lu2')
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_by_udid(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = ts.rm_lu(self.adp, self.ssp, udid='udid_lu2')
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_not_found(self):
        # By LU
        lu = stor.LU.bld('lu5', 6)
        self.assertRaises(exc.LUNotFoundError, ts.rm_lu, self.adp, self.ssp,
                          lu=lu)
        # By name
        self.assertRaises(exc.LUNotFoundError, ts.rm_lu, self.adp, self.ssp,
                          name='lu5')
        # By UDID
        self.assertRaises(exc.LUNotFoundError, ts.rm_lu, self.adp, self.ssp,
                          udid='lu5_udid')
