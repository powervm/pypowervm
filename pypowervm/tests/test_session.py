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

import copy
import gc
import mock
import os
import requests.models as req_mod
import requests.structures as req_struct
import six
import subunit
import testtools

import pypowervm.adapter as adp
import pypowervm.exceptions as pvmex
import pypowervm.tests.lib as testlib
import pypowervm.tests.test_fixtures as fx

_logon_response_password = testlib.file2b("logon.xml")
_logon_response_file = testlib.file2b("logon_file.xml")


class TestSession(subunit.IsolatedTestCase, testtools.TestCase):
    """Test cases to test the Session classes and methods."""

    @mock.patch('time.sleep')
    @mock.patch('lxml.etree.fromstring', new=mock.Mock())
    @mock.patch('pypowervm.adapter.Session._get_auth_tok_from_file',
                new=mock.Mock())
    def test_Session(self, mock_sleep):
        """Ensure Session can be instantiated, and test logon retries."""
        # Passing in 0.0.0.0 will raise a ConnectionError or SSLError, but only
        # if it gets past all the __init__ setup since _logon is the last
        # statement.
        self.assertRaises((pvmex.ConnectionError, pvmex.SSLError), adp.Session,
                          '0.0.0.0', 'uid', 'pwd')
        mock_sleep.assert_not_called()
        # Now set up a retry
        self.assertRaises((pvmex.ConnectionError, pvmex.SSLError), adp.Session,
                          '0.0.0.0', 'uid', 'pwd', conn_tries=5)
        # 5 tries = 4 sleeps
        mock_sleep.assert_has_calls([mock.call(2)] * 4)
        # Ensure 404 on the logon URI also retries
        mock_sleep.reset_mock()
        with mock.patch('requests.Session.request') as mock_rq:
            mock_rq.side_effect = [mock.Mock(status_code=404),
                                   mock.Mock(status_code=204)]
            adp.Session(conn_tries=5)
            # Only retried once, after the 404
            mock_sleep.assert_called_once_with(2)

    @mock.patch('pypowervm.adapter.Session._logon', new=mock.Mock())
    @mock.patch('pypowervm.adapter._EventListener._get_events')
    def test_session_init(self, mock_get_evts):
        """Ensure proper parameter handling in the Session initializer."""
        mock_get_evts.return_value = {'general': 'init'}, [], []
        logfx = self.useFixture(fx.LoggingFx())
        # No params - local, file-based, http.
        sess = adp.Session()
        self.assertTrue(sess.use_file_auth)
        self.assertIsNone(sess.password)
        self.assertTrue(sess.username.startswith('pypowervm_'))
        self.assertEqual('localhost', sess.host)
        self.assertEqual('http', sess.protocol)
        self.assertEqual(12080, sess.port)
        self.assertEqual('http://localhost:12080', sess.dest)
        self.assertEqual(1200, sess.timeout)
        self.assertEqual('/etc/ssl/certs/', sess.certpath)
        self.assertEqual('.crt', sess.certext)
        # localhost + http is okay
        self.assertEqual(0, logfx.patchers['warning'].mock.call_count)

        # Verify unique session names
        sess2 = adp.Session()
        self.assertNotEqual(sess.username, sess2.username)

        # Ensure proper protocol, port, and certpath defaulting when remote
        sess = adp.Session(host='host', username='user', password='pass')
        self.assertFalse(sess.use_file_auth)
        self.assertIsNotNone(sess.password)
        self.assertEqual('user', sess.username)
        self.assertEqual('host', sess.host)
        self.assertEqual('https', sess.protocol)
        self.assertEqual(12443, sess.port)
        self.assertEqual('https://host:12443', sess.dest)
        self.assertEqual(1200, sess.timeout)
        self.assertEqual('/etc/ssl/certs/', sess.certpath)
        self.assertEqual('.crt', sess.certext)
        # non-localhost + (implied) https is okay
        self.assertEqual(0, logfx.patchers['warning'].mock.call_count)

    @mock.patch('pypowervm.adapter.Session._logon', new=mock.Mock())
    @mock.patch('pypowervm.adapter._EventListener._get_events')
    @mock.patch('imp.load_source')
    def test_session_ext_cfg(self, mock_load, mock_get_evts):
        """Test Session init with external config from env var."""
        mock_get_evts.return_value = {'general': 'init'}, [], []
        with mock.patch.dict(os.environ, {'PYPOWERVM_SESSION_CONFIG': 'path'}):
            sess = adp.Session()
        mock_load.assert_called_once_with('sesscfg', 'path')
        mock_load.return_value.session_config.assert_called_once_with(sess)

    @mock.patch('pypowervm.adapter.Session._logon')
    def test_session_init_remote_http(self, mock_logon):
        # Proper port defaulting and warning emitted when remote + http
        with self.assertLogs(adp.__name__, 'WARNING'):
            sess = adp.Session(host='host', protocol='http')
        self.assertEqual(12080, sess.port)

    @mock.patch.object(adp.Session, '_logon')
    @mock.patch.object(adp.Session, '_logoff')
    def test_session_clone(self, mock_logoff, mock_logon):

        sess = adp.Session()
        # Ensure the id that created the object is recorded.
        self.assertTrue(hasattr(sess, '_init_by'))

        # Create a shallow clone and ensure the _init_by does not match the id
        sess_clone = copy.copy(sess)
        self.assertTrue(hasattr(sess_clone, '_init_by'))
        self.assertNotEqual(sess._init_by, id(sess_clone))

        # Now test what happens when the clone is garbage collected.
        self.assertFalse(mock_logoff.called)
        sess_clone = None
        gc.collect()
        # The clone was not logged off
        self.assertFalse(mock_logoff.called)

        if six.PY2:
            # Ensure deep copies raise an exception.
            self.assertRaises(TypeError, copy.deepcopy, sess)
        else:
            # Or if works, it is not logged off
            sess_deepclone = copy.deepcopy(sess)
            # Make pep8 happy, use the clone
            self.assertIsNotNone(sess_deepclone)
            sess_deepclone = None
            gc.collect()
            # The clone was not logged off
            self.assertFalse(mock_logoff.called)

        sess = None
        gc.collect()
        # The original session was logged off
        self.assertTrue(mock_logoff.called)

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
                        'set-cookie': 'JSESSIONID=0000a41BnJsGTNQvBGERA3wR1nj:'
                                      '759878cb-4f9a-4b05-a09a-3357abfea3b4; P'
                                      'ath=/; Secure; HttpOnly, CCFWSESSION=E4'
                                      'C0FFBE9130431DBF1864171ECC6A6E; Path=/;'
                                      ' Secure; HttpOnly',
                        'expires': 'Thu, 01 Dec 1994 16:00:00 GMT',
                        'x-transaction-id': 'XT10000073',
                        'cache-control': 'no-cache="set-cookie, set-cookie2"',
                        'date': 'Wed, 23 Jul 2014 21:51:10 GMT',
                        'content-type': 'application/vnd.ibm.powervm.web+xml; '
                                        'type=LogonResponse'}
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
