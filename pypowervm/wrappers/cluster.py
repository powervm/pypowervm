# Copyright 2015 IBM Corp.
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

import logging

import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)

# Shared Storage Pool Constants
SSP_NAME = 'StoragePoolName'
SSP_CAPACITY = 'Capacity'
SSP_FREE_SPACE = 'FreeSpace'
SSP_TOTAL_LU_SIZE = 'TotalLogicalUnitSize'
SSP_LUS = 'LogicalUnits'
SSP_LU = 'LogicalUnit'


class SharedStoragePool(ewrap.EntryWrapper):
    """A Shared Storage Pool containing PVs and LUs."""

    @property
    def name(self):
        return self.get_parm_value(SSP_NAME)

    @property
    def udid(self):
        return self.get_parm_value(c.UDID)

    @property
    def capacity(self):
        """Float capacity in GB."""
        return float(self.get_parm_value(SSP_CAPACITY))

    @property
    def free_space(self):
        """Float free space in GB."""
        return float(self.get_parm_value(SSP_FREE_SPACE))

    @property
    def total_lu_size(self):
        """Float total LU size in GB."""
        return float(self.get_parm_value(SSP_TOTAL_LU_SIZE))

    @property
    def logical_units(self):
        """WrapperElemList of LogicalUnit wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(SSP_LUS),
                                     SSP_LU, stor.LogicalUnit)

    @logical_units.setter
    def logical_units(self, lus):
        self.replace_list(SSP_LUS, lus)

    @property
    def physical_volumes(self):
        """WrapperElemList of PhysicalVolume wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(c.PVS),
                                     c.PV, stor.PhysicalVolume)

    @physical_volumes.setter
    def physical_volumes(self, pvs):
        self.replace_list(c.PVS, pvs)
