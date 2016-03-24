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

"""SharedProcPool, the EntryWrapper for SharedProcessorPool."""

from oslo_log import log as logging

import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

DEFAULT_POOL_DISPLAY_NAME = 'DefaultPool'

# Shared Processor Pool Constants
_POOL_ID = 'PoolID'
_CURR_RSRV_PROC_UNITS = 'CurrentReservedProcessingUnits'
_ASSIGNED_PARTITIONS = 'AssignedPartitions'
_MAX_PROC_UNITS = 'MaximumProcessingUnits'
_PEND_RSRV_PROC_UNITS = 'PendingReservedProcessingUnits'
_AVAL_PROC_UNITS = 'AvailableProcUnits'
_POOL_NAME = 'PoolName'
_SHARED_EL_ORDER = (_ASSIGNED_PARTITIONS, _CURR_RSRV_PROC_UNITS,
                    _MAX_PROC_UNITS, _PEND_RSRV_PROC_UNITS,
                    _POOL_ID, _AVAL_PROC_UNITS, _POOL_NAME)


@ewrap.EntryWrapper.pvm_type('SharedProcessorPool',
                             child_order=_SHARED_EL_ORDER)
class SharedProcPool(ewrap.EntryWrapper):

    @property
    def id(self):
        """Integer shared processor pool ID."""
        return self._get_val_int(_POOL_ID, default=0)

    @property
    def curr_rsrv_proc_units(self):
        """Floating point number of reserved processing units."""
        return self._get_val_float(_CURR_RSRV_PROC_UNITS, 0)

    @property
    def is_default(self):
        """If true, is the default processor pool."""
        return self.id == 0

    @property
    def name(self):
        """The name of the processor pool."""
        return self._get_val_str(_POOL_NAME)

    @name.setter
    def name(self, value):
        self.set_parm_value(_POOL_NAME, value)

    @property
    def max_proc_units(self):
        """Floating point number of the max processing units."""
        return self._get_val_float(_MAX_PROC_UNITS, 0)

    @max_proc_units.setter
    def max_proc_units(self, value):
        self.set_parm_value(_MAX_PROC_UNITS, u.sanitize_float_for_api(value))

    @property
    def pend_rsrv_proc_units(self):
        """Floating point number of pending reserved proc units."""
        return self._get_val_float(_PEND_RSRV_PROC_UNITS, 0)

    @pend_rsrv_proc_units.setter
    def pend_rsrv_proc_units(self, value):
        self.set_parm_value(_PEND_RSRV_PROC_UNITS,
                            u.sanitize_float_for_api(value))

    @property
    def avail_proc_units(self):
        """Returns the available proc units in the pool.

        If the default pool, will return 0.
        """
        return self._get_val_float(_AVAL_PROC_UNITS, 0)
