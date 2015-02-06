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

import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.cluster as clust


class TestSharedStoragePool(twrap.TestWrapper):

    file = 'ssp.txt'
    wrapper_class_to_test = clust.SharedStoragePool

    def test_name(self):
        self.assertEqual(self.dwrap.name, 'neossp1')

    def test_udid(self):
        self.assertEqual(self.dwrap.udid, '24cfc907d2abf511e4b2d540f2e95daf3'
                         '0000000000972FB370000000054D14EB8')

    def test_capacity(self):
        self.assertAlmostEqual(self.dwrap.capacity, 49.88, 3)

    def test_free_space(self):
        self.assertAlmostEqual(self.dwrap.free_space, 48.98, 3)

    def test_total_lu_size(self):
        self.assertAlmostEqual(self.dwrap.total_lu_size, 1, 1)

    def test_physical_volumes(self):
        pvs = self.dwrap.physical_volumes
        self.assertEqual(len(pvs), 1)
        pv = pvs[0]
        self.assertEqual(
            pv.udid,
            '01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDAwMw==')
        self.assertEqual(pv.name, 'hdisk3')
        # TODO(IBM): test setter

    def test_logical_units(self):
        lus = self.dwrap.logical_units
        self.assertEqual(len(lus), 1)
        lu = lus[0]
        self.assertEqual(lu.udid, '27cfc907d2abf511e4b2d540f2e95daf301a02b090'
                         '4778d755df5a46fe25e500d8')
        self.assertEqual(lu.name, 'neolu1')
        self.assertTrue(lu.is_thin)
        self.assertEqual(lu.lu_type, 'VirtualIO_Disk')
        self.assertAlmostEqual(lu.capacity, 1, 1)
        # TODO(IBM): test setter


class TestCluster(twrap.TestWrapper):

    file = 'cluster.txt'
    wrapper_class_to_test = clust.Cluster

    def test_name(self):
        self.assertEqual(self.dwrap.name, 'neoclust1')

    def test_id(self):
        self.assertEqual(self.dwrap.id, '22cfc907d2abf511e4b2d540f2e95daf30')

    def test_ssp_uri(self):
        self.assertEqual(self.dwrap.ssp_uri, 'https://9.1.2.3:12443/rest/api'
                         '/uom/SharedStoragePool/e357a79a-7a3d-35b6-8405-55ab'
                         '6a2d0de7')

    def test_ssp_uuid(self):
        self.assertEqual(self.dwrap.ssp_uuid.lower(),
                         'e357a79a-7a3d-35b6-8405-55ab6a2d0de7')

    def test_repos_pvs(self):
        repos = self.dwrap.repos_pvs
        self.assertEqual(len(repos), 1)
        pv = repos[0]
        # PhysicalVolume is tested elsewhere.  Minimal verification here.
        self.assertEqual(pv.name, 'hdisk2')
        # TODO(IBM): test setter

    def test_nodes(self):
        """Tests the Node and MTMS wrappers as well."""
        nodes = self.dwrap.nodes
        self.assertEqual(len(nodes), 2)
        node = nodes[0]
        self.assertEqual(node.hostname, 'foo.ibm.com')
        self.assertEqual(node.lparid, 2)
        self.assertEqual(
            node.vios_uri, 'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
            '98498bed-c78a-3a4f-b90a-4b715418fcb6/VirtualIOServer/58C9EB1D-'
            '7213-4956-A011-77D43CC4ACCC')
        self.assertEqual(
            node.vios_uuid.upper(), '58C9EB1D-7213-4956-A011-77D43CC4ACCC')
        # Make sure the different Node entries are there
        self.assertEqual(nodes[1].hostname, 'bar.ibm.com')
        # Test MTMS
        mtms = node.mtms
        self.assertEqual(mtms.machine_type, '8247')
        self.assertEqual(mtms.model, '22L')
        self.assertEqual(mtms.serial, '2125D1A')
        # TODO(IBM): test nodes setter

if __name__ == "__main__":
    unittest.main()