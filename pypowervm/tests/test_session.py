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

_logon_response_password = testlib.file2b("logon.xml")
_logon_response_file = testlib.file2b("logon_file.xml")


class TestAdapter(unittest.TestCase):
    """Test cases to test the Adapter classes and methods."""

    def test_Session(self):
        """This test is just meant to ensure Session can be instantiated."""
        # Passing in 0.0.0.0 will raise a ConnectionError, but only if it
        # gets past all the __init__ setup since _logon is the last statement.
        self.assertRaises(pvmex.ConnectionError, adp.Session, '0.0.0.0',
                          'uid', 'pwd')

    @mock.patch('pypowervm.adapter.LOG.warn')
    @mock.patch('pypowervm.adapter.Session._logon')
    def test_session_init(self, mock_logon, mock_log_warn):
        """Ensure proper parameter handling in the Session initializer."""
        # No params - local, file-based, http.
        sess = adp.Session()
        self.assertTrue(sess.use_file_auth)
        self.assertIsNone(sess.password)
        self.assertTrue(sess.username.startswith('pypowervm_'))
        self.assertEqual('localhost', sess.host)
        self.assertEqual('http', sess.protocol)
        self.assertEqual(12080, sess.port)
        self.assertEqual('http://localhost:12080', sess.dest)
        self.assertEqual(60, sess.timeout)
        self.assertEqual('/etc/ssl/certs/', sess.certpath)
        self.assertEqual('.crt', sess.certext)
        # localhost + http is okay
        self.assertEqual(0, mock_log_warn.call_count)

        # Ensure proper protocol, port, and certpath defaulting when remote
        sess = adp.Session(host='host', username='user', password='pass')
        self.assertFalse(sess.use_file_auth)
        self.assertIsNotNone(sess.password)
        self.assertEqual('user', sess.username)
        self.assertEqual('host', sess.host)
        self.assertEqual('https', sess.protocol)
        self.assertEqual(12443, sess.port)
        self.assertEqual('https://host:12443', sess.dest)
        self.assertEqual(60, sess.timeout)
        self.assertEqual('/etc/ssl/certs/', sess.certpath)
        self.assertEqual('.crt', sess.certext)
        # non-localhost + (implied) https is okay
        self.assertEqual(0, mock_log_warn.call_count)

        # Proper port defaulting and warning emitted when remote + http
        sess = adp.Session(host='host', protocol='http')
        self.assertEqual(12080, sess.port)
        self.assertEqual(1, mock_log_warn.call_count)

    @mock.patch('pypowervm.util.validate_certificate')
    @mock.patch('requests.Session')
    def test_logon(self, mock_session, mock_validate_cert):
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
        my_response._content = _logon_response_password

        # Mock out the method and class we are not currently testing
        session = mock_session.return_value
        session.request.return_value = my_response

        # Run the actual test
        result = adp.Session(host, user, pwd, auditmemento=auditmemento)

        # Verify the result
        self.assertTrue(result._logged_in)
        self.assertEqual('PUIoR6x0kP6fQqA7qZ8sLZQJ8MLx9JHfLCYzT4oGFSE2WaGIhaFX'
                         'IyQYvbqdKNS8QagjBpPi9NP7YR_h61SOJ3krS_RvKAp-oCf2p8x8'
                         'uvQrrDv-dUzc17IT5DkR7_jv2qc8iUD7DJ6Rw53a17rY0p63KqPg'
                         '9oUGd6Bn3fNDLiEwaBR4WICftVxUFj-tfWMOyZZY2hWEtN2K8ScX'
                         'vyFMe-w3SleyRbGnlR34jb0A99s=', result._sessToken)
        self.assertEqual(1, mock_validate_cert.call_count)
        # No X-MC-Type header => 'HMC' is assumed.
        self.assertEqual('HMC', result.mc_type)

        # Now test file-based authentication and X-MC-Type
        my_response._content = _logon_response_file

        # Local/HMC is bad
        self.assertRaises(pvmex.Error, adp.Session)

        my_response.headers['X-MC-Type'] = 'PVM'
        result = adp.Session()

        # Verify the result.
        self.assertTrue(result._logged_in)
        # Token read from token_file, as indicated by logon_file.xml response.
        self.assertEqual('file-based-auth-token', result._sessToken)
        # validate_certificate should not have been called again
        self.assertEqual(1, mock_validate_cert.call_count)
        self.assertEqual('PVM', result.mc_type)
