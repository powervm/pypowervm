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

"""This Adapter helper logs recent requests/responses on an exception."""

import collections
import copy
import threading

from oslo_log import log as logging

import pypowervm.const as c
import pypowervm.exceptions as pvmex
from pypowervm.i18n import _


LOG = logging.getLogger(__name__)

log_store = threading.local()


def _init_thread_stg(max_entries):
    """Sets up the storage for the logs for this thread."""
    if not hasattr(log_store, 'powervm_log'):
        log_store.powervm_log = collections.deque(maxlen=max_entries)


def _stash(sensitive, type_, value):
    """Enters the request or response in the thread log."""
    if sensitive:
        value = '<SENSITIVE>'
    log_store.powervm_log.append({type_: value})


def _stash_response(sensitive, resp):
    if resp is not None:
        logged_resp = dict(resp.__dict__)
        # Remove feed and entry from the dictionary of response attributes.
        # This avoids keeping heavy ElementTree objects in memory since
        # only the string version of the body is dumped for responses.
        logged_resp.pop('entry', None)
        logged_resp.pop('feed', None)
        _stash(sensitive, 'response', logged_resp)


def _write_thread_log():
    def format_request(req):
        body = None
        # Parse the arguments if we're passed a tuple else its a string
        if isinstance(req, tuple):
            req_args = req[0]
            req_kwds = req[1]
            dump = dict(method=req_args[0], path=req_args[1])
            for key in req_kwds:
                if key == 'body':
                    # special format for body
                    body = req_kwds.get('body')
                elif key == 'headers':
                    # deep copy the header and change what we can't dump
                    headers = copy.deepcopy(req_kwds.get(key))
                    if 'X-API-Session' in headers:
                        headers['X-API-Session'] = '<SENSITIVE>'
                    dump[key] = str(headers)
                else:
                    dump[key] = str(req_kwds.get(key))
        else:
            dump = req

        # Dump all fields besides the body
        LOG.info(_('REQUEST: %s') % dump)
        # Now dump the full body
        if body is not None:
            LOG.info(body)

    def format_response(resp):
        body = None
        # Parse the arguments if we're passed a dict else it's a string
        if isinstance(resp, dict):
            dump = {}
            for key in resp:
                if key == 'body':
                    # special format for body
                    body = resp.get('body')
                else:
                    dump[key] = str(resp.get(key))
        else:
            dump = resp

        # Dump all fields besides the body first
        LOG.info(_('RESPONSE: %s') % dump)
        # Now dump the full body, on the next line, if available
        if body is not None:
            LOG.info(body)

    # Pop each entry out of the log until it's empty
    try:
        while True:
            entry = log_store.powervm_log.popleft()
            request = entry.get('request')
            if request is not None:
                format_request(request)

            response = entry.get('response')
            if response is not None:
                format_response(response)
    except IndexError:
        pass


def log_helper(func, max_logs=3):
    """Log recent requests/responses on exception.

    This helper stashes the requests/responses it sees passing through to
    thread local storage.  If it then sees an exception surfacing, it will
    write the req/resp logs.

    :param func: The Adapter request method to call
    :param max_logs (int): Max number of req/resps to retain at a time
            This value can only be set once per thread.
            Once it's set, subsequent calls will ignore the value.
    """
    def is_etag_mismatch(ex):
        """Is ex an HttpError with status 412 (etag mismatch)?"""
        return (isinstance(ex, pvmex.HttpError) and
                ex.response.status == c.HTTPStatus.ETAG_MISMATCH)

    def log_req_resp(*args, **kwds):
        # Set aside storage for a req/resp pair
        _init_thread_stg(max_entries=(max_logs * 2))

        # See if this request has sensitive data
        sensitive = kwds.get('sensitive', False)
        # Log the request before the call
        _stash(sensitive, 'request', (args, kwds))
        try:
            # Call the request()
            response = func(*args, **kwds)
        except pvmex.Error as e:
            _stash_response(sensitive, e.response)
            # Now dump the log and raise the exception.
            # Special case for 412 (etag mismatch) - don't dump.
            if not is_etag_mismatch(e):
                _write_thread_log()
            raise
        else:
            _stash_response(sensitive, response)
            return response

    return log_req_resp
