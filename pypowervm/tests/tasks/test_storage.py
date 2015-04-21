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
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf

import unittest


CLUSTER = "cluster.txt"
LU_LINKED_CLONE_JOB = 'cluster_LULinkedClone_job_template.txt'
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
        if lu.lu_type is None:
            lu._lu_type(stor.LUType.DISK)
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

        v_opt, f_wrap = ts.upload_vopt(mock_adpt, self.v_uuid, None, 'test2',
                                       f_size=50)

        # Test that vopt was 'uploaded'
        mock_adpt.upload_file.assert_called_with(mock.ANY, None)
        self.assertIsNone(f_wrap)
        self.assertIsNotNone(v_opt)
        self.assertIsInstance(v_opt, stor.VOptMedia)
        self.assertEqual('test2', v_opt.media_name)

        # Ensure cleanup was called
        mock_adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')

        # Test cleanup failure
        mock_adpt.reset_mock()
        mock_adpt.delete.side_effect = exc.Error('Something bad')

        vopt, f_wrap = ts.upload_vopt(mock_adpt, self.v_uuid, None, 'test2',
                                      f_size=50)

        mock_adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNotNone(f_wrap)
        self.assertIsNotNone(vopt)
        self.assertIsInstance(vopt, stor.VOptMedia)
        self.assertEqual('test2', v_opt.media_name)

    @mock.patch('pypowervm.adapter.Adapter')
    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vdisk(self, mock_create_file, mock_adpt):
        """Tests the uploads of the virtual disks."""

        # Set the trait to use the REST API upload
        mock_adpt.traits.local_api = False

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
            mock_adpt, 'test2', vf.FileType.DISK_IMAGE, self.v_uuid,
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
    def test_upload_new_vdisk_coordinated(self, mock_create_file, mock_adpt):
        """Tests the uploads of a virtual disk using the coordinated path."""

        # Set the trait to use the coordinated local API
        mock_adpt.traits.local_api = True

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
            mock_adpt, 'test2', vf.FileType.DISK_IMAGE_COORDINATED,
            self.v_uuid, f_size=50,
            tdev_udid='0300f8d6de00004b000000014a54555cd9.3',
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
        # Tell the adapter to upload via REST API
        mock_adpt.traits.local_api = False

        ssp_in = stor.SSP.bld('ssp1', [])
        ssp_in.entry.properties = {'links': {'SELF': [
            '/rest/api/uom/SharedStoragePool/ssp_uuid']}}
        mock_adpt.update_by_path.side_effect = _mock_update_by_path
        mock_create_file.return_value = self._fake_meta()
        size_b = 1224067890

        new_lu, f_wrap = ts.upload_new_lu(
            mock_adpt, self.v_uuid, ssp_in, None, 'lu1', size_b,
            d_size=25, sha_chksum='abc123')

        # Check the new LU's properties
        self.assertEqual(new_lu.name, 'lu1')
        # 1224067890 / 1GB = 1.140002059; round up to 2dp
        self.assertEqual(new_lu.capacity, 1.15)
        self.assertTrue(new_lu.is_thin)
        self.assertEqual(new_lu.lu_type, stor.LUType.IMAGE)

        # Ensure the create file was called
        mock_create_file.assert_called_once_with(
            mock_adpt, 'lu1', vf.FileType.DISK_IMAGE, self.v_uuid,
            f_size=size_b, tdev_udid='udid_lu1',
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
        self.assertEqual(lu.lu_type, stor.LUType.DISK)
        self.assertEqual(ssp.etag, 'after')
        self.assertIn(lu, ssp.logical_units)

    def test_crt_lu_thin(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=True)
        self.assertTrue(lu.is_thin)

    def test_crt_lu_thick(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=False)
        self.assertFalse(lu.is_thin)

    def test_crt_lu_type_image(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10,
                            typ=stor.LUType.IMAGE)
        self.assertEqual(lu.lu_type, stor.LUType.IMAGE)

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


class TestLULinkedClone(unittest.TestCase):

    def setUp(self):
        self.adp = mock.patch('pypowervm.adapter.Adapter')
        self.adp.update_by_path = _mock_update_by_path
        self.adp.extend_path = lambda x, xag: x
        self.ssp = stor.SSP.bld('ssp1', [])
        # img_lu1 not cloned
        self.img_lu1 = self._mk_img_lu(1)
        self.ssp.logical_units.append(self.img_lu1)
        # img_lu2 has two clones
        self.img_lu2 = self._mk_img_lu(2)
        self.ssp.logical_units.append(self.img_lu2)
        self.dsk_lu3 = self._mk_dsk_lu(3, 2)
        self.ssp.logical_units.append(self.dsk_lu3)
        self.dsk_lu4 = self._mk_dsk_lu(4, 2)
        self.ssp.logical_units.append(self.dsk_lu4)
        # img_lu5 has one clone
        self.img_lu5 = self._mk_img_lu(5)
        self.ssp.logical_units.append(self.img_lu5)
        self.dsk_lu6 = self._mk_dsk_lu(6, 5)
        self.ssp.logical_units.append(self.dsk_lu6)
        self.ssp.entry.properties = {
            'links': {'SELF': ['/rest/api/uom/SharedStoragePool/123']}}
        self.ssp._etag = 'before'

    def _mk_img_lu(self, idx):
        lu = stor.LU.bld('img_lu%d' % idx, 123, typ=stor.LUType.IMAGE)
        lu._udid('xxImage-LU-UDID-%d' % idx)
        return lu

    def _mk_dsk_lu(self, idx, cloned_from_idx):
        lu = stor.LU.bld('dsk_lu%d' % idx, 123, typ=stor.LUType.DISK)
        lu._udid('xxDisk-LU-UDID-%d' % idx)
        lu._cloned_from_udid('yyImage-LU-UDID-%d' % cloned_from_idx)
        return lu

    @mock.patch('pypowervm.adapter.Adapter.read')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_crt_lu_linked_clone(self, mock_run_job, mock_read):
        clust1 = clust.Cluster.wrap(tju.load_file(CLUSTER))
        mock_read.return_value = tju.load_file(LU_LINKED_CLONE_JOB)
        self.adp.read = mock_read

        def verify_run_job(adapter, uuid, job_parms):
            self.assertEqual(clust1.uuid, uuid)
            self.assertEqual(
                '<web:JobParameter xmlns:web="http://www.ibm.com/xmlns/systems'
                '/power/firmware/web/mc/2012_10/" schemaVersion="V1_0"><web:Pa'
                'rameterName>SourceUDID</web:ParameterName><web:ParameterValue'
                '>xxImage-LU-UDID-1</web:ParameterValue></web:JobParameter>'.
                encode('utf-8'),
                job_parms[0].toxmlstring())
            self.assertEqual(
                '<web:JobParameter xmlns:web="http://www.ibm.com/xmlns/systems'
                '/power/firmware/web/mc/2012_10/" schemaVersion="V1_0"><web:Pa'
                'rameterName>DestinationUDID</web:ParameterName><web:Parameter'
                'Value>udid_linked_lu</web:ParameterValue></web:JobParameter>'.
                encode('utf-8'),
                job_parms[1].toxmlstring())
        mock_run_job.side_effect = verify_run_job
        ts.crt_lu_linked_clone(
            self.adp, self.ssp, clust1, self.ssp.logical_units[0], 'linked_lu')

    def test_image_lu_in_use(self):
        self.assertFalse(ts._image_lu_in_use(self.ssp, self.img_lu1))
        self.assertTrue(ts._image_lu_in_use(self.ssp, self.img_lu2))

    def test_image_lu_for_clone(self):
        self.assertEqual(self.img_lu2,
                         ts._image_lu_for_clone(self.ssp, self.dsk_lu3))

    def test_remove_lu_linked_clone(self):
        lu_names = set(lu.name for lu in self.ssp.logical_units)
        # This one should remove the disk LU but *not* the image LU
        ssp = ts.remove_lu_linked_clone(self.adp, self.ssp, self.dsk_lu3)
        lu_names.remove(self.dsk_lu3.name)
        self.assertEqual(lu_names, set(lu.name for lu in ssp.logical_units))
        # This one should remove *both* the disk LU and the image LU
        ssp = ts.remove_lu_linked_clone(self.adp, self.ssp, self.dsk_lu4,
                                        del_unused_image=True)
        lu_names.remove(self.dsk_lu4.name)
        lu_names.remove(self.img_lu2.name)
        self.assertEqual(lu_names, set(lu.name for lu in ssp.logical_units))
        # This one should remove the disk LU but *not* the image LU, even
        # though it's now unused.
        self.assertTrue(ts._image_lu_in_use(self.ssp, self.img_lu5))
        ssp = ts.remove_lu_linked_clone(self.adp, self.ssp, self.dsk_lu6)
        lu_names.remove(self.dsk_lu6.name)
        self.assertEqual(lu_names, set(lu.name for lu in ssp.logical_units))
        self.assertFalse(ts._image_lu_in_use(self.ssp, self.img_lu5))

    def test_remove_lu_linked_clone_no_update(self):
        def trap_update(*a, **k):
            self.fail()
        self.adp.update_by_path = trap_update
        ts.remove_lu_linked_clone(self.adp, self.ssp, self.dsk_lu3,
                                  update=False)

if __name__ == '__main__':
    unittest.main()
