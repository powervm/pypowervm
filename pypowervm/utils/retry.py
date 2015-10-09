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

"""Utility decorator to retry the decorated method."""

import functools
import time

from oslo_log import log as logging
from six import moves

from pypowervm import const
from pypowervm import exceptions as exc
from pypowervm.i18n import _


LOG = logging.getLogger(__name__)

DFT_RETRY_CODES = frozenset([const.HTTPStatus.ETAG_MISMATCH])

NO_TEST = lambda *args, **kwds: True
NO_CHECKER = lambda *args, **kwds: False
NO_DELAY = lambda *args, **kwds: None
NO_ARGMOD = lambda this_try, max_tries, *args, **kwds: (args, kwds)


def STEPPED_DELAY(attempt, max_attempts, *args, **kwds):
    """A delay function that increases its delay per attempt.

    The steps will be:
     - Attempt 1: 0.0s
     - Attempt 2: 0.5s
     - Attempt 3: 2.0s
     - Attempt 4: 6.5s
     - Attempt 5: 20s
     - Attempt 6+: 30s
    """
    sleep_time = (0.25 * (3**(attempt-1)) - 0.25)
    time.sleep(min(sleep_time, 30))


def refresh_wrapper(trynum, maxtries, *args, **kwargs):
    """A @retry argmod_func to refresh a Wrapper, which must be the first arg.

    When using @retry to decorate a method which modifies a Wrapper, a common
    cause of retry is etag mismatch.  In this case, the retry should refresh
    the wrapper before attempting the modifications again.  This method may be
    passed to @retry's argmod_func argument to effect such a refresh.

    Note that the decorated method must be defined such that the wrapper is its
    first argument.
    """
    arglist = list(args)
    # If we get here, we *usually* have an etag mismatch, so specifying
    # use_etag=False *should* be redundant.  However, for scenarios where we're
    # retrying for some other reason, we want to guarantee a fresh fetch to
    # obliterate any local changes we made to the wrapper (because the retry
    # should be making those changes again).
    arglist[0] = arglist[0].refresh(use_etag=False)
    return arglist, kwargs


def retry(tries=3, delay_func=NO_DELAY,
          retry_except=None, http_codes=DFT_RETRY_CODES, test_func=None,
          resp_checker=NO_CHECKER, limit_except=None, argmod_func=NO_ARGMOD):
    """Retry method decorator.

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
    :param test_func: A method to call to determine whether to retry. This
        method takes precedence over http codes. That is, if specified, the
        http codes are not considered.
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
    :param argmod_func: A method to call after delay_func, before retrying, to
                        modify the arguments to the main method.  The input
                        parameters are:
                            - the number of the current try
                            - the maximum number of tries
                            - the non-keyword arguments to the decorated method
                            - the keyword arguments to the decorated method
                        The return is expected to a list and a dict of the
                        new arguments to the decorated method.
                        Example:
                        def argmod(t, m, *a, **k):
                            l = list(a)
                            l[0] += 1
                            k['foo'] = bar
                            return l, k
    :returns: The return value of the wrapped method.
    """
    def _retry(func):
        @functools.wraps(func)
        def __retry(*args, **kwds):
            def _raise_exc():
                if _limit_except:
                    raise _limit_except
                else:
                    raise

            def _test_retry(e):
                # Determine if an exception should be raised
                if (not _test_func(e, try_, _tries, *args, **kwds) or
                        try_ == _tries):
                    _raise_exc()
                # Otherwise, we will continue trying
                return

            def _log_response_retry(try_, max_tries, uri, resp_code):
                LOG.warn(_('Attempt %(retry)d of total %(total)d for URI '
                           '%(uri)s.  Error was a known retry response code: '
                           '%(resp_code)s'),
                         {'retry': try_, 'total': max_tries, 'uri': uri,
                          'resp_code': resp_code})

            def _log_exception_retry(try_, max_tries, exc):
                LOG.warn(_('Attempt %(retry)d of %(total)d failed.  Will '
                           'retry. The exception was:\n %(except)s.'),
                         {'retry': try_, 'total': max_tries, 'except': exc})

            # Standardize input
            # For some reason, if we use the parms in an 'if' directly
            # python throws an exception.  Assigning them avoids it.
            _tries = tries
            _retry_except = retry_except
            _http_codes = http_codes
            _test_func = test_func
            _resp_checker = resp_checker
            _limit_except = limit_except
            _argmod_func = argmod_func

            if _retry_except is None:
                _retry_except = ()
            if _http_codes is None:
                _http_codes = ()
            caller_test_func = _test_func is not None
            if not caller_test_func:
                _test_func = NO_TEST
            if _resp_checker is None:
                _resp_checker = NO_CHECKER
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
                    if caller_test_func or e.response.status in _http_codes:
                        _test_retry(e)
                        _log_response_retry(try_, _tries, e.response.reqpath,
                                            e.response.status)
                    else:
                        _raise_exc()
                except _retry_except as e:
                    _test_retry(e)
                    _log_exception_retry(try_, _tries, e)
                # If we get here then we're going to retry
                delay_func(try_, _tries, *args, **kwds)
                # Adjust arguments if necessary
                args, kwds = _argmod_func(try_, _tries, *args, **kwds)
        return __retry
    return _retry
