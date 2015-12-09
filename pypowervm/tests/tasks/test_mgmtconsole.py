# Copyright 2015 IBM Corp.
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

from pypowervm import const
from pypowervm import exceptions as exc
from pypowervm.tasks import management_console as mc_task


class TestMgmtCon(testtools.TestCase):
    """Unit Tests for ManagementConsole tasks."""

    def setUp(self):
        super(TestMgmtCon, self).setUp()

        self.mc_p = mock.patch('pypowervm.wrappers.management_console.'
                               'ManagementConsole')
        self.mc = self.mc_p.start()
        # Make it easy to address the mock console wrapper
        self.mc_ws = self.mc.wrap.return_value
        self.cons_w = self.mc_ws.__getitem__.return_value
        self.addCleanup(self.mc_p.stop)

    def test_get_public_key(self):
        self.cons_w.ssh_public_key = '1234554321'
        key = mc_task.get_public_key(mock.Mock())
        self.assertEqual('1234554321', key)

    def test_add_auth_key(self):
        # Test adding a key ('4') to an existing list ('1', '2', '3')
        self.cons_w.ssh_authorized_keys = ('1', '2', '3')
        mc_task.add_authorized_key(mock.Mock(), '4')
        self.assertEqual(['1', '2', '3', '4'],
                         self.cons_w.ssh_authorized_keys)
        self.cons_w.update.assert_called_once_with()

        # Test we don't call update when not needed.
        self.cons_w.reset_mock()
        mc_task.add_authorized_key(mock.Mock(), '2')
        self.assertEqual(0, self.cons_w.update.called)

        # Test the transaction retry
        self.cons_w.reset_mock()
        resp = mock.Mock(status=const.HTTPStatus.ETAG_MISMATCH)
        self.cons_w.update.side_effect = exc.HttpError(resp)
        # When the transaction decorator refreshes the mgmt console wrapper
        # then we know it's retrying so just raise an exception and bail
        self.cons_w.refresh.side_effect = ValueError()
        self.assertRaises(ValueError, mc_task.add_authorized_key,
                          mock.Mock(), '5')
        # Ensure it really was refresh that caused the exception
        self.assertEqual(1, self.cons_w.refresh.call_count)
        # And that our update was called
        self.assertEqual(1, self.cons_w.update.call_count)

    def test_get_auth_keys(self):
        # Test adding a key ('4') to an existing list ('1', '2', '3')
        self.cons_w.ssh_authorized_keys = ('1', '2', '3')
        self.assertEqual(self.cons_w.ssh_authorized_keys,
                         mc_task.get_authorized_keys(mock.Mock()))
        mc_task.add_authorized_key(mock.Mock(), '4')
        self.assertEqual(self.cons_w.ssh_authorized_keys,
                         mc_task.get_authorized_keys(mock.Mock()))
        self.assertEqual(mc_task.get_authorized_keys(mock.Mock()),
                         ['1', '2', '3', '4'])
