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

from pypowervm import exceptions as e
from pypowervm import util as u
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import virtual_io_server as pvm_vios


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

    :param vios_wraps: A list of VIOS wrappers.  Can be built using the
                       extended attribute group (xag) of VIOS_FC_MAPPING.
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
    p_port_wwpns = list(map(u.sanitize_wwpn_for_api, p_port_wwpns))

    # Determine how many mappings are needed.
    needed_maps = len(fused_v_port_wwpns)
    resp_maps = []

    next_vio_pos = 0
    fuse_map_pos = 0
    loops_since_last_add = 0

    # This loop will continue through each VIOS (first set of load balancing
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
        loops_since_last_add += 1

        # If we've been looping more than the VIOS count, we need to exit.
        # Something has gone amuck.
        if loops_since_last_add > len(vios_wraps):
            raise e.UnableToFindFCPortMap()

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
        loops_since_last_add = 0

    return resp_maps


def _find_map_port(potential_ports, mappings):
    """Will determine which port to use for a new mapping.

    :param potential_ports: List of PhysFCPort wrappers that are candidate
                            ports.
    :param mappings: The existing mappings, as generated by derive_npiv_map.
    :return: The PhysFCPort that should be used for this mapping.
    """
    # The first thing that we need is to understand how many physical ports
    # have been used by mappings already.  This is important for the scenarios
    # where we're looping across the same set of physical ports on this VIOS.
    # We should avoid reusing those same physical ports as our previous
    # mappings as much as possible, to allow for as much physical multi pathing
    # as possible.
    #
    # This dictionary will have a key of every port's WWPN, within that it will
    # have a dictionary which contains 'port_mapping_use' and then the 'port'
    # which is the port passed in.
    port_dict = dict((p.wwpn, {'port_mapping_use': 0, 'port': p})
                     for p in potential_ports)

    for mapping in mappings:
        p_wwpn = mapping[0]

        # If this physical WWPN is not in our port_dict, then we know that
        # this port is not on the VIOS.  Therefore, we can't take it into
        # consideration.
        if p_wwpn not in port_dict.keys():
            continue

        # Increment our counter to indicate that a previous mapping already
        # has used this physical port.
        port_dict[p_wwpn]['port_mapping_use'] += 1

    # Now find the set of ports with the lowest count of usage by mappings.
    # The first time through this method, this will be all the physical ports.
    # This is only interesting once the previous mappings come into play.
    # This is where we reduce the 'candidate physical ports' down to those
    # that are least used by our existing mappings.
    #
    # There is a reasonable upper limit of 50 mappings (which should be far
    # beyond what admins will want to map vFC's to a single pFC).  We simply
    # put that in to avoid infinite loops in the extremely, almost unimaginable
    # event that we've reached an upper boundary.  :-)
    #
    # Subsequent logic should be OK with this, as we simply will return None
    # for the next available port.
    starting_count = 0
    list_of_cand_ports = []
    while len(list_of_cand_ports) == 0 and starting_count < 50:
        for port_info in port_dict.values():
            if port_info['port_mapping_use'] == starting_count:
                list_of_cand_ports.append(port_info['port'])

        # Increment the count, in case we have to loop again.
        starting_count += 1

    # At this point, the list_of_cand_ports is essentially a list of ports
    # least used by THIS mapping.  Now, we need to narrow that down to the
    # port that has the most npiv_available_ports.  The one with the most
    # available ports is the least used.  Therefore the best candidate (that
    # we can choose with limited info).
    high_avail_port = None
    for port in list_of_cand_ports:
        # If this is the first port, or this new port has more available NPIV
        # slots, then use that.
        if (high_avail_port is None or
                high_avail_port.npiv_available_ports <
                port.npiv_available_ports):
            high_avail_port = port

    return high_avail_port


def add_npiv_port_mappings(adapter, host_uuid, vm_uuid, npiv_port_map):
    """Adds the port mappings to the affected VIOSes.

    This method will verify that the port mappings (as defined by the
    derive_npiv_map method) are on the necessary VIOSes.  Will perform the
    update to the actual VIOSes if any change are needed.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The pypowervm UUID of the host.
    :param vm_uuid: The UUID of the VM that should have the vFC mapping added
                    to it.
    :param npiv_port_map: The list of port mappings, as defined by the
                          pypowervm wwpn derive_npiv_map method.
    """
    def add_action(vios_wraps, p_map):
        return _add_npiv_port_map(adapter, host_uuid, vm_uuid, vios_wraps,
                                  p_map)

    _mapping_actions(adapter, host_uuid, npiv_port_map, add_action)


def remove_npiv_port_mappings(adapter, host_uuid, npiv_port_map):
    """Removes the port mappings off of all of the affected VIOSes.

    This method will remove all of the NPIV Port Mappings (as defined by the
    derive_npiv_map) off of the affected VIOSes.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The pypowervm UUID of the host.
    :param npiv_port_map: The list of port mappings, as defined by the
                          pypowervm wwpn derive_npiv_map method.
    """
    def remove_action(vios_wraps, p_map):
        return _remove_npiv_port_map(adapter, vios_wraps, p_map)

    _mapping_actions(adapter, host_uuid, npiv_port_map, remove_action)


def _mapping_actions(adapter, host_uuid, npiv_port_map, func):
    """Handles the 'mapping' for a given instance.

    A mapping function is either an 'add' or 'remove' of the NPIV fabric
    from the VIOS query.

    This method reads all of the VIOSes up front, gathers the mapping
    function, and then executes it across the appropriate VIOSes.

    Once the modification wrappers are run, an update on the VIOS will occur.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The pypowervm UUID of the host.
    :param npiv_port_map: The list of port mappings, as defined by the
                          pypowervm wwpn derive_npiv_map method.
    :param func: The function to run against each fabric.  The input is:
                 - vios_wraps: A list of the wrappers
                 - phys_mappings: A single mapping for the fabric (as
                                  defined by pvm_wwpn derive_npiv_map).
                Expected response:
                 - A pypowervm VIOS wrapper that was impacted by the
                   function.  If none were, then None is acceptable.
    """
    # Get all the VIOSes
    vios_resp = adapter.read(pvm_ms.System.schema_type, root_id=host_uuid,
                             child_type=pvm_vios.VIOS.schema_type,
                             xag=[pvm_vios.XAGEnum.VIOS_FC_MAPPING])
    vios_wraps = pvm_vios.VIOS.wrap(vios_resp)

    # List of VIOSes that need to be updated.
    vioses_to_update = {}

    # For each port mapping...
    for npiv_port_map in npiv_port_map:
        # For each mapping connection, ensure that it is mapped into the
        # wrapper.
        vios_to_update = func(vios_wraps, npiv_port_map)

        # If there was a VIOS to update, and we're not already slated
        # to update it...add it to the list.  This is useful for
        # multi pathing scenarios, to make sure we don't update the
        # same VIOS multiple times.
        if (vios_to_update is not None and
                vioses_to_update.get(vios_to_update.uuid) is None):
            vioses_to_update[vios_to_update.uuid] = vios_to_update

    # Now run the update against the affected VIOSes
    for vios_w in vioses_to_update.values():
        vios_w.update(adapter, xag=[pvm_vios.XAGEnum.VIOS_FC_MAPPING])


def _remove_npiv_port_map(adapter, vios_wraps, npiv_port_map):
    """Ensures that the mapping is removed from the VIOS wrapper.

    This method takes in a port mapping (see the derive_npiv_map method), which
    is a pair of values: (p_wwpn, fused_v_wwpn)

    Will loop through all of the VIOSes and will remove it from the correct
    wrapper.  Does not call the update on the VIOS, simply modifies the
    wrapper.

    If the mapping does not exist on any VIOS, no action is taken.

    :param vios_wraps: The list of pypowervm VIOS wrappers.
    :param npiv_port_map: A single npiv port mapping, as defined by the
                          derive_npiv_map method.
    :return: The VIOS wrapper that had the port mapping removed.  If there
             were no affected VIOSes, returns None.
    """
    vios_w, p_port = find_vio_for_wwpn(vios_wraps, npiv_port_map[0])
    v_wwpns = set([u.sanitize_wwpn_for_api(x)
                   for x in npiv_port_map[1].split()])

    removal_map = None

    for vfc_map in vios_w.vfc_mappings:
        if vfc_map.client_adapter is None:
            continue
        if vfc_map.client_adapter.wwpns != v_wwpns:
            continue

        # If we reach this point, we know that we have a matching map.  So this
        # becomes the one we will want to remove from the connection list.
        removal_map = vfc_map
        break

    # If there was no removal map...then nothing to be done.
    if removal_map is None:
        return None

    # However, if it isn't none, then go into the VIOS wrapper and remove it
    vios_w.vfc_mappings.remove(removal_map)
    return vios_w


def _add_npiv_port_map(adapter, host_uuid, vm_uuid, vios_wraps, npiv_port_map):
    """Ensures that the mapping is on the VIOS wrapper.

    This method takes in a port mapping (see the derive_npiv_map method), which
    is a pair of values: (p_wwpn, fused_v_wwpn)

    Will loop through all of the VIOS wrappers and will add it to the correct
    wrapper.  Does not call the update on the VIOS, simply modifies the
    wrapper.

    If the mapping is already on one of the VIOSes, no action will be taken.

    :param host_uuid: The host system UUID.
    :param vm_uuid: The client virtual machine's UUID.
    :param vios_wraps: The list of pypowervm VIOS wrappers.
    :param npiv_port_map: A single npiv port mapping, as defined by the
                          derive_npiv_map method.
    :return: The VIOS wrapper that had the port mapping added.  If there
             were no affected VIOSes, returns None.
    """
    vios_w, p_port = find_vio_for_wwpn(vios_wraps, npiv_port_map[0])
    v_wwpns = set([u.sanitize_wwpn_for_api(x)
                   for x in npiv_port_map[1].split()])

    for vfc_map in vios_w.vfc_mappings:
        if vfc_map.client_adapter is None:
            continue
        if vfc_map.client_adapter.wwpns != v_wwpns:
            continue

        # If we reach this point, we know that we have a matching map.  So
        # the attach of this volume, for this vFC mapping is complete.
        # Nothing else needs to be done, exit the method.
        return None

    # However, if we hit here, then we need to create a new mapping and
    # attach it to the VIOS mapping
    vfc_map = pvm_vios.VFCMapping.bld(adapter, host_uuid, vm_uuid,
                                      p_port.name, v_wwpns)
    vios_w.vfc_mappings.append(vfc_map)
    return vios_w


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
    l = list(map(u.sanitize_wwpn_for_api, wwpn_list))
    return list(map(' '.join, zip(l[::2], l[1::2])))
