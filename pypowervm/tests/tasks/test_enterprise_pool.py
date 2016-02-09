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

import mock
import testtools

from pypowervm.tasks import enterprise_pool as ep_task
from pypowervm.tests.tasks import util
from pypowervm.wrappers import enterprise_pool as ep_wrap


ENTERPRISE_POOL_MEMBER = 'enterprise_pool_member.txt'


class TestEnterprisePool(testtools.TestCase):
    """Unit Tests for EnterprisePool tasks."""

    def setUp(self):
        super(TestEnterprisePool, self).setUp()

        self.adapter = mock.Mock()

        self.epm = ep_wrap.EnterprisePoolMember.wrap(
            util.load_file(ENTERPRISE_POOL_MEMBER, self.adapter))

        # Mock out the update method
        self.epm.update = mock.Mock()

        # ep_task._set_mobile_value calls
        # EnterprisePoolMember.getter(...).get().  The getter() method of
        # EntryWrapper returns an EntryWrapperGetter since entry_uuid is
        # passed. The EntryWrapperGetter object's get() method is then called,
        # which needs to return our pool member defined above (self.epm).
        self.mock_entry_wrap_getter = mock.Mock()
        self.mock_entry_wrap_getter.get.return_value = self.epm

        epm_getter_patch = mock.patch('pypowervm.wrappers.enterprise_pool.'
                                      'EnterprisePoolMember.getter')
        self.epm_getter = epm_getter_patch.start()
        self.epm_getter.return_value = self.mock_entry_wrap_getter
        self.addCleanup(epm_getter_patch.stop)

    def test_set_mobile_proc_units(self):
        num_proc_units = 12
        ep_task.set_mobile_proc_units(self.adapter, mock.Mock(), mock.Mock(),
                                      num_proc_units)
        self.assertEqual(num_proc_units, self.epm.mobile_proc_units)
        self.epm.update.assert_called_once_with()

    def test_set_mobile_proc_units_no_update_needed(self):
        # Tests that update is not called on the pool member wrapper if the
        # value it is being set to is unchanged
        num_proc_units = self.epm.mobile_proc_units
        ep_task.set_mobile_proc_units(self.adapter, mock.Mock(), mock.Mock(),
                                      num_proc_units)
        self.assertEqual(num_proc_units, self.epm.mobile_proc_units)
        self.assertEqual(0, self.epm.update.call_count)

    def test_set_mobile_proc_units_require_retry(self):
        self._test_set_mobile_value_require_retry(
            ep_task.set_mobile_proc_units, 19)

    def test_set_mobile_memory(self):
        memory_amount = 100000
        ep_task.set_mobile_memory(self.adapter, mock.Mock(), mock.Mock(),
                                  memory_amount)
        self.assertEqual(memory_amount, self.epm.mobile_memory)
        self.epm.update.assert_called_once_with()

    def test_set_mobile_memory_no_update_needed(self):
        # Tests that update is not called on the pool member wrapper if the
        # value it is being set to is unchanged
        memory_amount = self.epm.mobile_memory
        ep_task.set_mobile_memory(self.adapter, mock.Mock(), mock.Mock(),
                                  memory_amount)
        self.assertEqual(memory_amount, self.epm.mobile_memory)
        self.assertEqual(0, self.epm.update.call_count)

    def test_set_mobile_memory_require_retry(self):
        self._test_set_mobile_value_require_retry(
            ep_task.set_mobile_memory, 200000)

    def _test_set_mobile_value_require_retry(self, method, value):
        # Tests that the update is retried via the transaction decorator if
        # an ETAG_MISMATCH is raised
        self.epm.update.side_effect = util.raiseRetryException

        # When the transaction decorator refreshes the pool member wrapper
        # then we know it is retrying the update so raise an exception to bail
        self.epm.refresh = mock.Mock()
        self.epm.refresh.side_effect = AssertionError()

        self.assertRaises(AssertionError, method, self.adapter, mock.Mock(),
                          mock.Mock(), value)

        # Ensure it really was refresh that raised the exception
        self.assertEqual(1, self.epm.refresh.call_count)

        # Ensure that update was called that prompted the call to refresh
        self.assertEqual(1, self.epm.update.call_count)
