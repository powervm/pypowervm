# Copyright 2016 IBM Corp.
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

from pypowervm.tests.test_utils import test_wrapper_abc
from pypowervm.wrappers import enterprise_pool as ep
from pypowervm.wrappers import entry_wrapper


class TestPoolFile(test_wrapper_abc.TestWrapper):

    file = 'enterprise_pool_feed.txt'
    wrapper_class_to_test = ep.Pool

    def test_entries(self):
        self.assertEqual(1, len(self.entries))

    def test_type(self):
        self.assertIsInstance(self.dwrap, ep.Pool)

    def test_id(self):
        self.assertEqual(328, self.dwrap.id)

    def test_name(self):
        self.assertEqual('FVT_pool1', self.dwrap.name)

    def test_compliance_state(self):
        self.assertEqual(ep.ComplianceState.IN_COMPLIANCE,
                         self.dwrap.compliance_state)

    def test_compliance_hours_left(self):
        self.assertEqual(0, self.dwrap.compliance_hours_left)

    def test_total_mobile_procs(self):
        self.assertEqual(20, self.dwrap.total_mobile_procs)

    def test_total_mobile_mem(self):
        self.assertEqual(0, self.dwrap.total_mobile_mem)

    def test_avail_mobile_procs(self):
        self.assertEqual(16, self.dwrap.avail_mobile_procs)

    def test_avail_mobile_mem(self):
        self.assertEqual(0, self.dwrap.avail_mobile_mem)

    def test_unret_mobile_procs(self):
        self.assertEqual(0, self.dwrap.unret_mobile_procs)

    def test_unret_mobile_mem(self):
        self.assertEqual(0, self.dwrap.unret_mobile_mem)

    def test_mgmt_consoles(self):
        self.assertIsInstance(self.dwrap.mgmt_consoles,
                              entry_wrapper.WrapperElemList)
        self.assertEqual(1, len(self.dwrap.mgmt_consoles))
        console = self.dwrap.mgmt_consoles[0]
        self.assertIsInstance(console, ep.PoolMgmtConsole)
        self.assertEqual('ip9-1-2-3', console.name)
        self.assertEqual('7042-CR7*10B6EDC', console.mtms.mtms_str)
        self.assertTrue(console.is_master_console)
        self.assertEqual('9.1.2.3', console.ip_addr)

    def test_master_console_mtms(self):
        self.assertEqual('7042-CR7*10B6EDC',
                         self.dwrap.master_console_mtms.mtms_str)


class TestPoolMemberFile(test_wrapper_abc.TestWrapper):

    file = 'enterprise_pool_member_feed.txt'
    wrapper_class_to_test = ep.PoolMember

    def test_entries(self):
        self.assertEqual(5, len(self.entries))

    def test_type(self):
        for entry in self.entries:
            self.assertIsInstance(entry, ep.PoolMember)

    def test_mobile_procs(self):
        self.assertEqual(4, self.dwrap.mobile_procs)

    def test_mobile_mem(self):
        self.assertEqual(0, self.dwrap.mobile_mem)

    def test_set_mobile_procs(self):
        orig_value = self.dwrap.mobile_procs
        self.dwrap.mobile_procs = 999
        self.assertEqual(999, self.dwrap.mobile_procs)
        self.dwrap.mobile_procs = orig_value

    def test_set_mobile_mem(self):
        orig_value = self.dwrap.mobile_mem
        self.dwrap.mobile_mem = 888
        self.assertEqual(888, self.dwrap.mobile_mem)
        self.dwrap.mobile_mem = orig_value

    def test_inactive_procs(self):
        self.assertEqual(2, self.dwrap.inactive_procs)

    def test_inactive_mem(self):
        self.assertEqual(0, self.dwrap.inactive_mem)

    def test_unret_mobile_procs(self):
        self.assertEqual(0, self.dwrap.unret_mobile_procs)

    def test_unret_mobile_mem(self):
        self.assertEqual(0, self.dwrap.unret_mobile_mem)

    def test_proc_compliance_hours_left(self):
        self.assertEqual(0, self.dwrap.proc_compliance_hours_left)

    def test_mem_compliance_hours_left(self):
        self.assertEqual(0, self.dwrap.mem_compliance_hours_left)

    def test_sys_name(self):
        self.assertEqual('Server-8284-22A-SN21B63CV', self.dwrap.sys_name)

    def test_sys_installed_procs(self):
        self.assertEqual(20, self.dwrap.sys_installed_procs)

    def test_sys_installed_mem(self):
        self.assertEqual(524288, self.dwrap.sys_installed_mem)

    def test_sys_mtms(self):
        self.assertEqual('8284-22A*21B63CV', self.dwrap.sys_mtms.mtms_str)

    def test_sys_state(self):
        self.assertEqual('operating', self.dwrap.sys_state)

    def test_mgmt_consoles(self):
        self.assertIsInstance(self.dwrap.mgmt_consoles,
                              entry_wrapper.WrapperElemList)
        self.assertEqual(1, len(self.dwrap.mgmt_consoles))
        console = self.dwrap.mgmt_consoles[0]
        self.assertIsInstance(console, ep.PoolMgmtConsole)
        self.assertEqual('ip9-1-2-3', console.name)
        self.assertEqual('7042-CR7*10B6EDC', console.mtms.mtms_str)
        self.assertTrue(console.is_master_console)
        self.assertEqual('9.1.2.3', console.ip_addr)
