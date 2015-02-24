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

import logging
import unittest

from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.managed_system as mswrap

MS_HTTPRESP_FILE = "managedsystem.txt"
MC_HTTPRESP_FILE = "managementconsole.txt"
MS_NAME = 'HV4'

logging.basicConfig()


class TestMSEntryWrapper(unittest.TestCase):

    def setUp(self):
        super(TestMSEntryWrapper, self).setUp()

        self.ms_http = pvmhttp.load_pvm_resp(MS_HTTPRESP_FILE)
        self.assertNotEqual(self.ms_http, None,
                            "Could not load %s " %
                            MS_HTTPRESP_FILE)

        entries = self.ms_http.response.feed.findentries(
            c.SYSTEM_NAME, MS_NAME)

        self.assertNotEqual(entries, None,
                            "Could not find %s in %s" %
                            (MS_NAME, MS_HTTPRESP_FILE))

        self.myentry = entries[0]
        self.wrapper = mswrap.ManagedSystem.load(entry=self.myentry)

        # Set a hardcoded value for MemoryUsedByHypervisor
        fw_mem = self.myentry.element.find(
            './AssociatedSystemMemoryConfiguration/MemoryUsedByHypervisor')
        fw_mem.text = '1536'

        mc_http = pvmhttp.load_pvm_resp(MC_HTTPRESP_FILE)
        self.assertNotEqual(mc_http, None,
                            "Could not load %s" %
                            MC_HTTPRESP_FILE)

        """ Create a bad wrapper to use when
            retrieving properties which don't exist """
        self.bad_wrapper = mswrap.ManagedSystem.load(
            entry=mc_http.response.feed.entries[0])

    def verify_equal(self, method_name, returned_value, expected_value):
        self.assertEqual(returned_value, expected_value,
                         "%s returned %s instead of %s"
                         % (method_name, returned_value, expected_value))

    def call_simple_getter(self,
                           method_name,
                           expected_value,
                           expected_bad_value):

        # Use __getattribute__ to dynamically call the method
        value = self.wrapper.__getattribute__(method_name)
        if callable(value):
            value = value()
        self.verify_equal(method_name, value, expected_value)

        bad_value = self.bad_wrapper.__getattribute__(method_name)
        if callable(bad_value):
            bad_value = bad_value()
        self.verify_equal(method_name, bad_value, expected_bad_value)

    def test_get_val_str(self):
        expected_value = MS_NAME
        value = self.wrapper._get_val_str(c.SYSTEM_NAME)

        self.verify_equal("_get_val_str", value, expected_value)

        expected_value = None
        value = self.wrapper._get_val_str('BogusName')

        self.verify_equal(
            "_get_val_str for BogusName ", value, expected_value)

    def test_get_model(self):
        self.assertEqual(self.wrapper.mtms.model, "E4A")

    def test_get_type(self):
        self.assertEqual(self.wrapper.mtms.machine_type, "8203")

    def test_get_serial(self):
        self.assertEqual(self.wrapper.mtms.serial, "ACE0001")

    def test_get_mtms_str(self):
        self.assertEqual(self.wrapper.mtms.mtms_str, '8203-E4A*ACE0001')

    def test_get_proc_units(self):
        self.call_simple_getter("proc_units", "500", 0)

    def test_get_proc_units_configurable(self):
        self.call_simple_getter("proc_units_configurable", "500", 0)

    def test_get_proc_units_avail(self):
        self.call_simple_getter("proc_units_avail", "500", 0)

    def test_get_memory_total(self):
        self.call_simple_getter("memory_total", 5767168, 0)

    def test_get_memory_free(self):
        self.call_simple_getter("memory_free", 5242752, 0)

    def test_get_host_ip_address(self):
        self.call_simple_getter("host_ip_address", '127.0.0.1', None)

    def test_get_firmware_memory(self):
        self.call_simple_getter("firmware_memory", 1536, 0)

    def test_get_system_name(self):
        self.wrapper.set_parm_value(c.SYSTEM_NAME, 'XYZ')
        name = self.wrapper.system_name
        self.verify_equal("system_name", name, 'XYZ')
        self.wrapper.set_parm_value(c.SYSTEM_NAME, 'ABC')
        name = self.wrapper.system_name
        self.verify_equal("system_name", name, 'ABC')

    def test_max_procs_per_aix_linux_lpar(self):
        self.call_simple_getter("max_procs_per_aix_linux_lpar", 32, 0)
        # Test setter
        self.wrapper.max_procs_per_aix_linux_lpar = 64
        self.call_simple_getter("max_procs_per_aix_linux_lpar", 64, 0)
        # Test fallback condition.  Should retrieve max_sys_procs_limit
        self.wrapper.max_procs_per_aix_linux_lpar = 0
        self.call_simple_getter("max_procs_per_aix_linux_lpar",
                                self.wrapper.max_sys_procs_limit, 0)

    def test_max_vcpus_per_aix_linux_lpar(self):
        self.call_simple_getter("max_vcpus_per_aix_linux_lpar", 30, 0)
        # Test setter
        self.wrapper.max_vcpus_per_aix_linux_lpar = 60
        self.call_simple_getter("max_vcpus_per_aix_linux_lpar", 60, 0)
        # Test fallback condition.  Should retrieve max_sys_vcpus_limit
        self.wrapper.max_vcpus_per_aix_linux_lpar = 0
        self.call_simple_getter("max_vcpus_per_aix_linux_lpar",
                                self.wrapper.max_sys_vcpus_limit, 0)

    def test_vios_links(self):
        self.call_simple_getter(
            "vios_links",
            ('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/caae9209-25e5-'
             '35cd-a71a-ed55c03f294d/VirtualIOServer/32F3530F-ECA0-4EAA-A37E-'
             '4B792C21AF70',), ())

    def test_find_entry_by_mtm_serial(self):
        value = mswrap.find_entry_by_mtms(self.ms_http.get_response(),
                                          "8203-E4A*ACE0001")
        self.assertIsNotNone(value)

        value = mswrap.find_entry_by_mtms(self.ms_http.get_response(),
                                          "8203-E4A*ACE0011")
        self.assertIsNone(value)


class TestMTMS(unittest.TestCase):
    def test_mtms(self):
        mtms = mswrap.MTMS(mtms_str='1234-567*ABCDEF0')
        self.assertEqual(mtms.machine_type, '1234')
        self.assertEqual(mtms.model, '567')
        self.assertEqual(mtms.serial, 'ABCDEF0')
        self.assertEqual(mtms.mtms_str, '1234-567*ABCDEF0')
        # Setters
        mtms.machine_type = '4321'
        self.assertEqual(mtms.machine_type, '4321')
        mtms.model = '765'
        self.assertEqual(mtms.model, '765')
        mtms.serial = '0FEDCBA'
        self.assertEqual(mtms.serial, '0FEDCBA')
        self.assertEqual(mtms.mtms_str, '4321-765*0FEDCBA')

if __name__ == "__main__":
    unittest.main()
