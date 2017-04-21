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

""" Wrappers to parse the PCM JSON data from IBM.Host Resource Manager. """

import json


class LparInfo(object):
    """Represents a monitor sample from the IBM.Host Resource Manager.

    The Lpar JSON utilization data has the following structure:
    - LparUtil
      - LparMemory
    lpar_metrics are generally collected once every two minutes, as opposed
    to the other data which is collected every 30 seconds.
    """

    def __init__(self, raw_json):
        data = json.loads(raw_json)
        self._lparuuid_to_util_dict = dict()
        lpar_util_list = list()
        lpar_metric_list_rsct = data.get('lparUtil')
        for lpar_metrics_rsct in lpar_metric_list_rsct:
            if 'errorInfo' in lpar_metrics_rsct:
                error_code = lpar_metrics_rsct['errorInfo']['errorId']
                if error_code in ('6001', '6003'):
                    self._create_lpar_memory_util_for_errored_vm(
                        error_code, lpar_metrics_rsct)
                else:
                    # Any other errors that might get introduced at neo-rest.
                    continue
            lpar_util = LparUtil(lpar_metrics_rsct)
            lpar_util_list.append(lpar_util)
            self._lparuuid_to_util_dict[lpar_util.uuid] = lpar_util
        self._lpars_util = lpar_util_list

    def find(self, lpar_uuid):
        return self._lparuuid_to_util_dict.get(lpar_uuid, None)

    def _create_lpar_memory_util_for_errored_vm(
            self, error_code, lpar_metrics_rsct):
        if error_code == '6001':
            # If LPAR is powered off, then no memory is being used.
            memory = dict(pctRealMemFree=100,
                          vmPgInRate=0,
                          vmPgOutRate=0,
                          vmPgSpInRate=0,
                          vmPgSpOutRate=0)
        elif error_code == '6003':
            # If LPAR has inactive RMC, then assume all memory is being used.
            memory = dict(pctRealMemFree=0)
        lpar_metrics_rsct['memory'] = memory

    @property
    def lpars_util(self):
        return self._lpars_util


class LparUtil(object):
    """Represents individual Lpar metric information. """
    def __init__(self, lpar_util):
        self._uuid = lpar_util.get('uuid')
        self._lpar_id = lpar_util.get('id')
        self._name = lpar_util.get('name')
        self._timestamp = lpar_util.get('timestamp')
        self._memory = LparMemory(lpar_util.get('memory'))

    @property
    def lpar_id(self):
        return self._lpar_id

    @property
    def uuid(self):
        return self._uuid

    @property
    def name(self):
        return self._name

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def memory(self):
        return self._memory


class LparMemory(object):
    """Represents information on Lpar memory utilization """
    def __init__(self, memory):
        self._pct_real_mem_avbl = memory.get('pctRealMemAvbl')
        self._total_pg_count = memory.get('totalPgSpSizeCount')
        self._free_pg_count = memory.get('totalPgSpFreeCount')
        self._active_pg_count = memory.get('vmActivePgCount')
        self._real_mem_size_bytes = memory.get('realMemSizeBytes')
        self._pct_real_mem_free = memory.get('pctRealMemFree')
        self._vm_pg_in_rate = memory.get('vmPgInRate')
        self._vm_pg_out_rate = memory.get('vmPgOutRate')
        self._vm_pg_swap_in_rate = memory.get('vmPgSpInRate')
        self._vm_pg_swap_out_rate = memory.get('vmPgSpOutRate')

    @property
    def pct_real_mem_avbl(self):
        return self._pct_real_mem_avbl

    @property
    def total_pg_count(self):
        return self._total_pg_count

    @property
    def free_pg_count(self):
        return self._free_pg_count

    @property
    def active_pg_count(self):
        return self._active_pg_count

    @property
    def real_mem_size_bytes(self):
        return self._real_mem_size_bytes

    @property
    def pct_real_mem_free(self):
        return self._pct_real_mem_free

    @property
    def vm_pg_in_rate(self):
        return self._vm_pg_in_rate

    @property
    def vm_pg_out_rate(self):
        return self._vm_pg_out_rate

    @property
    def vm_pg_swap_in_rate(self):
        return self._vm_pg_swap_in_rate

    @property
    def vm_pg_swap_out_rate(self):
        return self._vm_pg_swap_out_rate
