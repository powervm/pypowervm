# Copyright 2014, 2017 IBM Corp.
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

from pypowervm.tests.test_utils import pvmhttp
import pypowervm.wrappers.managed_system as ms
import pypowervm.wrappers.mtms as mtmwrap

_MS_HTTPRESP_FILE = "managedsystem.txt"
_MC_HTTPRESP_FILE = "managementconsole.txt"
_MS_NAME = 'HV4'


class TestMSEntryWrapper(unittest.TestCase):

    def setUp(self):
        super(TestMSEntryWrapper, self).setUp()

        self.ms_http = pvmhttp.load_pvm_resp(_MS_HTTPRESP_FILE)
        self.assertNotEqual(self.ms_http, None,
                            "Could not load %s " %
                            _MS_HTTPRESP_FILE)

        entries = self.ms_http.response.feed.findentries(
            ms._SYSTEM_NAME, _MS_NAME)

        self.assertNotEqual(entries, None,
                            "Could not find %s in %s" %
                            (_MS_NAME, _MS_HTTPRESP_FILE))

        self.myentry = entries[0]
        self.wrapper = ms.System.wrap(self.myentry)

        # Set a hardcoded value for MemoryUsedByHypervisor
        fw_mem = self.myentry.element.find(
            'AssociatedSystemMemoryConfiguration/MemoryUsedByHypervisor')
        fw_mem.text = '1536'

        mc_http = pvmhttp.load_pvm_resp(_MC_HTTPRESP_FILE)
        self.assertNotEqual(mc_http, None,
                            "Could not load %s" %
                            _MC_HTTPRESP_FILE)

        self.test_ioslot = self.wrapper.asio_config.io_slots[0]

        """ Create a bad wrapper to use when
            retrieving properties which don't exist """
        self.bad_wrapper = ms.System.wrap(mc_http.response.feed.entries[0])

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
        expected_value = _MS_NAME
        value = self.wrapper._get_val_str(ms._SYSTEM_NAME)

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

    def test_highest_compat_mode(self):
        self.assertEqual(self.wrapper.highest_compat_mode(), 7)

    def test_proc_compat_modes(self):
        expected = ('default', 'POWER5', 'POWER6', 'POWER6_Enhanced',
                    'POWER6_Plus_Enhanced', 'POWER7')
        self.assertEqual(self.wrapper.proc_compat_modes, expected)

    def test_get_proc_units(self):
        self.call_simple_getter("proc_units", 500.0, 0)

    def test_get_min_proc_units(self):
        self.call_simple_getter("min_proc_units", 0.05, 0)

    def test_get_proc_units_configurable(self):
        self.call_simple_getter("proc_units_configurable", 500.0, 0)

    def test_get_proc_units_avail(self):
        self.call_simple_getter("proc_units_avail", 500.0, 0)

    def test_get_memory_total(self):
        self.call_simple_getter("memory_total", 5767168, 0)

    def test_get_memory_free(self):
        self.call_simple_getter("memory_free", 5242752, 0)

    def test_get_host_ip_address(self):
        self.call_simple_getter("host_ip_address", '127.0.0.1', None)

    def test_get_firmware_memory(self):
        self.call_simple_getter("firmware_memory", 1536, 0)

    def test_page_table_ratio(self):
        self.call_simple_getter("page_table_ratio", 7, 0)

    def test_get_system_name(self):
        self.wrapper.set_parm_value(ms._SYSTEM_NAME, 'XYZ')
        name = self.wrapper.system_name
        self.verify_equal("system_name", name, 'XYZ')
        self.wrapper.set_parm_value(ms._SYSTEM_NAME, 'ABC')
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

    def test_asio_wwpns(self):
        self.assertEqual(self.wrapper.asio_config.avail_wwpns, 65536)

    def test_asio_wwpn_prefix(self):
        self.assertEqual(self.wrapper.asio_config.wwpn_prefix,
                         '12379814471884843981')

    def test_ioslot_bus_grp_required(self):
        self.assertEqual(self.test_ioslot.bus_grp_required, False)

    def test_ioslot_description(self):
        self.assertEqual(self.test_ioslot.description, 'I/O Processor')

    def test_ioslot_feat_codes(self):
        self.assertEqual(self.test_ioslot.feat_codes, 0)

    def test_ioslot_pci_class(self):
        self.assertEqual(self.test_ioslot.pci_class, 512)

    def test_ioslot_pci_dev_id(self):
        self.assertEqual(self.test_ioslot.pci_dev_id, 4660)

    def test_ioslot_pci_subsys_dev_id(self):
        self.assertEqual(self.test_ioslot.pci_subsys_dev_id, 1202)

    def test_ioslot_pci_rev_id(self):
        self.assertEqual(self.test_ioslot.pci_rev_id, 0)

    def test_ioslot_pci_vendor_id(self):
        self.assertEqual(self.test_ioslot.pci_vendor_id, 4116)

    def test_ioslot_pci_subsys_vendor_id(self):
        self.assertEqual(self.test_ioslot.pci_subsys_vendor_id, 4116)

    def test_ioslot_drc_index(self):
        self.assertEqual(self.test_ioslot.drc_index,
                         553713681)

    def test_ioslot_drc_name(self):
        self.assertEqual(self.test_ioslot.drc_name,
                         'U5294.001.CEC1234-P01-C011')

    def test_get_capabilities(self):
        good_cap = {'active_lpar_mobility_capable': True,
                    'inactive_lpar_mobility_capable': True,
                    'ibmi_lpar_mobility_capable': True,
                    'custom_mac_addr_capable': True,
                    'ibmi_restrictedio_capable': True,
                    'ibmi_nativeio_capable': False,
                    'simplified_remote_restart_capable': False,
                    'aix_capable': False,
                    'ibmi_capable': True,
                    'linux_capable': False,
                    'shared_processor_pool_capable': True,
                    'active_memory_expansion_capable': True,
                    'dynamic_srr_capable': True,
                    'vnic_capable': True,
                    'vnic_failover_capable': True,
                    'disable_secure_boot_capable': False}
        bad_cap = {'active_lpar_mobility_capable': False,
                   'inactive_lpar_mobility_capable': False,
                   'ibmi_lpar_mobility_capable': False,
                   'custom_mac_addr_capable': True,
                   'ibmi_restrictedio_capable': False,
                   'ibmi_nativeio_capable': False,
                   'simplified_remote_restart_capable': False,
                   'aix_capable': True,
                   'ibmi_capable': False,
                   'linux_capable': True,
                   'shared_processor_pool_capable': False,
                   'active_memory_expansion_capable': False,
                   'dynamic_srr_capable': False,
                   'vnic_capable': False,
                   'vnic_failover_capable': False,
                   'disable_secure_boot_capable': False}
        self.call_simple_getter("get_capabilities", good_cap,
                                bad_cap)

    def test_session_is_master(self):
        self.assertTrue(self.wrapper.session_is_master)

    def test_migration_data(self):
        expected_data = {'active_lpar_mobility_capable': True,
                         'inactive_lpar_mobility_capable': True,
                         'ibmi_lpar_mobility_capable': True,
                         'custom_mac_addr_capable': True,
                         'ibmi_restrictedio_capable': True,
                         'ibmi_nativeio_capable': False,
                         'simplified_remote_restart_capable': False,
                         'aix_capable': False,
                         'ibmi_capable': True,
                         'linux_capable': False,
                         'shared_processor_pool_capable': True,
                         'active_memory_expansion_capable': True,
                         'max_migration_ops_supported': 9,
                         'active_migrations_supported': 0,
                         'inactive_migrations_supported': 5,
                         'preferred_active_migrations_supported': 0,
                         'preferred_inactive_migrations_supported': 5,
                         'active_migrations_in_progress': 0,
                         'inactive_migrations_in_progress': 0,
                         'proc_compat': 'default,POWER5,POWER6,POWER6_Enhanced'
                                        ',POWER6_Plus_Enhanced,POWER7',
                         'dynamic_srr_capable': True,
                         'vnic_capable': True,
                         'vnic_failover_capable': True,
                         'disable_secure_boot_capable': False}
        result_data = self.wrapper.migration_data
        self.assertEqual(result_data, expected_data,
                         'The returned data did not match expected values')


class TestMTMS(unittest.TestCase):
    def test_mtms(self):
        mtms = mtmwrap.MTMS.bld(None, '1234-567*ABCDEF0')
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
