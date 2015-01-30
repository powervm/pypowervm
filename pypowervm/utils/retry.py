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

from six import moves

from pypowervm import exceptions as exc
from pypowervm.wrappers import constants as const

RETRY_CODES = (const.HTTP_STATUS_ETAG_MISMATCH,)


def no_delay(try_, tries, *args, **kwds):
    pass


def retry(tries=3, delay_func=no_delay,
          retry_except=None, http_codes=None, test_func=None,
          resp_checker=None, limit_except=None):
    '''Retry method decorator

    :param tries: The max number of calls to the wrapped method.
    :param delay_func: A method to delay before retrying.
        Defaults to no delay.
        The parameters that are sent are:
            - the number of the current try
            - the maximum number of tries
            - the arguments to the decorated method
            - the keyword arguments to the decorated method
        No return value is expected.
    :param retry_except: A list of exceptions to retry if received.
        Defaults to no exceptions besides the HttpError which is
        handled separately by the http_codes parameter.
    :param http_codes: A list of http response codes to retry if received.
        Default is to not handle any specific http codes.
    :param test_func: A method to call to determine whether to retry.
        The parameters that are sent are:
            - the exception that was received
            - the number of the current try
            - the maximum number of tries
            - the arguments to the decorated method
            - the keyword arguments to the decorated method
        The return value is expected to be boolean, True or False, where
            True means to retry the decorated method.
    :param resp_checker: A method to call when no exception is caught, to
        check the response and determine whether to retry.
        The parameters that are sent are:
            - the number of the current try
            - the maximum number of tries
            - the arguments to the decorated method
            - the keyword arguments to the decorated method
        The return value is expected to be boolean, True or False, where
            True means to retry the decorated method.
    :param limit_except: An exception to raise if the number of tries is
        exhausted.
    :returns: The return value of the wrapped method.

    '''
    def _retry(func):
        @functools.wraps(func)
        def __retry(*args, **kwds):
            def test_retry(e):
                if (not _test_func(e, try_, _tries, *args, **kwds) or
                        try_ == _tries):
                    if _limit_except:
                        raise _limit_except
                    else:
                        raise
                return

            # Standardize input
            # For some reason, if we use the parms in an 'if' directly
            # python throws an exception.  Assigning them avoids it.
            _tries = tries
            _retry_except = retry_except
            _http_codes = http_codes
            _test_func = test_func
            _resp_checker = resp_checker
            _limit_except = limit_except
            if _retry_except is None:
                _retry_except = ()
            if _http_codes is None:
                _http_codes = ()
            if _test_func is None:
                caller_func = False
                _test_func = lambda *args, **kwds: True
            else:
                caller_func = True
            if _resp_checker is None:
                _resp_checker = lambda *args, **kwds: True
            # Start retries
            for try_ in moves.range(1, _tries+1):
                try:
                    resp = func(*args, **kwds)
                    # No exception raised, call the response checker
                    # If we're on the last iteration, we return the response
                    # the response checker should raise an exception if
                    # it doesn't want this behavior.
                    if (not _resp_checker(resp, try_, _tries, *args, **kwds)
                            or try_ == _tries):
                        return resp
                except exc.HttpError as e:
                    if caller_func or e.response.status in _http_codes:
                        test_retry(e)
                    else:
                        raise
                except _retry_except as e:
                        test_retry(e)
                # If we get here then we're going to retry
                delay_func(try_, _tries, *args, **kwds)
        return __retry
    return _retry
