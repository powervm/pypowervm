# Copyright 2020 IBM Corp.
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

"""Base classes, enums, and constants for Persistent Memory EntryWrappers."""

import pypowervm.wrappers.entry_wrapper as ewrap

_VM_NAME = "VmName"
_VM_ID = "VmID"
_AFFINITY = "Affinity"

@ewrap.EntryWrapper.pvm_type('GetDPOStatus')
class DPO(ewrap.EntryWrapper):
    """Class VirtualSerialNumber.

    This corresponds to the abstract VirtualSerialNumber
    object in the PowerVM schema.
    """
    @classmethod
    def bld(cls, adapter, lpar_id, lpar_name, affinity):
        """For VirtualSerialNumber

        """
        dpob = super(DPO, cls)._bld(adapter)
        dpob.id = lpar_id
        dpob.vm = lpar_name
        dpob.affinity = affinity
        return dpob

    @property
    def vm(self):
        return self._get_val_str(_VM_NAME)

    @vm.setter
    def vm(self, vm):
        self.set_parm_value(_VM_NAME, vm)

    @property
    def id(self):
        return self._get_val_str(_VM_ID)

    @id.setter
    def id(self, id):
        self.set_parm_value(_VM_ID, id)

    @property
    def affinity(self):
        return self._get_val_str(_AFFINITY)

    @affinity.setter
    def affinity(self, affinity):
        self.set_parm_value(_AFFINITY, affinity)
