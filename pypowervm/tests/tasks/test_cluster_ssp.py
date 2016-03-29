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

import fixtures
import mock
import unittest
import uuid

import pypowervm.entities as ent
import pypowervm.tasks.cluster_ssp as cs
import pypowervm.tests.tasks.util as tju
from pypowervm.tests.test_utils import test_wrapper_abc as twrap
import pypowervm.util as u
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.job as jwrap
import pypowervm.wrappers.storage as stor

CREATE_CLUSTER = 'cluster_create_job_template.txt'


class TestClusterSSP(unittest.TestCase):

    @mock.patch('pypowervm.wrappers.job.Job.delete_job')
    @mock.patch('pypowervm.wrappers.job.Job._monitor_job')
    @mock.patch('pypowervm.wrappers.job.Job.job_status')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_crt_cluster_ssp(self, mock_adp, mock_status, mock_monitor_job,
                             mock_del_job):
        # Load up GET Cluster/do/Create (job template)
        mock_adp.read.return_value = tju.load_file(CREATE_CLUSTER, mock_adp)
        # We'll pretend the job ran and completed successfully
        mock_monitor_job.return_value = False
        mock_status.__get__ = mock.Mock(
            return_value=jwrap.JobStatus.COMPLETED_OK)

        # Mock Job.create_job to check job parameter values
        def create_job(job_el, entry_type, *args, **kwargs):
            self.assertEqual(entry_type, clust.Cluster.schema_type)
            job = jwrap.Job.wrap(ent.Entry({}, job_el, None))
            param_vals = job._get_vals(u.xpath(
                'JobParameters', 'JobParameter', 'ParameterValue'))
            self.assertEqual(
                param_vals[0],
                '<uom:Cluster xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
                'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadat'
                'a><uom:Atom/></uom:Metadata><uom:ClusterName>clust_name</uom:'
                'ClusterName><uom:RepositoryDisk schemaVersion="V1_0"><uom:Phy'
                'sicalVolume schemaVersion="V1_0"><uom:Metadata><uom:Atom/></u'
                'om:Metadata><uom:VolumeName>repos_pv_name</uom:VolumeName></u'
                'om:PhysicalVolume></uom:RepositoryDisk><uom:Node schemaVersio'
                'n="V1_0"><uom:Node schemaVersion="V1_0"><uom:Metadata><uom:At'
                'om/></uom:Metadata><uom:HostName>vios1</uom:HostName><uom:Par'
                'titionID>5</uom:PartitionID><uom:MachineTypeModelAndSerialNum'
                'ber schemaVersion="V1_0"><uom:Metadata><uom:Atom/></uom:Metad'
                'ata><uom:MachineType>XXXX</uom:MachineType><uom:Model>YYY</uo'
                'm:Model><uom:SerialNumber>ZZZZZZZ</uom:SerialNumber></uom:Mac'
                'hineTypeModelAndSerialNumber><uom:VirtualIOServer href="https'
                '://a.example.com:12443/rest/api/uom/VirtualIOServer/12345678-'
                '1234-1234-1234-123456789012" rel="related"/></uom:Node></uom:'
                'Node></uom:Cluster>')
            self.assertEqual(
                param_vals[1],
                '<uom:SharedStoragePool xmlns:uom="http://www.ibm.com/xmlns/sy'
                'stems/power/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><u'
                'om:Metadata><uom:Atom/></uom:Metadata><uom:PhysicalVolumes sc'
                'hemaVersion="V1_0"><uom:PhysicalVolume schemaVersion="V1_0"><'
                'uom:Metadata><uom:Atom/></uom:Metadata><uom:VolumeName>hdisk1'
                '</uom:VolumeName></uom:PhysicalVolume><uom:PhysicalVolume sch'
                'emaVersion="V1_0"><uom:Metadata><uom:Atom/></uom:Metadata><uo'
                'm:VolumeName>hdisk2</uom:VolumeName></uom:PhysicalVolume><uom'
                ':PhysicalVolume schemaVersion="V1_0"><uom:Metadata><uom:Atom/'
                '></uom:Metadata><uom:VolumeName>hdisk3</uom:VolumeName></uom:'
                'PhysicalVolume></uom:PhysicalVolumes><uom:StoragePoolName>ssp'
                '_name</uom:StoragePoolName></uom:SharedStoragePool>')
            return mock.MagicMock()
        mock_adp.create_job.side_effect = create_job
        node = clust.Node.bld(
            mock_adp, hostname='vios1', lpar_id=5, mtms='XXXX-YYY*ZZZZZZZ',
            vios_uri='https://a.example.com:12443/rest/api/uom/VirtualIOServe'
            'r/12345678-1234-1234-1234-123456789012')
        repos = stor.PV.bld(mock_adp, name='repos_pv_name')
        data = [stor.PV.bld(mock_adp, name=n) for n in (
            'hdisk1', 'hdisk2', 'hdisk3')]
        cs.crt_cluster_ssp('clust_name', 'ssp_name', repos, node, data)
        # run_job() should run delete_job() at the end
        self.assertEqual(mock_del_job.call_count, 1)


class TestGetOrUploadImageLU(twrap.TestWrapper):
    file = 'ssp.txt'
    wrapper_class_to_test = stor.SSP

    def setUp(self):
        super(TestGetOrUploadImageLU, self).setUp()
        self.ssp = self.dwrap
        self.useFixture(
            fixtures.MockPatch('uuid.uuid4')).mock.return_value = uuid.UUID(
            '1234abcd-1234-1234-1234-abcdbcdecdef')
        self.mock_ssp_refresh = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.storage.SSP.refresh')).mock
        self.mock_ssp_refresh.return_value = self.ssp
        self.mock_rm_ssp_stg = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.storage.rm_ssp_storage')).mock
        self.mock_rm_ssp_stg.side_effect = self.rm_ssp_storage
        self.mock_crt_lu = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.storage.crt_lu')).mock
        self.mock_upload_new_lu = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.storage.upload_new_lu2')).mock
        self.mock_sleep = self.useFixture(fixtures.MockPatch(
            'time.sleep')).mock
        self.mock_sleep.side_effect = self.sleep_conflict_finishes
        self.vios_uuid = 'vios_uuid'
        self.mock_stream_func = mock.Mock()
        gb_size = 123
        self.b_size = gb_size * 1024 * 1024 * 1024
        # The image LU with the "real" content
        luname = 'lu_name'
        self.img_lu = stor.LU.bld(None, luname, gb_size, typ=stor.LUType.IMAGE)
        # The marker LU used by *this* thread
        mkrname = 'part1234abcd' + luname
        self.mkr_lu = stor.LU.bld(None, mkrname, 0.001, typ=stor.LUType.IMAGE)
        # Marker LU used by a conflicting thread.  This one will lose the bid.
        confl_luname_lose = 'part5678cdef' + luname
        self.confl_mkr_lu_lose = stor.LU.bld(None, confl_luname_lose, 0.001,
                                             typ=stor.LUType.IMAGE)
        self.confl_mkr_lu_lose._udid('conflict_img_lu_udid_lose')
        # Marker LU used by a conflicting thread.  This one will win the bid.
        confl_luname_win = 'part0123abcd' + luname
        self.confl_mkr_lu_win = stor.LU.bld(None, confl_luname_win, 0.001,
                                            typ=stor.LUType.IMAGE)
        self.confl_mkr_lu_win._udid('conflict_img_lu_udid_win')
        # Always expect to finish with exactly one more LU than we started with
        self.exp_num_lus = len(self.ssp.logical_units) + 1

    def crt_mkr_lu(self, ssp1, luname, lu_gb, typ=None):
        """Mock crt_lu, create just the marker LU for this thread."""
        self.assertEqual(self.ssp, ssp1)
        self.assertEqual(self.mkr_lu.name, luname)
        self.assertEqual(self.mkr_lu.capacity, lu_gb)
        self.assertEqual(stor.LUType.IMAGE, typ)
        ssp1.logical_units.append(self.mkr_lu)
        return ssp1, self.mkr_lu

    def upload_new_lu(self, vios_uuid, ssp1, stream, luname, b_size):
        """Mock upload_new_lu good path."""
        self.assertEqual(self.vios_uuid, vios_uuid)
        self.assertEqual(self.ssp, ssp1)
        self.assertEqual(self.mock_stream_func.return_value, stream)
        self.assertEqual(self.img_lu.name, luname)
        self.assertEqual(self.b_size, b_size)
        ssp1.logical_units.append(self.img_lu)
        return ssp1, self.img_lu, None

    @staticmethod
    def rm_ssp_storage(ssp1, lus):
        """Mock for rm_ssp_storage."""
        for lu in lus:
            ssp1.logical_units.remove(lu)
        return ssp1

    def sleep_conflict_finishes(self, sec):
        """Pretend the conflicting LU finishes while we sleep."""
        # We may have used either conflict marker LU
        if self.confl_mkr_lu_lose in self.ssp.logical_units:
            self.ssp.logical_units.remove(self.confl_mkr_lu_lose)
        if self.confl_mkr_lu_win in self.ssp.logical_units:
            self.ssp.logical_units.remove(self.confl_mkr_lu_win)
        if self.img_lu not in self.ssp.logical_units:
            self.ssp.logical_units.append(self.img_lu)

    def test_upload_no_conflict(self):
        """Upload a new LU - no conflict."""
        self.mock_crt_lu.side_effect = self.crt_mkr_lu
        self.mock_upload_new_lu.side_effect = self.upload_new_lu
        self.assertEqual((self.ssp, self.img_lu), cs.get_or_upload_image_lu(
            self.ssp, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))
        # Created marker LU
        self.assertEqual(1, self.mock_crt_lu.call_count)
        # Invoked the stream func
        self.mock_stream_func.assert_called_once_with()
        # Uploaded content
        self.assertEqual(1, self.mock_upload_new_lu.call_count)
        # Removed marker LU
        self.mock_rm_ssp_stg.assert_called_once_with(self.ssp, [self.mkr_lu])

    def test_conflict_not_started(self):
        """Another upload is about to start when we get there."""
        self.ssp.logical_units.append(self.confl_mkr_lu_lose)

        self.assertEqual((self.ssp, self.img_lu), cs.get_or_upload_image_lu(
            self.ssp, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))

        # I "waited" for the other guy to complete
        self.assertEqual(1, self.mock_sleep.call_count)
        # I did not create, upload, or remove
        self.assertFalse(self.mock_crt_lu.called)
        self.assertFalse(self.mock_upload_new_lu.called)
        self.assertFalse(self.mock_rm_ssp_stg.called)
        # Right number of LUs
        self.assertEqual(self.exp_num_lus, len(self.ssp.logical_units))

    # @mock.patch('pypowervm.tasks.storage.crt_lu')
    # @mock.patch('pypowervm.tasks.storage.upload_new_lu')
    # @mock.patch('pypowervm.tasks.storage.rm_ssp_storage')
    # @mock.patch('time.sleep')
    # @mock.patch('uuid.uuid4')
    # @mock.patch('nova_powervm.virt.powervm.disk.driver.DiskAdapter.'
    #             '_get_image_upload')
    # def test_upload_img_conflict(self, mock_img_upl, mock_uuid4, mock_sleep,
    #                              mock_rm_lu, mock_upload_lu, mock_crt_lu):
    #     """Multiple simultaneous uploads of the same image."""
    #     ssp_stor = self._get_ssp_stor()
    #     sspw = ssp_stor._ssp_wrap
    #     mock_uuid4.return_value = uuid.UUID(
    #         '1234abcd-1234-1234-1234-abcdbcdecdef')
    #     exp_luname = ('image_' + powervm.TEST_IMAGE1.name + '_' +
    #                   powervm.TEST_IMAGE1.checksum)
    #     my_tmp_luname = 'part1234abcd' + exp_luname
    #     my_mkr_lu = stor.LU.bld(None, my_tmp_luname, 123,
    #                             typ=stor.LUType.IMAGE)
    #     my_mkr_lu._udid('my_mkr_lu_udid')
    #     conflict_luname_win = 'part0123abcd' + exp_luname
    #     conflict_luname_lose = 'part5678cdef' + exp_luname
    #     conflict_mkr_lu = stor.LU.bld(None, conflict_luname_lose,
    #                                   123, typ=stor.LUType.IMAGE)
    #     conflict_mkr_lu._udid('conflict_img_lu_udid')
    #     img_lu = stor.LU.bld(None, exp_luname, 123,
    #                          typ=stor.LUType.IMAGE)
    #     img_lu._udid('real_img_lu_udid')
    #     # Always expect to finish with exactly one more LU than we started with
    #     exp_num_lus = len(sspw.logical_units) + 1
    #
    #     def crt_lu2(ssp1, luname, lu_gb, typ=None):
    #         """Both image LUs added to the SSP at the same time."""
    #         ssp1.logical_units.append(my_mkr_lu)
    #         ssp1.logical_units.append(conflict_mkr_lu)
    #         # The conflict happened "elsewhere" - return mine
    #         return ssp1, my_mkr_lu
    #     mock_crt_lu.side_effect = crt_lu2
    #
    #     def rm_ssp_storage(ssp1, lus):
    #         for lu in lus:
    #             ssp1.logical_units.remove(lu)
    #         return ssp1
    #     mock_rm_lu.side_effect = rm_ssp_storage
    #
    #     def mock_sleep_conflict_finishes(sec):
    #         # Pretend the conflicting LU finishes while we sleep
    #         sspw.logical_units.remove(conflict_mkr_lu)
    #         if img_lu not in sspw.logical_units:
    #             sspw.logical_units.append(img_lu)
    #     mock_sleep.side_effect = mock_sleep_conflict_finishes
    #
    #     def upload_new_lu(vios_uuid, ssp1, stream, luname, b_size):
    #         self.assertEqual(img_lu.name, luname)
    #         sspw.logical_units.append(img_lu)
    #         return img_lu, None
    #     mock_upload_lu.side_effect = upload_new_lu
    #
    #     def upload_new_lu_raise(vios_uuid, ssp1, stream, luname, b_size):
    #         self.assertEqual(img_lu.name, luname)
    #         sspw.logical_units.append(img_lu)
    #         raise IOError('Create succeeded, but upload failed')
    #
    #     # ==> Test case 1: another upload is about to start when we get there.
    #     sspw.logical_units.append(conflict_mkr_lu)
    #
    #     retlu = ssp_stor._get_or_upload_image_lu(None, self.instance,
    #                                              powervm.TEST_IMAGE1)
    #
    #     # I "waited" for the other guy to complete
    #     self.assertEqual(1, mock_sleep.call_count)
    #     # I did not create, upload, or remove
    #     self.assertFalse(mock_crt_lu.called)
    #     self.assertFalse(mock_upload_lu.called)
    #     self.assertFalse(mock_rm_lu.called)
    #     # The real LU was returned
    #     self.assertEqual(img_lu, retlu)
    #     # Right number of LUs
    #     self.assertEqual(exp_num_lus, len(sspw.logical_units))
    #
    #     # Clean up
    #     mock_sleep.reset_mock()
    #     sspw.logical_units.remove(retlu)
    #
    #     # ==> Test case 2: another upload is in progress when we get there.
    #     sspw.logical_units.append(conflict_mkr_lu)
    #     sspw.logical_units.append(img_lu)
    #
    #     retlu = ssp_stor._get_or_upload_image_lu(None, self.instance,
    #                                              powervm.TEST_IMAGE1)
    #
    #     # I "waited" for the other guy to complete
    #     self.assertEqual(1, mock_sleep.call_count)
    #     # I did not create, upload, or remove
    #     self.assertFalse(mock_crt_lu.called)
    #     self.assertFalse(mock_upload_lu.called)
    #     self.assertFalse(mock_rm_lu.called)
    #     # The real LU was returned
    #     self.assertEqual(img_lu, retlu)
    #     # Right number of LUs
    #     self.assertEqual(exp_num_lus, len(sspw.logical_units))
    #
    #     # Clean up
    #     mock_sleep.reset_mock()
    #     sspw.logical_units.remove(retlu)
    #
    #     # ==> Test case 3: we both bid at the same time; and I lose.
    #     conflict_mkr_lu._name(conflict_luname_win)
    #
    #     retlu = ssp_stor._get_or_upload_image_lu(None, self.instance,
    #                                              powervm.TEST_IMAGE1)
    #
    #     # I tried creating mine because his wasn't there at the start
    #     self.assertEqual(1, mock_crt_lu.call_count)
    #     # I "slept", waiting for the other guy to finish
    #     self.assertEqual(1, mock_sleep.call_count)
    #     # I didn't upload
    #     self.assertFalse(mock_upload_lu.called)
    #     # I did remove my marker from the SSP
    #     mock_rm_lu.assert_called_with(mock.ANY, [my_mkr_lu])
    #     # The real LU was returned
    #     self.assertEqual(img_lu, retlu)
    #     # Right number of LUs
    #     self.assertEqual(exp_num_lus, len(sspw.logical_units))
    #
    #     # Clean up
    #     mock_crt_lu.reset_mock()
    #     mock_sleep.reset_mock()
    #     mock_rm_lu.reset_mock()
    #     sspw.logical_units.remove(retlu)
    #
    #     # ==> Test case 4: we both bid at the same time; and I win.
    #     conflict_mkr_lu._name(conflict_luname_lose)
    #
    #     retlu = ssp_stor._get_or_upload_image_lu(None, self.instance,
    #                                              powervm.TEST_IMAGE1)
    #
    #     # I tried creating mine because his wasn't there at the start
    #     self.assertEqual(1, mock_crt_lu.call_count)
    #     # Since I won, I did the upload
    #     self.assertEqual(1, mock_upload_lu.call_count)
    #     # I removed my marker from the SSP
    #     mock_rm_lu.assert_called_with(mock.ANY, [my_mkr_lu])
    #     # I never slept
    #     self.assertFalse(mock_sleep.called)
    #     # The real LU was returned
    #     self.assertEqual(img_lu, retlu)
    #     # IRL, the other guy will have removed his marker LU at some point.
    #     # Here, we can expect it to remain, so there's one "extra".
    #     self.assertEqual(exp_num_lus + 1, len(sspw.logical_units))
    #
    #     # Clean up
    #     mock_crt_lu.reset_mock()
    #     mock_upload_lu.reset_mock()
    #     mock_rm_lu.reset_mock()
    #     sspw.logical_units.remove(retlu)
    #     sspw.logical_units.remove(conflict_mkr_lu)
    #
    #     # ==> Test case 5: Same, but upload raises *before* creating the LU.
    #     mock_upload_lu.side_effect = IOError('Upload failed in crt_lu')
    #
    #     self.assertRaises(IOError, ssp_stor._get_or_upload_image_lu, None,
    #                       self.instance, powervm.TEST_IMAGE1)
    #
    #     # I tried creating mine because his wasn't there at the start
    #     self.assertEqual(1, mock_crt_lu.call_count)
    #     # Since I won, I tried the upload
    #     self.assertEqual(1, mock_upload_lu.call_count)
    #     # I never slept
    #     self.assertFalse(mock_sleep.called)
    #     # I removed my marker only - the real LU wasn't there.
    #     mock_rm_lu.assert_called_once_with(mock.ANY, [my_mkr_lu])
    #     # ...thus leaving the SSP as it was (plus the other guy's extra, which
    #     # would actually be removed normally).
    #     self.assertEqual(exp_num_lus, len(sspw.logical_units))
    #
    #     # Clean up
    #     mock_crt_lu.reset_mock()
    #     mock_upload_lu.reset_mock()
    #     mock_rm_lu.reset_mock()
    #     sspw.logical_units.remove(conflict_mkr_lu)
    #
    #     # ==> Test case 6: Same, but upload raises *after* creating the LU.
    #     mock_upload_lu.side_effect = upload_new_lu_raise
    #
    #     self.assertRaises(IOError, ssp_stor._get_or_upload_image_lu, None,
    #                       self.instance, powervm.TEST_IMAGE1)
    #
    #     # I tried creating mine because his wasn't there at the start
    #     self.assertEqual(1, mock_crt_lu.call_count)
    #     # Since I won, I tried the upload
    #     self.assertEqual(1, mock_upload_lu.call_count)
    #     # I never slept
    #     self.assertFalse(mock_sleep.called)
    #     # I removed both the real LU and my marker
    #     mock_rm_lu.assert_has_calls([
    #         mock.call(mock.ANY, [img_lu]),
    #         mock.call(mock.ANY, [my_mkr_lu])])
    #     # ...thus leaving the SSP as it was (plus the other guy's extra, which
    #     # would actually be removed normally).
    #     self.assertEqual(exp_num_lus, len(sspw.logical_units))
    #
    #     # Clean up
    #     mock_crt_lu.reset_mock()
    #     mock_upload_lu.reset_mock()
    #     mock_rm_lu.reset_mock()
    #     sspw.logical_units.remove(conflict_mkr_lu)
    #
    #     # ==> Test case 7: Same, but something goes wrong before we even get to
    #     # the upload.
    #     mock_img_upl.side_effect = KeyboardInterrupt('Problem before upload.')
    #
    #     self.assertRaises(KeyboardInterrupt, ssp_stor._get_or_upload_image_lu,
    #                       None, self.instance, powervm.TEST_IMAGE1)
    #
    #     # I tried creating mine because his wasn't there at the start
    #     self.assertEqual(1, mock_crt_lu.call_count)
    #     # I didn't get to the upload
    #     mock_upload_lu.assert_not_called()
    #     # I never slept
    #     self.assertFalse(mock_sleep.called)
    #     # I removed my marker only - the real LU wasn't there yet.
    #     mock_rm_lu.assert_called_once_with(mock.ANY, [my_mkr_lu])
    #     # ...thus leaving the SSP as it was (plus the other guy's extra, which
    #     # would actually be removed normally).
    #     self.assertEqual(exp_num_lus, len(sspw.logical_units))
