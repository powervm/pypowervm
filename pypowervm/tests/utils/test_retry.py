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

from pypowervm import adapter as adpt
from pypowervm import const as c
from pypowervm import exceptions as pvm_exc
from pypowervm.utils import retry as pvm_retry

called_count = 0


class TestRetry(testtools.TestCase):
    """Unit tests for pypowervm.util."""

    def test_retry(self):
        global called_count

        # Test normal call with return values
        @pvm_retry.retry(tries=4)
        def some_method(x, y):
            global called_count
            called_count += 1
            return x, y

        called_count = 0
        val = some_method(1, 2)
        self.assertEqual(val, (1, 2))
        self.assertEqual(called_count, 1)

        # Test with an unexpected exception
        class OurException(Exception):
            pass

        @pvm_retry.retry(tries=4)
        def except_method(x, y):
            global called_count
            called_count += 1
            raise OurException()

        called_count = 0
        self.assertRaises(OurException, except_method, 1, 2)
        self.assertEqual(called_count, 1)

        # Test retry with an http code
        @pvm_retry.retry(tries=4, http_codes=(c.HTTPStatus.ETAG_MISMATCH,))
        def http_except_method(x, y):
            global called_count
            called_count += 1
            resp = adpt.Response('reqmethod', 'reqpath',
                                 c.HTTPStatus.ETAG_MISMATCH, 'reason',
                                 'headers', None)
            http_exc = pvm_exc.HttpError(resp)
            raise http_exc

        called_count = 0
        self.assertRaises(pvm_exc.HttpError, http_except_method, 1, 2)
        self.assertEqual(called_count, 4)

        # Test retry with an test func and custom exception
        def cust_test(e, try_, tries, *args, **kwds):
            return try_ != 2

        @pvm_retry.retry(tries=10, test_func=cust_test,
                         limit_except=OurException())
        def func_except_method(x, y):
            global called_count
            called_count += 1
            resp = adpt.Response('reqmethod', 'reqpath',
                                 c.HTTPStatus.ETAG_MISMATCH, 'reason',
                                 'headers', None)
            http_exc = pvm_exc.HttpError(resp)
            raise http_exc

        called_count = 0
        # Should get back OurException after just 2 calls
        self.assertRaises(OurException, func_except_method, 1, 2)
        self.assertEqual(called_count, 2)

        # Test custom exceptions to retry
        @pvm_retry.retry(tries=3, retry_except=OurException)
        def func_except_method(x, y):
            global called_count
            called_count += 1
            raise OurException()

        called_count = 0
        # Should get back OurException after just 3 calls
        with self.assertLogs(pvm_retry.__name__, 'WARNING') as warn_logs:
            self.assertRaises(OurException, func_except_method, 1, 2)
            self.assertEqual(2, len(warn_logs.output))
        self.assertEqual(called_count, 3)

        # Test the response checking function
        def resp_chkr(resp, try_, tries, *args, **kwds):
            if try_ == 2:
                raise OurException()
            # Tell it to retry
            return True

        @pvm_retry.retry(tries=10, resp_checker=resp_chkr)
        def func_resp_chkr(x, y):
            global called_count
            called_count += 1
            return x, y

        called_count = 0
        # Should get back OurException after just 2 calls
        self.assertRaises(OurException, func_resp_chkr, 1, 2)
        self.assertEqual(called_count, 2)

    def test_retry_example(self):
        global called_count
        called_count = 0

        def _resp_checker(resp, try_, _tries, *args, **kwds):
            # If the VIOS is busy, then retry
            return resp == 'VIOS IS BUSY'

        @pvm_retry.retry(tries=4, http_codes=pvm_retry.DFT_RETRY_CODES,
                         resp_checker=_resp_checker)
        def _powervm_update(parm):
            global called_count
            called_count += 1
            if called_count == 1:
                # etag mismatch
                resp = adpt.Response('reqmethod', 'reqpath',
                                     c.HTTPStatus.ETAG_MISMATCH, 'reason',
                                     'headers')
                http_exc = pvm_exc.HttpError(resp)
                raise http_exc

            if called_count == 2:
                # Pretend we got a valid response, but the VIOS is busy
                return 'VIOS IS BUSY'

            if called_count == 3:
                # Pretend we got a good response
                return parm

            return None

        with self.assertLogs(pvm_retry.__name__, 'WARNING') as warn_logs:
            self.assertEqual(_powervm_update('Req'), 'Req')
            # only one warning (etag mismatch).  The 'VIOS IS BUSY' is
            # returned as OK by the _resp_checker, but doesn't do its own
            # logging
            self.assertEqual(1, len(warn_logs.output))
            self.assertEqual(called_count, 3)

    def test_retry_argmod(self):
        global called_count
        called_count = 0

        def argmod_func(this_try, max_tries, *args, **kwargs):
            argl = list(args)
            if this_try == 1:
                argl[0] += 1
            kwargs['five'] += ' bar'
            if this_try == 2:
                kwargs['seven'] = 7
            return argl, kwargs

        @pvm_retry.retry(argmod_func=argmod_func,
                         resp_checker=lambda *a, **kwa: True)
        def _func(one, two, three='four', five='six', seven=None):
            global called_count
            called_count += 1
            self.assertEqual(20, two)
            self.assertEqual('four', three)
            if called_count == 1:
                self.assertEqual(10, one)
                self.assertEqual('foo', five)
                self.assertIsNone(seven)
            else:
                self.assertEqual(11, one)
                if called_count == 2:
                    self.assertEqual('foo bar', five)
                elif called_count == 3:
                    self.assertEqual(7, seven)
                    self.assertEqual('foo bar bar', five)

        _func(10, 20, five='foo')
        self.assertEqual(3, called_count)

    def test_retry_refresh_wrapper(self):
        """Test @retry with the 'refresh_wrapper' argmod_func."""
        global called_count
        called_count = 0
        mock_wrapper = mock.Mock()
        mock_wrapper.refreshes = 0

        def _refresh(**kwargs):
            mock_wrapper.refreshes += 1
            self.assertIn('use_etag', kwargs)
            self.assertFalse(kwargs['use_etag'])
            return mock_wrapper
        mock_wrapper.refresh.side_effect = _refresh

        @pvm_retry.retry(argmod_func=pvm_retry.refresh_wrapper,
                         resp_checker=lambda *a, **k: True)
        def _func(wrapper, arg1, arg2, kw0=None, kw1=None):
            global called_count
            self.assertEqual(called_count, wrapper.refreshes)
            # Ensure the other args didn't change
            self.assertEqual('a1', arg1)
            self.assertEqual('a2', arg2)
            self.assertEqual('k0', kw0)
            self.assertEqual('k1', kw1)
            called_count += 1
        _func(mock_wrapper, 'a1', 'a2', kw0='k0', kw1='k1')
        # Three calls (overall attempts)
        self.assertEqual(3, called_count)
        # ...equals two refreshes
        self.assertEqual(2, mock_wrapper.refreshes)

    @mock.patch('time.sleep')
    def test_stepped_delay(self, mock_sleep):
        # Last set of delays should hit the cap.
        delays = [0, .5, 2.0, 6.5, 20.0, 30.0, 30.0]
        for i in range(1, 7):
            pvm_retry.STEPPED_DELAY(i, 7)
            mock_sleep.assert_called_once_with(delays[i-1])
            mock_sleep.reset_mock()
