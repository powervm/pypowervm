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

import pypowervm.adapter as adp
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.storage as stor


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

    def test_repos_pv(self):
        repos = self.dwrap.repos_pv
        # PhysicalVolume is tested elsewhere.  Minimal verification here.
        self.assertEqual(repos.name, 'hdisk2')
        # Test setter
        newrepos = stor.PhysicalVolume(
            adp.Element(
                "PhysicalVolume",
                attrib={'schemaVersion': 'V1_2_0'},
                children=[
                    adp.Element('Metadata', children=[adp.Element('Atom')]),
                    adp.Element('VolumeName', text='hdisk99')]))
        self.dwrap.repos_pv = newrepos
        self.assertEqual(self.dwrap.repos_pv.name, 'hdisk99')

    def test_nodes(self):
        """Tests the Node and MTMS wrappers as well."""
        nodes = self.dwrap.nodes
        self.assertEqual(len(nodes), 2)
        node = nodes[0]
        self.assertEqual(node.hostname, 'foo.ibm.com')
        self.assertEqual(node.lpar_id, 2)
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
        # Test nodes setters
        node2 = nodes[1]
        nodes.remove(node)
        self.assertEqual(len(self.dwrap.nodes), 1)
        node.hostname = 'blah.ibm.com'
        self.dwrap.nodes = [node2, node]
        self.assertEqual(len(self.dwrap.nodes), 2)
        self.assertEqual(self.dwrap.nodes[1].hostname, 'blah.ibm.com')

if __name__ == "__main__":
    unittest.main()