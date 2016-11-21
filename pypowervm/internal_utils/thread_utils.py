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

""" Internal Utilities.  SUBJECT TO CHANGE.  Only for use within pypowervm"""

import sys
import traceback


def submit_thread(th_pool, func, *args, **kwargs):
    """Runs a command.  Wraps the original traceback.

    In python 2.x, when running a future, the original traceback is lost.
    There are hacks you can do to get it, but those don't work in python 3.x.

    This method runs a future, and if an exception occurs it will wrap the
    result in a new exception that also has the original traceback.
    """
    def future_func(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            # Get the original exception type.  Recreate it with the original
            # traceback.
            exception_type = sys.exc_info()[0]
            raise exception_type(traceback.format_exc())

    return th_pool.submit(future_func, func, *args, **kwargs)
