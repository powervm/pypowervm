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


def find_vio_for_wwpn(vios_wraps, p_port_wwpn):
    """Will find the VIOS that has a PhysFCPort for the p_port_wwpn.

    :param vios_wraps: A list or set of VIOS wrappers.
    :param p_port_wwpn: The physical ports WWPN.
    :return: The VIOS wrapper that contains a physical port with the WWPN.
             If there is not one, then None will be returned.
    :return: The port on the VIOS wrapper that represents the physical port.
    """
    # Sanitize our input
    s_p_port_wwpn = sanitize(p_port_wwpn)
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
    wwpn_set2 = set([sanitize(x) for x in wwpn_set2])
    return [y for y in wwpn_set1 if sanitize(y) in wwpn_set2]


def sanitize(wwpn):
    """Updates the format of the WWPN to match the expected PowerVM format.

    :param wwpn: The original WWPN.
    :return: A WWPN of the format expected by the API.
    """
    return wwpn.upper().replace(':', '')


def derive_npiv_map(vios_wraps, p_port_wwpns, v_port_wwpns):
    """This method will derive a NPIV map.

    A NPIV map is the linkage between an NPIV virtual FC Port and the backing
    physical port.  Two v_port_wwpns get tied to an individual p_port_wwpn.

    A list of the 'mappings' will be returned.  One per pair of v_port_wwpns.

    The mappings will first attempt to spread across the VIOSes.  Within each
    VIOS, the port with the most available free NPIV ports will be selected.

    There are scenarios where ports on a single VIOS could be reused.
     - 4 v_port_wwpns, all p_port_wwpns reside on single VIOS
     - 8 v_port_wwpns, only two VIOSes
     - Etc...

    In these scenarios, the ports will be spread such that they're running
    across all the physical ports (that were passed in) on a given VIOS.

    In even rarer scenarios, the same physical port may be re-used if the
    v_port_wwpn pairs exceed the total number of p_port_wwpns.

    :param vios_wraps: A list of VIOS wrappers.  Can be quick queried using
                       the VFC Mapping extended attribute.
    :param p_port_wwpns: A list of the WWPNs (strings) that can be used to
                         map the ports to.  These WWPNs should reside on
                         Physical FC Ports on the VIOS wrappers that were
                         passed in.
    :param v_port_wwpns: A list of the virtual fibre channel port WWPNs.  Must
                         be an even number of ports.
    :return: A list of sets.  The format will be:
      [ (p_port_wwpn1, fused_vfc_port_wwpn1),
        (p_port_wwpn2, fused_vfc_port_wwpn2),
        etc... ]

    A 'fused_vfc_port_wwpn' is simply taking two v_port_wwpns, sanitizing them
    and then putting them into a single string separated by a space.
    """

    # Fuse all the v_port_wwpns together.
    fused_v_port_wwpns = _fuse_vfc_ports(v_port_wwpns)

    # Up front sanitization of all the p_port_wwpns
    p_port_wwpns = [sanitize(p) for p in p_port_wwpns]

    # Determine how many mappings are needed.
    needed_maps = len(fused_v_port_wwpns)
    resp_maps = []

    next_vio_pos = 0
    fuse_map_pos = 0

    # This map will continue through each VIOS (first set of load balancing
    # should be done by VIOS) and if there are ports on that VIOS, will add
    # them to the mapping.
    #
    # There does need to be a rate limiter here though.  If none of the VIOSes
    # are servicing the request, then this has potential to be infinite loop.
    #
    # As such, limit it such that if no VIOS services the request, we break
    # out of the loop and throw error.
    while len(resp_maps) < needed_maps:
        # Walk through each VIOS.
        vio = vios_wraps[next_vio_pos]

        # This increments the VIOS position for the next loop
        next_vio_pos = (next_vio_pos + 1) % len(vios_wraps)

        # Find the FC Ports that are on this system.
        potential_ports = _find_ports_on_vio(vio, p_port_wwpns)
        if len(potential_ports) == 0:
            # No ports on this VIOS.  Continue to next.
            continue

        # Next, from the potential ports, find the PhysFCPort that we should
        # use for the mapping.
        new_map_port = _find_map_port(potential_ports, resp_maps)
        if new_map_port is None:
            # If there was no mapping port, then we should continue on to
            # the next VIOS.
            continue

        # Add the mapping!
        mapping = (new_map_port.wwpn, fused_v_port_wwpns[fuse_map_pos])
        fuse_map_pos += 1
        resp_maps.append(mapping)

    return resp_maps


def _find_map_port(potential_ports, mappings):
    """Will determine which port to use for a new mapping.

    :param potential_ports: List of PhysFCPort wrappers that are candidate
                            ports.
    :param mappings: The existing mappings, as generated by derive_npiv_map.
    :return: The PhysFCPort that should be used for this mapping.
    """
    # The first thing that we need is to understand how many ports have
    # been used by mappings already.
    port_wwpn_to_count = dict.fromkeys([x.wwpn for x in potential_ports], 0)

    for mapping in mappings:
        p_wwpn = mapping[0]

        # If this physical WWPN is not in our port, don't include it.
        # This will happen for multi-vios.
        if p_wwpn not in port_wwpn_to_count.keys():
            continue

        # Increment our counter.
        port_wwpn_to_count[mapping[0]] += 1

    # If there are no viable ports, return
    if len(port_wwpn_to_count.keys()) == 0:
        return

    # Now find the set of ports with the lowest count of usage by mappings.
    starting_count = 0
    list_of_cand_ports = []
    while len(list_of_cand_ports) == 0:
        for wwpn_key in port_wwpn_to_count.keys():
            if port_wwpn_to_count[wwpn_key] == starting_count:
                list_of_cand_ports.append(wwpn_key)

        # Increment the count, in case we have to loop again.
        starting_count += 1

    # At this point, the list_of_cand_ports is essentially a list of ports
    # least used by THIS mapping.  Now, we need to narrow that down to the
    # port that has the most npiv_available_ports.  The one with the most
    # available ports is the least used.  Therefore the best candidate (that
    # we can choose with limited info).
    high_avail_port = None
    for port_wwpn in list_of_cand_ports:
        # Get the port via re-using this method
        port = None
        for p in potential_ports:
            if p.wwpn == port_wwpn:
                port = p
                break

        # If this is the first port, or this new port has more available NPIV
        # slots, then use that.
        if (high_avail_port is None or
                high_avail_port.npiv_available_ports <
                port.npiv_available_ports):
            high_avail_port = port

    return high_avail_port


def _find_ports_on_vio(vio_w, p_port_wwpns):
    """Will return a list of Physical FC Ports on the vio_w.

    :param vio_w: The VIOS wrapper.
    :param p_port_wwpns: The list of all physical ports.  May exceed the
                         ports on the VIOS.
    :return: List of the physical FC Port wrappers that are on the VIOS
             for the WWPNs that exist on this system.
    """
    return [port for port in vio_w.pfc_ports if port.wwpn in p_port_wwpns]


def _fuse_vfc_ports(wwpn_list):
    """Returns a set of fused VFC WWPNs.  See derive_npiv_map."""
    return [sanitize(wwpn_list[i]) + ' ' + sanitize(wwpn_list[i+1])
            for i in range(0, len(wwpn_list), 2)]
