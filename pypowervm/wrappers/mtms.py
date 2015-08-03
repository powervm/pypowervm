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

import pypowervm.wrappers.entry_wrapper as ewrap

# MTMS XPath constants
MTMS_ROOT = 'MachineTypeModelAndSerialNumber'
_MTMS_MT = 'MachineType'
_MTMS_MODEL = 'Model'
_MTMS_SERIAL = 'SerialNumber'


@ewrap.ElementWrapper.pvm_type(MTMS_ROOT, has_metadata=True)
class MTMS(ewrap.ElementWrapper):
    """The Machine Type, Model and Serial Number wrapper."""

    @classmethod
    def bld(cls, adapter, mtms_str):
        """Creates a new MTMS ElementWrapper.

        If mtms_str is specified, it is parsed first.

        If machine_type, model, and/or serial is specified, their values are
        used, overriding any parsed values from mtms_str.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param mtms_str: String representation of Machine Type, Model,
        and Serial
                     Number.  The format is
                     Machine Type - Model Number * Serial
                     Example: 8247-22L*1234567
        """
        mtms = super(MTMS, cls)._bld(adapter)
        mtm, sn = mtms_str.split('*', 1)
        mt, md = mtm.split('-', 1)

        # Assignment order is significant
        mtms.machine_type = mt
        mtms.model = md
        mtms.serial = sn
        return mtms

    @property
    def machine_type(self):
        return self._get_val_str(_MTMS_MT)

    @machine_type.setter
    def machine_type(self, mt):
        self.set_parm_value(_MTMS_MT, mt)

    @property
    def model(self):
        return self._get_val_str(_MTMS_MODEL)

    @model.setter
    def model(self, md):
        self.set_parm_value(_MTMS_MODEL, md)

    @property
    def serial(self):
        return self._get_val_str(_MTMS_SERIAL)

    @serial.setter
    def serial(self, sn):
        self.set_parm_value(_MTMS_SERIAL, sn)

    @property
    def mtms_str(self):
        """Builds a string representation of the MTMS.

        Does not override default __str__ as that is useful for debug
        purposes.
        """
        return self.machine_type + '-' + self.model + '*' + self.serial
