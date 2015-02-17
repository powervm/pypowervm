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
import pypowervm.jobs.cluster_ssp as cs
import pypowervm.tests.jobs.util as tju
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.constants as wc
import pypowervm.wrappers.job as jwrap
import pypowervm.wrappers.storage as stor

import unittest

CREATE_CLUSTER = 'cluster_create_job_template.txt'


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
            self.assertEqual(entry_type, wc.CLUSTER)
            job = jwrap.Job(adp.Entry({}, job_el))
            param_vals = job.get_parm_values(
                wc.ROOT + wc.DELIM.join(['JobParameters', 'JobParameter',
                                         'ParameterValue']))
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
                'om/></uom:Metadata><uom:HostName>vios1</uom:HostName><uom:Mac'
                'hineTypeModelAndSerialNumber schemaVersion="V1_0"><uom:Metada'
                'ta><uom:Atom/></uom:Metadata><uom:MachineType>XXXX</uom:Machi'
                'neType><uom:Model>YYY</uom:Model><uom:SerialNumber>ZZZZZZZ</u'
                'om:SerialNumber></uom:MachineTypeModelAndSerialNumber><uom:Pa'
                'rtitionID>5</uom:PartitionID><uom:VirtualIOServer href="https'
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
        node = clust.Node()
        node.hostname = 'vios1'
        node.mtms = 'XXXX-YYY*ZZZZZZZ'
        node.lpar_id = 5
        node.vios_uri = ('https://a.example.com:12443/rest/api/uom/VirtualIOSe'
                         'rver/12345678-1234-1234-1234-123456789012')
        repos = stor.PhysicalVolume.new_instance(name='repos_pv_name')
        data = [stor.PhysicalVolume.new_instance(name=n) for n in (
            'hdisk1', 'hdisk2', 'hdisk3')]
        cs.crt_cluster_ssp(mock_adp, 'clust_name', 'ssp_name', repos,
                           node, data)
        # run_job() should run delete_job() at the end
        self.assertEqual(mock_del_job.call_count, 1)

if __name__ == '__main__':
    unittest.main()