# Copyright 2015,2016 IBM Corp.
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

from six.moves import builtins

import fixtures
import mock
import testtools

import pypowervm.adapter as adp
import pypowervm.exceptions as exc
import pypowervm.helpers.vios_busy as vb
import pypowervm.tasks.storage as ts
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as fx
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.utils.transaction as tx
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf
import pypowervm.wrappers.virtual_io_server as vios

CLUSTER = "cluster.txt"
LU_LINKED_CLONE_JOB = 'cluster_LULinkedClone_job_template.txt'
UPLOAD_VOL_GRP_ORIG = 'upload_volgrp.txt'
UPLOAD_VOL_GRP_NEW_VDISK = 'upload_volgrp2.txt'
VG_FEED = 'fake_volume_group2.txt'
UPLOADED_FILE = 'upload_file.txt'
VIOS_FEED = 'fake_vios_feed.txt'
VIOS_FEED2 = 'fake_vios_hosting_vios_feed.txt'
VIOS_ENTRY = 'fake_vios_ssp_npiv.txt'
VIOS_ENTRY2 = 'fake_vios_mappings.txt'
LPAR_FEED = 'lpar.txt'
LU_FEED = 'lufeed.txt'


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

    @mock.patch('tempfile.mkdtemp')
    @mock.patch('pypowervm.tasks.storage.os')
    @mock.patch('pypowervm.util.retry_io_command')
    @mock.patch('pypowervm.tasks.storage.open')
    def test_rest_api_pipe(self, mock_open, mock_retry, mock_os, mock_mkdtemp):
        mock_writer = mock.Mock()
        with ts._rest_api_pipe(mock_writer) as read_stream:
            self.assertEqual(mock_retry.return_value, read_stream)
        mock_mkdtemp.assert_called_once_with()
        mock_os.path.join.assert_called_once_with(mock_mkdtemp.return_value,
                                                  'REST_API_Pipe')
        mock_os.mkfifo.assert_called_once_with(mock_os.path.join.return_value)
        mock_writer.assert_called_once_with(mock_os.path.join.return_value)
        mock_os.remove.assert_called_once_with(mock_os.path.join.return_value)
        mock_os.rmdir.assert_called_once_with(mock_mkdtemp.return_value)
        # _eintr_retry_call was invoked once with open and once with close
        mock_retry.assert_has_calls(
            [mock.call(mock_open, mock_os.path.join.return_value, 'r')],
            [mock.call(mock_retry.return_value.close)])

    @mock.patch('pypowervm.tasks.storage._rest_api_pipe')
    def test_upload_stream_api_func(self, mock_rap):
        """With FUNC, _upload_stream_api uses _rest_api_pipe properly."""
        vio_file = mock.Mock()
        vio_file.adapter.helpers = [vb.vios_busy_retry_helper]
        ts._upload_stream_api(vio_file, 'io_handle', ts.UploadType.FUNC)
        mock_rap.assert_called_once_with('io_handle')
        vio_file.adapter.upload_file.assert_called_once_with(
            vio_file.element, mock_rap.return_value.__enter__.return_value)
        self.assertEqual(vio_file.adapter.helpers, [vb.vios_busy_retry_helper])

    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vopt(self, mock_create_file):
        """Tests the uploads of the virtual disks."""

        fake_file = self._fake_meta()
        fake_file.adapter.helpers = [vb.vios_busy_retry_helper]
        mock_create_file.return_value = fake_file

        v_opt, f_wrap = ts.upload_vopt(self.adpt, self.v_uuid, None, 'test2',
                                       f_size=50)

        mock_create_file.assert_called_once_with(
            self.adpt, 'test2', vf.FileType.MEDIA_ISO, self.v_uuid, None, 50)
        # Test that vopt was 'uploaded'
        self.adpt.upload_file.assert_called_with(mock.ANY, None, helpers=[])
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

    @mock.patch.object(ts.LOG, 'warning')
    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_vopt_by_filepath(self, mock_create_file, mock_log_warn):
        """Tests the uploads of the virtual disks with an upload retry."""

        fake_file = self._fake_meta()
        fake_file.adapter.helpers = [vb.vios_busy_retry_helper]

        mock_create_file.return_value = fake_file
        self.adpt.upload_file.side_effect = [exc.Error("error"),
                                             object()]
        m = mock.mock_open()
        with mock.patch.object(builtins, 'open', m):
            v_opt, f_wrap = ts.upload_vopt(
                self.adpt, self.v_uuid, 'fake-path', 'test2', f_size=50)

        # Test that vopt was 'uploaded'
        self.adpt.upload_file.assert_called_with(mock.ANY, m(), helpers=[])
        self.assertIsNone(f_wrap)
        self.assertIsNotNone(v_opt)
        self.assertIsInstance(v_opt, stor.VOptMedia)
        self.assertEqual('test2', v_opt.media_name)

        # Validate that there was a warning log call and multiple executions
        # of the upload
        mock_log_warn.assert_called_once()
        self.assertEqual(2, self.adpt.upload_file.call_count)

        # Ensure cleanup was called twice since the first uploads fails.
        self.adpt.delete.assert_has_calls([mock.call(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')]*2)

    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_new_vopt_w_fail(self, mock_create_file):
        """Tests the uploads of the virtual disks with an upload fail."""
        mock_create_file.return_value = self._fake_meta()
        self.adpt.upload_file.side_effect = exc.Error("error")

        self.assertRaises(exc.Error, ts.upload_vopt, self.adpt, self.v_uuid,
                          None, 'test2', f_size=50)

    @mock.patch('pypowervm.tasks.storage.rm_vg_storage')
    @mock.patch('pypowervm.wrappers.storage.VG.get')
    @mock.patch('pypowervm.tasks.storage._upload_stream')
    @mock.patch('pypowervm.tasks.storage._create_file')
    @mock.patch('pypowervm.tasks.storage.crt_vdisk')
    def test_upload_new_vdisk_failed(
            self, mock_create_vdisk, mock_create_file, mock_upload_stream,
            mock_vg_get, mock_rm):
        """Tests the uploads of the virtual disks."""
        # First need to load in the various test responses.
        mock_vdisk = mock.Mock()
        mock_create_vdisk.return_value = mock_vdisk
        mock_create_file.return_value = self._fake_meta()

        fake_vg = mock.Mock()
        mock_vg_get.return_value = fake_vg

        mock_upload_stream.side_effect = exc.ConnectionError('fake error')

        self.assertRaises(
            exc.ConnectionError, ts.upload_new_vdisk, self.adpt, self.v_uuid,
            self.vg_uuid, None, 'test2', 50, d_size=25, sha_chksum='abc123')
        self.adpt.delete.assert_called_once()
        mock_rm.assert_called_once_with(fake_vg, vdisks=[mock_vdisk])

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

    @mock.patch('pypowervm.tasks.storage.crt_vdisk')
    def test_crt_copy_vdisk(self, mock_crt_vdisk):
        """Tests the uploads of the virtual disks."""
        # traits are already set to use the REST API upload

        # First need to load in the various test responses.
        vg_orig = tju.load_file(UPLOAD_VOL_GRP_ORIG, self.adpt)
        vg_post_crt = tju.load_file(UPLOAD_VOL_GRP_NEW_VDISK, self.adpt)

        self.adpt.read.return_value = vg_orig
        self.adpt.update_by_path.return_value = vg_post_crt
        n_vdisk = ts.crt_copy_vdisk(
            self.adpt, self.v_uuid, self.vg_uuid, 'src', 1073741824, 'test2',
            d_size=2147483648, file_format=stor.FileFormatType.RAW)

        self.assertIsNotNone(n_vdisk)
        mock_crt_vdisk.assert_called_once_with(
            self.adpt, self.v_uuid, self.vg_uuid, 'test2', 2,
            base_image='src', file_format=stor.FileFormatType.RAW)

    @mock.patch('pypowervm.tasks.storage.crt_vdisk')
    @mock.patch('pypowervm.tasks.storage._create_file')
    @mock.patch('pypowervm.tasks.storage._upload_stream_api')
    def test_upload_new_vdisk_func_remote(self, mock_usa, mock_crt_file,
                                          mock_crt_vdisk):
        """With FUNC and non-local, upload_new_vdisk uses REST API upload."""
        mock_crt_file.return_value = mock.Mock(schema_type='File')

        n_vdisk, maybe_file = ts.upload_new_vdisk(
            self.adpt, 'v_uuid', 'vg_uuid', 'io_handle', 'd_name', 10,
            upload_type=ts.UploadType.FUNC,
            file_format=stor.FileFormatType.RAW)
        mock_crt_vdisk.assert_called_once_with(
            self.adpt, 'v_uuid', 'vg_uuid', 'd_name', 1.0,
            file_format=stor.FileFormatType.RAW)
        mock_crt_file.assert_called_once_with(
            self.adpt, 'd_name', vf.FileType.DISK_IMAGE, 'v_uuid', f_size=10,
            tdev_udid=mock_crt_vdisk.return_value.udid, sha_chksum=None)
        mock_usa.assert_called_once_with(
            mock_crt_file.return_value, 'io_handle', ts.UploadType.FUNC)
        mock_crt_file.return_value.adapter.delete.assert_called_once_with(
            vf.File.schema_type, root_id=mock_crt_file.return_value.uuid,
            service='web')
        self.assertEqual(mock_crt_vdisk.return_value, n_vdisk)
        self.assertIsNone(maybe_file)

    @mock.patch('pypowervm.tasks.storage._upload_stream_api')
    @mock.patch('pypowervm.tasks.storage._create_file')
    def test_upload_stream_via_stream_bld(self, mock_create_file,
                                          mock_upload_st):
        """Tests the uploads of a vDisk - via UploadType.IO_STREAM_BUILDER."""
        mock_file = self._fake_meta()
        # Prove that COORDINATED is gone (uses API upload now)
        mock_file._enum_type(vf.FileType.DISK_IMAGE_COORDINATED)
        mock_create_file.return_value = mock_file

        mock_io_stream = mock.MagicMock()
        mock_io_handle = mock.MagicMock()
        mock_io_handle.return_value = mock_io_stream

        # Run the code
        ts._upload_stream(mock_file, mock_io_handle,
                          ts.UploadType.IO_STREAM_BUILDER)

        # Make sure the function was called.
        mock_io_handle.assert_called_once_with()
        mock_upload_st.assert_called_once_with(
            mock_file, mock_io_stream, ts.UploadType.IO_STREAM)

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
    @mock.patch('pypowervm.tasks.storage.crt_lu')
    def test_upload_new_lu(self, mock_crt_lu, mock_create_file):
        """Tests create/upload of SSP LU."""
        # traits are already set to use the REST API upload
        ssp = mock.Mock(adapter=mock.Mock(traits=mock.Mock(local_api=True)))
        interim_lu = mock.Mock(adapter=self.adpt)
        mock_create_file.return_value = self._fake_meta()
        mock_crt_lu.return_value = ssp, interim_lu
        size_b = 1224067890

        new_lu, f_wrap = ts.upload_new_lu(
            self.v_uuid, ssp, None, 'lu1', size_b, d_size=25,
            sha_chksum='abc123')

        # The LU created by crt_lu was returned
        self.assertEqual(interim_lu, new_lu)
        # crt_lu was called properly
        # 1224067890 / 1GB = 1.140002059; round up to 2dp
        mock_crt_lu.assert_called_with(ssp, 'lu1', 1.15, typ=stor.LUType.IMAGE)

        # Ensure the create file was called
        mock_create_file.assert_called_once_with(
            self.adpt, interim_lu.name, vf.FileType.DISK_IMAGE, self.v_uuid,
            f_size=size_b, tdev_udid=interim_lu.udid, sha_chksum='abc123')

        # Ensure cleanup was called after the upload
        self.adpt.delete.assert_called_once_with(
            'File', service='web',
            root_id='6233b070-31cc-4b57-99bd-37f80e845de9')
        self.assertIsNone(f_wrap)

    @mock.patch('pypowervm.util.convert_bytes_to_gb')
    @mock.patch('pypowervm.tasks.storage.crt_lu')
    @mock.patch('pypowervm.tasks.storage.upload_lu')
    def test_upload_new_lu_calls(self, mock_upl, mock_crt, mock_b2g):
        """Various permutations of how to call upload_new_lu."""
        mock_crt.return_value = 'ssp_out', 'new_lu'
        f_size = 10

        # No optionals
        self.assertEqual(('new_lu', mock_upl.return_value), ts.upload_new_lu(
            'v_uuid', 'ssp_in', 'd_stream', 'lu_name', f_size))
        mock_b2g.assert_called_with(f_size, dp=2)
        mock_crt.assert_called_with('ssp_in', 'lu_name', mock_b2g.return_value,
                                    typ=stor.LUType.IMAGE)
        mock_upl.assert_called_with('v_uuid', 'new_lu', 'd_stream', f_size,
                                    sha_chksum=None,
                                    upload_type=ts.UploadType.IO_STREAM)
        mock_b2g.reset_mock()
        mock_crt.reset_mock()
        mock_upl.reset_mock()

        # d_size < f_size; sha_chksum specified
        self.assertEqual(('new_lu', mock_upl.return_value), ts.upload_new_lu(
            'v_uuid', 'ssp_in', 'd_stream', 'lu_name', f_size, d_size=1,
            sha_chksum='sha_chksum'))
        mock_b2g.assert_called_with(10, dp=2)
        mock_crt.assert_called_with('ssp_in', 'lu_name', mock_b2g.return_value,
                                    typ=stor.LUType.IMAGE)
        mock_upl.assert_called_with('v_uuid', 'new_lu', 'd_stream', f_size,
                                    sha_chksum='sha_chksum',
                                    upload_type=ts.UploadType.IO_STREAM)
        mock_b2g.reset_mock()
        mock_crt.reset_mock()
        mock_upl.reset_mock()

        # d_size > f_size; return_ssp specified
        self.assertEqual(('ssp_out', 'new_lu', mock_upl.return_value),
                         ts.upload_new_lu(
                             'v_uuid', 'ssp_in', 'd_stream', 'lu_name', f_size,
                             d_size=100, return_ssp=True))
        mock_b2g.assert_called_with(100, dp=2)
        mock_crt.assert_called_with('ssp_in', 'lu_name', mock_b2g.return_value,
                                    typ=stor.LUType.IMAGE)
        mock_upl.assert_called_with('v_uuid', 'new_lu', 'd_stream', f_size,
                                    sha_chksum=None,
                                    upload_type=ts.UploadType.IO_STREAM)

    @mock.patch('pypowervm.tasks.storage._create_file')
    @mock.patch('pypowervm.tasks.storage._upload_stream_api')
    def test_upload_lu_func_remote(self, mock_usa, mock_crt_file):
        """With FUNC and non-local, upload_lu uses REST API upload."""
        lu = mock.Mock(adapter=self.adpt)
        self.assertIsNone(ts.upload_lu('v_uuid', lu, 'io_handle', 'f_size',
                                       upload_type=ts.UploadType.FUNC))
        mock_crt_file.assert_called_once_with(
            lu.adapter, lu.name, vf.FileType.DISK_IMAGE, 'v_uuid',
            f_size='f_size', tdev_udid=lu.udid, sha_chksum=None)
        mock_usa.assert_called_once_with(mock_crt_file.return_value,
                                         'io_handle', ts.UploadType.FUNC)

    @mock.patch('pypowervm.util.convert_bytes_to_gb')
    @mock.patch('pypowervm.tasks.storage.crt_lu')
    @mock.patch('pypowervm.tasks.storage.upload_lu')
    def test_upload_new_lu_calls_via_func(self, mock_upl, mock_crt, mock_b2g):
        """Various permutations of how to call upload_new_lu."""
        mock_crt.return_value = 'ssp_out', 'new_lu'
        f_size = 10

        # Successful call
        ssp_in = mock.Mock(adapter=mock.Mock(traits=mock.Mock(local_api=True)))
        self.assertEqual(('new_lu', mock_upl.return_value), ts.upload_new_lu(
            'v_uuid', ssp_in, 'd_stream', 'lu_name', f_size,
            upload_type=ts.UploadType.FUNC))
        mock_b2g.assert_called_with(f_size, dp=2)
        mock_crt.assert_called_with(ssp_in, 'lu_name', mock_b2g.return_value,
                                    typ=stor.LUType.IMAGE)
        mock_upl.assert_called_with('v_uuid', 'new_lu', 'd_stream', f_size,
                                    sha_chksum=None,
                                    upload_type=ts.UploadType.FUNC)

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


class TestVG(twrap.TestWrapper):
    file = VG_FEED
    wrapper_class_to_test = stor.VG

    def setUp(self):
        super(TestVG, self).setUp()

        # TestWrapper sets up the VG feed.
        self.mock_vg_get = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.storage.VG.get')).mock
        self.mock_vg_get.return_value = self.entries

        # Need a VIOS feed too.
        self.vios_feed = vios.VIOS.wrap(tju.load_file(VIOS_FEED))
        self.mock_vio_get = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.virtual_io_server.VIOS.get')).mock
        self.mock_vio_get.return_value = self.vios_feed
        self.mock_vio_search = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.virtual_io_server.VIOS.search')).mock

    def test_find_vg_all_vioses(self):
        ret_vio, ret_vg = ts.find_vg('adap', 'image_pool')
        self.assertEqual(self.vios_feed[0], ret_vio)
        self.assertEqual(self.entries[1], ret_vg)
        self.mock_vio_get.assert_called_once_with('adap')
        self.mock_vio_search.assert_not_called()
        self.mock_vg_get.assert_called_once_with(
            'adap', parent=self.vios_feed[0])

    def test_find_vg_specified_vios(self):
        self.mock_vio_search.return_value = self.vios_feed[1:]
        ret_vio, ret_vg = ts.find_vg(
            'adap', 'image_pool', vios_name='nimbus-ch03-p2-vios1')
        self.assertEqual(self.vios_feed[1], ret_vio)
        self.assertEqual(self.entries[1], ret_vg)
        self.mock_vio_get.assert_not_called()
        self.mock_vio_search.assert_called_once_with(
            'adap', name='nimbus-ch03-p2-vios1')
        self.mock_vg_get.assert_called_once_with(
            'adap', parent=self.vios_feed[1])

    def test_find_vg_no_vios(self):
        self.mock_vio_search.return_value = []
        self.assertRaises(exc.VIOSNotFound,
                          ts.find_vg, 'adap', 'n/a', vios_name='no_such_vios')
        self.mock_vio_get.assert_not_called()
        self.mock_vio_search.assert_called_once_with(
            'adap', name='no_such_vios')
        self.mock_vg_get.assert_not_called()

    def test_find_vg_not_found(self):
        self.assertRaises(exc.VGNotFound, ts.find_vg, 'adap', 'n/a')
        self.mock_vio_get.assert_called_once_with('adap')
        self.mock_vio_search.assert_not_called()
        self.mock_vg_get.assert_has_calls([
            mock.call('adap', parent=self.vios_feed[0]),
            mock.call('adap', parent=self.vios_feed[1])])


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
            self.adpt, self.v_uuid, self.vg_uuid, 'vdisk_name', 10,
            file_format=stor.FileFormatType.RAW)
        self.assertEqual('vdisk_name', ret.name)
        self.assertEqual(10, ret.capacity)
        self.assertEqual(stor.FileFormatType.RAW, ret.file_format)

        def _mock_update_path(*a, **kwa):
            vg_wrap = a[0]
            vg_wrap.virtual_disks[-1].name = ('/path/to/' +
                                              vg_wrap.virtual_disks[-1].name)
            new_vdisk = vg_wrap.virtual_disks[-1]
            self.assertEqual('/path/to/vdisk_name2', new_vdisk.name)
            self.assertEqual(10, new_vdisk.capacity)
            return vg_wrap.entry

        mock_update.side_effect = _mock_update_path
        ret = ts.crt_vdisk(
            self.adpt, self.v_uuid, self.vg_uuid, 'vdisk_name2', 10,
            file_format=stor.FileFormatType.RAW)
        self.assertEqual('/path/to/vdisk_name2', ret.name)
        self.assertEqual(10, ret.capacity)
        self.assertEqual(stor.FileFormatType.RAW, ret.file_format)


class TestRMStorage(testtools.TestCase):
    def setUp(self):
        super(TestRMStorage, self).setUp()
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
            dev1.toxmlstring.assert_called_with(pretty=True)
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


class TestTier(testtools.TestCase):
    @mock.patch('pypowervm.wrappers.storage.Tier.search')
    def test_default_tier_for_ssp(self, mock_srch):
        ssp = mock.Mock()
        self.assertEqual(mock_srch.return_value, ts.default_tier_for_ssp(ssp))
        mock_srch.assert_called_with(ssp.adapter, parent=ssp, is_default=True,
                                     one_result=True)
        mock_srch.return_value = None
        self.assertRaises(exc.NoDefaultTierFoundOnSSP,
                          ts.default_tier_for_ssp, ssp)


class TestLUEnt(twrap.TestWrapper):
    file = LU_FEED
    wrapper_class_to_test = stor.LUEnt

    def setUp(self):
        super(TestLUEnt, self).setUp()
        self.mock_feed_get = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.storage.LUEnt.get')).mock
        self.mock_feed_get.return_value = self.entries
        self.tier = mock.Mock(spec=stor.Tier, get=mock.Mock(
            return_value=self.entries))
        # Mock out each LUEnt's .delete so I can know I called the right ones.
        for luent in self.entries:
            luent.delete = mock.Mock()
        # This image LU...
        self.img_lu = self.entries[4]
        # ...backs these three linked clones
        self.clone1 = self.entries[9]
        self.clone2 = self.entries[11]
        self.clone3 = self.entries[21]
        self.orig_len = len(self.entries)

    def test_rm_tier_storage_errors(self):
        """Test rm_tier_storage ValueErrors."""
        # Neither tier nor lufeed provided
        self.assertRaises(ValueError, ts.rm_tier_storage, self.entries)
        # Invalid lufeed provided
        self.assertRaises(ValueError, ts.rm_tier_storage,
                          self.entries, lufeed=[1, 2])
        # Same, even if tier provided
        self.assertRaises(ValueError, ts.rm_tier_storage,
                          self.entries, tier=self.tier, lufeed=[1, 2])

    @mock.patch('pypowervm.tasks.storage._rm_lus')
    def test_rm_tier_storage_feed_get(self, mock_rm_lus):
        """Verify rm_tier_storage does a feed GET if lufeed not provided."""
        # Empty return from _rm_lus so the loop doesn't run
        mock_rm_lus.return_value = []
        lus_to_rm = [mock.Mock()]
        ts.rm_tier_storage(lus_to_rm, tier=self.tier)
        self.mock_feed_get.assert_called_once_with(self.tier.adapter,
                                                   parent=self.tier)
        mock_rm_lus.assert_called_once_with(self.entries, lus_to_rm,
                                            del_unused_images=True)
        self.mock_feed_get.reset_mock()
        mock_rm_lus.reset_mock()
        # Now ensure we don't do the feed get if a valid lufeed is provided.
        lufeed = [mock.Mock(spec=stor.LUEnt)]
        # Also test del_unused_images=False
        ts.rm_tier_storage(lus_to_rm, lufeed=lufeed, del_unused_images=False)
        self.mock_feed_get.assert_not_called()
        mock_rm_lus.assert_called_once_with(lufeed, lus_to_rm,
                                            del_unused_images=False)

    def test_rm_tier_storage1(self):
        """Verify rm_tier_storage removes what it oughtta."""
        # Should be able to use either LUEnt or LU
        clone1 = stor.LU.bld(None, self.clone1.name, 1)
        clone1._udid(self.clone1.udid)
        # HttpError doesn't prevent everyone from deleting.
        clone1.side_effect = exc.HttpError(mock.Mock())
        ts.rm_tier_storage([clone1, self.clone2], lufeed=self.entries)
        self.clone1.delete.assert_called_once_with()
        self.clone2.delete.assert_called_once_with()
        # Backing image should not be removed because clone3 still linked.  So
        # final result should be just the two removed.
        self.assertEqual(self.orig_len - 2, len(self.entries))
        # Now if we remove the last clone, the image LU should go too.
        ts.rm_tier_storage([self.clone3], lufeed=self.entries)
        self.clone3.delete.assert_called_once_with()
        self.img_lu.delete.assert_called_once_with()
        self.assertEqual(self.orig_len - 4, len(self.entries))


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

    @mock.patch('pypowervm.wrappers.storage.LUEnt.bld')
    @mock.patch('pypowervm.wrappers.storage.Tier.search')
    def test_crt_lu(self, mock_tier_srch, mock_lu_bld):
        ssp = mock.Mock(spec=stor.SSP)
        tier = mock.Mock(spec=stor.Tier)

        def validate(ret, use_ssp, thin, typ, clone):
            self.assertEqual(ssp.refresh.return_value if use_ssp else tier,
                             ret[0])
            self.assertEqual(mock_lu_bld.return_value.create.return_value,
                             ret[1])
            if use_ssp:
                mock_tier_srch.assert_called_with(
                    ssp.adapter, parent=ssp, is_default=True, one_result=True)
            mock_lu_bld.assert_called_with(
                ssp.adapter if use_ssp else tier.adapter, 'lu5', 10, thin=thin,
                typ=typ, clone=clone)
            mock_lu_bld.return_value.create.assert_called_with(
                parent=mock_tier_srch.return_value if use_ssp else tier)
            mock_lu_bld.reset_mock()

        # No optionals
        validate(ts.crt_lu(tier, 'lu5', 10), False, None, None, None)
        validate(ts.crt_lu(ssp, 'lu5', 10), True, None, None, None)

        # Thin
        validate(ts.crt_lu(tier, 'lu5', 10, thin=True), False, True, None,
                 None)
        validate(ts.crt_lu(ssp, 'lu5', 10, thin=True), True, True, None, None)

        # Type
        validate(ts.crt_lu(tier, 'lu5', 10, typ=stor.LUType.IMAGE), False,
                 None, stor.LUType.IMAGE, None)
        validate(ts.crt_lu(ssp, 'lu5', 10, typ=stor.LUType.IMAGE), True, None,
                 stor.LUType.IMAGE, None)

        # Clone
        clone = mock.Mock(udid='cloned_from_udid')
        validate(ts.crt_lu(tier, 'lu5', 10, clone=clone), False, None, None,
                 clone)
        validate(ts.crt_lu(ssp, 'lu5', 10, clone=clone), True, None, None,
                 clone)

        # Exception path
        mock_tier_srch.return_value = None
        self.assertRaises(exc.NoDefaultTierFoundOnSSP, ts.crt_lu, ssp, '5', 10)
        # But that doesn't happen if specifying tier
        validate(ts.crt_lu(tier, 'lu5', 10), False, None, None, None)

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

    @mock.patch('warnings.warn')
    @mock.patch('pypowervm.tasks.storage.crt_lu')
    def test_crt_lu_linked_clone(self, mock_crt_lu, mock_warn):
        src_lu = self.ssp.logical_units[0]

        mock_crt_lu.return_value = ('ssp', 'dst_lu')
        self.assertEqual(('ssp', 'dst_lu'), ts.crt_lu_linked_clone(
            self.ssp, 'clust1', src_lu, 'linked_lu'))
        mock_crt_lu.assert_called_once_with(
            self.ssp, 'linked_lu', 0, thin=True, typ=stor.LUType.DISK,
            clone=src_lu)
        mock_warn.assert_called_once_with(mock.ANY, DeprecationWarning)

    def test_image_lu_in_use(self):
        # The orphan will trigger a warning as we cycle through all the LUs
        # without finding any backed by this image.
        with self.assertLogs(ts.__name__, 'WARNING'):
            self.assertFalse(ts._image_lu_in_use(self.ssp.logical_units,
                                                 self.img_lu1))
        self.assertTrue(ts._image_lu_in_use(self.ssp.logical_units,
                                            self.img_lu2))

    def test_image_lu_for_clone(self):
        self.assertEqual(self.img_lu2,
                         ts._image_lu_for_clone(self.ssp.logical_units,
                                                self.dsk_lu3))
        self.dsk_lu3._cloned_from_udid(None)
        self.assertIsNone(ts._image_lu_for_clone(self.ssp.logical_units,
                                                 self.dsk_lu3))

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
        self.assertTrue(ts._image_lu_in_use(self.ssp.logical_units,
                                            self.img_lu5))
        ssp = ts.rm_ssp_storage(self.ssp, [self.dsk_lu6],
                                del_unused_images=False)
        lu_names.remove(self.dsk_lu6.name)
        self.assertEqual(lu_names, set(lu.name for lu in ssp.logical_units))
        self.assertFalse(ts._image_lu_in_use(self.ssp.logical_units,
                                             self.img_lu5))

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
        self.assertEqual(0, self.logfx.patchers['warning'].mock.call_count)
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
            self.logfx.patchers['warning'].mock.assert_any_call(
                mock.ANY, dict(stg_type='VFC', num_maps=3, lpar_id=32,
                               vios_name=vname))
        self.logfx.patchers['warning'].mock.assert_any_call(
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
        self.assertEqual(2, mock_rm_vopt.call_count)
        self.assertEqual(2, mock_rm_vd.call_count)
        self.logfx.patchers['warning'].mock.assert_has_calls(
            warns, any_order=True)

    @mock.patch('pypowervm.tasks.storage._rm_vdisks')
    @mock.patch('pypowervm.tasks.storage._rm_vopts')
    @mock.patch('pypowervm.tasks.storage._rm_lus')
    def test_no_remove_storage(self, mock_rm_lu, mock_rm_vopt, mock_rm_vd):
        ts.add_lpar_storage_scrub_tasks([3], self.ftsk, lpars_exist=True,
                                        remove_storage=False)
        self.ftsk.execute()
        mock_rm_lu.assert_not_called()
        mock_rm_vopt.assert_not_called()
        mock_rm_vd.assert_not_called()

    @mock.patch('pypowervm.wrappers.logical_partition.LPAR.get')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
    def test_find_stale_lpars(self, mock_vios, mock_lpar):
        mock_vios.return_value = self.vio_feed
        mock_lpar.return_value = lpar.LPAR.wrap(
            tju.load_file(LPAR_FEED, adapter=self.adpt))
        self.assertEqual({55, 21}, set(ts.find_stale_lpars(self.vio_feed[0])))


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
        self.assertEqual(3, self.logfx.patchers['warning'].mock.call_count)
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

    @staticmethod
    def count_maps_for_lpar(mappings, lpar_id):
        """Count the mappings whose client side is the specified LPAR ID.

        :param mappings: List of VFC or VSCSI mappings to search.
        :param lpar_id: The client LPAR ID to search for.
        :return: Integer - the number of mappings whose server_adapter.lpar_id
                 matches the specified lpar_id.
        """
        return len([1 for amap in mappings
                    if amap.server_adapter.lpar_id == lpar_id])

    def test_remove_portless_vfc_maps1(self):
        """Test _remove_portless_vfc_maps with no LPAR ID."""
        vwrap = self.vio_feed[0]
        # Save the "before" size of the VFC mapping list
        vfc_len = len(vwrap.vfc_mappings)
        # Count our target LPARs' mappings before
        lpar24maps = self.count_maps_for_lpar(vwrap.vfc_mappings, 24)
        lpar124maps = self.count_maps_for_lpar(vwrap.vfc_mappings, 124)
        ts.ScrubPortlessVFCMaps(self.adpt).execute()
        # Overall two fewer maps
        self.assertEqual(vfc_len - 2, len(vwrap.vfc_mappings))
        # ...and they were the right ones
        self.assertEqual(lpar24maps - 1,
                         self.count_maps_for_lpar(vwrap.vfc_mappings, 24))
        self.assertEqual(lpar124maps - 1,
                         self.count_maps_for_lpar(vwrap.vfc_mappings, 124))
        self.assertEqual(1, self.txfx.patchers['update'].mock.call_count)

    def test_remove_portless_vfc_maps2(self):
        """Test _remove_portless_vfc_maps specifying an LPAR ID."""
        vwrap = self.vio_feed[0]
        # Save the "before" size of the VFC mapping list
        vfc_len = len(vwrap.vfc_mappings)
        # Count our target LPAR's mappings before
        lpar24maps = self.count_maps_for_lpar(vwrap.vfc_mappings, 24)
        ts.ScrubPortlessVFCMaps(self.adpt, lpar_id=24).execute()
        # Overall one map was scrubbed
        self.assertEqual(vfc_len - 1, len(vwrap.vfc_mappings))
        # ...and it was the right one
        self.assertEqual(lpar24maps - 1,
                         self.count_maps_for_lpar(vwrap.vfc_mappings, 24))
        self.assertEqual(1, self.txfx.patchers['update'].mock.call_count)

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
        # LPAR 24 has one orphan FC mapping, one portless FC mapping, one legit
        # FC mapping, and one orphan SCSI mapping (for a vopt).
        ts.ScrubOrphanStorageForLpar(self.adpt, 24).execute()
        # The right number of maps remain.
        self.assertEqual(vscsi_len - 1, len(vwrap.scsi_mappings))
        self.assertEqual(vfc_len - 1, len(vwrap.vfc_mappings))
        self.assertEqual(1, self.txfx.patchers['update'].mock.call_count)
        self.assertEqual(1, mock_rm_vopts.call_count)


class TestScrub4(testtools.TestCase):
    """Novalink partition hosting storage for another VIOS partition"""
    def setUp(self):
        super(TestScrub4, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.vio_feed = vios.VIOS.wrap(tju.load_file(VIOS_FEED2, self.adpt))
        self.txfx = self.useFixture(fx.FeedTaskFx(self.vio_feed))
        self.logfx = self.useFixture(fx.LoggingFx())
        self.ftsk = tx.FeedTask('scrub', [self.vio_feed[0]])
        self.mock_lpar = self.useFixture(
            fixtures.MockPatch('pypowervm.tasks.storage.lpar.LPAR.get')).mock
        self.mock_vios = self.useFixture(
            fixtures.MockPatch('pypowervm.tasks.storage.vios.VIOS.get')).mock
        # Set default mock return values, these may be overridden per test
        self.mock_lpar.return_value = lpar.LPAR.wrap(
            tju.load_file(LPAR_FEED), self.adpt)
        self.mock_vios.return_value = self.vio_feed

    def test_find_stale_lpars_vios_only(self):
        self.mock_lpar.return_value = []
        self.assertEqual({16, 102}, set(ts.find_stale_lpars(self.vio_feed[0])))

    def test_find_stale_lpars_combined(self):
        self.assertEqual([102], ts.find_stale_lpars(self.vio_feed[0]))

    @mock.patch('pypowervm.tasks.storage._remove_lpar_maps')
    def test_orphan_scrub(self, mock_rm_lpar):
        def client_adapter_data(mappings):
            return {(smap.server_adapter.lpar_id,
                     smap.server_adapter.lpar_slot_num) for smap in mappings}

        scsi_maps = client_adapter_data(self.vio_feed[0].scsi_mappings)
        vfc_maps = client_adapter_data(self.vio_feed[0].vfc_mappings)
        ts.ComprehensiveScrub(self.adpt).execute()
        # Assert that stale lpar detection works correctly
        # (LPAR 102 does not exist)
        mock_rm_lpar.assert_has_calls([
            mock.call(self.vio_feed[0], [102], mock.ANY),
            mock.call(self.vio_feed[1], [], mock.ANY),
            mock.call(self.vio_feed[2], [], mock.ANY)
        ], any_order=True)
        # Assert that orphan detection removed the correct SCSI mapping
        # (VSCSI Mapping for VIOS 101, slot 17 has no client adapter)
        scsi_maps -= client_adapter_data(self.vio_feed[0].scsi_mappings)
        self.assertEqual({(101, 17)}, scsi_maps)
        # Assert that orphan detection removed the correct VFC mapping
        # (VFC Mapping for LP 100 slot 50 has no client adapter)
        vfc_maps -= client_adapter_data(self.vio_feed[0].vfc_mappings)
        self.assertEqual({(100, 50)}, vfc_maps)

    @mock.patch('pypowervm.tasks.storage._remove_lpar_maps')
    def test_add_lpar_storage_scrub_tasks(self, mock_rm_lpar):
        # Some of the IDs in "lpar_list" appear in the LPAR feed,
        # and others appear in the VIOS feed.
        # IDs in "stale_lpars" do not exist in either the LPAR or VIOS feed.
        lpar_list = [100, 101, 102, 55, 21, 4, 2, 16]
        stale_lpars = {102, 55, 21}
        ts.add_lpar_storage_scrub_tasks(lpar_list, self.ftsk,
                                        remove_storage=False)
        self.ftsk.execute()
        self.assertEqual(2, mock_rm_lpar.call_count)
        mock_rm_lpar.assert_has_calls([
            mock.call(self.vio_feed[0], stale_lpars, 'VSCSI'),
            mock.call(self.vio_feed[0], stale_lpars, 'VFC')
        ], any_order=True)
