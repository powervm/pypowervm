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
import pypowervm.entities as ent
import pypowervm.exceptions as pvmex

# Make UT a little easier
SLEEP = time.sleep

# Error codes that indicate the VIOS is busy
_VIOS_BUSY_ERR_CODES = ['HSCL3205', 'VIOS0014']


def _message_scrape(message):
    """Check HttpError message for strings indicating VIOS busy.

    :param message: The <Message/> field of the HttpError to check.
    :return: True if the message contains a string indicating VIOS busy; False
             otherwise.
    """
    # The old message met the following criteria
    if ('VIOS' in message and
            'is busy processing some other request' in message):
        return True

    # The new message format is the following
    if 'The system is currently too busy' in message:
        return True

    # All others, assume not busy
    return False


def is_vios_busy(message, status):
    """Determine whether the VIOS is busy, based on HttpErrorResponse data.

    :param message: The string value of the <Message/> field of the
                    HttpErrorResponse.
    :param status: The integer value of the <HTTPStatus/> field of the
                   HttpErrorResponse.
    :return: True if the VIOS is considered "busy"; False otherwise.
    """
    try:
        if any(code in message for code in _VIOS_BUSY_ERR_CODES):
            return True

        # Legacy message checks
        if status != c.HTTPStatus.INTERNAL_ERROR:
            return False

        return _message_scrape(message)

    except Exception:
        # If anything went wrong, assume not busy
        return False


def vios_busy_retry_helper(func, max_retries=3, delay=5):
    """This helper retries the request if the resource is busy.

    Args:
        func: The Adapter request method to call
        max_retries (int): Max number retries.
    """

    def is_retry(resp):
        """Determines if the error is one that can be retried."""
        # If the response is empty/invalid, assume no retry
        if not resp or not resp.body or not resp.entry:
            return False

        el = ent.Element.wrapelement(resp.entry.element, None)
        # If it is not an HttpError, it can't be retried.
        if el.tag != 'HttpErrorResponse':
            return False

        # Check if the VIOS is clearly busy, or if there is a service
        # unavailable.  The service unavailable can occur on child objects when
        # a VIOS is busy.
        message = el.find('Message')
        if message is not None:
            message = message.text.strip()
        status = el.find('HTTPStatus')
        if status is not None and status.text.isdigit():
            status = int(status.text.strip())
        else:
            status = None
        return (is_vios_busy(message, status) or
                status == c.HTTPStatus.SERVICE_UNAVAILABLE)

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
                if is_retry(e.response):
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
