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
    """

    def __init__(self, raw_json):
        data = json.loads(raw_json)
        lpar_util_list = list()
        lpar_metric_list_rsct = data.get('lparUtil')
        for lpar_metrics_rsct in lpar_metric_list_rsct:
            if 'errorInfo' in lpar_metrics_rsct:
                # Lpar was in error. We do not have metrics info for it.
                continue
            lpar_util = LparUtil(lpar_metrics_rsct)
            lpar_util_list.append(lpar_util)
        self._lpars_util = lpar_util_list

    def to_dict(self):
        """ Returns dict of form {lpar_uuid: LparUtil}. """
        lparuuid_to_util_dict = dict()
        for lpar_util in self.lpars_util:
            lparuuid_to_util_dict[lpar_util.uuid] = lpar_util
        return lparuuid_to_util_dict

    @property
    def lpars_util(self):
        return self._lpars_util

    @lpars_util.setter
    def lpars_util(self, lpar_util_list):
        self._lpars_util = lpar_util_list


class LparUtil(object):
    """ Represents individual Lpar metric information. """
    def __init__(self, lpar_util):
        self._uuid = lpar_util.get('uuid')
        self._id = lpar_util.get('id')
        self._name = lpar_util.get('name')
        self._timestamp = lpar_util.get('timestamp')
        self._memory = LparMemory(lpar_util.get('memory'))

    @property
    def memory(self):
        return self._memory

    @memory.setter
    def memory(self, value):
        self._memory = value

    @property
    def uuid(self):
        return self._uuid

    @uuid.setter
    def uuid(self, value):
        self._uuid = value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value):
        self._timestamp = value


class LparMemory(object):
    """ Represents information on Lpar memory utilization """
    def __init__(self, memory):
        self._pct_real_mem_free = memory.get('pctRealMemFree')
        self._vm_pg_in_rate = memory.get('vmPgInRate')
        self._vm_pg_out_rate = memory.get('vmPgOutRate')
        self._vm_pg_swap_in_rate = memory.get('vmPgSpInRate')
        self._vm_pg_swap_out_rate = memory.get('vmPgSpOutRate')

    @property
    def pct_real_mem_free(self):
        return self._pct_real_mem_free

    @pct_real_mem_free.setter
    def pct_real_mem_free(self, value):
        self._pct_real_mem_free = value

    @property
    def vm_pg_in_rate(self):
        return self._vm_pg_in_rate

    @vm_pg_in_rate.setter
    def vm_pg_in_rate(self, value):
        self._vm_pg_in_rate = value

    @property
    def vm_pg_out_rate(self):
        return self._vm_pg_out_rate

    @vm_pg_out_rate.setter
    def vm_pg_out_rate(self, value):
        self._vm_pg_out_rate = value

    @property
    def vm_pg_swap_in_rate(self):
        return self.vm_pg_swap_in_rate

    @vm_pg_swap_in_rate.setter
    def vm_pg_swap_in_rate(self, value):
        self.vm_pg_swap_in_rate = value

    @property
    def vm_pg_swap_out_rate(self):
        return self.vm_pg_swap_out_rate

    @vm_pg_swap_out_rate.setter
    def vm_pg_swap_out_rate(self, value):
        self.vm_pg_swap_out_rate = value
