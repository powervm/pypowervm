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

import pypowervm.wrappers.cluster as clust
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as ms
import pypowervm.wrappers.network as net
import pypowervm.wrappers.shared_proc_pool as spp
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf
import pypowervm.wrappers.virtual_io_server as vios


class TestSearch(unittest.TestCase):

    expected_search_keys = {
        clust.Cluster: dict(name='ClusterName'),
        job.Job: None,
        lpar.LPAR: dict(name='PartitionName', id='PartitionID'),
        ms.System: None,
        net.NetBridge: None,
        net.VNet: None,
        net.CNA: None,
        net.VSwitch: None,
        spp.SharedProcPool: None,
        stor.SSP: dict(name='StoragePoolName'),
        stor.VG: None,
        vf.File: None,
        vios.VIOS: dict(name='PartitionName', id='PartitionID'),
    }

    def test_all_search_keys(self):
        for wcls in list(self.expected_search_keys):
            sk = self.expected_search_keys[wcls]
            if sk is None:
                self.assertFalse(hasattr(wcls, 'search_keys'))
            else:
                self.assertEqual(sk, wcls.search_keys)

if __name__ == '__main__':
    unittest.main()
