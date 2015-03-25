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

from pypowervm import util as u


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


def find_vio_for_wwpn(vios_wraps, p_port_wwpn):
    """Will find the VIOS that has a PhysFCPort for the p_port_wwpn.

    :param vios_wraps: A list or set of VIOS wrappers.
    :param p_port_wwpn: The physical port's WWPN.
    :return: The VIOS wrapper that contains a physical port with the WWPN.
             If there is not one, then None will be returned.
    :return: The port (which is a PhysFCPort wrapper) on the VIOS wrapper that
             represents the physical port.
    """
    # Sanitize our input
    s_p_port_wwpn = u.sanitize_wwpn_for_api(p_port_wwpn)
    for vios_w in vios_wraps:
        for port in vios_w.pfc_ports:
            # No need to sanitize the API WWPN, it comes from the API.
            if port.wwpn == s_p_port_wwpn:
                return vios_w, port
    return None, None


def intersect_wwpns(wwpn_set1, wwpn_set2):
    """Will return the intersection of WWPNs between the two sets.

    :param wwpn_set1: A set or list of WWPNs.
    :param wwpn_set2: A set or list of WWPNs.
    :return: The intersection of the WWPNs.  Will maintain the WWPN format
             of wwpn_set1, but the comparison done will be agnostic of
             formats (ex. colons and/or upper/lower case).
    """
    wwpn_set2 = set([u.sanitize_wwpn_for_api(x) for x in wwpn_set2])
    return [y for y in wwpn_set1 if u.sanitize_wwpn_for_api(y) in wwpn_set2]
