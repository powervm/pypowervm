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

"""Specialized tasks for NPIV World-Wide Port Names (WWPNs)."""

from oslo_log import log as logging

from pypowervm import const as c
from pypowervm import exceptions as e
from pypowervm.i18n import _
from pypowervm import util as u
from pypowervm.utils import uuid
from pypowervm.wrappers import base_partition as bp
from pypowervm.wrappers import job as pvm_job
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import virtual_io_server as pvm_vios

import six

LOG = logging.getLogger(__name__)


_ANY_WWPN = '-1'
_FUSED_ANY_WWPN = '-1 -1'
_GET_NEXT_WWPNS = 'GetNextWWPNs'


def build_wwpn_pair(adapter, host_uuid, pair_count=1):
    """Builds a WWPN pair that can be used for a VirtualFCAdapter.

    Note: The API will only generate up to 8 pairs at a time.  Any more will
    cause the API to raise an error.

    :param adapter: The adapter to talk over the API.
    :param host_uuid: The host system for the generation.
    :param pair_count: (Optional, Default: 1) The number of WWPN pairs to
                       generate.  Can not be more than 8 or else the API will
                       fail.
    :return: Non-mutable WWPN Pairs (list)
    """
    # Build up the job & invoke
    resp = adapter.read(
        pvm_ms.System.schema_type, root_id=host_uuid,
        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=_GET_NEXT_WWPNS)
    job_w = pvm_job.Job.wrap(resp)
    job_p = [job_w.create_job_parameter('numberPairsRequested',
                                        str(pair_count))]
    job_w.run_job(host_uuid, job_parms=job_p)

    # Get the job result, and parse the output.
    job_result = job_w.get_job_results_as_dict()
    return job_result['wwpnList'].split(',')


def find_vios_for_wwpn(vios_wraps, p_port_wwpn):
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
            if u.sanitize_wwpn_for_api(port.wwpn) == s_p_port_wwpn:
                return vios_w, port
    return None, None


def find_vios_for_vfc_wwpns(vios_wraps, vfc_wwpns):
    """Will find the VIOS that is hosting the vfc_wwpns.

    :param vios_wraps: A list or set of VIOS wrappers.
    :param vfc_wwpns: The list or set of virtual fibre channel WWPNs.
    :return: The VIOS wrapper that supports the vfc adapters.  If there is not
             one, then None will be returned.
    :return: The VFCMapping on the VIOS that supports the client adapters.
    """
    # Sanitize our input
    vfc_wwpns = {u.sanitize_wwpn_for_api(x) for x in vfc_wwpns}
    for vios_w in vios_wraps:
        for vfc_map in vios_w.vfc_mappings:
            # If the map has no client adapter...then move on
            if not vfc_map.client_adapter:
                continue

            # If the WWPNs match, return it
            if vfc_wwpns == set(vfc_map.client_adapter.wwpns):
                return vios_w, vfc_map
    return None, None


def intersect_wwpns(wwpn_set1, wwpn_set2):
    """Will return the intersection of WWPNs between the two sets.

    :param wwpn_set1: A list of WWPNs.
    :param wwpn_set2: A list of WWPNs.
    :return: The intersection of the WWPNs.  Will maintain the WWPN format
             of wwpn_set1, but the comparison done will be agnostic of
             formats (ex. colons and/or upper/lower case).
    """
    wwpn_set2 = [u.sanitize_wwpn_for_api(x) for x in wwpn_set2]
    return [y for y in wwpn_set1 if u.sanitize_wwpn_for_api(y) in wwpn_set2]


def derive_base_npiv_map(vios_wraps, p_port_wwpns, v_port_count):
    """Builds a blank NPIV port mapping, without any known vFC WWPNs.

    This method is functionally similar to the derive_npiv_map.  However, the
    derive_npiv_map method assumes knowledge of the Virtual Fibre Channel
    mappings beforehand.  This method will generate a similar map, but when
    sent to the add_map method, that method will allow the API to generate the
    globally unique WWPNs rather than pre-seeding them.

    :param vios_wraps: A list of VIOS wrappers.  Can be built using the
                       extended attribute group (xag) of VIO_FMAP.
    :param p_port_wwpns: A list of the WWPNs (strings) that can be used to
                         map the ports to.  These WWPNs should reside on
                         Physical FC Ports on the VIOS wrappers that were
                         passed in.
    :param v_port_count: The number of virtual ports to create.
    :return: A list of sets.  The format will be similar to that of the
             derive_npiv_map method.  However, instead of a fused_vfc_port_wwpn
             a marker will be used to indicate that the API should generate
             the WWPN.
    """
    # Double the count of the markers.  Should result in -1 -1 as the WWPN.
    v_port_markers = [_ANY_WWPN] * v_port_count * 2
    return derive_npiv_map(vios_wraps, p_port_wwpns, v_port_markers)


def derive_npiv_map(vios_wraps, p_port_wwpns, v_port_wwpns, preserve=True):
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
                       extended attribute group (xag) of VIO_FMAP.
    :param p_port_wwpns: A list of the WWPNs (strings) that can be used to
                         map the ports to.  These WWPNs should reside on
                         Physical FC Ports on the VIOS wrappers that were
                         passed in.
    :param v_port_wwpns: A list of the virtual fibre channel port WWPNs.  Must
                         be an even number of ports.
    :param preserve: (Optional, Default=True) If True, existing mappings with
                     matching virtual fibre channel ports are preserved. Else
                     new mappings are generated.
    :return: A list of tuples representing both new and preserved mappings.
             The format will be:
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

    existing_maps = []
    new_fused_wwpns = []

    # Detect if any mappings already exist on the system.
    for fused_v_wwpn in fused_v_port_wwpns:
        # If the mapping already exists, then add it to the existing maps.
        vfc_map = has_client_wwpns(vios_wraps, fused_v_wwpn.split(" "))[1]
        # Preserve an existing mapping if preserve=True. Otherwise, the
        # backing_port may not be set and this is not an error condition if
        # the vfc mapping is getting rebuilt.
        if vfc_map is not None and preserve:
            mapping = (vfc_map.backing_port.wwpn, fused_v_wwpn)
            existing_maps.append(mapping)
        else:
            new_fused_wwpns.append(fused_v_wwpn)
            LOG.debug("Add new map for client wwpns %s. Existing map=%s, "
                      "preserve=%s", fused_v_wwpn, vfc_map, preserve)

    # Determine how many mappings are needed.
    needed_maps = len(new_fused_wwpns)
    newly_built_maps = []

    next_vio_pos = 0
    fuse_map_pos = 0
    loops_since_last_add = 0

    # This loop will continue through each VIOS (first set of load balancing
    # should be done by VIOS) and if there are ports on that VIOS, will add
    # them to the mapping.
    #
    # There is a rate limiter here though.  If none of the VIOSes are servicing
    # the request, then this has potential to be infinite loop.  The rate
    # limiter detects such a scenario and will prevent it from occurring.  In
    # these cases the UnableToFindFCPortMap exception is raised.
    #
    # As such, limit it such that if no VIOS services the request, we break
    # out of the loop and throw error.
    while len(newly_built_maps) < needed_maps:
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
        new_map_port = _find_map_port(potential_ports,
                                      newly_built_maps + existing_maps)
        if new_map_port is None:
            # If there was no mapping port, then we should continue on to
            # the next VIOS.
            continue

        # Add the mapping!
        mapping = (new_map_port.wwpn, new_fused_wwpns[fuse_map_pos])
        fuse_map_pos += 1
        newly_built_maps.append(mapping)
        loops_since_last_add = 0

    # Mesh together the existing mapping lists plus the newly built ports.
    return newly_built_maps + existing_maps


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
    # There is a reasonable upper limit of 128 mappings (which should be
    # beyond what admins will want to map vFC's to a single pFC).  We simply
    # put that in to avoid infinite loops in the extremely, almost unimaginable
    # event that we've reached an upper boundary.  :-)
    #
    # Subsequent logic should be OK with this, as we simply will return None
    # for the next available port.
    starting_count = 0
    list_of_cand_ports = []
    while len(list_of_cand_ports) == 0 and starting_count < 128:
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


def _find_ports_on_vio(vio_w, p_port_wwpns):
    """Will return a list of Physical FC Ports on the vio_w.

    :param vio_w: The VIOS wrapper.
    :param p_port_wwpns: The list of all physical ports.  May exceed the
                         ports on the VIOS.
    :return: List of the physical FC Port wrappers that are on the VIOS
             for the WWPNs that exist on this system.
    """
    return [port for port in vio_w.pfc_ports
            if u.sanitize_wwpn_for_api(port.wwpn) in p_port_wwpns]


def _fuse_vfc_ports(wwpn_list):
    """Returns a list of fused VFC WWPNs.  See derive_npiv_map."""
    l = list(map(u.sanitize_wwpn_for_api, wwpn_list))
    return list(map(' '.join, zip(l[::2], l[1::2])))


def _find_pfc_wwpn_by_name(vios_w, pfc_name):
    """Returns the physical port wwpn within a VIOS based off the FC port name.

    :param vios_w: VIOS wrapper.
    :param pfc_name: The physical fibre channel port name.
    """
    for port in vios_w.pfc_ports:
        if port.name == pfc_name:
            return port.wwpn
    return None


def find_maps(mapping_list, client_lpar_id, client_adpt=None, port_map=None):
    """Filter a list of VFC mappings by LPAR ID.

    This is based on scsi_mapper.find_maps, but does not yet provide all the
    same functionality.

    :param mapping_list: The mappings to filter.  Iterable of VFCMapping.
    :param client_lpar_id: Integer short ID or string UUID of the LPAR on the
                           client side of the mapping.  Note that the UUID form
                           relies on the presence of the client_lpar_href
                           field.  Some mappings lack this field, and would
                           therefore be ignored.
    :param client_adpt: (Optional, Default=None) If set, will only include the
                        mapping if the client adapter's WWPNs match as well.
    :param port_map: (Optional, Default=None) If set, will look for a matching
                     mapping based off the client WWPNs as specified by the
                     port mapping.  The format of this is defined by the
                     derive_npiv_map method.
    :return: A list comprising the subset of the input mapping_list whose
             client LPAR IDs match client_lpar_id.
    """
    is_uuid, client_id = uuid.id_or_uuid(client_lpar_id)
    matching_maps = []

    if port_map:
        v_wwpns = [u.sanitize_wwpn_for_api(x) for x in port_map[1].split()]

    for vfc_map in mapping_list:
        # If to a different VM, continue on.
        href = vfc_map.client_lpar_href
        if is_uuid and (not href or client_id != u.get_req_path_uuid(
                href, preserve_case=True)):
            continue
        elif not is_uuid and vfc_map.server_adapter.lpar_id != client_id:
            # Use the server adapter ^^ in case this is an orphan.
            continue

        # If there is a client adapter, and it is not a 'ANY WWPN', then
        # check to see if the mappings match.
        if client_adpt and client_adpt.wwpns != {_ANY_WWPN}:
            # If they passed in a client adapter, but the map doesn't have
            # one, then we have to ignore
            if not vfc_map.client_adapter:
                continue

            # Check to make sure the WWPNs between the two match.  This should
            # be an order independence check (as this query shouldn't care...
            # but the API itself does care about order).
            if set(client_adpt.wwpns) != set(vfc_map.client_adapter.wwpns):
                continue

        # If the user had a port map, do the virtual WWPNs from that port
        # map match the client adapter wwpn map.
        if port_map:
            if vfc_map.client_adapter is None:
                continue

            # If it is a new mapping with generated WWPNs, then the client
            # adapter can't have WWPNs.
            if v_wwpns == [_ANY_WWPN, _ANY_WWPN]:
                if vfc_map.client_adapter.wwpns != []:
                    continue
            elif set(vfc_map.client_adapter.wwpns) != set(v_wwpns):
                continue

        # Found a match!
        matching_maps.append(vfc_map)

    return matching_maps


def remove_maps(v_wrap, client_lpar_id, client_adpt=None, port_map=None):
    """Remove one or more VFC mappings from a VIOS wrapper.

    The changes are not flushed back to the REST server.

    :param v_wrap: VIOS EntryWrapper representing the Virtual I/O Server whose
                   VFC mappings are to be updated.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param client_adpt: (Optional, Default=None) If set, will only add the
                        mapping if the client adapter's WWPNs match as well.
    :param port_map: (Optional, Default=None) If set, will look for a matching
                     mapping based off the client WWPNs as specified by the
                     port mapping.  The format of this is defined by the
                     derive_npiv_map method.
    :return: The mappings removed from the VIOS wrapper.
    """
    resp_list = []

    for matching_map in find_maps(v_wrap.vfc_mappings, client_lpar_id,
                                  client_adpt=client_adpt,
                                  port_map=port_map):
        v_wrap.vfc_mappings.remove(matching_map)
        resp_list.append(matching_map)
    return resp_list


def find_vios_for_port_map(vios_wraps, port_map):
    """Finds the appropriate VIOS wrapper for a given port map.

    Note that the algorithm first checks based off of the client WWPNs.  If the
    client WWPNs can not be found (perhaps the map is still -1 -1 from the
    derive_base_npiv_map) then the physical port WWPN will be checked.

    :param vios_wraps: A list of Virtual I/O Server wrapper objects.
    :param port_map: The port mapping (as defined by the derive_npiv_map
                     method).
    :return: The Virtual I/O Server wrapper that supports the port map.
    """
    # Check first based off the client WWPNs.  Note that this may be -1 -1
    # in which case it will return nothing
    vios_w = find_vios_for_vfc_wwpns(vios_wraps, port_map[1].split())[0]
    if vios_w:
        return vios_w

    # If we had nothing, check based off the physical port WWPN.  The
    # reason this is not the first check is because the mapping may be mid
    # live migration, thus pointing to a source.  But if that was the case
    # then the first check would have returned the right WWPNs.  The only
    # time this should be hit is in the middle of a create operation.
    return find_vios_for_wwpn(vios_wraps, port_map[0])[0]


def add_map(vios_w, host_uuid, lpar_uuid, port_map, error_if_invalid=True,
            lpar_slot_num=None):
    """Adds a vFC mapping to a given VIOS wrapper.

    These changes are not flushed back to the REST server.  The wrapper itself
    is simply modified.

    :param vios_w: VIOS EntryWrapper representing the Virtual I/O Server whose
                   VFC mappings are to be updated.
    :param host_uuid: The pypowervm UUID of the host.
    :param lpar_uuid: The pypowervm UUID of the client LPAR to attach to.
    :param port_map: The port mapping (as defined by the derive_npiv_map
                     method).
    :param error_if_invalid: (Optional, Default: True) If the port mapping
                             physical port can not be found, raise an error.
    :param lpar_slot_num: (Optional, Default: None) The client adapter
                          VirtualSlotNumber to be set. If None the next
                          available slot would be used.
    :return: The VFCMapping that was added or updated with a missing backing
             port.  If the mapping already existed then None is returned.
    """
    # This is meant to find the physical port.  Can run against a single
    # element.  We assume invoker has passed correct VIOS.
    new_vios_w, p_port = find_vios_for_wwpn([vios_w], port_map[0])
    if new_vios_w is None:
        if error_if_invalid:
            # Log the payload in the response.
            LOG.warning(_("Unable to find appropriate VIOS.  The payload "
                          "provided was likely insufficient.  The payload "
                          "data is:\n %s)"), vios_w.toxmlstring(pretty=True))
            raise e.UnableToDerivePhysicalPortForNPIV(wwpn=port_map[0],
                                                      vio_uri=vios_w.href)
        else:
            return None

    v_wwpns = None
    if port_map[1] != _FUSED_ANY_WWPN:
        v_wwpns = [u.sanitize_wwpn_for_api(x) for x in port_map[1].split()]

    if v_wwpns is not None:
        for vfc_map in vios_w.vfc_mappings:
            if (vfc_map.client_adapter is None or
                    vfc_map.client_adapter.wwpns is None):
                continue
            if set(vfc_map.client_adapter.wwpns) != set(v_wwpns):
                continue

            # If we reach this point, we know that we have a matching map.
            # Check that the physical port is set in the mapping.
            if vfc_map.backing_port:
                LOG.debug("Matching existing vfc map found with backing port:"
                          " %s", vfc_map.backing_port.wwpn)
                # The attach of this volume, for this vFC mapping is complete.
                # Nothing else needs to be done, exit the method.
                return None
            else:
                LOG.info(_("The matched VFC port map has no backing port set."
                           " Adding %(port)s to mapping for client wwpns: "
                           "%(wwpns)s"),
                         {'port': p_port.name, 'wwpns': v_wwpns})
                # Build the backing_port and add it to the vfc_map.
                vfc_map.backing_port = bp.PhysFCPort.bld_ref(
                    vios_w.adapter, p_port.name, ref_tag='Port')
                return vfc_map

    # However, if we hit here, then we need to create a new mapping and
    # attach it to the VIOS mapping
    vfc_map = pvm_vios.VFCMapping.bld(vios_w.adapter, host_uuid, lpar_uuid,
                                      p_port.name, client_wwpns=v_wwpns,
                                      lpar_slot_num=lpar_slot_num)
    vios_w.vfc_mappings.append(vfc_map)
    return vfc_map


def has_client_wwpns(vios_wraps, client_wwpn_pair):
    """Returns the vios wrapper and vfc map if the client WWPNs already exist.

    :param vios_wraps: The VIOS wrappers.  Should be queried with the
                       VIO_FMAP extended attribute.
    :param client_wwpn_pair: The pair (list or set) of the client WWPNs.
    :return vios_w: The VIOS wrapper containing the wwpn pair.  None if none
                    of the wrappers contain the pair.
    :return vfc_map: The mapping containing the client pair.  May be None.
    """
    client_wwpn_pair = set([u.sanitize_wwpn_for_api(x)
                            for x in client_wwpn_pair])

    for vios_wrap in vios_wraps:
        for vfc_map in vios_wrap.vfc_mappings:
            if vfc_map.client_adapter is None:
                continue

            pair = set([u.sanitize_wwpn_for_api(x)
                        for x in vfc_map.client_adapter.wwpns])
            if pair == client_wwpn_pair:
                return vios_wrap, vfc_map

    return None, None


def build_migration_mappings_for_fabric(vios_wraps, p_port_wwpns,
                                        client_slots):
    """Builds the vFC migration mappings for a given fabric.

    This method will build the migration mappings for a given fabric.
    The response is a list of strings that can be used in the migration.py

    Note: If you have multiple fabrics, then each fabric will need to
    independently call this method with the appropriate p_port_wwpns.

    Note: This must be run on the destination server before the migration.
    It is typically input back to the source server for the migration call.

    :param vios_wraps: The VIOS wrappers for the target system.  Must
                       have the VIO_FMAP xag specified.
    :param p_port_wwpns: The physical port WWPNs that can be used for
                         this specific fabric.  May span multiple VIOSes,
                         but each must be part of the vios_wraps.
    :param client_slots: A list of integers which represent the *source*
                         system's LPAR virtual Fibre Channel slots that
                         are participating in this fabric.
    :return: List of mappings that can be passed into the migration.py
             for the live migration.  The format is defined within the
             migration.py, migrate_lpar method.
    """
    basic_mappings = derive_base_npiv_map(vios_wraps, p_port_wwpns,
                                          len(client_slots))
    resp = []
    for basic_map, client_slot in zip(basic_mappings, client_slots):
        # Find the appropriate VIOS hosting this physical port.
        vios_w, port = find_vios_for_wwpn(vios_wraps, basic_map[0])

        # The format is:
        #     virtual-slot-number/vios-lpar-name/vios-lpar-ID
        #     [/[vios-virtual-slot-number][/[vios-fc-port-name]]]
        #
        # We do not specify the vios-virtual-slot-number.
        resp.append(str(client_slot) + "/" + vios_w.name + "/" +
                    str(vios_w.id) + "//" + port.name)
    return resp


def _split_ports_per_fabric(slot_grouping, fabric_data):
    """Splits the slots per fabric which are to be placed on the same VIOS.

    :param slot_grouping: The slots which are to be placed in the same vios
                          Ex:
                          [3, 6]
                          Here the slots 3 and 6 are to be placed on the same
                          vios.
    :param fabric_data: Dictionary where the key is the fabric name.  The
                        value is another dictionary with the slots and the
                        p_port_wwpns.

                        Ex:
                        { 'A': {'slots': [3, 4, 5], p_port_wwpns: [1, 2, 3] },
                          'B': {'slots': [6, 7, 8], p_port_wwpns: [4, 5] } }

                        The slot indicates which slots from the client slots
                        align with which fabric.
    :return resp: The slots which can be placed on the same VIOS alone are
                  returned.
                  {'A': {'slots': [3],  p_port_wwpns: [1, 2, 3] },
                   'B': {'slots': [6],  p_port_wwpns: [4, 5] } }
    """
    resp = {}
    for fabric in fabric_data:
        slots = [x for x in fabric_data[fabric]['slots'] if x in slot_grouping]
        if not slots:
            continue

        resp[fabric] = {'slots': slots,
                        'p_port_wwpns': fabric_data[fabric]['p_port_wwpns']}
    return resp


def _does_vios_support_split_map(vios_w, split_map):
    """Split_map provided by _split_ports_per_fabric.

    :param vios_w: The VIOS wrapper to validate if the split map can match
    :param split_map: This contains the physical ports and the slots to be
                      matched on the VIOS
                      Ex: {'A': {'p_port_wwpns': ['phy_port1'], 'slots': [3]}
                      Check if the number of slots required can be satisfied
                      by the given VIOS.
    """
    for fabric_map in six.itervalues(split_map):
        needed_pports = len(fabric_map['slots'])
        fabric_pports_on_vios = _find_ports_on_vio(
            vios_w, fabric_map['p_port_wwpns'])
        if len(fabric_pports_on_vios) < needed_pports:
            return False
    return True


def build_migration_mappings(vios_wraps, fabric_data, slot_peers):
    """Builds the vFC migration mappings.

    Looks holistically at the system.  Should generally be used instead of
    build_migration_mappings_for_fabric.

    :param vios_wraps: The VIOS wrappers for the target system.  Must
                       have the VIO_FMAP xag specified.
    :param fabric_data: Dictionary where the key is the fabric name.  The
                        value is another dictionary with the slots and the
                        p_port_wwpns.

                        Ex:
                        { 'A': {'slots': [3, 4, 5], p_port_wwpns: [1, 2, 3] },
                          'B': {'slots': [6, 7, 8], p_port_wwpns: [4, 5] } }

                        The slot indicates which slots from the client slots
                        align with which fabric.

    :param slot_peers: An array of arrays.  Indicates all of the slots that
                       need to be grouped together on a given VIOS.

                       Ex:
                       [ [3, 6, 7], [4, 8], [5] ]

                       Indicates that (based on the data from fabric_data)
                       one VIOS must host client slot 3 (from fabric A) and
                       slots 6 and 7 (from fabric B).  Then another VIOS must
                       host client slot 4 (from fabric A) and client slot 8
                       (from fabric B).  And the third VIOS must only host
                       client slot 5 (from fabric A).
    :return: List of mappings that can be passed into the migration.py
             for the live migration.  The format is defined within the
             migration.py, migrate_lpar method.
    """

    # First sort the slot peers.  The one with the most peers needs to go first
    # then work down from there.
    slot_peers = sorted(slot_peers, key=len, reverse=True)

    vios_to_split_map = {}

    # We create a map of all the VIOSes and their corresponding slots
    for peer_grouping in slot_peers:
        split_map = _split_ports_per_fabric(peer_grouping, fabric_data)
        LOG.debug("split_map %s" % split_map)
        for vios_w in vios_wraps:
            LOG.debug("Checking vios name %(name)s vios fc ports %(port)s" %
                      dict(name=vios_w.name,
                           port=[port.wwpn for port in vios_w.pfc_ports]))
            if vios_w in vios_to_split_map.keys():
                continue
            if not _does_vios_support_split_map(vios_w, split_map):
                continue
            vios_to_split_map[vios_w] = split_map
            break
        else:
            # When no vios match is found for peer group error
            raise e.UnableToFindFCPortMap()

    LOG.debug("vios_to_split_map %s" % vios_to_split_map)
    resp = []
    # Each VIOS has a split map.  the split map contains the fabric (as
    # the key), the physical port wwpns, and the slots.
    for vios_w, split_map in six.iteritems(vios_to_split_map):
        for fabric_map in six.itervalues(split_map):
            p_port_wwpns = fabric_map['p_port_wwpns']
            slots = fabric_map['slots']
            basic_mappings = derive_base_npiv_map([vios_w], p_port_wwpns,
                                                  len(slots))
            for basic_map, client_slot in zip(basic_mappings, slots):
                # Find the appropriate VIOS hosting this physical port.
                vios_w, port = find_vios_for_wwpn([vios_w], basic_map[0])

                # The format is:
                #     virtual-slot-number/vios-lpar-name/vios-lpar-ID
                #     [/[vios-virtual-slot-number][/[vios-fc-port-name]]]
                #
                # We do not specify the vios-virtual-slot-number.
                items = (str(client_slot), vios_w.name, str(vios_w.id),
                         '', port.name)
                resp.append("/".join(items))
    return resp
