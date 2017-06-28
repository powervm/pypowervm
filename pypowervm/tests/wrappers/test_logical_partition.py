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
import uuid

import mock
import testtools

import pypowervm.tests.test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.utils.uuid as pvm_uuid
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.logical_partition as lpar

LPAR_HTTPRESP_FILE = "lpar.txt"
IBMI_HTTPRESP_FILE = "lpar_ibmi.txt"
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

    def test_get_ref_code(self):
        self.call_simple_getter("ref_code", "00000000", None)

    def test_get_ref_code_full(self):
        self.call_simple_getter(
            "ref_code_full", ("time_stamp=08/13/2016 23:52:08,refcode=00000000"
                              ",word2=03D00000,fru_call_out_loc_codes=#47-"
                              "Ubuntu SMP Fri Jun 24 10:09:20 UTC 2016"), None)

    def test_uuid(self):
        wrapper = self._dedicated_wrapper
        self.assertEqual('42DF39A2-3A4A-4748-998F-25B15352E8A7', wrapper.uuid)
        # Test set and retrieve
        uuid1 = pvm_uuid.convert_uuid_to_pvm(str(uuid.uuid4()))
        up_uuid1 = uuid1.upper()
        wrapper.set_uuid(uuid1)
        self.assertEqual(up_uuid1, wrapper.uuid)
        self.assertEqual(up_uuid1, wrapper.partition_uuid)

        uuid2 = pvm_uuid.convert_uuid_to_pvm(str(uuid.uuid4()))
        wrapper.uuid = uuid2
        self.assertEqual(uuid2.upper(), wrapper.uuid)

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

    def test_get_operating_system(self):
        self.call_simple_getter(
            "operating_system", EXPECTED_OPERATING_SYSTEM_VER, "Unknown")

    @mock.patch('warnings.warn')
    def test_rr_off(self, mock_warn):
        """Remote Restart fields when not RR capable."""
        self.call_simple_getter("rr_enabled", None, None)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)
        mock_warn.reset_mock()
        self._shared_wrapper.rr_enabled = True
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)
        mock_warn.reset_mock()
        self.call_simple_getter("rr_enabled", None, None)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)

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

    def test_is_svc_partition(self):
        self.call_simple_getter("is_service_partition", False, False)
        self._shared_wrapper.is_service_partition = True
        self.call_simple_getter("is_service_partition", True, False)

    def test_keylock_pos(self):
        self.call_simple_getter("keylock_pos", "normal", None)
        self._shared_wrapper.keylock_pos = bp.KeylockPos.MANUAL
        self.call_simple_getter("keylock_pos", "manual", None)
        with testtools.ExpectedException(ValueError):
            self._shared_wrapper.keylock_pos = 'frobnicated'

    def test_bootmode(self):
        self.call_simple_getter("bootmode", "Normal", None)
        self._shared_wrapper.bootmode = bp.BootMode.SMS
        self.call_simple_getter("bootmode", "System_Management_Services", None)
        with testtools.ExpectedException(ValueError):
            self._shared_wrapper.bootmode = 'frobnicated'

    def test_disable_secure_boot(self):
        self.call_simple_getter("disable_secure_boot", False, False)
        self._shared_wrapper.disable_secure_boot = True
        self.call_simple_getter("disable_secure_boot", True, False)

    def test_allow_perf_data_collection(self):
        self.call_simple_getter("allow_perf_data_collection", False, False)
        self._shared_wrapper.allow_perf_data_collection = True
        self.call_simple_getter("allow_perf_data_collection", True, False)

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

    def test_can_modifies(self):
        """Simple check on the 'can_modify_xxx' methods."""
        wrap = TestLogicalPartition._shared_wrapper
        wrap.set_parm_value(bp._BP_STATE, bp.LPARState.RUNNING)
        wrap.set_parm_value(bp._BP_RMC_STATE, bp.RMCState.ACTIVE)
        self.assertTrue(wrap.can_modify_io()[0])
        self.assertFalse(wrap.can_modify_mem()[0])
        self.assertTrue(wrap.can_modify_proc()[0])

    def test_can_modify(self):
        """Detailed testing on the _can_modify method."""
        wrap = TestLogicalPartition._shared_wrapper

        # By default, it will return True because it is a non-activated LPAR
        self.assertTrue(wrap._can_modify(mock.Mock(), '')[0])
        # Turn on the LPAR.  Should fail due to RMC
        wrap.set_parm_value(bp._BP_MGT_PARTITION, False)
        wrap.set_parm_value(bp._BP_STATE, bp.LPARState.RUNNING)
        val, reason = wrap._can_modify(mock.Mock(), '')
        self.assertFalse(val)
        self.assertTrue('RMC' in reason)

        # Turn on Management Partition
        wrap.set_parm_value(bp._BP_MGT_PARTITION, True)
        val, reason = wrap._can_modify(mock.Mock(), '')
        self.assertTrue(val)
        self.assertIsNone(reason)

        # Turn on RMC, but have the DLPAR return false.
        wrap.set_parm_value(bp._BP_RMC_STATE, bp.RMCState.ACTIVE)
        val, reason = wrap._can_modify(None, 'Testing')
        self.assertFalse(val)
        self.assertTrue('DLPAR' in reason)
        self.assertTrue('Testing' in reason)

        # Turn on DLPAR
        val, reason = wrap._can_modify(mock.Mock(), '')
        self.assertTrue(val)
        self.assertIsNone(reason)

        # Now turn off RMC but change the LPAR type to OS400.  Should be OK.
        wrap.set_parm_value(bp._BP_RMC_STATE, bp.RMCState.INACTIVE)
        wrap.set_parm_value(bp._BP_TYPE, bp.LPARType.OS400)
        val, reason = wrap._can_modify(mock.Mock(), '')
        self.assertTrue(val)
        self.assertIsNone(reason)

    def test_can_lpm(self):
        """Tests for the can_lpm method."""
        wrap = TestLogicalPartition._shared_wrapper

        # By default, it will return True because it is a non-activated LPAR
        val, reason = wrap.can_lpm(mock.ANY)
        self.assertFalse(val)
        self.assertTrue('active' in reason)

        # Turn on the LPAR, but make it RMC inactive
        wrap.set_parm_value(bp._BP_MGT_PARTITION, False)
        wrap.set_parm_value(bp._BP_STATE, bp.LPARState.RUNNING)
        wrap.set_parm_value(bp._BP_RMC_STATE, bp.RMCState.INACTIVE)
        val, reason = wrap.can_lpm(mock.ANY)
        self.assertFalse(val)
        self.assertTrue('RMC' in reason)

        # Turn on RMC, but by default some of the capabilities are off.
        wrap.set_parm_value(bp._BP_RMC_STATE, bp.RMCState.ACTIVE)
        val, reason = wrap.can_lpm(mock.ANY)
        self.assertFalse(val)
        self.assertTrue('DLPAR' in reason)

        # Turn on the DLPAR bits.  Mem is the only one required as the others
        # are on in the root XML.
        wrap.capabilities.set_parm_value(bp._CAP_DLPAR_MEM_CAPABLE, True)
        val, reason = wrap.can_lpm(mock.ANY)
        self.assertTrue(val)
        self.assertIsNone(reason)

        # Turn on Management Partition
        wrap.set_parm_value(bp._BP_MGT_PARTITION, True)
        val, reason = wrap.can_lpm(mock.ANY)
        self.assertFalse(val)
        self.assertTrue('management' in reason)

    def test_can_lpm_ibmi(self):
        """Tests for the can_lpm method for IBM i branches."""
        wrap = TestLogicalPartition._shared_wrapper

        # Set that it is IBM i
        wrap.set_parm_value(bp._BP_MGT_PARTITION, False)
        wrap.set_parm_value(bp._BP_TYPE, bp.LPARType.OS400)
        wrap.set_parm_value(bp._BP_STATE, bp.LPARState.RUNNING)
        host_w = mock.MagicMock()

        # Destination host is not capable for IBMi LPM
        migr_data = {'ibmi_lpar_mobility_capable': False}
        val, reason = wrap.can_lpm(host_w, migr_data=migr_data)
        self.assertFalse(val)
        self.assertEqual(reason, 'Target system does not have the IBM i '
                         'LPAR Mobility Capability.')

        # Check if restricted I/O is off.
        migr_data = {'ibmi_lpar_mobility_capable': True}
        wrap.set_parm_value(lpar._LPAR_RESTRICTED_IO, 'False')
        val, reason = wrap.can_lpm(host_w, migr_data=migr_data)
        self.assertFalse(val)
        self.assertIn('restricted I/O', reason)

        # Turn restricted I/O on, but get a host without the mobility cap
        wrap.set_parm_value(lpar._LPAR_RESTRICTED_IO, 'True')
        host_w = mock.MagicMock()
        host_w.get_capability.return_value = False
        val, reason = wrap.can_lpm(host_w, migr_data=migr_data)
        self.assertFalse(val)
        self.assertEqual('Source system does not have the IBM i LPAR '
                         'Mobility Capability.', reason)

        # Turn all required capabilities on
        host_w.get_capability.return_value = True
        wrap.capabilities.set_parm_value(bp._CAP_DLPAR_MEM_CAPABLE, True)
        val, reason = wrap.can_lpm(host_w, migr_data=migr_data)
        self.assertTrue(val)
        self.assertIsNone(reason)

        # Turn all required capabilities on but migration data is empty
        val, reason = wrap.can_lpm(host_w)
        self.assertTrue(val)
        self.assertIsNone(reason)

        # Turn all required capabilities on but migration data doesn't contain
        # the key 'ibmi_lpar_mobility_capable'
        migr_data = {}
        val, reason = wrap.can_lpm(host_w, migr_data=migr_data)
        self.assertTrue(val)
        self.assertIsNone(reason)

    def test_capabilities(self):
        # PartitionCapabilities
        self.call_simple_getter("capabilities.io_dlpar", True, False)
        self.call_simple_getter("capabilities.mem_dlpar", False, False)
        self.call_simple_getter("capabilities.proc_dlpar", True, False)

    def test_get_proc_mode(self):
        # PartitionProcessorConfiguration
        self.call_simple_getter(
            "proc_config.has_dedicated", False, False)
        self.call_simple_getter(
            "proc_config.has_dedicated", True, False, use_dedicated=True)
        self._dedicated_wrapper.proc_config._has_dedicated(False)
        self.call_simple_getter(
            "proc_config.has_dedicated", False, False, use_dedicated=True)

    def test_get_current_sharing_mode(self):
        # SharedProcessorConfiguration
        self.call_simple_getter("proc_config.sharing_mode", "uncapped", None)
        self._shared_wrapper.proc_config.sharing_mode = "keep idle procs"
        self.call_simple_getter("proc_config.sharing_mode", "keep idle procs",
                                None)

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

    def test_nvram(self):
        self.assertEqual("TheNVRAMis20KofBASE64encodedDATA",
                         self._dedicated_wrapper.nvram)
        self._dedicated_wrapper.nvram = "RRNVRAMis20KofBASE64encodedDATA"
        self.assertEqual("RRNVRAMis20KofBASE64encodedDATA",
                         self._dedicated_wrapper.nvram)
        # Test setting one that's absent
        self.assertIsNone(self._shared_wrapper.nvram)
        self._shared_wrapper.nvram = 'SomeOtherValue'
        self.assertEqual('SomeOtherValue', self._shared_wrapper.nvram)

    def test_uptime(self):
        self.assertEqual(1185681, self._dedicated_wrapper.uptime)


class TestIBMiSpecific(twrap.TestWrapper):
    """IBMi-specific tests, requiring a test file from an IBMi partition."""
    file = IBMI_HTTPRESP_FILE
    wrapper_class_to_test = lpar.LPAR

    def test_restricted_io(self):
        self.dwrap.restrictedio = True
        self.assertTrue(self.dwrap.restrictedio)

    def test_desig_ipl_src(self):
        self.assertEqual('b', self.dwrap.desig_ipl_src)
        self.dwrap.desig_ipl_src = 'c'
        self.assertEqual('c', self.dwrap.desig_ipl_src)
        # Argh, testtools.TestCase overrides assertRaises - can't use 'with'
        try:
            self.dwrap.desig_ipl_src = 'q'
            self.fail()
        except ValueError:
            pass

    def test_tagged_io(self):
        # Getter
        tio = self.dwrap.io_config.tagged_io
        self.assertIsInstance(tio, bp.TaggedIO)
        # Field getters & setters
        self.assertEqual('NONE', tio.alt_load_src)
        tio.alt_load_src = 34
        self.assertEqual('34', tio.alt_load_src)
        self.assertEqual('0', tio.console)
        tio.console = 'NONE'
        self.assertEqual('NONE', tio.console)
        self.assertEqual('NONE', tio.load_src)
        tio.load_src = '56'
        self.assertEqual('56', tio.load_src)

        # _bld honors child ordering
        new_tio = bp.TaggedIO.bld(self.adpt)
        new_tio.load_src = 1
        new_tio.alt_load_src = 2
        new_tio.console = 3
        self.assertEqual(
            '<uom:TaggedIO xmlns:uom="http://www.ibm.com/xmlns/systems/power/f'
            'irmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><uom:'
            'Atom/></uom:Metadata><uom:AlternateLoadSource>2</uom:AlternateLoa'
            'dSource><uom:Console>3</uom:Console><uom:LoadSource>1</uom:LoadSo'
            'urce></uom:TaggedIO>'.encode('utf-8'), new_tio.toxmlstring())

        # Setter
        self.dwrap.io_config.tagged_io = new_tio
        self.assertEqual('3', self.dwrap.io_config.tagged_io.console)

        new_tio = bp.TaggedIO.bld(self.adpt)
        self.assertEqual(
            '<uom:TaggedIO xmlns:uom="http://www.ibm.com/xmlns/systems/power/f'
            'irmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><uom:'
            'Atom/></uom:Metadata><uom:AlternateLoadSource>NONE</uom:Alternate'
            'LoadSource><uom:Console>HMC</uom:Console><uom:LoadSource>0</uom:L'
            'oadSource></uom:TaggedIO>'.encode('utf-8'), new_tio.toxmlstring())

    @mock.patch('warnings.warn')
    def test_rr_real_values(self, mock_warn):
        """Test Remote Restart fields when RR capable."""
        # Testing this under IBMi because the IBMi payload file happens to have
        # real data to use.
        self.assertIsNone(self.dwrap.rr_enabled)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)
        mock_warn.reset_mock()
        self.assertIsNone(self.dwrap.rr_state)
        mock_warn.assert_called_with(mock.ANY, DeprecationWarning)


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


class TestMemCfg(twrap.TestWrapper):
    """Test cases to test the lpar mem operations."""

    file = LPAR_HTTPRESP_FILE
    wrapper_class_to_test = lpar.LPAR

    def setUp(self):
        super(TestMemCfg, self).setUp()
        self.mem_config = self.entries[0].mem_config

    def test_mem(self):
        mem_wrap = bp.PartitionMemoryConfiguration.bld(
            None, 1024, min_mem=512, max_mem=2048)
        self.assertIsNotNone(mem_wrap)
        self.assertEqual(512, mem_wrap.min)
        self.assertEqual(1024, mem_wrap.desired)
        self.assertEqual(2048, mem_wrap.max)
        self.assertEqual(0, mem_wrap.exp_factor)
        self.assertFalse(mem_wrap.ame_enabled)

    def test_current_mem(self):
        self.assertEqual(512, self.mem_config.current)


class TestPhysFCPort(unittest.TestCase):

    def test_bld(self):
        port = bp.PhysFCPort.bld_ref(None, 'fcs0')
        self.assertIsNotNone(port)
        self.assertEqual('fcs0', port.name)


if __name__ == "__main__":
    unittest.main()
