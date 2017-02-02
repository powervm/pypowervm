# Copyright 2014, 2017 IBM Corp.
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

"""Logging helpers."""

import functools
import logging

from oslo_log import log as oslo_logging

LOG = oslo_logging.getLogger('pypowervm')


def _logcall(filter_=None, dump_parms=False):
    def func_parms(f):
        @functools.wraps(f)
        def wrapper(*args, **kwds):
            logging_dbg = LOG.isEnabledFor(logging.DEBUG)
            if logging_dbg:
                if dump_parms:
                    d_args, d_kwds = ((args, kwds)
                                      if filter_ is None else filter_(*args,
                                                                      **kwds))
                    LOG.debug("Entering args:%s kwds:%s  '%s' %s" %
                              (d_args, d_kwds, f.__name__, f.__module__))
                else:
                    LOG.debug("Entering '%s' %s" % (f.__name__, f.__module__))

            r = f(*args, **kwds)
            if logging_dbg:
                if dump_parms:
                    LOG.debug("Exiting: return '%s'  '%s' %s" %
                              (r, f.__name__, f.__module__))
                else:
                    LOG.debug("Exiting: return '%s' %s" %
                              (f.__name__, f.__module__))
            return r
        return wrapper
    return func_parms

logcall = _logcall()
logcall_args = _logcall(dump_parms=True)
