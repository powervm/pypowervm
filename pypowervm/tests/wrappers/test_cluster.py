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

from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.cluster as clust

SSP_FILE = 'ssp.txt'


class TestSharedStoragePool(unittest.TestCase):

    _ssp_resp = None

    def setUp(self):
        super(TestSharedStoragePool, self).setUp()
        if TestSharedStoragePool._ssp_resp:
            self.ssp_resp = TestSharedStoragePool._ssp_resp
            return
        TestSharedStoragePool._ssp_resp = pvmhttp.load_pvm_resp(
            SSP_FILE).get_response()
        self.ssp_resp = TestSharedStoragePool._ssp_resp

    def test_name(self):
        ssp_wrapper = clust.SharedStoragePool(self.ssp_resp.entry)
        self.assertEqual(ssp_wrapper.name, 'neossp1')

    def test_udid(self):
        ssp_wrapper = clust.SharedStoragePool(self.ssp_resp.entry)
        self.assertEqual(ssp_wrapper.udid, '24cfc907d2abf511e4b2d540f2e95daf3'
                         '0000000000972FB370000000054D14EB8')

    def test_capacity(self):
        ssp_wrapper = clust.SharedStoragePool(self.ssp_resp.entry)
        self.assertAlmostEqual(ssp_wrapper.capacity, 49.88, 3)

    def test_free_space(self):
        ssp_wrapper = clust.SharedStoragePool(self.ssp_resp.entry)
        self.assertAlmostEqual(ssp_wrapper.free_space, 48.98, 3)

    def test_total_lu_size(self):
        ssp_wrapper = clust.SharedStoragePool(self.ssp_resp.entry)
        self.assertAlmostEqual(ssp_wrapper.total_lu_size, 1, 1)

    def test_physical_volumes(self):
        ssp_wrapper = clust.SharedStoragePool(self.ssp_resp.entry)
        pvs = ssp_wrapper.physical_volumes
        self.assertEqual(len(pvs), 1)
        pv = pvs[0]
        self.assertEqual(
            pv.udid,
            '01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDAwMw==')
        self.assertEqual(pv.name, 'hdisk3')
        # TODO(IBM): test setter

    def test_logical_units(self):
        ssp_wrapper = clust.SharedStoragePool(self.ssp_resp.entry)
        lus = ssp_wrapper.logical_units
        self.assertEqual(len(lus), 1)
        lu = lus[0]
        self.assertEqual(lu.udid, '27cfc907d2abf511e4b2d540f2e95daf301a02b090'
                         '4778d755df5a46fe25e500d8')
        self.assertEqual(lu.name, 'neolu1')
        self.assertTrue(lu.is_thin)
        self.assertEqual(lu.lu_type, 'VirtualIO_Disk')
        self.assertAlmostEqual(lu.capacity, 1, 1)
        # TODO(IBM): test setter

if __name__ == "__main__":
    unittest.main()