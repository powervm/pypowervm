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

import unittest

from pypowervm import adapter as adpt
from pypowervm import const as c
from pypowervm import exceptions as pvm_exc
from pypowervm.utils import retry as pvm_retry

called_count = 0


class TestRetry(unittest.TestCase):
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
        @pvm_retry.retry(tries=4, http_codes=(c.HTTPStatusEnum.ETAG_MISMATCH,))
        def http_except_method(x, y):
            global called_count
            called_count += 1
            resp = adpt.Response(
                'reqmethod', 'reqpath', c.HTTPStatusEnum.ETAG_MISMATCH,
                'reason', 'headers')
            http_exc = pvm_exc.HttpError('msg', resp)
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
            resp = adpt.Response(
                'reqmethod', 'reqpath', c.HTTPStatusEnum.ETAG_MISMATCH,
                'reason', 'headers')
            http_exc = pvm_exc.HttpError('msg', resp)
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
        self.assertRaises(OurException, func_except_method, 1, 2)
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
                resp = adpt.Response(
                    'reqmethod', 'reqpath', c.HTTPStatusEnum.ETAG_MISMATCH,
                    'reason', 'headers')
                http_exc = pvm_exc.HttpError('msg', resp)
                raise http_exc

            if called_count == 2:
                # Pretend we got a valid response, but the VIOS is busy
                return 'VIOS IS BUSY'

            if called_count == 3:
                # Pretend we got a good response
                return parm

            return None

        self.assertEqual(_powervm_update('Req'), 'Req')
        self.assertEqual(called_count, 3)


if __name__ == "__main__":
    unittest.main()
