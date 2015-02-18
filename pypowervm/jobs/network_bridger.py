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

import copy

from pypowervm import util as pvm_util
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import network as pvm_net


def ensure_vlan_on_nb(adapter, host_uuid, nb_uuid, vlan_id):
    """Will make sure that the VLAN is assigned to the Network Bridge.

    :param adapter: The pypowervm Adapter.
    :param host_uuid: The Server's UUID
    :param nb_uuid: The Network Bridge UUID.
    :param vlan_id: The VLAN identifier to ensure is on the system.
    """
    # Get the updated feed of NetworkBridges
    nb_feed = adapter.read(pvm_ms.MS_ROOT, root_id=host_uuid,
                           child_type=pvm_net.NB_ROOT)
    nb_wraps = pvm_net.NetworkBridge.load_from_response(nb_feed)

    # Find our SEA
    req_nb = pvm_util.find_wrapper(nb_wraps, nb_uuid)

    # If the VLAN is already on the SEA, no action
    if req_nb.supports_vlan(vlan_id):
        return

    # If not, we need to find out if another SEA has the VLAN.  This should
    # be done within the virtual switch boundary.
    peer_nbs = _find_peer_nbs(nb_wraps, req_nb)
    for peer_nb in peer_nbs:
        if peer_nb.supports_vlan(vlan_id):
            # We need to remove that VLAN.
            remove_vlan_from_nb(adapter, host_uuid, nb_uuid, vlan_id,
                                fail_if_pvid=True)

    # Determine if this VLAN is an arbitrary VID on any peer NB.  If so, we
    # need to re-order the arbitrary VID out.
    all_nbs_on_vs = [req_nb]
    all_nbs_on_vs.extend(peer_nbs)
    if _is_arbitrary_vid(vlan_id, all_nbs_on_vs):
        # Find a new arbitrary VLAN ID, and re-assign the original value
        # to this new one.
        new_a_vid = _find_new_arbitrary_vid(all_nbs_on_vs)
        _reassign_arbitrary_vid(adapter, host_uuid, vlan_id, new_a_vid, req_nb)

        # At this point, we should restart this method (which won't hit this
        # block again) so we regenerate the data and etags.
        return ensure_vlan_on_nb(adapter, host_uuid, nb_uuid, vlan_id)

    # At this point, we need to create a new Virtual Network and put it on
    # the NetworkBridge.
    #
    # This is where it starts to get expensive.  Feeds for multiple objects
    # are needed.
    #
    # Start by building (or finding) the virtual network for the vlan being
    # requested.
    vswitch_w = _find_vswitch(adapter, host_uuid, req_nb.vswitch_id)
    vnet_resp_feed = adapter.read(pvm_ms.MS_ROOT, root_id=host_uuid,
                                  child_type=pvm_net.VNET_ROOT)
    vnets = pvm_net.VirtualNetwork.load_from_response(vnet_resp_feed)
    vid_vnet = _find_or_create_vnet(adapter, host_uuid, vnets, vlan_id,
                                    vswitch_w, tagged=True)

    # Now find the appropriate Load Group that the virtual network can
    # be added to.
    ld_grp = _find_available_ld_grp(req_nb)
    if ld_grp is None:
        # No load group means they're all full.  Need to create a new Load
        # Group.
        #
        # First, create a new 'non-tagging' virtual network
        arb_vid = _find_new_arbitrary_vid(all_nbs_on_vs)
        arb_vnet = _find_or_create_vnet(adapter, host_uuid, vnets, arb_vid,
                                        vswitch_w, False)

        # Now create the new load group...
        vnet_uris = [arb_vnet.href, vid_vnet.href]
        ld_grp = pvm_net.LoadGroup(pvm_net.crt_load_group(arb_vid, vnet_uris))

        # Append to network bridge...
        req_nb.load_grps.append(ld_grp)
    else:
        # There was a Load Group.  Just need to append this vnet to it.
        ld_grp.virtual_network_uri_list.append(vid_vnet.href)

    # At this point, the network bridge should just need to be updated.  The
    # Load Groups on the Network Bridge should be correct.
    adapter.update(req_nb._element, req_nb.etag, pvm_ms.MS_ROOT,
                   root_id=host_uuid, child_type=pvm_net.NB_ROOT,
                   child_id=req_nb.uuid)


def _find_vswitch(adapter, host_uuid, vswitch_id):
    """Gathers the VirtualSwitch wrapper from the system.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host UUID for the system.
    :param vswitch_id: The identifier (not uuid) for the vswitch.
    :return: Wrapper for the corresponding VirtualSwitch.
    """
    resp_feed = adapter.read(pvm_ms.MS_ROOT, root_id=host_uuid,
                             child_type=pvm_net.VSW_ROOT)
    vswitches = pvm_net.VirtualSwitch.load_from_response(resp_feed)
    for vswitch in vswitches:
        if vswitch.switch_id == int(vswitch_id):
            return vswitch
    return None


def _find_or_create_vnet(adapter, host_uuid, vnets, vlan, vswitch,
                         tagged=True):
    """Will find (or create) the VirtualNetwork.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host_uuid for the system.
    :param vnets: The virtual network wrappers on the system.
    :param vlan: The VLAN to find.
    :param vswitch: The vSwitch wrapper.
    :param tagged: True if tagged traffic will flow through this network.
    :return: The VirtualNetwork wrapper for this element.
    """
    # Look through the list of vnets passed in
    for vnet in vnets:
        if vnet.vlan == vlan and vnet.vswitch_id == vswitch.switch_id:
            if tagged == vnet.tagged:
                return vnet
            else:
                # We found a matching vNet, but the tag was wrong.  Need to
                # delete it.
                adapter.delete_by_href(vnet.href)
                break

    # Could not find one.  Time to create it.
    name = 'VLAN%(vid)s-%(vswitch)s' % {'vid': str(vlan),
                                        'vswitch': vswitch.name}
    vnet_elem = pvm_net.crt_vnet(name, vlan, vswitch.href, tagged)
    resp = adapter.create(vnet_elem, pvm_ms.MS_ROOT, host_uuid,
                          pvm_net.VNET_ROOT)
    return pvm_net.VirtualNetwork.load_from_response(resp)


def _find_available_ld_grp(nb):
    """Will return the Load Group that can support a new VLAN.

    :param nb: The NetworkBridge to search through.
    :returns: The LoadGroup within the NetworkBridge that can support a new
              VLAN.  If all are full, will return None.
    """
    # Never provision to the first load group.
    if len(nb.load_grps) == 1:
        return None

    ld_grps = nb.load_grps[1:]
    for ld_grp in ld_grps:
        if len(ld_grp.virtual_network_uri_list) < 19:
            return ld_grp
    return None


def _is_arbitrary_vid(vlan, all_nbs):
    """Returns if the VLAN is an arbitrary PVID on any passed in network.

    :param vlan: The VLAN to check.
    :param all_nbs: All of the network bridges on a given vSwitch.
    :return: The network bridge that this is an arbitrary VLAN on.
    """
    for nb in all_nbs:
        if vlan in nb.arbitrary_pvids:
            return nb
    return None


def _find_new_arbitrary_vid(all_nbs):
    """Returns a new VLAN ID that can be used as an arbitrary VID.

    :param all_nbs: All of the impacted network bridges.  Should all be on
                    the same vSwitch.
    :return: A new VLAN ID that is not in use by any network bridge on this
             vSwitch.
    """
    all_vlans = []

    for i_nb in all_nbs:
        all_vlans.extend(i_nb.list_vlans(pvid=True, arbitrary=True))

    # Start at 4094, and walk down to find one that isn't already used.
    for i in range(4094, 1, -1):
        if i not in all_vlans:
            return i
    return None


def _reassign_arbitrary_vid(adapter, host_uuid, old_vid, new_vid, impacted_nb):
    """Moves the arbitrary VLAN ID from one value to another.

    :param adapter: The adapter to powervm.
    :param host_uuid: The host system UUID.
    :param old_vid: The original arbitrary VLAN ID.
    :param new_vid: The new arbitrary VLAN ID.
    :param impacted_nb: The network bridge that is impacted.
    """
    # Find the Load Group that has this arbitrary VID
    impacted_lg = None
    for ld_grp in impacted_nb.load_grps:
        if ld_grp.pvid == old_vid:
            impacted_lg = ld_grp
            break

    # For the _find_or_create_vnet, we need to query all the virtual networks
    vswitch_w = _find_vswitch(adapter, host_uuid, impacted_nb.vswitch_id)
    vnet_resp_feed = adapter.read(pvm_ms.MS_ROOT, root_id=host_uuid,
                                  child_type=pvm_net.VNET_ROOT)
    vnets = pvm_net.VirtualNetwork.load_from_response(vnet_resp_feed)

    # Read the old virtual network
    vnet_resp = adapter.read_by_href(impacted_lg.virtual_network_uri_list[0])
    old_vnet = pvm_net.VirtualNetwork.load_from_response(vnet_resp)

    # Need to create the new Virtual Network
    new_vnet = _find_or_create_vnet(adapter, host_uuid, vnets, new_vid,
                                    vswitch_w, tagged=False)

    # Now we need to clone the load group
    uris = copy.copy(impacted_lg.virtual_network_uri_list)
    uris[0] = new_vnet.href
    new_lg = pvm_net.crt_load_group(new_vid, uris)
    new_lb_w = pvm_net.LoadGroup(new_lg)

    impacted_nb.load_grps.remove(impacted_lg)
    impacted_nb.load_grps.append(new_lb_w)

    # Update the network bridge
    adapter.update(impacted_nb._element, impacted_nb.etag, pvm_ms.MS_ROOT,
                   root_id=host_uuid, child_type=pvm_net.NB_ROOT,
                   child_id=impacted_nb.uuid)

    # Now that the old vid is detached from the load group, need to delete
    # the Virtual Network (because it was 'tagged' = False).
    adapter.delete_by_href(old_vnet.href)


def _find_peer_nbs(nb_wraps, nb):
    """Finds all of the peer (same vSwitch) Network Bridges.

    :param nb_wraps: List of pypowervm NetworkBridge wrappers.
    :param nb: The NetworkBridge to find.
    :return: List of Network Bridges on the same vSwitch as the seed.  Does
             not include the nb element.
    """
    # Find the vswitch to search for.
    vs_search_id = nb.seas[0].primary_adpt.vswitch_id

    ret = []
    for nb_elem in nb_wraps:
        # Don't include self.
        if nb.uuid == nb_elem.uuid:
            continue

        # See if the vswitches match
        other_vs_id = nb_elem.seas[0].primary_adpt.vswitch_id
        if other_vs_id == vs_search_id:
            ret.append(nb_elem)
    return ret


def remove_vlan_from_nb(adapter, host_uuid, nb_uuid, vlan_id,
                        fail_if_pvid=False):
    """Will remove the VLAN from a given Network Bridge.

    :param adapter: The pypowervm Adapter.
    :param host_uuid: The host system UUID.
    :param nb_uuid: The Network Bridge UUID.
    :param vlan_id: The VLAN identifier.
    :param fail_if_pvid: If set to true, will raise an exception if this is
                         the PVID on a Network Bridge.
    """
    # TODO(thorst) Implement
    pass
