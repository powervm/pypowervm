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

_VIRTUAL_SERIAL_NUM = "VirtualSerialNumber"
_VSN_ASC_PARTITION = "AssociatedPartitionId"
_AUTO_ASSIGN_CAPBLE = "IsAutoAssignCapable"

_VSN_EL_ORDER = (_VIRTUAL_SERIAL_NUM,
                 _VSN_ASC_PARTITION,
                 _AUTO_ASSIGN_CAPBLE)


@ewrap.EntryWrapper.pvm_type('VirtualSerialNumberInformation',
                             child_order=_VSN_EL_ORDER)
class VirtualSerialNumber(ewrap.EntryWrapper):
    """Class VirtualSerialNumber.

    This corresponds to the abstract VirtualSerialNumber
    object in the PowerVM schema.
    """

    @classmethod
    def bld(cls, adapter, vsn):
        """For VirtualSerialNumber

        """

        vsnob = super(VirtualSerialNumber, cls)._bld(adapter)
        vsnob.vsn = vsn
        return vsnob

    @property
    def vsn(self):
        return self._get_val_str(_VIRTUAL_SERIAL_NUM)

    @vsn.setter
    def vsn(self, vsn):
        self.set_parm_value(_VIRTUAL_SERIAL_NUM, vsn)

    @property
    def assoc_partition_id(self):
        if self._get_val_str(_VSN_ASC_PARTITION) != '65535':
            return self._get_val_int(_VSN_ASC_PARTITION)
        else:
            return "-"

    @property
    def auto_assign(self):
        return self._get_val_bool(_AUTO_ASSIGN_CAPBLE)
