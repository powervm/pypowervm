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


class TestPool(testtools.TestCase):
    """Unit Tests for Enterprise Pool tasks."""

    def setUp(self):
        super(TestPool, self).setUp()

        self.adapter = mock.Mock()

        self.pm = ep_wrap.PoolMember.wrap(
            util.load_file(ENTERPRISE_POOL_MEMBER, self.adapter))

        # Mock out the update method
        self.pm.update = mock.Mock()

        # ep_task._set_mobile_value calls PoolMember.getter(...).get(). The
        # getter() method of EntryWrapper returns an EntryWrapperGetter since
        # entry_uuid is passed. The EntryWrapperGetter object's get() method
        # is then called, which needs to return our pool member defined above.
        self.mock_entry_wrap_getter = mock.Mock()
        self.mock_entry_wrap_getter.get.return_value = self.pm

        pm_getter_patch = mock.patch('pypowervm.wrappers.enterprise_pool.'
                                     'PoolMember.getter')
        self.pm_getter = pm_getter_patch.start()
        self.pm_getter.return_value = self.mock_entry_wrap_getter
        self.addCleanup(pm_getter_patch.stop)

    def test_set_mobile_procs(self):
        num_procs = 12
        ep_task.set_mobile_procs(self.adapter, mock.Mock(), mock.Mock(),
                                 num_procs)
        self.assertEqual(num_procs, self.pm.mobile_procs)
        self.pm.update.assert_called_once_with()

    def test_set_mobile_procs_no_update_needed(self):
        # Tests that update is not called on the pool member wrapper if the
        # value it is being set to is unchanged
        num_procs = self.pm.mobile_procs
        ep_task.set_mobile_procs(self.adapter, mock.Mock(), mock.Mock(),
                                 num_procs)
        self.assertEqual(num_procs, self.pm.mobile_procs)
        self.assertEqual(0, self.pm.update.call_count)

    def test_set_mobile_procs_require_retry(self):
        self._test_set_mobile_value_require_retry(
            ep_task.set_mobile_procs, 19)

    def test_set_mobile_mem(self):
        memory_amount = 100000
        ep_task.set_mobile_mem(self.adapter, mock.Mock(), mock.Mock(),
                               memory_amount)
        self.assertEqual(memory_amount, self.pm.mobile_mem)
        self.pm.update.assert_called_once_with()

    def test_set_mobile_mem_no_update_needed(self):
        # Tests that update is not called on the pool member wrapper if the
        # value it is being set to is unchanged
        memory_amount = self.pm.mobile_mem
        ep_task.set_mobile_mem(self.adapter, mock.Mock(), mock.Mock(),
                               memory_amount)
        self.assertEqual(memory_amount, self.pm.mobile_mem)
        self.assertEqual(0, self.pm.update.call_count)

    def test_set_mobile_mem_require_retry(self):
        self._test_set_mobile_value_require_retry(
            ep_task.set_mobile_mem, 200000)

    def _test_set_mobile_value_require_retry(self, method, value):
        # Tests that the update is retried via the transaction decorator if
        # an ETAG_MISMATCH is raised
        self.pm.update.side_effect = util.raiseRetryException

        # When the transaction decorator refreshes the pool member wrapper
        # then we know it is retrying the update so raise an exception to bail
        self.pm.refresh = mock.Mock()
        self.pm.refresh.side_effect = AssertionError()

        self.assertRaises(AssertionError, method, self.adapter, mock.Mock(),
                          mock.Mock(), value)

        # Ensure it really was refresh that raised the exception
        self.assertEqual(1, self.pm.refresh.call_count)

        # Ensure that update was called that prompted the call to refresh
        self.assertEqual(1, self.pm.update.call_count)
