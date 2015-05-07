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

"""Example of an Adapter helper.

Helpers can be associated with an Adapter or on an individual request.
They take as their first parameter the next helper or request method to
call to handle the request / response.

"""
import time

import pypowervm.exceptions as pvmex

BUSY_ERR_CODES = ['HSCL3205']


def sample_retry_helper(func, max_retries=1):
    """This helper retries the request if the resource is busy.

    Args:
        func: The Adapter request method to call
        max_logs (int): Max number retries.
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
                if resp.body is not None:
                    resp_body = str(resp.body)
                    if any(code in resp_body
                           for code in BUSY_ERR_CODES):
                        retries += 1
                        if retries <= max_retries:
                            # Wait a few seconds before trying again
                            time.sleep(5 * retries)
                            continue
                raise e
            else:
                return resp

    return wrapper
