# Copyright 2014, 2015 IBM Corp.
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

import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.shared_proc_pool as spp

SHRPROC_HTTPRESP_FILE = "shrprocpool.txt"


class TestShrPrcPoolTestCase(twrap.TestWrapper):

    file = 'shrprocpool.txt'
    wrapper_class_to_test = spp.SharedProcPool

    def test_validate_attribues(self):
        # First element from the feed is the default pool
        self.assertEqual('DefaultPool', self.dwrap.name)
        self.assertEqual(0, self.dwrap.id)
        self.assertEqual(0, self.dwrap.curr_rsrv_proc_units)
        self.assertTrue(self.dwrap.is_default)
        self.assertEqual(0, self.dwrap.max_proc_units)
        self.assertEqual(0, self.dwrap.pend_rsrv_proc_units)
        self.assertEqual(0, self.dwrap.avail_proc_units)

        # The second pool is non-default.
        n_spp = self.entries[1]
        self.assertEqual('SharedPool01', n_spp.name)
        self.assertEqual(1, n_spp.id)
        self.assertEqual(5.35, n_spp.curr_rsrv_proc_units)
        self.assertFalse(n_spp.is_default)
        self.assertEqual(10.25, n_spp.max_proc_units)
        self.assertEqual(6.15, n_spp.pend_rsrv_proc_units)
        self.assertEqual(5.05, n_spp.avail_proc_units)

    def test_setters(self):
        self.dwrap.name = 'new'
        self.assertEqual('new', self.dwrap.name)

        self.dwrap.max_proc_units = 5.5
        self.assertEqual(5.5, self.dwrap.max_proc_units)

        self.dwrap.pend_rsrv_proc_units = 4.3
        self.assertEqual(4.3, self.dwrap.pend_rsrv_proc_units)
