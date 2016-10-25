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
import pypowervm.tasks.storage as tsk_st
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
    file = 'lufeed.txt'
    wrapper_class_to_test = stor.LUEnt

    def setUp(self):
        super(TestGetOrUploadImageLU, self).setUp()
        self.tier = mock.Mock(spec=stor.Tier)
        self.mock_luent_srch = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.storage.LUEnt.search')).mock
        self.mock_luent_srch.side_effect = self.luent_search
        self.useFixture(fixtures.MockPatch(
            'uuid.uuid4')).mock.return_value = uuid.UUID('1234abcd-1234-1234-1'
                                                         '234-abcdbcdecdef')
        self.mock_crt_lu = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.storage.crt_lu')).mock
        self.mock_upload_lu = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.storage.upload_lu')).mock
        self.mock_upload_lu.side_effect = self.upload_lu
        self.mock_sleep = self.useFixture(fixtures.MockPatch(
            'time.sleep')).mock
        self.mock_sleep.side_effect = self.sleep_conflict_finishes
        self.vios_uuid = 'vios_uuid'
        self.mock_stream_func = mock.Mock()
        self.gb_size = 123
        self.b_size = self.gb_size * 1024 * 1024 * 1024
        # The image LU with the "real" content
        luname = 'lu_name'
        self.img_lu = self.bld_lu(luname, self.gb_size)
        # The marker LU used by *this* thread
        mkrname = 'part1234abcd' + luname
        self.mkr_lu = self.bld_lu(mkrname, cs.MKRSZ)
        # Marker LU used by a conflicting thread.  This one will lose the bid.
        confl_luname_lose = 'part5678cdef' + luname
        self.confl_mkr_lu_lose = self.bld_lu(confl_luname_lose, cs.MKRSZ)
        # Marker LU used by a conflicting thread.  This one will win the bid.
        confl_luname_win = 'part0123abcd' + luname
        self.confl_mkr_lu_win = self.bld_lu(confl_luname_win, cs.MKRSZ)
        # Always expect to finish with exactly one more LU than we started with
        self.exp_num_lus = len(self.entries) + 1

    def bld_lu(self, luname, gb_size):
        lu = stor.LUEnt.bld(None, luname, gb_size, typ=cs.IMGTYP)
        lu._udid('udid_' + luname)
        lu.delete = mock.Mock()
        lu.delete.side_effect = lambda: self.entries.remove(lu)
        return lu

    def luent_search(self, adapter, parent=None, lu_type=None):
        """Mock side effect for LUEnt.search, validating arguments.

        :return: self.entries (the LUEnt feed)
        """
        self.assertEqual(self.tier.adapter, adapter)
        self.assertEqual(self.tier, parent)
        self.assertEqual(cs.IMGTYP, lu_type)
        return self.entries

    def setup_crt_lu_mock(self, crt_img_lu_se, conflicting_mkr_lu=None):
        """Set up the mock side effect for crt_lu calls.

        The marker LU side always creates "my" marker LU.  If a
        conflicting_mkr_lu is specified, also creates that marker LU (to
        simulate simultaneous attempts from separate hosts).

        The image LU side behaves as indicated by the crt_img_lu_se parameter.

        :param crt_img_lu_se: Side effect for crt_lu of the image LU.
        :param conflicting_mkr_lu: If specified, the resulting mock pretends
                                   that some other host created the specified
                                   marker LU at the same time we're creating
                                   ours.
        :return: A callable suitable for assigning to
                 self.mock_crt_lu.side_effect.
        """
        def crt_mkr_lu(tier, luname, lu_gb, typ=None):
            self.assertEqual(self.tier, tier)
            self.assertEqual(self.mkr_lu.name, luname)
            self.assertEqual(self.mkr_lu.capacity, lu_gb)
            self.assertEqual(cs.IMGTYP, typ)
            self.entries.append(self.mkr_lu)
            if conflicting_mkr_lu is not None:
                self.entries.append(conflicting_mkr_lu)
            # Second time through, creation of the image LU
            self.mock_crt_lu.side_effect = crt_img_lu_se
            return tier, self.mkr_lu

        # First time through, creation of the marker LU
        self.mock_crt_lu.side_effect = crt_mkr_lu

    def crt_img_lu(self, tier, luname, lu_gb, typ=None):
        """Mock side effect for crt_lu of the image LU."""
        self.assertEqual(self.tier, tier)
        self.assertEqual(self.img_lu.name, luname)
        self.assertEqual(self.img_lu.capacity, lu_gb)
        self.assertEqual(cs.IMGTYP, typ)
        self.entries.append(self.img_lu)
        return tier, self.img_lu

    def upload_lu(self, vios_uuid, new_lu, stream, b_size, upload_type=None):
        self.assertEqual(self.vios_uuid, vios_uuid)
        self.assertEqual(self.img_lu, new_lu)
        self.assertEqual(self.mock_stream_func, stream)
        self.assertEqual(self.b_size, b_size)
        self.assertEqual(tsk_st.UploadType.IO_STREAM_BUILDER, upload_type)

    def sleep_conflict_finishes(self, sec):
        """Pretend the conflicting LU finishes while we sleep."""
        self.assertTrue(cs.SLEEP_U_MIN <= sec <= cs.SLEEP_U_MAX)
        # We may have used either conflict marker LU
        if self.confl_mkr_lu_lose in self.entries:
            self.entries.remove(self.confl_mkr_lu_lose)
        if self.confl_mkr_lu_win in self.entries:
            self.entries.remove(self.confl_mkr_lu_win)
        if self.img_lu not in self.entries:
            self.entries.append(self.img_lu)

    def test_already_exists(self):
        """The image LU is already there."""
        self.entries.append(self.img_lu)

        self.assertEqual(self.img_lu, cs.get_or_upload_image_lu(
            self.tier, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))

        # We only searched once
        self.assertEqual(1, self.mock_luent_srch.call_count)
        # We didn't create anything
        self.mock_crt_lu.assert_not_called()
        # We didn't upload anything
        self.mock_upload_lu.assert_not_called()
        # We didn't delete anything
        self.mkr_lu.delete.assert_not_called()
        self.img_lu.delete.assert_not_called()
        # We didn't sleep
        self.mock_sleep.assert_not_called()
        # Stream func not invoked
        self.mock_stream_func.assert_not_called()
        # Right number of LUs
        self.assertEqual(self.exp_num_lus, len(self.entries))

    def test_upload_no_conflict(self):
        """Upload a new LU - no conflict."""
        self.setup_crt_lu_mock(self.crt_img_lu)

        self.assertEqual(self.img_lu, cs.get_or_upload_image_lu(
            self.tier, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))

        # Uploaded content
        self.assertEqual(1, self.mock_upload_lu.call_count)
        # Removed marker LU
        self.mkr_lu.delete.assert_called_once_with()
        # Did not delete image LU
        self.img_lu.delete.assert_not_called()
        # I pulled the feed the first time through, and for _upload_conflict
        self.assertEqual(2, self.mock_luent_srch.call_count)
        # Right number of LUs
        self.assertEqual(self.exp_num_lus, len(self.entries))

    def test_conflict_not_started(self):
        """Another upload is about to start when we get there."""
        # Note that the conflicting process wins, even though its marker LU
        # name would lose to ours - because we don't get around to creating
        # ours.
        self.entries.append(self.confl_mkr_lu_lose)

        self.assertEqual(self.img_lu, cs.get_or_upload_image_lu(
            self.tier, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))

        # I "waited" for the other guy to complete
        self.assertEqual(1, self.mock_sleep.call_count)
        # I did not create, upload, or remove anything
        self.mock_crt_lu.assert_not_called()
        self.mock_upload_lu.assert_not_called()
        self.mkr_lu.delete.assert_not_called()
        self.img_lu.delete.assert_not_called()
        # I pulled the feed the first time through, and once after the sleep
        self.assertEqual(2, self.mock_luent_srch.call_count)
        # Right number of LUs
        self.assertEqual(self.exp_num_lus, len(self.entries))

    def test_conflict_started(self):
        """Another upload is in progress when we get there."""
        self.entries.append(self.confl_mkr_lu_lose)
        self.entries.append(self.img_lu)

        self.assertEqual(self.img_lu, cs.get_or_upload_image_lu(
            self.tier, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))

        # I "waited" for the other guy to complete
        self.assertEqual(1, self.mock_sleep.call_count)
        # I did not create, upload, or remove anything
        self.mock_crt_lu.assert_not_called()
        self.mock_upload_lu.assert_not_called()
        self.mkr_lu.delete.assert_not_called()
        self.img_lu.delete.assert_not_called()
        # I searched the first time through, and once after the sleep
        self.assertEqual(2, self.mock_luent_srch.call_count)
        # Right number of LUs
        self.assertEqual(self.exp_num_lus, len(self.entries))

    def test_conflict_I_lose(self):
        """We both bid at the same time; and I lose."""
        self.setup_crt_lu_mock(self.fail,
                               conflicting_mkr_lu=self.confl_mkr_lu_win)

        self.assertEqual(self.img_lu, cs.get_or_upload_image_lu(
            self.tier, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))

        # I tried creating mine because his wasn't there at the start
        self.assertEqual(1, self.mock_crt_lu.call_count)
        # I "slept", waiting for the other guy to finish
        self.assertEqual(1, self.mock_sleep.call_count)
        # I didn't upload
        self.mock_upload_lu.assert_not_called()
        # I did remove my marker from the SSP
        self.mkr_lu.delete.assert_called_once_with()
        # I didn't remove the image LU (because I didn't create it)
        self.img_lu.delete.assert_not_called()
        # I searched the first time through, once in _upload_conflict, and once
        # after the sleep
        self.assertEqual(3, self.mock_luent_srch.call_count)
        # Right number of LUs
        self.assertEqual(self.exp_num_lus, len(self.entries))

    def test_conflict_I_win(self):
        """We both bid at the same time; and I win."""
        self.setup_crt_lu_mock(self.crt_img_lu,
                               conflicting_mkr_lu=self.confl_mkr_lu_lose)

        self.assertEqual(self.img_lu, cs.get_or_upload_image_lu(
            self.tier, self.img_lu.name, self.vios_uuid, self.mock_stream_func,
            self.b_size))

        # I tried creating mine because his wasn't there at the start; and I
        # also created the image LU.
        self.assertEqual(2, self.mock_crt_lu.call_count)
        # Since I won, I did the upload
        self.assertEqual(1, self.mock_upload_lu.call_count)
        # I did remove my marker from the SSP
        self.mkr_lu.delete.assert_called_once_with()
        # I didn't remove the image LU (because I won)
        self.img_lu.delete.assert_not_called()
        # I never slept
        self.mock_sleep.assert_not_called()
        # I searched the first time through, and in _upload_conflict
        self.assertEqual(2, self.mock_luent_srch.call_count)
        # IRL, the other guy will have removed his marker LU at some point.
        # Here, we can expect it to remain, so there's one "extra".
        self.assertEqual(self.exp_num_lus + 1, len(self.entries))

    def test_crt_img_lu_raises(self):
        """Exception during crt_lu of the image LU."""
        self.setup_crt_lu_mock(IOError('crt_lu raises on the image LU'),
                               conflicting_mkr_lu=self.confl_mkr_lu_lose)

        self.assertRaises(IOError, cs.get_or_upload_image_lu, self.tier,
                          self.img_lu.name, self.vios_uuid,
                          self.mock_stream_func, self.b_size)

        # I didn't get to the upload
        self.mock_upload_lu.assert_not_called()
        # I never slept
        self.mock_sleep.assert_not_called()
        # I removed my marker
        self.mkr_lu.delete.assert_called_once_with()
        # I didn't remove the image LU (because I failed to create it)
        self.img_lu.delete.assert_not_called()
        # I searched the first time through, and in _upload_conflict
        self.assertEqual(2, self.mock_luent_srch.call_count)
        # We left the SSP as it was (plus the other guy's extra, which would
        # actually be removed normally).
        self.assertEqual(self.exp_num_lus, len(self.entries))

    def test_upload_raises(self):
        """I win; upload_lu raises after crt_lu of the image LU."""
        self.setup_crt_lu_mock(self.crt_img_lu,
                               conflicting_mkr_lu=self.confl_mkr_lu_lose)
        self.mock_upload_lu.side_effect = IOError('upload_lu raises.')

        self.assertRaises(IOError, cs.get_or_upload_image_lu, self.tier,
                          self.img_lu.name, self.vios_uuid,
                          self.mock_stream_func, self.b_size)

        # I created my marker and the image LU
        self.assertEqual(2, self.mock_crt_lu.call_count)
        # Since I won, I tried the upload
        self.assertEqual(1, self.mock_upload_lu.call_count)
        # I never slept
        self.mock_sleep.assert_not_called()
        # I removed both the real LU and my marker
        self.mkr_lu.delete.assert_called_once_with()
        self.img_lu.delete.assert_called_once_with()
        # I searched the first time through, and in _upload_conflict
        self.assertEqual(2, self.mock_luent_srch.call_count)
        # We left the SSP as it was (plus the other guy's extra, which would
        # actually be removed normally).
        self.assertEqual(self.exp_num_lus, len(self.entries))
