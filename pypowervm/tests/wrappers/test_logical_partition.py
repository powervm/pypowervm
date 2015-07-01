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

import testtools

import pypowervm.tests.test_fixtures as fx
from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.logical_partition as lpar

LPAR_HTTPRESP_FILE = "lpar.txt"
MC_HTTPRESP_FILE = "managementconsole.txt"
DEDICATED_LPAR_NAME = 'z3-9-5-126-168-00000002'
SHARED_LPAR_NAME = 'z3-9-5-126-127-00000001'

EXPECTED_OPERATING_SYSTEM_VER = 'Linux/Red Hat 2.6.32-358.el6.ppc64 6.4'
EXPECTED_ASSOC_SYSTEM_UUID = 'a168a3ec-bb3e-3ead-86c1-7d98b9d50239'


class TestLogicalPartition(testtools.TestCase):

    _skip_setup = False
    _shared_wrapper = None
    _dedicated_wrapper = None
    _bad_wrapper = None
    _shared_entry = None
    _dedicated_entry = None

    def setUp(self):
        super(TestLogicalPartition, self).setUp()

        self.adptfx = self.useFixture(fx.AdapterFx(traits=fx.LocalPVMTraits))
        self.adpt = self.adptfx.adpt

        self.TC = TestLogicalPartition

        lpar_http = pvmhttp.load_pvm_resp(LPAR_HTTPRESP_FILE,
                                          adapter=self.adpt)
        self.assertIsNotNone(lpar_http,
                             "Could not load %s " %
                             LPAR_HTTPRESP_FILE)

        entries = lpar_http.response.feed.findentries(
            bp._BP_NAME, SHARED_LPAR_NAME)

        self.assertIsNotNone(entries,
                             "Could not find %s in %s" %
                             (SHARED_LPAR_NAME, LPAR_HTTPRESP_FILE))

        self.TC._shared_entry = entries[0]

        entries = lpar_http.response.feed.findentries(
            bp._BP_NAME, DEDICATED_LPAR_NAME)

        self.assertIsNotNone(entries,
                             "Could not find %s in %s" %
                             (DEDICATED_LPAR_NAME, LPAR_HTTPRESP_FILE))

        self.TC._dedicated_entry = entries[0]

        TestLogicalPartition._shared_wrapper = lpar.LPAR.wrap(
            self.TC._shared_entry)

        TestLogicalPartition._dedicated_wrapper = lpar.LPAR.wrap(
            self.TC._dedicated_entry)

        mc_http = pvmhttp.load_pvm_resp(MC_HTTPRESP_FILE, adapter=self.adpt)
        self.assertIsNotNone(mc_http,
                             "Could not load %s" %
                             MC_HTTPRESP_FILE)

        # Create a bad wrapper to use when retrieving properties which don't
        # exist
        TestLogicalPartition._bad_wrapper = lpar.LPAR.wrap(
            mc_http.response.feed.entries[0])

        TestLogicalPartition._skip_setup = True

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

    @staticmethod
    def _get_nested_prop(wrapper, prop_path):
        value = None
        for partial in prop_path.split('.'):
            value = wrapper.__getattribute__(partial)
            if callable(value):
                value = value()
            wrapper = value
        return value

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

        value = self._get_nested_prop(wrapper, method_name)
        self.verify_equal(method_name, value, expected_value)

        bad_value = self._get_nested_prop(TestLogicalPartition._bad_wrapper,
                                          method_name)
        self.verify_equal(method_name, bad_value, expected_bad_value)

    def test_get_val_str(self):
        expected_value = SHARED_LPAR_NAME
        value = TestLogicalPartition._shared_wrapper._get_val_str(
            bp._BP_NAME)

        self.verify_equal("_get_val_str", value, expected_value)

        expected_value = None
        value = TestLogicalPartition._shared_wrapper._get_val_str(
            'BogusName')

        self.verify_equal(
            "_get_val_str for BogusName ", value, expected_value)

    def test_get_state(self):
        self.call_simple_getter("state", bp.LPARState.NOT_ACTIVATED, None)
        self._shared_wrapper.set_parm_value(bp._BP_STATE, bp.LPARState.RUNNING)
        self.call_simple_getter("state", bp.LPARState.RUNNING, None)

    def test_get_name(self):
        self.call_simple_getter("name", SHARED_LPAR_NAME, None)

    def test_get_id(self):
        self.call_simple_getter("id", 9, None)

    def test_uuid(self):
        wrapper = self._dedicated_wrapper
        self.assertEqual('42DF39A2-3A4A-4748-998F-25B15352E8A7', wrapper.uuid)
        # Test set and retrieve
        wrapper.set_uuid('99999999-3A4A-4748-998F-25B153529999')
        self.assertEqual('99999999-3A4A-4748-998F-25B153529999', wrapper.uuid)

        wrapper.uuid = '89999999-3A4A-4748-998F-25B153529998'
        self.assertEqual('89999999-3A4A-4748-998F-25B153529998', wrapper.uuid)

    def test_rmc_state(self):
        self.call_simple_getter("rmc_state", bp.RMCState.INACTIVE, None)
        self._shared_wrapper.set_parm_value(bp._BP_RMC_STATE,
                                            bp.RMCState.ACTIVE)
        self.call_simple_getter("rmc_state", bp.RMCState.ACTIVE, None)

    def test_avail_priority(self):
        self.call_simple_getter("avail_priority", 127, 0)
        self._shared_wrapper.avail_priority = 63
        self.call_simple_getter("avail_priority", 63, 0)

    def test_profile_sync(self):
        self.call_simple_getter("profile_sync", True, False)
        self.assertEqual(
            self._shared_wrapper._get_val_str(bp._BP_PROFILE_SYNC), "On")
        self._shared_wrapper.profile_sync = False
        self.call_simple_getter("profile_sync", False, False)
        self.assertEqual(
            self._shared_wrapper._get_val_str(bp._BP_PROFILE_SYNC), "Off")
        self._shared_wrapper.profile_sync = "Off"
        self.call_simple_getter("profile_sync", False, False)

    def test_check_dlpar_connectivity(self):
        self.call_simple_getter("check_dlpar_connectivity",
                                (False, bp.RMCState.INACTIVE), (False, None))
        self._shared_wrapper.capabilities.set_parm_value(
            bp._CAP_DLPAR_MEM_CAPABLE, 'true')
        self.call_simple_getter("check_dlpar_connectivity",
                                (True, bp.RMCState.INACTIVE), (False, None))

    def test_get_operating_system(self):
        self.call_simple_getter(
            "operating_system", EXPECTED_OPERATING_SYSTEM_VER, "Unknown")

    def test_srr(self):
        self.call_simple_getter("srr_enabled", True, False)
        self._shared_wrapper.srr_enabled = False
        self.call_simple_getter("srr_enabled", False, False)

    def test_get_proc_compat_modes(self):
        self.call_simple_getter("proc_compat_mode", "POWER6_Plus", None)
        self.call_simple_getter("pending_proc_compat_mode", "default", None)

    def test_get_type(self):
        self.call_simple_getter("env", "AIX/Linux", None)

    def test_associated_managed_system_uuid(self):
        self.call_simple_getter("assoc_sys_uuid", EXPECTED_ASSOC_SYSTEM_UUID,
                                None)

    def test_is_mgmt_partition(self):
        self.call_simple_getter("is_mgmt_partition", True, False)

    def test_subwrapper_getters(self):
        wrap = self._shared_wrapper
        self.assertIsInstance(wrap.capabilities, bp.PartitionCapabilities)
        self.assertIsInstance(wrap.io_config, bp.PartitionIOConfiguration)
        self.assertIsInstance(wrap.mem_config, bp.PartitionMemoryConfiguration)
        proc = wrap.proc_config
        self.assertIsInstance(proc, bp.PartitionProcessorConfiguration)
        self.assertIsInstance(proc.shared_proc_cfg,
                              bp.SharedProcessorConfiguration)
        self.assertIsInstance(proc.dedicated_proc_cfg,
                              bp.DedicatedProcessorConfiguration)

    # PartitionCapabilities

    def test_capabilities(self):
        self.call_simple_getter("capabilities.io_dlpar", True, False)
        self.call_simple_getter("capabilities.mem_dlpar", False, False)
        self.call_simple_getter("capabilities.proc_dlpar", True, False)

    # PartitionProcessorConfiguration

    def test_get_proc_mode(self):
        self.call_simple_getter(
            "proc_config.has_dedicated", False, False)
        self.call_simple_getter(
            "proc_config.has_dedicated", True, False, use_dedicated=True)
        self._dedicated_wrapper.proc_config._has_dedicated(False)
        self.call_simple_getter(
            "proc_config.has_dedicated", False, False, use_dedicated=True)

    def test_get_current_sharing_mode(self):
        self.call_simple_getter("proc_config.sharing_mode", "uncapped", None)
        self._shared_wrapper.proc_config.sharing_mode = "keep idle procs"
        self.call_simple_getter("proc_config.sharing_mode", "keep idle procs",
                                None)

    # SharedProcessorConfiguration

    def test_desired_units(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.desired_units",
                                1.5, None)
        self._shared_wrapper.proc_config.shared_proc_cfg.desired_units = 1.75
        self.call_simple_getter("proc_config.shared_proc_cfg.desired_units",
                                1.75, None)

    def test_max_units(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.max_units",
                                2.5, None)
        self._shared_wrapper.proc_config.shared_proc_cfg.max_units = 1.75
        self.call_simple_getter("proc_config.shared_proc_cfg.max_units",
                                1.75, None)

    def test_min_units(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.min_units",
                                0.5, None)
        self._shared_wrapper.proc_config.shared_proc_cfg.min_units = 1.75
        self.call_simple_getter("proc_config.shared_proc_cfg.min_units",
                                1.75, None)

    def test_desired_virtual(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.desired_virtual",
                                2, None)
        self._shared_wrapper.proc_config.shared_proc_cfg.desired_virtual = 5
        self.call_simple_getter("proc_config.shared_proc_cfg.desired_virtual",
                                5, None)

    def test_max_virtual(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.max_virtual",
                                3, None)
        self._shared_wrapper.proc_config.shared_proc_cfg.max_virtual = 2
        self.call_simple_getter("proc_config.shared_proc_cfg.max_virtual",
                                2, None)

    def test_min_virtual(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.min_virtual",
                                1, None)
        self._shared_wrapper.proc_config.shared_proc_cfg.min_virtual = 2
        self.call_simple_getter("proc_config.shared_proc_cfg.min_virtual",
                                2, None)

    def test_get_shared_proc_pool_id(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.pool_id", 9, 0)
        self._shared_wrapper.proc_config.shared_proc_cfg.pool_id = 2
        self.call_simple_getter("proc_config.shared_proc_cfg.pool_id", 2, 0)

    def test_uncapped_weight(self):
        self.call_simple_getter("proc_config.shared_proc_cfg.uncapped_weight",
                                128, 0)
        self._shared_wrapper.proc_config.shared_proc_cfg.uncapped_weight = 100
        self.call_simple_getter("proc_config.shared_proc_cfg.uncapped_weight",
                                100, 0)

    # DedicatedProcessorConfiguration

    def test_desired(self):
        self.call_simple_getter("proc_config.dedicated_proc_cfg.desired",
                                2, 0, use_dedicated=True)
        self._dedicated_wrapper.proc_config.dedicated_proc_cfg.desired = 3
        self.call_simple_getter("proc_config.dedicated_proc_cfg.desired",
                                3, 0, use_dedicated=True)

    def test_max(self):
        self.call_simple_getter("proc_config.dedicated_proc_cfg.max",
                                3, 0, use_dedicated=True)
        self._dedicated_wrapper.proc_config.dedicated_proc_cfg.max = 4
        self.call_simple_getter("proc_config.dedicated_proc_cfg.max",
                                4, 0, use_dedicated=True)

    def test_min(self):
        self.call_simple_getter("proc_config.dedicated_proc_cfg.min",
                                1, 0, use_dedicated=True)
        self._dedicated_wrapper.proc_config.dedicated_proc_cfg.min = 3
        self.call_simple_getter("proc_config.dedicated_proc_cfg.min",
                                3, 0, use_dedicated=True)


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


class TestMemCfg(unittest.TestCase):
    """Test cases to test the lpar mem operations."""

    def test_mem(self):
        mem_wrap = bp.PartitionMemoryConfiguration.bld(
            None, 1024, min_mem=512, max_mem=2048)
        self.assertIsNotNone(mem_wrap)
        self.assertEqual(512, mem_wrap.min)
        self.assertEqual(1024, mem_wrap.desired)
        self.assertEqual(2048, mem_wrap.max)


class TestPhysFCPort(unittest.TestCase):

    def test_bld(self):
        port = bp.PhysFCPort.bld_ref(None, 'fcs0')
        self.assertIsNotNone(port)
        self.assertEqual('fcs0', port.name)


if __name__ == "__main__":
    unittest.main()
