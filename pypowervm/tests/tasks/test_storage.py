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

import pypowervm.adapter as adp
import pypowervm.exceptions as exc
import pypowervm.tasks.storage as ts
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as fx
import pypowervm.utils.transaction as tx
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf
import pypowervm.wrappers.virtual_io_server as vios

import unittest

CLUSTER = "cluster.txt"
LU_LINKED_CLONE_JOB = 'cluster_LULinkedClone_job_template.txt'
UPLOAD_VOL_GRP_ORIG = 'upload_volgrp.txt'
UPLOAD_VOL_GRP_NEW_VDISK = 'upload_volgrp2.txt'
UPLOADED_FILE = 'upload_file.txt'
VIOS_FEED = 'fake_vios_feed.txt'
VIOS_ENTRY = 'fake_vios_ssp_npiv.txt'
VIOS_ENTRY2 = 'fake_vios_mappings.txt'
LPAR_FEED = 'lpar.txt'


def _mock_update_by_path(ssp, etag, path, timeout=-1):
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


class TestUploadLV(testtools.TestCase):
    """Unit Tests for Instance uploads."""

    def setUp(self):
        super(TestUploadLV, self).setUp()
        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemotePVMTraits))
        self.adpt = self.adptfx.adpt
        self.v_uuid = '14B854F7-42CE-4FF0-BD57-1D117054E701'
        self.vg_uuid = 'b6bdbf1f-eddf-3c81-8801-9859eb6fedcb'

    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vopt(self, mock_create_file):
        """Tests the uploads of the virtual disks."""

        mock_create_file.return_value = self._fake_meta()

        v_opt, f_wrap = ts.upload_vopt(self.adpt, self.v_uuid, None, 'test2',
                                       f_size=50)

        # Test that vopt was 'uploaded'
        self.adpt.upload_file.assert_called_with(mock.ANY, None)
        self.assertIsNone(f_wrap)
        self.assertIsNotNone(v_opt)
        self.assertIsInstance(v_opt, stor.VOptMedia)
        self.assertEqual('test2', v_opt.media_name)

        # Ensure cleanup was called
        self.adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')

        # Test cleanup failure
        self.adpt.reset_mock()
        self.adpt.delete.side_effect = exc.Error('Something bad')

        vopt, f_wrap = ts.upload_vopt(self.adpt, self.v_uuid, None, 'test2',
                                      f_size=50)

        self.adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNotNone(f_wrap)
        self.assertIsNotNone(vopt)
        self.assertIsInstance(vopt, stor.VOptMedia)
        self.assertEqual('test2', v_opt.media_name)

    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vdisk(self, mock_create_file):
        """Tests the uploads of the virtual disks."""

        # traits are already set to use the REST API upload

        # First need to load in the various test responses.
        vg_orig = tju.load_file(UPLOAD_VOL_GRP_ORIG, self.adpt)
        vg_post_crt = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK, self.adpt)

        self.adpt.read.return_value = vg_orig
        self.adpt.update_by_path.return_value = vg_post_crt
        mock_create_file.return_value = self._fake_meta()

        n_vdisk, f_wrap = ts.upload_new_vdisk(
            self.adpt, self.v_uuid, self.vg_uuid, None, 'test2', 50,
            d_size=25, sha_chksum='abc123')

        # Ensure the create file was called
        mock_create_file.assert_called_once_with(
            self.adpt, 'test2', vf.FileType.DISK_IMAGE, self.v_uuid,
            f_size=50, tdev_udid='0300f8d6de00004b000000014a54555cd9.3',
            sha_chksum='abc123')

        # Ensure cleanup was called after the upload
        self.adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNone(f_wrap)
        self.assertIsNotNone(n_vdisk)
        self.assertIsInstance(n_vdisk, stor.VDisk)

    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vdisk_coordinated(self, mock_create_file):
        """Tests the uploads of a virtual disk using the coordinated path."""

        # Override adapter's traits to use the coordinated local API
        self.adptfx.set_traits(fx.LocalPVMTraits)

        # First need to load in the various test responses.
        vg_orig = tju.load_file(UPLOAD_VOL_GRP_ORIG, self.adpt)
        vg_post_crt = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK, self.adpt)

        self.adpt.read.return_value = vg_orig
        self.adpt.update_by_path.return_value = vg_post_crt
        mock_create_file.return_value = self._fake_meta()

        n_vdisk, f_wrap = ts.upload_new_vdisk(
            self.adpt, self.v_uuid, self.vg_uuid, None, 'test2', 50,
            d_size=25, sha_chksum='abc123')

        # Ensure the create file was called
        mock_create_file.assert_called_once_with(
            self.adpt, 'test2', vf.FileType.DISK_IMAGE_COORDINATED,
            self.v_uuid, f_size=50,
            tdev_udid='0300f8d6de00004b000000014a54555cd9.3',
            sha_chksum='abc123')

        # Ensure cleanup was called after the upload
        self.adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNone(f_wrap)
        self.assertIsNotNone(n_vdisk)
        self.assertIsInstance(n_vdisk, stor.VDisk)

    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vdisk_failure(self, mock_create_file):
        """Tests the failure path for uploading of the virtual disks."""

        # First need to load in the various test responses.
        vg_orig = tju.load_file(UPLOAD_VOL_GRP_ORIG, self.adpt)
        vg_post_crt = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK, self.adpt)

        self.adpt.read.return_value = vg_orig
        self.adpt.update_by_path.return_value = vg_post_crt
        mock_create_file.return_value = self._fake_meta()

        self.assertRaises(exc.Error, ts.upload_new_vdisk, self.adpt,
                          self.v_uuid, self.vg_uuid, None, 'test3', 50)

        # Test cleanup failure
        self.adpt.delete.side_effect = exc.Error('Something bad')
        f_wrap = ts.upload_new_vdisk(self.adpt, self.v_uuid, self.vg_uuid,
                                     None, 'test2', 50, sha_chksum='abc123')

        self.adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNotNone(f_wrap)

    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_lu(self, mock_create_file):
        """Tests create/upload of SSP LU."""

        # traits are already set to use the REST API upload

        ssp_in = stor.SSP.bld(self.adpt, 'ssp1', [])
        ssp_in.entry.properties = {'links': {'SELF': [
            '/rest/api/uom/SharedStoragePool/ssp_uuid']}}
        self.adpt.update_by_path.side_effect = _mock_update_by_path
        mock_create_file.return_value = self._fake_meta()
        size_b = 1224067890

        new_lu, f_wrap = ts.upload_new_lu(
            self.v_uuid, ssp_in, None, 'lu1', size_b, d_size=25,
            sha_chksum='abc123')

        # Check the new LU's properties
        self.assertEqual(new_lu.name, 'lu1')
        # 1224067890 / 1GB = 1.140002059; round up to 2dp
        self.assertEqual(new_lu.capacity, 1.15)
        self.assertTrue(new_lu.is_thin)
        self.assertEqual(new_lu.lu_type, stor.LUType.IMAGE)

        # Ensure the create file was called
        mock_create_file.assert_called_once_with(
            self.adpt, 'lu1', vf.FileType.DISK_IMAGE, self.v_uuid,
            f_size=size_b, tdev_udid='udid_lu1',
            sha_chksum='abc123')

        # Ensure cleanup was called after the upload
        self.adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNone(f_wrap)

    def test_create_file(self):
        """Validates that the _create_file builds the Element properly."""
        def validate_in(*args, **kwargs):
            # Validate that the element is built properly
            wrap = args[0]

            self.assertEqual('chk', wrap._get_val_str(vf._FILE_CHKSUM))
            self.assertEqual(50, wrap.expected_file_size)
            self.assertEqual('f_name', wrap.file_name)
            self.assertEqual('application/octet-stream',
                             wrap.internet_media_type)
            self.assertEqual('f_type', wrap.enum_type)
            self.assertEqual('v_uuid', wrap.vios_uuid)
            self.assertEqual('tdev_uuid', wrap.tdev_udid)
            ret = adp.Response('reqmethod', 'reqpath', 'status', 'reason', {})
            ret.entry = ewrap.EntryWrapper._bld(self.adpt, tag='File').entry
            return ret
        self.adpt.create.side_effect = validate_in

        ts._create_file(self.adpt, 'f_name', 'f_type', 'v_uuid', 'chk', 50,
                        'tdev_uuid')
        self.assertTrue(self.adpt.create.called)

    def _fake_meta(self):
        """Returns a fake meta class for the _create_file mock."""
        resp = tju.load_file(UPLOADED_FILE, self.adpt)
        return vf.File.wrap(resp)


class TestVDisk(testtools.TestCase):
    def setUp(self):
        super(TestVDisk, self).setUp()
        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemotePVMTraits))
        self.adpt = self.adptfx.adpt
        self.v_uuid = '14B854F7-42CE-4FF0-BD57-1D117054E701'
        self.vg_uuid = 'b6bdbf1f-eddf-3c81-8801-9859eb6fedcb'
        self.vg_resp = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK, self.adpt)

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    @mock.patch('pypowervm.adapter.Adapter.read')
    def test_crt_vdisk(self, mock_read, mock_update):
        mock_read.return_value = self.vg_resp

        def _mock_update(*a, **kwa):
            vg_wrap = a[0]
            new_vdisk = vg_wrap.virtual_disks[-1]
            self.assertEqual('vdisk_name', new_vdisk.name)
            self.assertEqual(10, new_vdisk.capacity)
            return vg_wrap.entry

        mock_update.side_effect = _mock_update
        ret = ts.crt_vdisk(
            self.adpt, self.v_uuid, self.vg_uuid, 'vdisk_name', 10)
        self.assertEqual('vdisk_name', ret.name)
        self.assertEqual(10, ret.capacity)


class TestRMSTorage(testtools.TestCase):
    def setUp(self):
        super(TestRMSTorage, self).setUp()
        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.RemotePVMTraits))
        self.adpt = self.adptfx.adpt
        self.v_uuid = '14B854F7-42CE-4FF0-BD57-1D117054E701'
        self.vg_uuid = 'b6bdbf1f-eddf-3c81-8801-9859eb6fedcb'
        self.vg_resp = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK, self.adpt)

    def test_rm_dev_by_udid(self):
        dev1 = mock.Mock(udid=None)
        # dev doesn't have a UDID
        with self.assertLogs(ts.__name__, 'WARNING'):
            self.assertIsNone(ts._rm_dev_by_udid(dev1, None))
            dev1.toxmlstring.assert_called_with()
        # Remove from empty list returns None, and warns (like not-found)
        dev1.udid = 123
        with self.assertLogs(ts.__name__, 'WARNING'):
            self.assertIsNone(ts._rm_dev_by_udid(dev1, []))
        # Works when exact same dev is in the list,
        devlist = [dev1]
        self.assertEqual(dev1, ts._rm_dev_by_udid(dev1, devlist))
        self.assertEqual([], devlist)
        # Works when matching-but-not-same dev is in the list.  Return is the
        # one that was in the list, not the one that was passed in.
        devlist = [dev1]
        dev2 = mock.Mock(udid=123)
        # Two different mocks are not equal
        self.assertNotEqual(dev1, dev2)
        self.assertEqual(dev1, ts._rm_dev_by_udid(dev2, devlist))
        self.assertEqual([], devlist)
        # Error when multiples found
        devlist = [dev1, dev2, dev1]
        self.assertRaises(exc.FoundDevMultipleTimes, ts._rm_dev_by_udid, dev1,
                          devlist)
        # One more good path with a longer list
        dev3 = mock.Mock()
        dev4 = mock.Mock(udid=456)
        devlist = [dev3, dev2, dev4]
        self.assertEqual(dev2, ts._rm_dev_by_udid(dev1, devlist))
        self.assertEqual([dev3, dev4], devlist)

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    def test_rm_vdisks(self, mock_update):
        mock_update.return_value = self.vg_resp
        vg_wrap = stor.VG.wrap(self.vg_resp)
        # Remove a valid VDisk
        valid_vd = vg_wrap.virtual_disks[0]
        # Removal should hit.
        vg_wrap = ts.rm_vg_storage(vg_wrap, vdisks=[valid_vd])
        # Update happens, by default
        self.assertEqual(1, mock_update.call_count)
        self.assertEqual(1, len(vg_wrap.virtual_disks))
        self.assertNotEqual(valid_vd.udid, vg_wrap.virtual_disks[0].udid)

        # Bogus removal doesn't affect vg_wrap, and doesn't update.
        mock_update.reset_mock()
        invalid_vd = mock.Mock()
        invalid_vd.name = 'vdisk_name'
        invalid_vd.udid = 'vdisk_udid'
        vg_wrap = ts.rm_vg_storage(vg_wrap, vdisks=[invalid_vd])
        # Update doesn't happen, because no changes
        self.assertEqual(0, mock_update.call_count)
        self.assertEqual(1, len(vg_wrap.virtual_disks))

        # Valid (but sparse) removal; invalid is ignored.
        mock_update.reset_mock()
        valid_vd = mock.Mock()
        valid_vd.name = 'vdisk_name'
        valid_vd.udid = '0300f8d6de00004b000000014a54555cd9.3'
        vg_wrap = ts.rm_vg_storage(vg_wrap, vdisks=[valid_vd, invalid_vd])
        self.assertEqual(1, mock_update.call_count)
        self.assertEqual(0, len(vg_wrap.virtual_disks))

    @mock.patch('pypowervm.adapter.Adapter.update_by_path')
    def test_rm_vopts(self, mock_update):
        mock_update.return_value = self.vg_resp
        vg_wrap = stor.VG.wrap(self.vg_resp)
        repo = vg_wrap.vmedia_repos[0]
        # Remove a valid VOptMedia
        valid_vopt = repo.optical_media[0]
        # Removal should hit.
        vg_wrap = ts.rm_vg_storage(vg_wrap, vopts=[valid_vopt])
        # Update happens, by default
        self.assertEqual(1, mock_update.call_count)
        repo = vg_wrap.vmedia_repos[0]
        self.assertEqual(2, len(repo.optical_media))
        self.assertNotEqual(valid_vopt.udid, repo.optical_media[0].udid)
        self.assertNotEqual(valid_vopt.udid, repo.optical_media[1].udid)

        # Bogus removal doesn't affect vg_wrap, and doesn't update.
        mock_update.reset_mock()
        invalid_vopt = stor.VOptMedia.bld(self.adpt, 'bogus')
        mock_update.reset_mock()
        vg_wrap = ts.rm_vg_storage(vg_wrap, vopts=[invalid_vopt])
        self.assertEqual(0, mock_update.call_count)
        self.assertEqual(2, len(vg_wrap.vmedia_repos[0].optical_media))

        # Valid multiple removal
        mock_update.reset_mock()
        vg_wrap = ts.rm_vg_storage(vg_wrap, vopts=repo.optical_media[:])
        self.assertEqual(1, mock_update.call_count)
        self.assertEqual(0, len(vg_wrap.vmedia_repos[0].optical_media))


class TestLU(testtools.TestCase):

    def setUp(self):
        super(TestLU, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.adpt.update_by_path = _mock_update_by_path
        self.adpt.extend_path = lambda x, xag: x
        self.ssp = stor.SSP.bld(self.adpt, 'ssp1', [])
        for i in range(5):
            lu = stor.LU.bld(self.adpt, 'lu%d' % i, i+1)
            lu._udid('udid_' + lu.name)
            self.ssp.logical_units.append(lu)
        self.ssp.entry.properties = {
            'links': {'SELF': ['/rest/api/uom/SharedStoragePool/123']}}
        self.ssp._etag = 'before'

    def test_crt_lu(self):
        ssp, lu = ts.crt_lu(self.ssp, 'lu5', 10)
        self.assertEqual(lu.name, 'lu5')
        self.assertEqual(lu.udid, 'udid_lu5')
        self.assertTrue(lu.is_thin)
        self.assertEqual(lu.lu_type, stor.LUType.DISK)
        self.assertEqual(ssp.etag, 'after')
        self.assertIn(lu, ssp.logical_units)

    def test_crt_lu_thin(self):
        ssp, lu = ts.crt_lu(self.ssp, 'lu5', 10, thin=True)
        self.assertTrue(lu.is_thin)

    def test_crt_lu_thick(self):
        ssp, lu = ts.crt_lu(self.ssp, 'lu5', 10, thin=False)
        self.assertFalse(lu.is_thin)

    def test_crt_lu_type_image(self):
        ssp, lu = ts.crt_lu(self.ssp, 'lu5', 10, typ=stor.LUType.IMAGE)
        self.assertEqual(lu.lu_type, stor.LUType.IMAGE)

    def test_crt_lu_name_conflict(self):
        self.assertRaises(exc.DuplicateLUNameError, ts.crt_lu, self.ssp, 'lu1',
                          5)

    def test_rm_lu_by_lu(self):
        lu = self.ssp.logical_units[2]
        ssp = ts.rm_ssp_storage(self.ssp, [lu])
        self.assertNotIn(lu, ssp.logical_units)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)


class TestLULinkedClone(testtools.TestCase):

    def setUp(self):
        super(TestLULinkedClone, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.adpt.update_by_path = _mock_update_by_path
        self.adpt.extend_path = lambda x, xag: x
        self.ssp = stor.SSP.bld(self.adpt, 'ssp1', [])
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
        self.dsk_lu_orphan = self._mk_dsk_lu(7, None)
        self.ssp.logical_units.append(self.dsk_lu_orphan)
        self.ssp.entry.properties = {
            'links': {'SELF': ['/rest/api/uom/SharedStoragePool/123']}}
        self.ssp._etag = 'before'

    def _mk_img_lu(self, idx):
        lu = stor.LU.bld(self.adpt, 'img_lu%d' % idx, 123,
                         typ=stor.LUType.IMAGE)
        lu._udid('xxabc123%d' % idx)
        return lu

    def _mk_dsk_lu(self, idx, cloned_from_idx):
        lu = stor.LU.bld(self.adpt, 'dsk_lu%d' % idx, 123,
                         typ=stor.LUType.DISK)
        lu._udid('xxDisk-LU-UDID-%d' % idx)
        # Allow for "orphan" clones
        if cloned_from_idx is not None:
            lu._cloned_from_udid('yyabc123%d' % cloned_from_idx)
        return lu

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_crt_lu_linked_clone(self, mock_run_job):
        clust1 = clust.Cluster.wrap(tju.load_file(CLUSTER, self.adpt))
        self.adpt.read.return_value = tju.load_file(LU_LINKED_CLONE_JOB,
                                                    self.adpt)

        def verify_run_job(uuid, job_parms):
            self.assertEqual(clust1.uuid, uuid)
            self.assertEqual(
                '<web:JobParameter xmlns:web="http://www.ibm.com/xmlns/systems'
                '/power/firmware/web/mc/2012_10/" schemaVersion="V1_0"><web:Pa'
                'rameterName>SourceUDID</web:ParameterName><web:ParameterValue'
                '>xxabc1231</web:ParameterValue></web:JobParameter>'.
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
        ts.crt_lu_linked_clone(self.ssp, clust1, self.ssp.logical_units[0],
                               'linked_lu')

    def test_image_lu_in_use(self):
        # The orphan will trigger a warning as we cycle through all the LUs
        # without finding any backed by this image.
        with self.assertLogs(ts.__name__, 'WARNING'):
            self.assertFalse(ts._image_lu_in_use(self.ssp, self.img_lu1))
        self.assertTrue(ts._image_lu_in_use(self.ssp, self.img_lu2))

    def test_image_lu_for_clone(self):
        self.assertEqual(self.img_lu2,
                         ts._image_lu_for_clone(self.ssp, self.dsk_lu3))

    def test_rm_ssp_storage(self):
        lu_names = set(lu.name for lu in self.ssp.logical_units)
        # This one should remove the disk LU but *not* the image LU
        ssp = ts.rm_ssp_storage(self.ssp, [self.dsk_lu3],
                                del_unused_images=False)
        lu_names.remove(self.dsk_lu3.name)
        self.assertEqual(lu_names, set(lu.name for lu in ssp.logical_units))
        # This one should remove *both* the disk LU and the image LU
        ssp = ts.rm_ssp_storage(self.ssp, [self.dsk_lu4])
        lu_names.remove(self.dsk_lu4.name)
        lu_names.remove(self.img_lu2.name)
        self.assertEqual(lu_names, set(lu.name for lu in ssp.logical_units))
        # This one should remove the disk LU but *not* the image LU, even
        # though it's now unused.
        self.assertTrue(ts._image_lu_in_use(self.ssp, self.img_lu5))
        ssp = ts.rm_ssp_storage(self.ssp, [self.dsk_lu6],
                                del_unused_images=False)
        lu_names.remove(self.dsk_lu6.name)
        self.assertEqual(lu_names, set(lu.name for lu in ssp.logical_units))
        self.assertFalse(ts._image_lu_in_use(self.ssp, self.img_lu5))

        # No update if no change
        self.adpt.update_by_path = lambda *a, **k: self.fail()
        ssp = ts.rm_ssp_storage(self.ssp, [self.dsk_lu4])


class TestScrub(testtools.TestCase):
    """Two VIOSes in feed; no VFC mappings; no storage in VSCSI mappings."""
    def setUp(self):
        super(TestScrub, self).setUp()
        adpt = self.useFixture(fx.AdapterFx()).adpt
        self.vio_feed = vios.VIOS.wrap(tju.load_file(VIOS_FEED, adpt))
        self.txfx = self.useFixture(fx.FeedTaskFx(self.vio_feed))
        self.logfx = self.useFixture(fx.LoggingFx())
        self.ftsk = tx.FeedTask('scrub', self.vio_feed)

    @mock.patch('pypowervm.tasks.storage._RemoveStorage.execute')
    def test_no_matches(self, mock_rm_stg):
        """When removals have no hits, log debug messages, but no warnings."""
        # Our data set has no VFC mappings and no VSCSI mappings with LPAR ID 1
        ts.add_lpar_storage_scrub_tasks([1], self.ftsk, lpars_exist=True)
        self.ftsk.execute()
        self.assertEqual(0, self.logfx.patchers['warn'].mock.call_count)
        for vname in (vwrap.name for vwrap in self.vio_feed):
            self.logfx.patchers['debug'].mock.assert_any_call(
                mock.ANY, dict(stg_type='VSCSI', lpar_id=1, vios_name=vname))
            self.logfx.patchers['debug'].mock.assert_any_call(
                mock.ANY, dict(stg_type='VFC', lpar_id=1, vios_name=vname))
        self.assertEqual(0, self.txfx.patchers['update'].mock.call_count)
        self.assertEqual(1, mock_rm_stg.call_count)

    @mock.patch('pypowervm.tasks.vfc_mapper.remove_maps')
    def test_matches_warn(self, mock_rm_vfc_maps):
        """When removals hit, log warnings including the removal count."""
        # Mock vfc remove_maps with a multi-element list to verify num_maps
        mock_rm_vfc_maps.return_value = [1, 2, 3]
        ts.add_lpar_storage_scrub_tasks([32], self.ftsk, lpars_exist=True)
        self.ftsk.execute()
        mock_rm_vfc_maps.assert_has_calls(
            [mock.call(wrp, 32) for wrp in self.vio_feed], any_order=True)
        for vname in (vwrap.name for vwrap in self.vio_feed):
            self.logfx.patchers['warn'].mock.assert_any_call(
                mock.ANY, dict(stg_type='VFC', num_maps=3, lpar_id=32,
                               vios_name=vname))
        self.logfx.patchers['warn'].mock.assert_any_call(
            mock.ANY, dict(stg_type='VSCSI', num_maps=1, lpar_id=32,
                           vios_name='nimbus-ch03-p2-vios1'))
        self.logfx.patchers['debug'].mock.assert_any_call(
            mock.ANY, dict(stg_type='VSCSI', lpar_id=32,
                           vios_name='nimbus-ch03-p2-vios2'))
        self.assertEqual(2, self.txfx.patchers['update'].mock.call_count)
        # By not mocking _RemoveStorage, prove it shorts out (the mapping for
        # LPAR ID 32 has no backing storage).

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.wrap')
    def test_multiple_removals(self, mock_wrap):
        # Pretend LPAR feed is "empty" so we don't skip any removals.
        mock_wrap.return_value = []
        v1 = self.vio_feed[0]
        v2 = self.vio_feed[1]
        v1_map_count = len(v1.scsi_mappings)
        v2_map_count = len(v2.scsi_mappings)
        # Zero removals works
        ts.add_lpar_storage_scrub_tasks([], self.ftsk)
        self.ftsk.execute()
        self.assertEqual(0, self.txfx.patchers['update'].mock.call_count)
        # Removals for which no mappings exist
        ts.add_lpar_storage_scrub_tasks([71, 72, 76, 77], self.ftsk)
        self.ftsk.execute()
        self.assertEqual(0, self.txfx.patchers['update'].mock.call_count)
        # Remove some from each VIOS
        self.assertEqual(v1_map_count, len(v1.scsi_mappings))
        self.assertEqual(v2_map_count, len(v2.scsi_mappings))
        ts.add_lpar_storage_scrub_tasks([3, 37, 80, 7, 27, 85], self.ftsk)
        self.ftsk.execute()
        self.assertEqual(2, self.txfx.patchers['update'].mock.call_count)
        self.assertEqual(v1_map_count - 3, len(v1.scsi_mappings))
        self.assertEqual(v2_map_count - 3, len(v2.scsi_mappings))
        # Now make the LPAR feed hit some of the removals.  They should be
        # skipped.
        self.txfx.patchers['update'].mock.reset_mock()
        v1_map_count = len(v1.scsi_mappings)
        v2_map_count = len(v2.scsi_mappings)
        mock_wrap.return_value = [mock.Mock(id=i) for i in (4, 5, 8, 11)]
        ts.add_lpar_storage_scrub_tasks([4, 5, 6, 8, 11, 12], self.ftsk)
        self.ftsk.execute()
        self.assertEqual(2, self.txfx.patchers['update'].mock.call_count)
        self.assertEqual(v1_map_count - 1, len(v1.scsi_mappings))
        self.assertEqual(v2_map_count - 1, len(v2.scsi_mappings))
        # Make sure the right ones were ignored
        v1_map_lids = [sm.server_adapter.lpar_id for sm in v1.scsi_mappings]
        v2_map_lids = [sm.server_adapter.lpar_id for sm in v2.scsi_mappings]
        self.assertIn(4, v1_map_lids)
        self.assertIn(5, v1_map_lids)
        self.assertIn(8, v2_map_lids)
        self.assertIn(11, v2_map_lids)
        # ...and the right ones were removed
        self.assertNotIn(6, v1_map_lids)
        self.assertNotIn(12, v2_map_lids)


class TestScrub2(testtools.TestCase):
    """One VIOS in feed; VFC mappings; interesting VSCSI mappings."""
    def setUp(self):
        super(TestScrub2, self).setUp()
        self.adpt = self.useFixture(
            fx.AdapterFx(traits=fx.RemotePVMTraits)).adpt
        self.vio_feed = [vios.VIOS.wrap(tju.load_file(VIOS_ENTRY, self.adpt))]
        self.txfx = self.useFixture(fx.FeedTaskFx(self.vio_feed))
        self.logfx = self.useFixture(fx.LoggingFx())
        self.ftsk = tx.FeedTask('scrub', self.vio_feed)

    @mock.patch('pypowervm.tasks.storage._rm_vdisks')
    @mock.patch('pypowervm.tasks.storage._rm_vopts')
    @mock.patch('pypowervm.tasks.storage._rm_lus')
    def test_lu_vopt_vdisk(self, mock_rm_lu, mock_rm_vopt, mock_rm_vd):
        def verify_rm_stg_call(exp_list):
            def _rm_stg(wrapper, stglist, *a, **k):
                self.assertEqual(len(exp_list), len(stglist))
                for exp, act in zip(exp_list, stglist):
                    self.assertEqual(exp.udid, act.udid)
            return _rm_stg
        warns = [mock.call(
            mock.ANY, {'stg_type': 'VSCSI', 'lpar_id': 3, 'num_maps': 3,
                       'vios_name': self.vio_feed[0].name})]

        # We should ignore the LUs...
        mock_rm_lu.side_effect = self.fail
        # ...but should emit a warning about ignoring them
        warns.append(mock.call(
            mock.ANY,
            {'stg_name': 'volume-boot-8246L1C_0604CAA-salsman66-00000004',
             'stg_type': 'LogicalUnit'}))

        vorm = self.vio_feed[0].scsi_mappings[5].backing_storage
        mock_rm_vopt.side_effect = verify_rm_stg_call([vorm])
        warns.append(mock.call(
            mock.ANY, {'vocount': 1, 'vios': self.vio_feed[0].name,
                       'volist' '': ["%s (%s)" % (vorm.name, vorm.udid)]}))

        vdrm = self.vio_feed[0].scsi_mappings[8].backing_storage
        mock_rm_vd.side_effect = verify_rm_stg_call([vdrm])
        warns.append(mock.call(
            mock.ANY, {'vdcount': 1, 'vios': self.vio_feed[0].name,
                       'vdlist' '': ["%s (%s)" % (vdrm.name, vdrm.udid)]}))

        ts.add_lpar_storage_scrub_tasks([3], self.ftsk, lpars_exist=True)
        # LPAR ID 45 is not represented in the mappings.  Test a) that it is
        # ignored, b) that we can have two separate LPAR storage scrub tasks
        # in the same FeedTask (no duplicate 'provides' names).
        ts.add_lpar_storage_scrub_tasks([45], self.ftsk, lpars_exist=True)
        self.ftsk.execute()
        self.logfx.patchers['warn'].mock.assert_has_calls(
            warns, any_order=True)

    def test_find_stale_lpars(self):
        self.adpt.read.return_value = tju.load_file(LPAR_FEED,
                                                    adapter=self.adpt)
        vwrap = vios.VIOS.wrap(tju.load_file(VIOS_ENTRY, adapter=self.adpt))
        self.assertEqual({55, 21}, set(ts.find_stale_lpars(vwrap)))


class TestScrub3(testtools.TestCase):
    """One VIOS; lots of orphan VSCSI and VFC mappings."""
    def setUp(self):
        super(TestScrub3, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.vio_feed = [vios.VIOS.wrap(tju.load_file(VIOS_ENTRY2, self.adpt))]
        self.txfx = self.useFixture(fx.FeedTaskFx(self.vio_feed))
        self.logfx = self.useFixture(fx.LoggingFx())
        self.ftsk = tx.FeedTask('scrub', self.vio_feed)

    @mock.patch('pypowervm.tasks.storage._rm_vopts')
    def test_orphan(self, mock_rm_vopts):
        """Scrub orphan VSCSI and VFC mappings."""
        def validate_rm_vopts(vgwrap, vopts, **kwargs):
            # Two of the VSCSI mappings have storage; both are vopts
            self.assertEqual(2, len(vopts))
        mock_rm_vopts.side_effect = validate_rm_vopts
        vwrap = self.vio_feed[0]
        # Save the "before" sizes of the mapping lists
        vscsi_len = len(vwrap.scsi_mappings)
        vfc_len = len(vwrap.vfc_mappings)
        ts.add_orphan_storage_scrub_tasks(self.ftsk)
        ret = self.ftsk.execute()
        # One for vscsi maps, one for vfc maps, one for vopt storage
        self.assertEqual(3, self.logfx.patchers['warn'].mock.call_count)
        # Pull out the WrapperTask returns from the (one) VIOS
        wtr = ret['wrapper_task_rets'].popitem()[1]
        vscsi_removals = wtr['vscsi_removals_orphans']
        self.assertEqual(18, len(vscsi_removals))
        # Removals are really orphans
        for srm in vscsi_removals:
            self.assertIsNone(srm.client_adapter)
        # The right number of maps remain.
        self.assertEqual(vscsi_len - 18, len(vwrap.scsi_mappings))
        # Remaining maps are not orphans.
        for smp in vwrap.scsi_mappings:
            self.assertIsNotNone(smp.client_adapter)
        # _RemoveOrphanVfcMaps doesn't "provide", so the following are limited.
        # The right number of maps remain.
        self.assertEqual(vfc_len - 19, len(vwrap.vfc_mappings))
        # Remaining maps are not orphans.
        for fmp in vwrap.vfc_mappings:
            self.assertIsNotNone(fmp.client_adapter)
        # POST was warranted.
        self.assertEqual(1, self.txfx.patchers['update'].mock.call_count)
        # _RemoveStorage invoked _rm_vopts
        self.assertEqual(1, mock_rm_vopts.call_count)

    @mock.patch('pypowervm.tasks.storage._rm_vdisks')
    @mock.patch('pypowervm.tasks.storage._rm_vopts')
    @mock.patch('pypowervm.tasks.storage.find_stale_lpars')
    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.wrap')
    def test_comprehensive_scrub(self, mock_wrap, mock_stale_lids,
                                 mock_rm_vopts, mock_rm_vdisks):
        # Don't confuse the 'update' call count with the VG POST
        mock_rm_vopts.return_value = None
        mock_rm_vdisks.return_value = None
        # Three "stale" LPARs in addition to the orphans.  These LPAR IDs are
        # represented in both VSCSI and VFC mappings.
        mock_stale_lids.return_value = [15, 18, 22]
        # Make sure all our "stale" lpars hit.
        mock_wrap.return_value = []
        vwrap = self.vio_feed[0]
        # Save the "before" sizes of the mapping lists
        vscsi_len = len(vwrap.scsi_mappings)
        vfc_len = len(vwrap.vfc_mappings)
        ts.ComprehensiveScrub(self.adpt).execute()
        # The right number of maps remain.
        self.assertEqual(vscsi_len - 21, len(vwrap.scsi_mappings))
        self.assertEqual(vfc_len - 22, len(vwrap.vfc_mappings))
        self.assertEqual(1, self.txfx.patchers['update'].mock.call_count)
        self.assertEqual(1, mock_rm_vopts.call_count)
        self.assertEqual(1, mock_rm_vdisks.call_count)

    @mock.patch('pypowervm.tasks.storage._rm_vopts')
    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.wrap')
    def test_orphans_by_lpar_id(self, mock_wrap, mock_rm_vopts):
        # Don't confuse the 'update' call count with the VG POST
        mock_rm_vopts.return_value = None
        mock_wrap.return_value = []
        vwrap = self.vio_feed[0]
        # Save the "before" sizes of the mapping lists
        vscsi_len = len(vwrap.scsi_mappings)
        vfc_len = len(vwrap.vfc_mappings)
        # LPAR 24 has one orphan FC mapping, one legit FC mapping, and one
        # orphan SCSI mapping (for a vopt).
        ts.ScrubOrphanStorageForLpar(self.adpt, 24).execute()
        # The right number of maps remain.
        self.assertEqual(vscsi_len - 1, len(vwrap.scsi_mappings))
        self.assertEqual(vfc_len - 1, len(vwrap.vfc_mappings))
        self.assertEqual(1, self.txfx.patchers['update'].mock.call_count)
        self.assertEqual(1, mock_rm_vopts.call_count)

if __name__ == '__main__':
    unittest.main()
