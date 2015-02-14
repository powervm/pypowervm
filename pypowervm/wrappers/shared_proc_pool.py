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

import pypowervm.wrappers.entry_wrapper as ewrap

import logging

LOG = logging.getLogger(__name__)

import pypowervm.wrappers.constants as c


class SharedProcPool(ewrap.EntryWrapper):

    @property
    def id(self):
        """Integer shared processor pool ID."""
        return self.get_parm_value(c.POOL_ID, default=0, converter=int)

    @property
    def curr_rsrv_proc_units(self):
        """Floating point string: number of reserved processing units."""
        return self.get_parm_value(c.CURR_RSRV_PROC_UNITS, c.ZERO)
