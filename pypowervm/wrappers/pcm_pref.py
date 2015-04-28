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

import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

import logging

_SYSTEM_NAME = 'SystemName'
_LTM_ENABLED = 'LongTermMonitorEnabled'
_AGG_ENABLED = 'AggregationEnabled'
_STM_ENABLED = 'ShortTermMonitorEnabled'
_COMP_LTM_ENABLED = 'ComputeLTMEnabled'

LOG = logging.getLogger(__name__)


@ewrap.EntryWrapper.pvm_type('ManagedSystemPcmPreference')
class PcmPref(ewrap.EntryWrapper):

    @property
    def system_name(self):
        return self._get_val_str(_SYSTEM_NAME)

    @property
    def ltm_enabled(self):
        return self._get_val_bool(_LTM_ENABLED)

    @ltm_enabled.setter
    def ltm_enabled(self, value):
        self.set_parm_value(_LTM_ENABLED, u.sanitize_bool_for_api(value))

    @property
    def aggregation_enabled(self):
        return self._get_val_bool(_AGG_ENABLED)

    @aggregation_enabled.setter
    def aggregation_enabled(self, value):
        self.set_parm_value(_AGG_ENABLED, u.sanitize_bool_for_api(value))

    @property
    def stm_enabled(self):
        return self._get_val_bool(_STM_ENABLED)

    @stm_enabled.setter
    def stm_enabled(self, value):
        self.set_parm_value(_STM_ENABLED, u.sanitize_bool_for_api(value))

    @property
    def compute_ltm_enabled(self):
        return self._get_val_bool(_COMP_LTM_ENABLED)

    @compute_ltm_enabled.setter
    def compute_ltm_enabled(self, value):
        self.set_parm_value(_COMP_LTM_ENABLED, u.sanitize_bool_for_api(value))
