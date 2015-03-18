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

import random


def build_wwpn_pair(adapter, host_uuid):
    """Builds a WWPN pair that can be used for a VirtualFCAdapter.

    TODO(IBM): Future implementation will interrogate the system for globally
               unique WWPN.  For now, generate based off of random number
               generation.  Likelihood of overlap is 1 in 281 trillion.

    :param adapter: The adapter to talk over the API.
    :param host_uuid: The host system for the generation.
    :return: Non-mutable WWPN Pair (set)
    """
    resp = "C0"
    while len(resp) < 14:
        resp += random.choice('0123456789ABCDEF')
    return resp + "00", resp + "01"
