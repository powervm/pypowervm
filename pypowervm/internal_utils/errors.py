# Copyright 2016 IBM Corp.
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

""" Internal Utility Class.  DO NOT USE for code not in pypowervm."""

from oslo_log import log as logging

# Set up logging
LOG = logging.getLogger(__name__)


def future_log_if_exception(fut, msgfmt, *msgargs):
    """Inspect a concurrent.futures Future and generate logs if it raised.

    If the fut param does not indicate an exception, this method does nothing
    and returns False.

    If the fut param indicates an exception, this method will generate an ERROR
    log using msgfmt and msgargs, as well as the traceback of fut's exception.

    :param fut: concurrent.futures.Future instance to inspect.
    :param msgfmt: Internationalized message for the ERROR log.
    :param msgargs: Positional arguments to LOG.error.
    :return: True if the future contains an exception; False otherwise.
    """
    exc, trb = fut.exception_info()
    if exc is None:
        return False
    LOG.error(msgfmt, *msgargs, exc_info=(exc.__class__, exc, trb))
    return True
