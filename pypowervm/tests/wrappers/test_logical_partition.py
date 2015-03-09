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
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
from pypowervm.tests.wrappers.util import xml_sections
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.logical_partition as lpar

LPAR_HTTPRESP_FILE = "lpar.txt"
MC_HTTPRESP_FILE = "managementconsole.txt"
DEDICATED_LPAR_NAME = 'z3-9-5-126-168-00000002'
SHARED_LPAR_NAME = 'z3-9-5-126-127-00000001'


EXPECTED_CURR_MAX_MEM = 9999
EXPECTED_CURR_MEM = 5555
EXPECTED_CURR_MIN_MEM = 1111
EXPECTED_CURR_MAX_PROCS = 99
EXPECTED_CURR_PROCS = 55
EXPECTED_CURR_MIN_PROCS = 11
EXPECTED_CURR_MAX_VCPU = 9
EXPECTED_CURR_VCPU = 5
EXPECTED_CURR_MIN_VCPU = 1
EXPECTED_CURR_MAX_PROC_UNITS = 0.5
EXPECTED_CURR_PROC_UNITS = 0.5
EXPECTED_CURR_MIN_PROC_UNITS = 0.5
EXPECTED_CURR_UNCAPPED_WEIGHT = 128
EXPECTED_AVAIL_PRIORITY = 127
EXPECTED_CURR_PROC_COMPAT_MODE = 'POWER6_Plus'
EXPECTED_PENDING_PROC_COMPAT_MODE = 'default'
EXPECTED_OPERATING_SYSTEM_VER = 'Linux/Red Hat 2.6.32-358.el6.ppc64 6.4'

EXPECTED_CURRENT_SHARE_MODE = "uncapped"
EXPECTED_LPAR_STATE = "not activated"
ZERO_STR = '0'
ZERO_INT = 0


class TestLogicalPartition(unittest.TestCase):

    _skip_setup = False
    _shared_wrapper = None
    _dedicated_wrapper = None
    _bad_wrapper = None
    _shared_entry = None
    _dedicated_entry = None

    def setUp(self):
        super(TestLogicalPartition, self).setUp()
        self.TC = TestLogicalPartition
        if (TestLogicalPartition._shared_wrapper
                and TestLogicalPartition._bad_wrapper):
            return

        ms_http = pvmhttp.load_pvm_resp(LPAR_HTTPRESP_FILE)
        self.assertNotEqual(ms_http, None,
                            "Could not load %s " %
                            LPAR_HTTPRESP_FILE)

        entries = ms_http.response.feed.findentries(
            lpar._LPAR_NAME, SHARED_LPAR_NAME)

        self.assertNotEqual(entries, None,
                            "Could not find %s in %s" %
                            (SHARED_LPAR_NAME, LPAR_HTTPRESP_FILE))

        self.TC._shared_entry = entries[0]

        entries = ms_http.response.feed.findentries(
            lpar._LPAR_NAME, DEDICATED_LPAR_NAME)

        self.assertNotEqual(entries, None,
                            "Could not find %s in %s" %
                            (DEDICATED_LPAR_NAME, LPAR_HTTPRESP_FILE))

        self.TC._dedicated_entry = entries[0]

        self.set_shared_test_property_values()
        self.set_dedicated_test_property_values()

        TestLogicalPartition._shared_wrapper = lpar.LPAR.wrap(
            self.TC._shared_entry)

        TestLogicalPartition._dedicated_wrapper = lpar.LPAR.wrap(
            self.TC._dedicated_entry)

        mc_http = pvmhttp.load_pvm_resp(MC_HTTPRESP_FILE)
        self.assertNotEqual(mc_http, None,
                            "Could not load %s" %
                            MC_HTTPRESP_FILE)

        # Create a bad wrapper to use when retrieving properties which don't
        # exist
        TestLogicalPartition._bad_wrapper = lpar.LPAR.wrap(
            mc_http.response.feed.entries[0])

        TestLogicalPartition._skip_setup = True

    def set_single_value(self, entry, property_name, value):
        prop = entry.element.find(property_name)
        lpar_name = 'unset*lpar*name'
        if entry == self.TC._shared_entry:
            lpar_name = SHARED_LPAR_NAME
        elif entry == self.TC._dedicated_entry:
            lpar_name = DEDICATED_LPAR_NAME

        self.assertNotEqual(prop, None,
                            "Could not find property %s in lpar %s" %
                            (property_name, lpar_name))

        prop.text = str(value)

    def set_shared_test_property_values(self):
        """Set expected values in entry so test code can work consistently."""
        entry = self.TC._shared_entry
        self.set_single_value(
            entry, c.CURR_MEM, EXPECTED_CURR_MEM)

        self.set_single_value(
            entry, c.CURR_MAX_MEM, EXPECTED_CURR_MAX_MEM)

        self.set_single_value(
            entry, c.CURR_MIN_MEM, EXPECTED_CURR_MIN_MEM)

        self.set_single_value(
            entry, c.CURR_VCPU, EXPECTED_CURR_VCPU)

        self.set_single_value(
            entry, c.CURR_MIN_VCPU, EXPECTED_CURR_MIN_VCPU)

        self.set_single_value(
            entry, c.CURR_MAX_VCPU, EXPECTED_CURR_MAX_VCPU)

    def set_dedicated_test_property_values(self):
        """Set expected values in entry so test code can work consistently."""

        entry = self.TC._dedicated_entry

        self.set_single_value(
            entry, c.CURR_MEM, EXPECTED_CURR_MEM)

        self.set_single_value(
            entry, c.CURR_MAX_MEM, EXPECTED_CURR_MAX_MEM)

        self.set_single_value(
            entry, c.CURR_MIN_MEM, EXPECTED_CURR_MIN_MEM)

        self.set_single_value(
            entry, c.CURR_PROCS, EXPECTED_CURR_PROCS)

        self.set_single_value(
            entry, c.CURR_MIN_PROCS, EXPECTED_CURR_MIN_PROCS)

        self.set_single_value(
            entry, c.CURR_MAX_PROCS, EXPECTED_CURR_MAX_PROCS)

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

    def call_simple_getter(self,
                           method_name,
                           expected_value,
                           expected_bad_value,
                           use_dedicated=False):

        # Use __getattribute__ to dynamically call the method
        if use_dedicated:
            wrapper = TestLogicalPartition._dedicated_wrapper
        else:
            wrapper = TestLogicalPartition._shared_wrapper

        value = wrapper.__getattribute__(method_name)
        if callable(value):
            value = value()
        self.verify_equal(method_name, value, expected_value)

        bad_value = TestLogicalPartition._bad_wrapper.__getattribute__(
            method_name)
        if callable(bad_value):
            bad_value = bad_value()
        self.verify_equal(method_name, bad_value, expected_bad_value)

    def test_get_val_str(self):
        expected_value = SHARED_LPAR_NAME
        value = TestLogicalPartition._shared_wrapper._get_val_str(
            lpar._LPAR_NAME)

        self.verify_equal("_get_val_str", value, expected_value)

        expected_value = None
        value = TestLogicalPartition._shared_wrapper._get_val_str(
            'BogusName')

        self.verify_equal(
            "_get_val_str for BogusName ", value, expected_value)

    def test_get_cna_links(self):
        """Test getting the list of ClientNetworkAdapters."""
        lpar_resp = pvmhttp.load_pvm_resp(LPAR_HTTPRESP_FILE).get_response()
        lpar_wrapper = lpar.LPAR.wrap(lpar_resp.feed.entries[2])

        self.assertEqual(1, len(lpar_wrapper.cna_uris))

    def test_get_state(self):
        self.call_simple_getter("state", EXPECTED_LPAR_STATE, None)

    def test_get_name(self):
        self.call_simple_getter("name", SHARED_LPAR_NAME, None)

    def test_get_id(self):
        self.call_simple_getter("id", 9, ZERO_INT)

    def test_get_current_mem(self):
        self.call_simple_getter(
            "current_mem", str(EXPECTED_CURR_MEM), ZERO_STR)

    def test_get_current_max_mem(self):
        self.call_simple_getter(
            "current_max_mem", str(EXPECTED_CURR_MAX_MEM), ZERO_STR)

    def test_get_current_min_mem(self):
        self.call_simple_getter(
            "current_min_mem", str(EXPECTED_CURR_MIN_MEM), ZERO_STR)

    def test_get_current_sharing_mode(self):
        self.call_simple_getter(
            "sharing_mode", EXPECTED_CURRENT_SHARE_MODE, None)

    def test_get_current_proc_mode(self):
        self.call_simple_getter(
            "current_proc_mode_is_dedicated", True, False,
            use_dedicated=True)

    def test_get_proc_mode(self):
        self.call_simple_getter(
            "proc_mode_is_dedicated", True, False, use_dedicated=True)

    def test_get_current_procs(self):
        self.call_simple_getter(
            "current_procs", str(EXPECTED_CURR_PROCS), ZERO_STR,
            use_dedicated=True)

    def test_get_current_max_procs(self):
        self.call_simple_getter(
            "current_max_procs", str(EXPECTED_CURR_MAX_PROCS), ZERO_STR,
            use_dedicated=True)

    def test_get_current_min_procs(self):
        self.call_simple_getter(
            "current_min_procs", str(EXPECTED_CURR_MIN_PROCS), ZERO_STR,
            use_dedicated=True)

    def test_get_current_vcpus(self):
        self.call_simple_getter(
            "current_vcpus", str(EXPECTED_CURR_VCPU), ZERO_STR)

    def test_get_current_max_vcpus(self):
        self.call_simple_getter(
            "current_max_vcpus", str(EXPECTED_CURR_MAX_VCPU), ZERO_STR)

    def test_get_current_min_vcpus(self):
        self.call_simple_getter(
            "current_min_vcpus", str(EXPECTED_CURR_MIN_VCPU), ZERO_STR)

    def test_get_current_proc_units(self):
        self.call_simple_getter(
            "current_proc_units", str(EXPECTED_CURR_PROC_UNITS), ZERO_STR)

    def test_get_current_max_proc_units(self):
        self.call_simple_getter(
            "current_max_proc_units",
            str(EXPECTED_CURR_MAX_PROC_UNITS), ZERO_STR)

    def test_get_current_min_proc_units(self):
        self.call_simple_getter(
            "current_min_proc_units",
            str(EXPECTED_CURR_MIN_PROC_UNITS), ZERO_STR)

    def test_get_curr_uncapped_weight(self):
        self.call_simple_getter(
            "current_uncapped_weight",
            str(EXPECTED_CURR_UNCAPPED_WEIGHT), ZERO_STR)

    def test_get_avail_priority(self):
        self.call_simple_getter(
            "avail_priority", str(EXPECTED_AVAIL_PRIORITY), ZERO_STR)

    def test_get_proc_compat_modes(self):
        self.call_simple_getter(
            "proc_compat_mode", EXPECTED_CURR_PROC_COMPAT_MODE, None)
        self.call_simple_getter(
            "pending_proc_compat_mode", EXPECTED_PENDING_PROC_COMPAT_MODE,
            None)

    def test_get_shared_proc_pool_id(self):
        self.call_simple_getter(
            "shared_proc_pool_id", 0, 0)

    def test_get_type(self):
        self.call_simple_getter(
            "env", 'AIX/Linux', None)

    def test_get_operating_system(self):
        self.call_simple_getter(
            "operating_system",
            EXPECTED_OPERATING_SYSTEM_VER, 'Unknown')

    def test_io_config(self):
        self.assertIsNotNone(TestLogicalPartition._dedicated_wrapper.io_config)


class TestPartitionIOConfiguration(twrap.TestWrapper):

    file = LPAR_HTTPRESP_FILE
    wrapper_class_to_test = lpar.LPAR

    def setUp(self):
        super(TestPartitionIOConfiguration, self).setUp()
        self.io_config = self.entries[0].io_config

    def test_max_slots(self):
        self.assertEqual(64, self.io_config.max_virtual_slots)

    def test_io_slots(self):
        # IO Slots are typically associated with the VIOS.  Further testing
        # driven there.
        self.assertIsNotNone(self.io_config.io_slots)
        self.assertEqual(0, len(self.io_config.io_slots))


class TestCreateLogicalPartition(unittest.TestCase):
    """Test cases to test the lpar operations."""
    def setUp(self):
        super(TestCreateLogicalPartition, self).setUp()
        self.sections = xml_sections.load_xml_sections('lpar_sections.txt')

    def tearDown(self):
        super(TestCreateLogicalPartition, self).tearDown()

    def section_tostring(self, section):
        sec_text = ''.encode('ascii')
        for entry in section:
            sec_text += entry.toxmlstring() + '\n'.encode('ascii')
        return sec_text.decode('ascii')

    def test_ded_procs(self):
        """Test crt_ded_procs_struct() method."""
        # Test minimum parms
        dprocs = lpar.crt_ded_procs('2')
        self.assertEqual(self.sections['ded_procs'],
                         self.section_tostring(dprocs))
        # All parms
        dprocs = lpar.crt_ded_procs('2',
                                    sharing_mode=lpar._DED_SHARING_MODES[0],
                                    min_proc='2', max_proc='2')
        self.assertEqual(self.sections['ded_procs'],
                         self.section_tostring(dprocs))

    def test_shared_procs(self):
        """Test crt_shared_procs_struct() method."""
        # Test minimum parms
        sprocs = lpar.crt_shared_procs('1.2', '2')
        self.assertEqual(self.sections['shared_procs'],
                         self.section_tostring(sprocs))
        # All parms
        sprocs = lpar.crt_shared_procs('1.2', '2',
                                       sharing_mode=lpar._SHARING_MODES[1],
                                       uncapped_weight='128',
                                       min_proc_unit='1.2',
                                       max_proc_unit='1.2',
                                       min_proc='2',
                                       max_proc='2')
        self.assertEqual(self.sections['shared_procs'],
                         self.section_tostring(sprocs))

    def test_lpar_struct(self):
        """Test crt_lpar_struct() method."""
        dprocs = lpar.crt_ded_procs('2')
        lpar_elem = lpar.crt_lpar('the_name', 'OS400', dprocs,
                                  '1024', min_mem='1024',
                                  max_mem='1024',
                                  max_io_slots='64')
        self.assertEqual(self.sections['lpar_1'],
                         self.section_tostring(lpar_elem))


class TestPhysFCPort(unittest.TestCase):

    def test_bld(self):
        port = lpar.PhysFCPort.bld('fcs0')
        self.assertIsNotNone(port)
        self.assertEqual('fcs0', port.name)


if __name__ == "__main__":
    unittest.main()
