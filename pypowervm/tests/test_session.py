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

import logging
import unittest

import mock
import requests.models as req_mod
import requests.structures as req_struct

import pypowervm.adapter as adp
import pypowervm.exceptions as pvmex
import pypowervm.tests.lib as testlib

logging.basicConfig()

response_text = testlib.file2b("logon.xml")


class TestAdapter(unittest.TestCase):
    """Test cases to test the Adapter classes and methods."""

    @mock.patch('pypowervm.adapter.LOG.warn')
    def test_Session(self, mock_log):
        """This test is just meant to ensure Session can be instantiated."""
        # Passing in 0.0.0.0 will raise a ConnectionError, but only if it
        # gets past all the __init__ setup since _logon is the last statement.
        self.assertRaises(pvmex.ConnectionError, adp.Session, '0.0.0.0',
                          'uid', 'pwd')
        mock_log.assert_called_once_with(mock.ANY)

    @mock.patch('requests.Session')
    def test_logon(self, mock_session):
        """Ensure a Session can be created and log on to PowerVM."""

        # Init test data
        host = '0.0.0.0'
        user = 'user'
        pwd = 'pwd'
        auditmemento = 'audit'

        # Create a Response object, that will serve as a mock return value
        my_response = req_mod.Response()
        my_response.status_code = 200
        my_response.reason = 'OK'
        dict_headers = {'content-length': '576',
                        'x-powered-by': 'Servlet/3.0',
                        'set-cookie': 'JSESSIONID=0000a41BnJsGTNQvBGERA' +
                        '3wR1nj:759878cb-4f9a-4b05-a09a-3357abfea3b4; ' +
                        'Path=/; Secure; HttpOnly, CCFWSESSION=E4C0FFBE9' +
                        '130431DBF1864171ECC6A6E; Path=/; Secure; HttpOnly',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000073',
                        'cache-control': 'no-cache="set-cookie, ' +
                                         'set-cookie2"',
                        'date': 'Wed, 23 Jul 2014 21:51:10 GMT',
                        'content-type': 'application/vnd.ibm.powervm' +
                                        '.web+xml; type=LogonResponse'}
        my_response.headers = req_struct.CaseInsensitiveDict(dict_headers)
        my_response._content = response_text

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = my_response

        # Run the actual test
        result = adp.Session(host, user, pwd, auditmemento=auditmemento,
                             certpath=None)

        # Verify the result
        self.assertTrue(result._logged_in)
