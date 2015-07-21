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

"""This Adapter helper retries a request when 'VIOS busy' error is detected.

A 'VIOS busy' error usually means the VIOS is processing another operation
which is mutually exclusive with the submitted request.  If this state
persists, it may mean the VIOS is in need of manual intervention.
"""

import time

import pypowervm.const as c
import pypowervm.exceptions as pvmex
import pypowervm.wrappers.entry_wrapper as ew
import pypowervm.wrappers.http_error as he

# Make UT a little easier
SLEEP = time.sleep


def vios_busy_retry_helper(func, max_retries=3, delay=5):
    """This helper retries the request if the resource is busy.

    Args:
        func: The Adapter request method to call
        max_retries (int): Max number retries.
    """

    def is_retry(http_error):
        """Determines if the error is one that can be retried."""
        # If for some reason it is not an Http Error, it can't be retried.
        if not isinstance(http_error, he.HttpError):
            return False

        # Check if the VIOS is clearly busy, or if there is a service
        # unavailable.  The service unavailable can occur on child objects when
        # a VIOS is busy.
        return (http_error.is_vios_busy() or
                http_error.status == c.HTTPStatus.SERVICE_UNAVAILABLE)

    def wrapper(*args, **kwds):
        retries = 0
        while True:
            try:
                # Call the request()
                resp = func(*args, **kwds)
            except pvmex.Error as e:
                # See if there are any retries left.
                if retries >= max_retries:
                    raise

                # See if the system was busy
                resp = e.response
                if resp and resp.body and resp.entry:
                    wrap = ew.EntryWrapper.wrap(resp.entry)
                    if is_retry(wrap):
                        retries += 1
                        # Wait a few seconds before trying again, scaling
                        # out the delay based on the retry count.
                        SLEEP(delay * retries)
                        continue

                # Doesn't look like a VIOS busy error, so just raise it.
                raise
            else:
                return resp

    return wrapper
