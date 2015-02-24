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
import pypowervm.const as pc
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.constants as wc
import pypowervm.wrappers.managed_system as ms
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
        # PV is tested elsewhere.  Minimal verification here.
        self.assertEqual(repos.name, 'hdisk2')
        # Test setter
        newrepos = stor.PV(
            adp.Element(
                "PhysicalVolume",
                attrib={'schemaVersion': 'V1_2_0'},
                children=[
                    adp.Element('Metadata', children=[adp.Element('Atom')]),
                    adp.Element('VolumeName', text='hdisk99')]))
        self.dwrap.repos_pv = newrepos
        self.assertEqual(self.dwrap.repos_pv.name, 'hdisk99')
        # Now try the same thing, but using no-arg constructor to build PV
        newrepos = stor.PV()
        newrepos.name = 'hdisk123'
        self.dwrap.repos_pv = newrepos
        self.assertAlmostEqual(self.dwrap.repos_pv.name, 'hdisk123')

    def test_nodes(self):
        """Tests the Node and MTMS wrappers as well."""
        nodes = self.dwrap.nodes
        self.assertEqual(len(nodes), 2)
        node = nodes[0]
        self.assertEqual(node.hostname, 'foo.example.com')
        self.assertEqual(node.lpar_id, 2)
        self.assertEqual(
            node.vios_uri, 'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
            '98498bed-c78a-3a4f-b90a-4b715418fcb6/VirtualIOServer/58C9EB1D-'
            '7213-4956-A011-77D43CC4ACCC')
        self.assertEqual(
            node.vios_uuid.upper(), '58C9EB1D-7213-4956-A011-77D43CC4ACCC')
        # Make sure the different Node entries are there
        self.assertEqual(nodes[1].hostname, 'bar.example.com')
        # Test MTMS
        mtms = node.mtms
        self.assertEqual(mtms.machine_type, '8247')
        self.assertEqual(mtms.model, '22L')
        self.assertEqual(mtms.serial, '2125D1A')
        # Test nodes setters
        node2 = nodes[1]
        nodes.remove(node)
        self.assertEqual(len(self.dwrap.nodes), 1)
        node.hostname = 'blah.example.com'
        node.lpar_id = 9
        node.vios_uri = 'https://foo'
        self.dwrap.nodes = [node2, node]
        self.assertEqual(len(self.dwrap.nodes), 2)
        node = self.dwrap.nodes[1]
        self.assertEqual(node.hostname, 'blah.example.com')
        self.assertEqual(node.lpar_id, 9)
        self.assertEqual(node.vios_uri, 'https://foo')
        # MTMS needs a little more depth
        node.mtms = '1234-567*ABCDEF0'
        mtms = node.mtms
        self.assertEqual(mtms.machine_type, '1234')
        self.assertEqual(mtms.model, '567')
        self.assertEqual(mtms.serial, 'ABCDEF0')
        # Now try with a MTMS ElementWrapper
        node.mtms = ms.MTMS.new('4321-765*0FEDCBA')
        mtms = node.mtms
        self.assertEqual(mtms.machine_type, '4321')
        self.assertEqual(mtms.model, '765')
        self.assertEqual(mtms.serial, '0FEDCBA')

    def test_fresh_cluster(self):
        n1 = clust.Node()
        n1.hostname = 'a.example.com'
        n2 = clust.Node()
        n2.hostname = 'b.example.com'
        repos = stor.PV.new(name='hdisk123')
        cl = clust.Cluster.new(name='foo', repos_pv=repos, node_list=[n1, n2])
        self.assertEqual(cl.name, 'foo')
        self.assertEqual(cl.repos_pv.name, 'hdisk123')
        self.assertEqual(cl.pvm_type, wc.CLUSTER)
        self.assertEqual(cl.schema_ns, pc.UOM_NS)
        nodes = cl.nodes
        self.assertEqual(len(nodes), 2)
        node = nodes[0]
        self.assertEqual(node.hostname, 'a.example.com')
        self.assertEqual(node.pvm_type, wc.CLUST_NODE)
        self.assertEqual(node.schema_ns, pc.UOM_NS)

if __name__ == "__main__":
    unittest.main()