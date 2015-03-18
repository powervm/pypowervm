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
import pypowervm.tasks.cluster_ssp as cs
import pypowervm.tests.tasks.util as tju
import pypowervm.util as u
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.constants as wc
import pypowervm.wrappers.job as jwrap
import pypowervm.wrappers.storage as stor

import unittest

CREATE_CLUSTER = 'cluster_create_job_template.txt'


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


class TestClusterSSP(unittest.TestCase):

    @mock.patch('pypowervm.wrappers.job.Job.delete_job')
    @mock.patch('pypowervm.wrappers.job.Job.monitor_job')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_crt_cluster_ssp(self, mock_adp, mock_monitor_job, mock_del_job):
        # Load up GET Cluster/do/Create (job template)
        mock_adp.read.return_value = tju.load_file(CREATE_CLUSTER)
        # We'll pretend the job ran and completed successfully
        mock_monitor_job.return_value = (wc.PVM_JOB_STATUS_COMPLETED_OK, 'ok',
                                         False)

        # Mock Job.create_job to check job parameter values
        def create_job(job_el, entry_type, *args, **kwargs):
            self.assertEqual(entry_type, clust.Cluster.schema_type)
            job = jwrap.Job.wrap(adp.Entry({}, job_el))
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
            hostname='vios1', lpar_id=5, mtms='XXXX-YYY*ZZZZZZZ',
            vios_uri='https://a.example.com:12443/rest/api/uom/VirtualIOServe'
            'r/12345678-1234-1234-1234-123456789012')
        repos = stor.PV.bld(name='repos_pv_name')
        data = [stor.PV.bld(name=n) for n in (
            'hdisk1', 'hdisk2', 'hdisk3')]
        cs.crt_cluster_ssp(mock_adp, 'clust_name', 'ssp_name', repos,
                           node, data)
        # run_job() should run delete_job() at the end
        self.assertEqual(mock_del_job.call_count, 1)


class TestSSP(unittest.TestCase):

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
        ssp, lu = cs.crt_lu(self.adp, self.ssp, 'lu5', 10)
        self.assertEqual(lu.name, 'lu5')
        self.assertEqual(lu.udid, 'udid_lu5')
        self.assertTrue(lu.is_thin)
        self.assertEqual(ssp.etag, 'after')
        self.assertIn(lu, ssp.logical_units)

    def test_crt_lu_thin(self):
        ssp, lu = cs.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=True)
        self.assertTrue(lu.is_thin)

    def test_crt_lu_thick(self):
        ssp, lu = cs.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=False)
        self.assertFalse(lu.is_thin)

    def test_crt_lu_name_conflict(self):
        self.assertRaises(exc.DuplicateLUNameError, cs.crt_lu, self.adp,
                          self.ssp, 'lu1', 5)

    def test_rm_lu_by_lu(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = cs.rm_lu(self.adp, self.ssp, lu=lu)
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_by_name(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = cs.rm_lu(self.adp, self.ssp, name='lu2')
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_by_udid(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = cs.rm_lu(self.adp, self.ssp, udid='udid_lu2')
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_not_found(self):
        # By LU
        lu = stor.LU.bld('lu5', 6)
        self.assertRaises(exc.LUNotFoundError, cs.rm_lu, self.adp, self.ssp,
                          lu=lu)
        # By name
        self.assertRaises(exc.LUNotFoundError, cs.rm_lu, self.adp, self.ssp,
                          name='lu5')
        # By UDID
        self.assertRaises(exc.LUNotFoundError, cs.rm_lu, self.adp, self.ssp,
                          udid='lu5_udid')

if __name__ == '__main__':
    unittest.main()