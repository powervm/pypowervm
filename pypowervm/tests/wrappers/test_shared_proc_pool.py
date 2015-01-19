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

import unittest

from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.shared_proc_pool as spp

SHRPROC_HTTPRESP_FILE = "shrprocpool.txt"
MC_HTTPRESP_FILE = "managementconsole.txt"
POOLID = '1'
EXPECTED_CURR_RSRV_PROC_UNITS = '.1'

ZERO_STR = '0'


class TestShrPrcPoolTestCase(unittest.TestCase):

    _proc_pool_wrapper = None
    _bad_wrapper = None

    def setUp(self):
        super(TestShrPrcPoolTestCase, self).setUp()
        if (TestShrPrcPoolTestCase._proc_pool_wrapper and
                TestShrPrcPoolTestCase._bad_wrapper):
            return

        shrproc_http = pvmhttp.load_pvm_resp(SHRPROC_HTTPRESP_FILE)
        self.assertNotEqual(shrproc_http, None,
                            "Could not load %s " %
                            SHRPROC_HTTPRESP_FILE)

        entries = shrproc_http.response.feed.findentries(
            c.POOL_ID, '1')
        self.assertNotEqual(entries, None, "Could not find %s in %s" %
                            (c.POOL_ID,
                             SHRPROC_HTTPRESP_FILE))

        self.pool_entry = entries[0]

        self.set_test_property_values()

        TestShrPrcPoolTestCase._proc_pool_wrapper = (
            spp.SharedProcPool(self.pool_entry))

        mc_http = pvmhttp.load_pvm_resp(MC_HTTPRESP_FILE)
        self.assertNotEqual(mc_http, None,
                            "Could not load %s" %
                            MC_HTTPRESP_FILE)

        # Create a bad wrapper to use when retrieving properties which don't
        # exist
        TestShrPrcPoolTestCase._bad_wrapper = spp.SharedProcPool(
            mc_http.response.feed.entries[0])

    def set_single_value(self, entry, property_name, value):
        prop = entry.element.find(property_name)
        pool_id = 'unset*shared*proc*pool*id'
        if entry == self.pool_entry:
            pool_id = POOLID

        self.assertNotEqual(
            prop, None,
            "Could not find property %s in shared processor pool %s" %
            (property_name, pool_id))

        prop.text = str(value)

    def set_test_property_values(self):
        """Set expected values in entry so test code can work consistently."""
        entry = self.pool_entry
        self.set_single_value(
            entry, c.CURR_RSRV_PROC_UNITS,
            EXPECTED_CURR_RSRV_PROC_UNITS)

    def verify_equal(self, method_name, returned_value, expected_value):
        if returned_value is not None and expected_value is not None:
            returned_type = type(returned_value)
            expected_type = type(expected_value)
            self.assertEqual(returned_type, expected_type,
                             "%s: type mismatch.  "
                             "Returned %s(%s). Expected %s(%s)" %
                             (method_name,
                              returned_value, returned_type,
                              expected_value, expected_type))

        self.assertEqual(returned_value, expected_value,
                         "%s returned %s instead of %s"
                         % (method_name, returned_value, expected_value))

    def call_simple_getter(self, method_name, expected_value,
                           expected_bad_value):

        # Use __getattribute__ to dynamically call the method
        wrapper = TestShrPrcPoolTestCase._proc_pool_wrapper

        value = wrapper.__getattribute__(method_name)
        if callable(value):
            value = value()
        self.verify_equal(method_name, value, expected_value)

        bad_value = TestShrPrcPoolTestCase._bad_wrapper.__getattribute__(
            method_name)
        if callable(bad_value):
            bad_value = bad_value()
        self.verify_equal(method_name, bad_value, expected_bad_value)

    def test_get_parm_value(self):
        expected_value = POOLID
        value = TestShrPrcPoolTestCase._proc_pool_wrapper.get_parm_value(
            c.POOL_ID)

        self.verify_equal("get_parm_value", value, expected_value)

        expected_value = None
        value = TestShrPrcPoolTestCase._proc_pool_wrapper.get_parm_value(
            'BogusName')

        self.verify_equal(
            "get_parm_value for BogusName ", value, expected_value)

    def test_get_pool_id(self):
        self.call_simple_getter("id", int(POOLID), int(ZERO_STR))

    def test_get_curr_rsrv_proc_units(self):
        self.call_simple_getter("curr_rsrv_proc_units",
                                EXPECTED_CURR_RSRV_PROC_UNITS, ZERO_STR)

if __name__ == "__main__":
    unittest.main()
