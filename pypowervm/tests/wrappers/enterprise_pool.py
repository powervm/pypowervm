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


class TestEnterprisePoolFile(test_wrapper_abc.TestWrapper):

    file = 'enterprise_pool_feed.txt'
    wrapper_class_to_test = ep.EnterprisePool

    def test_entries(self):
        self.assertEqual(1, len(self.entries))

    def test_type(self):
        self.assertEqual(ep.EnterprisePool, type(self.dwrap))

    def test_id(self):
        self.assertEqual(328, self.dwrap.id)

    def test_name(self):
        self.assertEqual('FVT_pool1', self.dwrap.name)

    def test_compliance_state(self):
        self.assertEqual('InCompliance', self.dwrap.compliance_state)

    def test_compliance_remaining_hours(self):
        self.assertEqual(None, self.dwrap.compliance_remaining_hours)

    def test_total_mobile_proc_units(self):
        self.assertEqual(20, self.dwrap.total_mobile_proc_units)

    def test_total_mobile_memory(self):
        self.assertEqual(0, self.dwrap.total_mobile_memory)

    def test_available_mobile_proc_units(self):
        self.assertEqual(17, self.dwrap.available_mobile_proc_units)

    def test_available_mobile_memory(self):
        self.assertEqual(0, self.dwrap.available_mobile_memory)

    def test_unreturned_mobile_proc_units(self):
        self.assertEqual(0, self.dwrap.unreturned_mobile_proc_units)

    def test_unreturned_mobile_memory(self):
        self.assertEqual(0, self.dwrap.unreturned_mobile_memory)

    def test_master_console_mtms(self):
        self.assertEqual('7042-CR7*10B6EDC', self.dwrap.master_console_mtms)


class TestEnterprisePoolMemberFile(test_wrapper_abc.TestWrapper):

    file = 'enterprise_pool_member_feed.txt'
    wrapper_class_to_test = ep.EnterprisePoolMember

    def test_entries(self):
        self.assertEqual(5, len(self.entries))

    def test_type(self):
        for entry in self.entries:
            self.assertEqual(ep.EnterprisePoolMember, type(entry))

    def test_mobile_proc_units(self):
        self.assertEqual(0, self.dwrap.mobile_proc_units)

    def test_mobile_memory(self):
        self.assertEqual(0, self.dwrap.mobile_memory)

    def test_set_mobile_proc_units(self):
        orig_value = self.dwrap.mobile_proc_units
        self.dwrap.mobile_proc_units = 999
        self.assertEqual(999, self.dwrap.mobile_proc_units)
        self.dwrap.mobile_proc_units = orig_value

    def test_set_mobile_memory(self):
        orig_value = self.dwrap.mobile_memory
        self.dwrap.mobile_memory = 888
        self.assertEqual(888, self.dwrap.mobile_memory)
        self.dwrap.mobile_memory = orig_value

    def test_inactive_proc_units(self):
        self.assertEqual(6, self.dwrap.inactive_proc_units)

    def test_inactive_memory(self):
        self.assertEqual(0, self.dwrap.inactive_memory)

    def test_unreturned_mobile_proc_units(self):
        self.assertEqual(0, self.dwrap.unreturned_mobile_proc_units)

    def test_unreturned_mobile_memory(self):
        self.assertEqual(0, self.dwrap.unreturned_mobile_memory)

    def test_proc_compliance_remaining_hours(self):
        self.assertEqual(None, self.dwrap.proc_compliance_remaining_hours)

    def test_mem_compliance_remaining_hours(self):
        self.assertEqual(None, self.dwrap.mem_compliance_remaining_hours)

    def test_system_name(self):
        self.assertEqual('V7R2_14', self.dwrap.system_name)

    def test_system_installed_proc_units(self):
        self.assertEqual(16, self.dwrap.system_installed_proc_units)

    def test_system_installed_memory(self):
        self.assertEqual(262144, self.dwrap.system_installed_memory)

    def test_system_mtms(self):
        self.assertEqual('8246-L2D*100854A', self.dwrap.system_mtms)
