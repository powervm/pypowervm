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

from pypowervm import exceptions as pvm_exc
from pypowervm import util as pvm_util
from pypowervm.utils import retry as pvm_retry
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import network as pvm_net

_MAX_VLANS_PER_VEA = 20
_MS_ROOT = pvm_ms.System.schema_type


@pvm_retry.retry()
def ensure_vlans_on_nb(adapter, host_uuid, nb_uuid, vlan_ids):
    """Will make sure that the VLANs are assigned to the Network Bridge.

    This method will reorder the arbitrary VLAN IDs as needed (those which are
    the PVID of the VEAs, but not the primary VEA).

    VLANs are always added to VEAs that are 'non-primary' (not the first VEA).
    However, if the VLAN is on the primary VEA then it is left on the system.
    The only 'untagged' VLAN that is allowed is the primary VEA's PVID.

    If the VLAN specified is on another Network Bridge's VEA (which happens
    to be on the same virtual switch):
     - An error will be thrown if it is on the primary VEA.
     - It will be removed off the Network Bridge if it is on the non-primary
       VEA.

    This method will not remove VLAN IDs from the network bridge that aren't
    part of the vlan_ids list.  Instead, each VLAN is simply added to the
    Network Bridge's VLAN list.

    :param adapter: The pypowervm Adapter.
    :param host_uuid: The Server's UUID
    :param nb_uuid: The Network Bridge UUID.
    :param vlan_ids: The list of VLANs to ensure are on the Network Bridge.
    """
    # Get the updated feed of NetworkBridges
    nb_feed = adapter.read(_MS_ROOT, root_id=host_uuid,
                           child_type=pvm_net.NetBridge.schema_type)
    nb_wraps = pvm_net.NetBridge.wrap(nb_feed)

    # Find the appropriate Network Bridge
    req_nb = pvm_util.find_wrapper(nb_wraps, nb_uuid)

    # Call down to the ensure_vlan_on_nb method only for the additions.
    new_vlans = []
    peer_nbs = _find_peer_nbs(nb_wraps, req_nb)
    all_nbs_on_vs = [req_nb]
    all_nbs_on_vs.extend(peer_nbs)

    # Need to evaluate the status of each VLAN.
    for vlan_id in vlan_ids:
        # No action required.  The VLAN is already part of the bridge.
        if req_nb.supports_vlan(vlan_id):
            continue

        # If its supported by a peer...
        for peer_nb in peer_nbs:
            if peer_nb.supports_vlan(vlan_id):
                # Remove the VLAN.
                remove_vlan_from_nb(adapter, host_uuid, nb_uuid, vlan_id,
                                    fail_if_pvid=True, existing_nbs=nb_wraps)
                break

        # If it is an arbitrary VLAN ID on our network.  This should be very
        # rare.  But if it does happen, we should re-order the VLANs and then
        # retry this whole method.
        if _is_arbitrary_vid(vlan_id, all_nbs_on_vs):
            # Find a new arbitrary VLAN ID, and re-assign the original value
            # to this new one.
            new_a_vid = _find_new_arbitrary_vid(all_nbs_on_vs, others=vlan_ids)
            _reassign_arbitrary_vid(adapter, host_uuid, vlan_id, new_a_vid,
                                    req_nb)
            return ensure_vlans_on_nb(adapter, host_uuid, nb_uuid, vlan_ids)

        # Lastly, if we're here...it must be a completely new VLAN.
        new_vlans.append(vlan_id)

    # If there are no new VLANs, no need to continue.
    if len(new_vlans) == 0:
        return

    # At this point, all of the new VLANs that need to be added are in the
    # new_vlans list.  Now we need to put them on load groups.
    vswitch_w = _find_vswitch(adapter, host_uuid, req_nb.vswitch_id)
    vnet_resp_feed = adapter.read(_MS_ROOT, root_id=host_uuid,
                                  child_type=pvm_net.VNet.schema_type)
    vnets = pvm_net.VNet.wrap(vnet_resp_feed)

    for vlan_id in new_vlans:
        ld_grp = _find_available_ld_grp(req_nb)
        vid_vnet = _find_or_create_vnet(adapter, host_uuid, vnets, vlan_id,
                                        vswitch_w, tagged=True)
        if ld_grp is None:
            # No load group means they're all full.  Need to create a new Load
            # Group.
            #
            # First, create a new 'non-tagging' virtual network
            arb_vid = _find_new_arbitrary_vid(all_nbs_on_vs, others=[vlan_id])
            arb_vnet = _find_or_create_vnet(adapter, host_uuid, vnets, arb_vid,
                                            vswitch_w, tagged=False)

            # Now create the new load group...
            vnet_uris = [arb_vnet.href, vid_vnet.href]
            ld_grp = pvm_net.LoadGroup.bld(arb_vid, vnet_uris)

            # Append to network bridge...
            req_nb.load_grps.append(ld_grp)
        else:
            # There was a Load Group.  Just need to append this vnet to it.
            ld_grp.virtual_network_uri_list.append(vid_vnet.href)

    # At this point, the network bridge should just need to be updated.  The
    # Load Groups on the Network Bridge should be correct.
    adapter.update(
        req_nb.element, req_nb.etag, _MS_ROOT, root_id=host_uuid,
        child_type=pvm_net.NetBridge.schema_type, child_id=req_nb.uuid)


@pvm_retry.retry()
def ensure_vlan_on_nb(adapter, host_uuid, nb_uuid, vlan_id):
    """Will make sure that the VLAN is assigned to the Network Bridge.

    This method will reorder the arbitrary VLAN IDs as needed (those which are
    the PVID of the VEAs, but not the primary VEA).

    VLANs are always added to VEAs that are 'non-primary' (not the first VEA).
    However, if the VLAN is on the primary VEA then it is left on the system.
    The only 'untagged' VLAN that is allowed is the primary VEA's PVID.

    If the VLAN specified is on another Network Bridge's VEA (which happens
    to be on the same virtual switch):
     - An error will be thrown if it is on the primary VEA.
     - It will be removed off the Network Bridge if it is on the non-primary
       VEA.

    :param adapter: The pypowervm Adapter.
    :param host_uuid: The Server's UUID
    :param nb_uuid: The Network Bridge UUID.
    :param vlan_id: The VLAN identifier to ensure is on the system.
    """
    ensure_vlans_on_nb(adapter, host_uuid, nb_uuid, [vlan_id])


def _find_vswitch(adapter, host_uuid, vswitch_id):
    """Gathers the VSwitch wrapper from the system.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host UUID for the system.
    :param vswitch_id: The identifier (not uuid) for the vswitch.
    :return: Wrapper for the corresponding VirtualSwitch.
    """
    resp_feed = adapter.read(
        _MS_ROOT, root_id=host_uuid, child_type=pvm_net.VSwitch.schema_type)
    vswitches = pvm_net.VSwitch.wrap(resp_feed)
    for vswitch in vswitches:
        if vswitch.switch_id == int(vswitch_id):
            return vswitch
    return None


def _find_or_create_vnet(adapter, host_uuid, vnets, vlan, vswitch,
                         tagged=True):
    """Will find (or create) the VNet.

    If the VirtualNetwork already exists but has a different tag attribute,
    this method will delete the old virtual network, and then recreate with
    the specified tagged value.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host_uuid for the system.
    :param vnets: The virtual network wrappers on the system.
    :param vlan: The VLAN to find.
    :param vswitch: The vSwitch wrapper.
    :param tagged: True if tagged traffic will flow through this network.
    :return: The VNet wrapper for this element.
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
    vnet_elem = pvm_net.VNet.bld(name, vlan, vswitch.href, tagged)
    resp = adapter.create(
        vnet_elem, _MS_ROOT, host_uuid, pvm_net.VNet.schema_type)
    return pvm_net.VNet.wrap(resp.entry)


def _find_available_ld_grp(nb):
    """Will return the Load Group that can support a new VLAN.

    :param nb: The NetBridge to search through.
    :returns: The LoadGroup within the NetBridge that can support a new
              VLAN.  If all are full, will return None.
    """
    # Never provision to the first load group.  We do this to keep consistency
    # with how projects have done in past.
    if len(nb.load_grps) == 1:
        return None

    ld_grps = nb.load_grps[1:]
    for ld_grp in ld_grps:
        if len(ld_grp.virtual_network_uri_list) < _MAX_VLANS_PER_VEA:
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


def _find_new_arbitrary_vid(all_nbs, others=()):
    """Returns a new VLAN ID that can be used as an arbitrary VID.

    :param all_nbs: All of the impacted network bridges.  Should all be on
                    the same vSwitch.
    :param others: List of other VLANs that should not be used as an arbitrary.
    :return: A new VLAN ID that is not in use by any network bridge on this
             vSwitch.
    """
    all_vlans = []

    for i_nb in all_nbs:
        all_vlans.extend(i_nb.list_vlans(pvid=True, arbitrary=True))
    all_vlans.extend(others)

    # Start at 4094, and walk down to find one that isn't already used.
    # Stop right before VLAN 1 as that is special in the system.
    for i in range(4094, 1, -1):
        if i not in all_vlans:
            return i
    return None


def _reassign_arbitrary_vid(adapter, host_uuid, old_vid, new_vid, impacted_nb):
    """Moves the arbitrary VLAN ID from one Load Group to another.

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
    vnet_resp_feed = adapter.read(_MS_ROOT, root_id=host_uuid,
                                  child_type=pvm_net.VNet.schema_type)
    vnets = pvm_net.VNet.wrap(vnet_resp_feed)

    # Read the old virtual network
    old_uri = _find_vnet_uri_from_lg(adapter, impacted_lg, old_vid)

    # Need to create the new Virtual Network
    new_vnet = _find_or_create_vnet(adapter, host_uuid, vnets, new_vid,
                                    vswitch_w, tagged=False)

    # Now we need to clone the load group
    uris = copy.copy(impacted_lg.virtual_network_uri_list)
    if old_uri is not None:
        uris.remove(old_uri)
    uris.insert(0, new_vnet.href)
    new_lg_w = pvm_net.LoadGroup.bld(new_vid, uris)

    impacted_nb.load_grps.remove(impacted_lg)

    # Need two updates.  One to remove the load group.
    nb_resp = adapter.update(impacted_nb.element, impacted_nb.etag,
                             _MS_ROOT, root_id=host_uuid,
                             child_type=pvm_net.NetBridge.schema_type,
                             child_id=impacted_nb.uuid)

    # A second to add the new load group in
    impacted_nb = pvm_net.NetBridge.wrap(nb_resp)
    impacted_nb.load_grps.append(new_lg_w)
    adapter.update(impacted_nb.element, impacted_nb.etag, _MS_ROOT,
                   root_id=host_uuid, child_type=pvm_net.NetBridge.schema_type,
                   child_id=impacted_nb.uuid)

    # Now that the old vid is detached from the load group, need to delete
    # the Virtual Network (because it was 'tagged' = False).
    if old_uri is not None:
        adapter.delete_by_href(old_uri)


def _find_peer_nbs(nb_wraps, nb):
    """Finds all of the peer (same vSwitch) Network Bridges.

    :param nb_wraps: List of pypowervm NetBridge wrappers.
    :param nb: The NetBridge to find.
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


@pvm_retry.retry()
def remove_vlan_from_nb(adapter, host_uuid, nb_uuid, vlan_id,
                        fail_if_pvid=False, existing_nbs=None):
    """Will remove the VLAN from a given Network Bridge.

    :param adapter: The pypowervm Adapter.
    :param host_uuid: The host system UUID.
    :param nb_uuid: The Network Bridge UUID.
    :param vlan_id: The VLAN identifier.
    :param fail_if_pvid: If set to true, will raise an exception if this is
                         the PVID on a Network Bridge.
    :param existing_nbs: Optional.  If set, should be the existing network
                         bridge wrappers.  If not provided, will gather from
                         the system directly.
    """
    if existing_nbs is not None:
        nb_wraps = existing_nbs
    else:
        # Get the updated feed of NetworkBridges
        nb_feed = adapter.read(_MS_ROOT, root_id=host_uuid,
                               child_type=pvm_net.NetBridge.schema_type)
        nb_wraps = pvm_net.NetBridge.wrap(nb_feed)

    # Find our Network Bridge
    req_nb = pvm_util.find_wrapper(nb_wraps, nb_uuid)

    # TODO(thorst) need to handle removing the VLAN if it is an arbitrary VID.

    # If the VLAN is not on the bridge, no action
    if not req_nb.supports_vlan(vlan_id):
        return

    # Fail if we're the PVID.
    if fail_if_pvid and req_nb.load_grps[0].pvid == vlan_id:
        raise pvm_exc.PvidOfNetworkBridgeError(vlan_id=vlan_id)

    # If this is on the first load group, we leave it.
    if (req_nb.load_grps[0].pvid == vlan_id or
            vlan_id in req_nb.load_grps[0].tagged_vlans or
            len(req_nb.load_grps) == 1):
        return

    # Find the matching load group.  Since the 'supports_vlan' passed before,
    # this will always return True.
    matching_lg = None
    for lg in req_nb.load_grps[1:]:
        if vlan_id in lg.tagged_vlans:
            matching_lg = lg
            break

    if len(matching_lg.tagged_vlans) == 1:
        # If last VLAN in Load Group, remove the whole Load Group
        req_nb.load_grps.remove(matching_lg)
    else:
        # Else just remove that virtual network
        vnet_uri = _find_vnet_uri_from_lg(adapter, matching_lg, vlan_id)
        matching_lg.virtual_network_uri_list.remove(vnet_uri)

    # Now update the network bridge.
    adapter.update(req_nb.element, req_nb.etag, _MS_ROOT,
                   root_id=host_uuid, child_type=pvm_net.NetBridge.schema_type,
                   child_id=req_nb.uuid)


def _find_vnet_uri_from_lg(adapter, lg, vlan):
    """Finds the Virtual Network for a VLAN within a LoadGroup.

    :param adapter: The pypowervm adapter to access the API.
    :param lg: The LoadGroup wrapper.
    :param vlan: The VLAN within the Load Group to look for.
    :return: The Virtual Network URI for the vlan.  If not found within the
             Load Group, None will be returned.
    """
    for vnet_uri in lg.virtual_network_uri_list:
        vnet_resp = adapter.read_by_href(vnet_uri)
        vnet_net = pvm_net.VNet.wrap(vnet_resp)
        if vnet_net.vlan == vlan:
            return vnet_net.href
    return None
