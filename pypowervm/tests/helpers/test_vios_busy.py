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
import unittest

import mock

import pypowervm.adapter as adp
import pypowervm.exceptions as pvmex
from pypowervm.helpers import vios_busy
from pypowervm.tests.test_utils import pvmhttp

HTTPRESP_FILE = "fake_httperror.txt"
HTTPRESP_SA_FILE = "fake_httperror_service_unavail.txt"


class TestVIOSBusyHelper(unittest.TestCase):

    def setUp(self):
        super(TestVIOSBusyHelper, self).setUp()

        self.http_error = pvmhttp.load_pvm_resp(HTTPRESP_FILE)
        self.http_error_sa = pvmhttp.load_pvm_resp(HTTPRESP_SA_FILE)

    @mock.patch('pypowervm.adapter.Session')
    @mock.patch('pypowervm.helpers.vios_busy.SLEEP')
    def test_vios_busy_helper(self, mock_sleep, mock_sess):
        # Try with 1 retries
        hlp = functools.partial(vios_busy.vios_busy_retry_helper,
                                max_retries=1)
        error = pvmex.Error('yo', response=self.http_error.response)
        mock_sess.request.side_effect = error
        adpt = adp.Adapter(mock_sess, helpers=hlp)
        self.assertRaises(
            pvmex.Error, adpt._request, 'method', 'path', body='the body')
        # Test that the request method was called twice and sleep was called
        self.assertEqual(mock_sess.request.call_count, 2)
        mock_sleep.assert_called_once_with(5 * 1)

        # Test with more retries and sleep values
        retries = 10
        hlp = functools.partial(vios_busy.vios_busy_retry_helper,
                                max_retries=retries, delay=15)
        mock_sess.reset_mock()
        self.assertRaises(pvmex.Error, adpt._request, 'method', 'path',
                          body='the body', helpers=hlp)
        # Should have tried 'retries' times plus the initial one
        self.assertEqual(mock_sess.request.call_count, retries+1)

        # Test with None response
        mock_sess.reset_mock()
        error = pvmex.Error('yo', response=None)
        mock_sess.request.side_effect = error
        hlp = functools.partial(vios_busy.vios_busy_retry_helper,
                                max_retries=1, delay=15)
        self.assertRaises(pvmex.Error, adpt._request, 'method', 'path',
                          body='the body', helpers=hlp)
        # There should be no retries since the response was None
        self.assertEqual(mock_sess.request.call_count, 1)

        # Test with a Service Unavailable exception
        mock_sess.reset_mock()
        hlp = functools.partial(vios_busy.vios_busy_retry_helper,
                                max_retries=1)
        error = pvmex.Error('yo', response=self.http_error_sa.response)
        mock_sess.request.side_effect = error
        adpt = adp.Adapter(mock_sess, helpers=hlp)
        self.assertRaises(
            pvmex.Error, adpt._request, 'method', 'path', body='the body')
        self.assertEqual(mock_sess.request.call_count, 2)
