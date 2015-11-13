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

import unittest

import mock

import pypowervm.entities as ent
import pypowervm.tasks.cluster_ssp as cs
import pypowervm.tests.tasks.util as tju
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
