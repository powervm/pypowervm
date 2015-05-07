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

"""This Adapter helper retries a request when 'VIOS busy' error is detected."""

import time

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
    def wrapper(*args, **kwds):
        retries = 0
        while True:
            try:
                # Call the request()
                resp = func(*args, **kwds)
            except pvmex.Error as e:
                resp = e.response
                # See if the system was busy

                if resp.body and resp.entry:
                    wrap = ew.EntryWrapper.wrap(resp.entry)
                    if (isinstance(wrap, he.HttpError) and
                            wrap.is_vios_busy()):
                        retries += 1
                        if retries <= max_retries:
                            # Wait a few seconds before trying again, scaling
                            # out the delay based on the retry count.
                            SLEEP(delay * retries)
                            continue
                # Doesn't look like a VIOS busy error, so just raise it.
                raise
            else:
                return resp

    return wrapper
