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

import functools

import mock
import testtools

import pypowervm.adapter as adp
import pypowervm.exceptions as pvmex
import pypowervm.helpers.sample_helper as smpl_hlp
import pypowervm.tests.test_fixtures as fx


class TestSampleHelper(testtools.TestCase):

    def setUp(self):
        super(TestSampleHelper, self).setUp()
        self.sess = self.useFixture(fx.SessionFx()).sess

    @mock.patch('time.sleep')
    def test_sample_helper(self, mock_sleep):

        helpers = smpl_hlp.sample_retry_helper
        fake_resp1 = adp.Response(
            'GET', '/some/path', 200, 'OK', ['headers'],
            body='Some Text HSCL3205 More Text')
        self.sess.request.side_effect = pvmex.Error('yo', response=fake_resp1)
        adpt = adp.Adapter(self.sess, helpers=helpers)
        self.assertRaises(
            pvmex.Error, adpt._request, 'method', 'path', body='the body')

        # Test that the request method was called twice and sleep was called
        self.assertEqual(self.sess.request.call_count, 2)
        mock_sleep.assert_called_once_with(5 * 1)

        hlp = functools.partial(smpl_hlp.sample_retry_helper, max_retries=5)
        self.sess.reset_mock()
        try:
            adpt._request('method', 'path', body='the body', helpers=hlp)
        except Exception:
            # Should have tried 6 times total
            self.assertEqual(self.sess.request.call_count, 6)
