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
import logging
import unittest

import mock

import pypowervm.adapter as adp
import pypowervm.exceptions as pvmex
import pypowervm.helpers.log_helper as log_hlp

# Testing by hand it's useful to enable the next line instead of the following
# logging.basicConfig(level=logging.INFO)
logging.basicConfig()

fake_resp1 = adp.Response('GET', '/some/path', 200, 'OK', ['headers'])


class TestLogHelper(unittest.TestCase):
    def setUp(self):
        return

    @mock.patch('pypowervm.adapter.Session')
    @mock.patch('pypowervm.helpers.log_helper.LOG')
    def test_log_helper(self, mock_log, mock_sess):

        helpers = log_hlp.log_helper
        response = fake_resp1
        mock_sess.request.return_value = response
        adpt = adp.Adapter(mock_sess, use_cache=False, helpers=helpers)

        # Test that we get the response we expect passed back unharmed
        self.assertEqual(response,
                         adpt._request('method', 'path', body='the body'))

        # Should be 1 req/resp in the log now, which would be 4 info messages
        mock_log.reset_mock()
        log_hlp._write_thread_log()
        self.assertEqual(mock_log.info.call_count, 4)

        # Should be empty now
        mock_log.reset_mock()
        log_hlp._write_thread_log()
        self.assertEqual(mock_log.info.call_count, 0)

        # Test that we limit the number of entries
        mock_log.reset_mock()
        for x in range(0, 30):
            adpt._request('method1', 'path', body='the body')
        log_hlp._write_thread_log()
        # Each req/resp pair is 2 log entries but headers and body
        # are logged separately, so with maxlogs=5, it's 5 * 2 * 2.
        self.assertEqual(mock_log.info.call_count, (5 * 2 * 2))

        # Add a few records, and ensure an exception dumps the logs
        # and is then raised
        adpt._request('method1', 'path', body='the body')
        adpt._request('method2', 'path', body='the body')
        mock_sess.request.side_effect = pvmex.Error('yo')
        mock_log.reset_mock()
        self.assertRaises(
            pvmex.Error, adpt._request, 'method', 'path', body='the body')
        # Should be 10 entries. 4 * 2 req/resp, 2 for this req.
        self.assertEqual(mock_log.info.call_count, 10)

        # Ensure the log storage is initialized correctly, and we can change
        # the default value
        hlp_size = functools.partial(log_hlp.log_helper, max_logs=20)
        adpt1 = adp.Adapter(mock_sess, use_cache=False, helpers=hlp_size)
        mock_sess.request.side_effect = None
        with mock.patch('pypowervm.helpers.log_helper._init_thread_stg'
                        ) as mock_init:
            adpt1._request('method1', 'path', body='the body')
            # Should be called with 40 since 20 * 2 entries.
            self.assertEqual(mock_init.call_args_list,
                             [mock.call(max_entries=40)])
