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
        self.lpars_util = list()
        lpar_metric_list_rsct = data.get('lparUtil')
        for lpar_metrics_rsct in lpar_metric_list_rsct:
            if 'errorInfo' in lpar_metrics_rsct:
                # Lpar was in error. We do not have metrics info for it.
                continue
            lpar_util = LparUtil(lpar_metrics_rsct)
            self.lpars_util.append(lpar_util)

    def to_dict(self):
        """ Returns dict of form {lpar_uuid: LparUtil}. """
        lparuuid_to_util_dict = dict()
        for lpar_util in self.lpars_util:
            lparuuid_to_util_dict[lpar_util.uuid] = lpar_util
        return lparuuid_to_util_dict

    @property
    def lpars_util(self):
        return self.lpars_util

class LparUtil(object):
    """ Represents individual Lpar metric information. """
    def __init__(self, lpar_util):
        self.uuid = lpar_util.get('uuid')
        self.id = lpar_util.get('id')
        self.name = lpar_util.get('name')
        self.timestamp = lpar_util.get('timestamp')
        self.memory = LparMemory(lpar_util.get('memory'))

    @property
    def uuid(self):
        return self.uuid

    @property
    def memory(self):
        return self.memory

class LparMemory(object):
    """ Represents information on Lpar memory utilization """
    def __init__(self, memory):
        self.pct_real_mem_free = memory.get('pctRealMemFree')
        self.vm_pg_in_rate = memory.get('vmPgInRate')
        self.vm_pg_out_rate = memory.get('vmPgOutRate')
        self.vm_pg_swap_in_rate = memory.get('vmPgSpInRate')
        self.vm_pg_swap_out_rate = memory.get('vmPgSpOutRate')

    @property
    def pct_real_mem_free(self):
        return self.pct_real_mem_free

    @property
    def vm_pg_in_rate(self):
        return self.vm_pg_in_rate