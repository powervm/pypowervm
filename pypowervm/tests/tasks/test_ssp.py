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

import unittest

import pypowervm.adapter as adp
import pypowervm.exceptions as exc
import pypowervm.tasks.ssp as ts
import pypowervm.wrappers.storage as stor


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
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10)
        self.assertEqual(lu.name, 'lu5')
        self.assertEqual(lu.udid, 'udid_lu5')
        self.assertTrue(lu.is_thin)
        self.assertEqual(ssp.etag, 'after')
        self.assertIn(lu, ssp.logical_units)

    def test_crt_lu_thin(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=True)
        self.assertTrue(lu.is_thin)

    def test_crt_lu_thick(self):
        ssp, lu = ts.crt_lu(self.adp, self.ssp, 'lu5', 10, thin=False)
        self.assertFalse(lu.is_thin)

    def test_crt_lu_name_conflict(self):
        self.assertRaises(exc.DuplicateLUNameError, ts.crt_lu, self.adp,
                          self.ssp, 'lu1', 5)

    def test_rm_lu_by_lu(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = ts.rm_lu(self.adp, self.ssp, lu=lu)
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_by_name(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = ts.rm_lu(self.adp, self.ssp, name='lu2')
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_by_udid(self):
        lu = self.ssp.logical_units[2]
        ssp, lurm = ts.rm_lu(self.adp, self.ssp, udid='udid_lu2')
        self.assertEqual(lu, lurm)
        self.assertEqual(ssp.etag, 'after')
        self.assertEqual(len(ssp.logical_units), 4)

    def test_rm_lu_not_found(self):
        # By LU
        lu = stor.LU.bld('lu5', 6)
        self.assertRaises(exc.LUNotFoundError, ts.rm_lu, self.adp, self.ssp,
                          lu=lu)
        # By name
        self.assertRaises(exc.LUNotFoundError, ts.rm_lu, self.adp, self.ssp,
                          name='lu5')
        # By UDID
        self.assertRaises(exc.LUNotFoundError, ts.rm_lu, self.adp, self.ssp,
                          udid='lu5_udid')
