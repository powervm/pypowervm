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

"""Manage NetworkBridge, TrunkAdapter, LoadGroup, SEA, etc."""

import abc
import copy

import six

from pypowervm import exceptions as pvm_exc
from pypowervm import util as pvm_util
from pypowervm.utils import retry as pvm_retry
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import network as pvm_net

_MAX_VLANS_PER_VEA = 20


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
    _get_bridger(adapter, host_uuid).ensure_vlans_on_nb(nb_uuid, vlan_ids)


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
    _get_bridger(adapter, host_uuid).remove_vlan_from_nb(nb_uuid, vlan_id,
                                                         fail_if_pvid,
                                                         existing_nbs)


def _get_bridger(adapter, host_uuid):
    """Returns the appropriate bridger for the action."""
    if adapter.traits.vnet_aware:
        return NetworkBridgerVNET(adapter, host_uuid)
    else:
        return NetworkBridgerTA(adapter, host_uuid)


@six.add_metaclass(abc.ABCMeta)
class NetworkBridger(object):
    """Defines the high level flows for the VLAN provisioning.

    This class has the generic flows, subclasses extend this for the
    derivations of vnet_aware and direct VLAN application.
    """

    def __init__(self, adapter, host_uuid):
        """Creates the bridger.

        :param adapter: The pypowervm Adapter.
        :param host_uuid: The host systems's UUID
        """
        self.adapter = adapter
        self.host_uuid = host_uuid

    @pvm_retry.retry()
    def ensure_vlans_on_nb(self, nb_uuid, vlan_ids):
        """Will make sure that the VLANs are assigned to the Network Bridge.

        This method will reorder the arbitrary VLAN IDs as needed (those which
        are the PVID of the TrunkAdapter, but not the primary TrunkAdapter).

        VLANs are always added to TrunkAdapters that are 'non-primary' (not the
        first TrunkAdapter).  However, if the VLAN is on the primary
        TrunkAdapter then it is left on the system. The only 'untagged' VLAN
        that is allowed is the primary TrunkAdapter's PVID.

        If the VLAN specified is on another Network Bridge's TrunkAdapter
        (which happens to be on the same virtual switch):
         - An error will be thrown if it is on the primary TrunkAdapter.
         - It will be removed off the Network Bridge if it is on the
           non-primary TrunkAdapter.

        This method will not remove VLAN IDs from the network bridge that
        aren't part of the vlan_ids list.  Instead, each VLAN is simply added
        to the Network Bridge's VLAN list.

        :param nb_uuid: The Network Bridge UUID.
        :param vlan_ids: The list of VLANs to ensure are on the Network Bridge.
        """
        # Ensure the VLANs are ints, not strings.
        vlan_ids = [int(x) for x in vlan_ids]

        # Get the updated feed of NetworkBridges
        nb_feed = self.adapter.read(pvm_ms.System.schema_type,
                                    root_id=self.host_uuid,
                                    child_type=pvm_net.NetBridge.schema_type)
        nb_wraps = pvm_net.NetBridge.wrap(nb_feed)

        # Find the appropriate Network Bridge
        req_nb = pvm_util.find_wrapper(nb_wraps, nb_uuid)

        # Call down to the ensure_vlan_on_nb method only for the additions.
        new_vlans = []
        peer_nbs = self._find_peer_nbs(nb_wraps, req_nb)
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
                    self.remove_vlan_from_nb(nb_uuid, vlan_id,
                                             fail_if_pvid=True,
                                             existing_nbs=nb_wraps)
                    break

            # If it is an arbitrary VLAN ID on our network.  This should be
            # very rare.  But if it does happen, we should re-order the VLANs
            # and then retry this whole method.
            if self._is_arbitrary_vid(vlan_id, all_nbs_on_vs):
                # Find a new arbitrary VLAN ID, and re-assign the original
                # value to this new one.
                new_a_vid = self._find_new_arbitrary_vid(all_nbs_on_vs,
                                                         others=vlan_ids)
                self._reassign_arbitrary_vid(vlan_id, new_a_vid, req_nb)
                return self.ensure_vlans_on_nb(nb_uuid, vlan_ids)

            # Lastly, if we're here...it must be a completely new VLAN.
            new_vlans.append(vlan_id)

        # If there are no new VLANs, no need to continue.
        if len(new_vlans) == 0:
            return

        # At this point, all of the new VLANs that need to be added are in the
        # new_vlans list.  Now we need to put them on load groups.
        self._add_vlans_to_nb(req_nb, all_nbs_on_vs, new_vlans)

        # At this point, the network bridge should just need to be updated.
        # The Load Groups on the Network Bridge should be correct.
        req_nb.update()

    @pvm_retry.retry()
    def remove_vlan_from_nb(self, nb_uuid, vlan_id, fail_if_pvid=False,
                            existing_nbs=None):
        """Will remove the VLAN from a given Network Bridge.

        :param nb_uuid: The Network Bridge UUID.
        :param vlan_id: The VLAN identifier.
        :param fail_if_pvid: If set to true, will raise an exception if this is
                             the PVID on a Network Bridge.
        :param existing_nbs: Optional.  If set, should be the existing network
                             bridge wrappers.  If not provided, will gather
                             from the system directly.
        """
        # Ensure we're working with an integer
        vlan_id = int(vlan_id)

        if existing_nbs is not None:
            nb_wraps = existing_nbs
        else:
            # Get the updated feed of NetworkBridges
            nb_feed = self.adapter.read(
                pvm_ms.System.schema_type, root_id=self.host_uuid,
                child_type=pvm_net.NetBridge.schema_type)
            nb_wraps = pvm_net.NetBridge.wrap(nb_feed)

        # Find our Network Bridge
        req_nb = pvm_util.find_wrapper(nb_wraps, nb_uuid)

        # TODO(thorst) need to handle removing the VLAN if it is an arbitrary
        # VID.

        # If the VLAN is not on the bridge, no action
        if not req_nb.supports_vlan(vlan_id):
            return

        # Fail if we're the PVID.
        if fail_if_pvid and req_nb.load_grps[0].pvid == vlan_id:
            raise pvm_exc.PvidOfNetworkBridgeError(vlan_id=vlan_id)

        # If this is on the first load group/trunk adapter, we leave it.
        if (req_nb.load_grps[0].pvid == vlan_id or
                vlan_id in req_nb.load_grps[0].tagged_vlans or
                len(req_nb.load_grps) == 1):
            return

        # Rip the VLAN out of the wrapper element.
        self._remove_vlan_from_nb(req_nb, vlan_id)

        # Now update the network bridge.
        req_nb.update()

    def _is_arbitrary_vid(self, vlan, all_nbs):
        """Returns if the VLAN is an arbitrary PVID on any passed in network.

        :param vlan: The VLAN to check.
        :param all_nbs: All of the network bridges on a given vSwitch.
        :return: The network bridge that this is an arbitrary VLAN on.
        """
        for nb in all_nbs:
            if vlan in nb.arbitrary_pvids:
                return nb
        return None

    def _find_new_arbitrary_vid(self, all_nbs, others=()):
        """Returns a new VLAN ID that can be used as an arbitrary VID.

        :param all_nbs: All of the impacted network bridges.  Should all be on
                        the same vSwitch.
        :param others: List of other VLANs that should not be used as an
                       arbitrary.
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

    def _find_vswitch(self, vswitch_id):
        """Gathers the VSwitch wrapper from the system.

        :param vswitch_id: The identifier (not uuid) for the vswitch.
        :return: Wrapper for the corresponding VirtualSwitch.
        """
        resp_feed = self.adapter.read(
            pvm_ms.System.schema_type, root_id=self.host_uuid,
            child_type=pvm_net.VSwitch.schema_type)
        vswitches = pvm_net.VSwitch.wrap(resp_feed)
        for vswitch in vswitches:
            if vswitch.switch_id == int(vswitch_id):
                return vswitch
        return None

    def _find_peer_nbs(self, nb_wraps, nb):
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

    def _reassign_arbitrary_vid(self,  old_vid, new_vid, impacted_nb):
        """Moves the arbitrary VLAN ID from one Load Group to another.

        Should perform the actual update to the API.

        :param old_vid: The original arbitrary VLAN ID.
        :param new_vid: The new arbitrary VLAN ID.
        :param impacted_nb: The network bridge that is impacted.
        """
        raise NotImplementedError()

    def _add_vlans_to_nb(self, req_nb, all_nbs_on_vs, new_vlans):
        """Adds the VLANs to the Network Bridge Wrapper.

        :param req_nb: The NetworkBridge to add the VLANs to.  After this
                       method is complete, this req_nb will have the
                       appropriate information to perform an update to the
                       API.
        :param all_nbs_on_vs: List of all the network bridges on the virtual
                              switch.
        :param new_vlans: List of the new VLANs to put on the network bridge.
        """
        raise NotImplementedError()

    def _remove_vlan_from_nb(self, req_nb, vlan_id):
        """Removes the VLAN from the Network Bridge wrapper.

        :param req_nb: The Network Bridge.  Upon return, the wrapper should
                       not support the VLAN.
        :param vlan_id: The VLAN ID to remove.
        """
        raise NotImplementedError()


class NetworkBridgerVNET(NetworkBridger):
    """The virtual network aware NetworkBridger."""

    def _add_vlans_to_nb(self, req_nb, all_nbs_on_vs, new_vlans):
        """Adds the VLANs to the Network Bridge Wrapper.

        :param req_nb: The NetworkBridge to add the VLANs to.  After this
                       method is complete, this req_nb will have the
                       appropriate information to perform an update to the
                       API.
        :param all_nbs_on_vs: List of all the network bridges on the virtual
                              switch.
        :param new_vlans: List of the new VLANs to put on the network bridge.
        """
        # At this point, all of the new VLANs that need to be added are in the
        # new_vlans list.  Now we need to put them on load groups.
        vswitch_w = self._find_vswitch(req_nb.vswitch_id)
        vnet_resp_feed = self.adapter.read(pvm_ms.System.schema_type,
                                           root_id=self.host_uuid,
                                           child_type=pvm_net.VNet.schema_type)
        vnets = pvm_net.VNet.wrap(vnet_resp_feed)

        for vlan_id in new_vlans:
            ld_grp = self._find_available_ld_grp(req_nb)
            vid_vnet = self._find_or_create_vnet(vnets, vlan_id, vswitch_w,
                                                 tagged=True)
            if ld_grp is None:
                # No load group means they're all full.  Need to create a new
                # Load Group.
                #
                # First, create a new 'non-tagging' virtual network
                arb_vid = self._find_new_arbitrary_vid(all_nbs_on_vs,
                                                       others=new_vlans)
                arb_vnet = self._find_or_create_vnet(vnets, arb_vid, vswitch_w,
                                                     tagged=False)

                # Now create the new load group...
                vnet_uris = [arb_vnet.related_href, vid_vnet.related_href]
                ld_grp = pvm_net.LoadGroup.bld(self.adapter, arb_vid,
                                               vnet_uris)

                # Append to network bridge...
                req_nb.load_grps.append(ld_grp)
            else:
                # There was a Load Group.  Just need to append this vnet to it.
                ld_grp.vnet_uri_list.append(vid_vnet.related_href)

    def _remove_vlan_from_nb(self, req_nb, vlan_id):
        """Removes the VLAN from the Network Bridge wrapper.

        :param req_nb: The Network Bridge.  Upon return, the wrapper should
                       not support the VLAN.
        :param vlan_id: The VLAN ID to remove.
        """
        # Find the matching load group.  Since the 'supports_vlan' passed
        # before, this will always find a value.
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
            vnet_uri = self._find_vnet_uri_from_lg(matching_lg, vlan_id)
            matching_lg.vnet_uri_list.remove(vnet_uri)

    def _reassign_arbitrary_vid(self,  old_vid, new_vid, impacted_nb):
        """Moves the arbitrary VLAN ID from one Load Group to another.

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

        # For the _find_or_create_vnet, we need to query all the virtual
        # networks
        vswitch_w = self._find_vswitch(impacted_nb.vswitch_id)
        vnet_resp_feed = self.adapter.read(
            pvm_ms.System.schema_type, root_id=self.host_uuid,
            child_type=pvm_net.VNet.schema_type)
        vnets = pvm_net.VNet.wrap(vnet_resp_feed)

        # Read the old virtual network
        old_uri = self._find_vnet_uri_from_lg(impacted_lg, old_vid)

        # Need to create the new Virtual Network
        new_vnet = self._find_or_create_vnet(vnets, new_vid, vswitch_w,
                                             tagged=False)

        # Now we need to clone the load group
        uris = copy.copy(impacted_lg.vnet_uri_list)
        if old_uri is not None:
            uris.remove(old_uri)
        uris.insert(0, new_vnet.related_href)
        new_lg_w = pvm_net.LoadGroup.bld(self.adapter, new_vid, uris)

        impacted_nb.load_grps.remove(impacted_lg)

        # Need two updates.  One to remove the load group.
        impacted_nb = impacted_nb.update()

        # A second to add the new load group in
        impacted_nb.load_grps.append(new_lg_w)
        impacted_nb = impacted_nb.update()

        # Now that the old vid is detached from the load group, need to delete
        # the Virtual Network (because it was 'tagged' = False).
        if old_uri is not None:
            self.adapter.delete_by_href(old_uri)

    def _find_or_create_vnet(self, vnets, vlan, vswitch,
                             tagged=True):
        """Will find (or create) the VNet.

        If the VirtualNetwork already exists but has a different tag attribute,
        this method will delete the old virtual network, and then recreate with
        the specified tagged value.

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
                    self.adapter.delete_by_href(vnet.href)
                    break

        # Could not find one.  Time to create it.
        name = 'VLAN%(vid)s-%(vswitch)s' % {'vid': str(vlan),
                                            'vswitch': vswitch.name}
        vnet_elem = pvm_net.VNet.bld(
            self.adapter, name, vlan, vswitch.related_href, tagged)
        return vnet_elem.create(parent_type=pvm_ms.System,
                                parent_uuid=self.host_uuid)

    def _find_available_ld_grp(self, nb):
        """Will return the Load Group that can support a new VLAN.

        :param nb: The NetBridge to search through.
        :returns: The LoadGroup within the NetBridge that can support a new
                  VLAN.  If all are full, will return None.
        """
        # Never provision to the first load group.  We do this to keep
        # consistency with how projects have done in past.
        if len(nb.load_grps) == 1:
            return None

        ld_grps = nb.load_grps[1:]
        for ld_grp in ld_grps:
            if len(ld_grp.vnet_uri_list) < _MAX_VLANS_PER_VEA:
                return ld_grp
        return None

    def _find_vnet_uri_from_lg(self, lg, vlan):
        """Finds the Virtual Network for a VLAN within a LoadGroup.

        :param lg: The LoadGroup wrapper.
        :param vlan: The VLAN within the Load Group to look for.
        :return: The Virtual Network URI for the vlan.  If not found within the
                 Load Group, None will be returned.
        """
        for vnet_uri in lg.vnet_uri_list:
            vnet_resp = self.adapter.read_by_href(vnet_uri)
            vnet_net = pvm_net.VNet.wrap(vnet_resp)
            if vnet_net.vlan == vlan:
                return vnet_net.related_href
        return None


class NetworkBridgerTA(NetworkBridger):
    """The Trunk Adapter aware NetworkBridger."""

    def _reassign_arbitrary_vid(self,  old_vid, new_vid, impacted_nb):
        """Moves the arbitrary VLAN ID from one Load Group to another.

        Should perform the actual update to the API.

        :param old_vid: The original arbitrary VLAN ID.
        :param new_vid: The new arbitrary VLAN ID.
        :param impacted_nb: The network bridge that is impacted.
        """
        # Find the Trunk Adapters that has this arbitrary VID
        impacted_tas = (None, None)
        for ta in impacted_nb.seas[0].addl_adpts:
            if ta.pvid == old_vid:
                impacted_tas = self._trunk_list(impacted_nb, ta)
                break

        # For each Trunk Adapter, change the VID to the new value.
        for ta in impacted_tas:
                ta.pvid = new_vid

        # Call the update
        impacted_nb = impacted_nb.update()

    def _add_vlans_to_nb(self, req_nb, all_nbs_on_vs, new_vlans):
        """Adds the VLANs to the Network Bridge Wrapper.

        :param req_nb: The NetworkBridge to add the VLANs to.  After this
                       method is complete, this req_nb will have the
                       appropriate information to perform an update to the
                       API.
        :param all_nbs_on_vs: List of all the network bridges on the virtual
                              switch.
        :param new_vlans: List of the new VLANs to put on the network bridge.
        """
        # At this point, all of the new VLANs that need to be added are in the
        # new_vlans list.  Now we need to put them on trunk adapters.
        vswitch_w = self._find_vswitch(req_nb.vswitch_id)
        for vlan_id in new_vlans:
            trunks = self._find_available_trunks(req_nb)

            if trunks is None:
                # No trunk adapter list means they're all full.  Need to create
                # a new Trunk Adapter (or pair) for the new VLAN.
                arb_vid = self._find_new_arbitrary_vid(all_nbs_on_vs,
                                                       others=new_vlans)

                for sea in req_nb.seas:
                    trunk = pvm_net.TrunkAdapter.bld(
                        self.adapter, arb_vid, [vlan_id], vswitch_w,
                        trunk_pri=sea.primary_adpt.trunk_pri)
                    sea.addl_adpts.append(trunk)
            else:
                # Available trunks were found.  Add the VLAN to each
                for trunk in trunks:
                    trunk.tagged_vlans.append(vlan_id)

    def _remove_vlan_from_nb(self, req_nb, vlan_id):
        """Removes the VLAN from the Network Bridge wrapper.

        :param req_nb: The Network Bridge.  Upon return, the wrapper should
                       not support the VLAN.
        :param vlan_id: The VLAN ID to remove.
        """
        # Find the matching trunk adapter.
        matching_tas = None
        for trunk in req_nb.seas[0].addl_adpts:
            if vlan_id in trunk.tagged_vlans:
                matching_tas = self._trunk_list(req_nb, trunk)
                break

        for matching_ta in matching_tas:
            if len(matching_ta.tagged_vlans) == 1:
                # Last VLAN, so it can be removed from the SEA.
                for sea in req_nb.seas:
                    if matching_ta in sea.addl_adpts:
                        sea.addl_adpts.remove(matching_ta)
                        break
            else:
                # Otherwise, we just remove it from the list.
                matching_ta.tagged_vlans.remove(vlan_id)

    def _find_peer_trunk(self, nb, ta):
        """Finds the peer adapter when the network bridge is failover ready.

        When a Network Bridge is set up for failover, there are two SEAs.  Each
        is essentially a mirror of each other, but are on different Virtual
        I/O Servers.  This means identical Trunk Adapters - but a different
        physical adapters.

        This method finds the 'peer' adapter, that happens to be on a different
        I/O Server.

        :param nb: The network bridge wrapper.
        :param ta: The Trunk Adapter from the first SEA in the network bridge.
        :return: The peer adapter per the above criteria.  If the network
                 bridge is not set up for failover, then None is returned.
        """
        if len(nb.seas) <= 1:
            return None

        sea = nb.seas[1]
        if ta.is_primary:
            return sea.primary_adpt

        for addl_adpt in sea.addl_adpts:
            if addl_adpt.pvid == ta.pvid:
                return addl_adpt

        return None

    def _trunk_list(self, nb, ta):
        """For a given trunk adapter, builds the list of trunks to modify.

        :param nb: The network bridge wrapper.
        :param ta: The Trunk Adapter from the first SEA in the network bridge.
        :return: List of trunk adapters.  Includes the peer.  If no peer, then
                 only one element is returned in the list.
        """
        peer = self._find_peer_trunk(nb, ta)
        if peer:
            return [ta, peer]
        else:
            return [ta]

    def _find_available_trunks(self, nb):
        """Will return a list of Trunk Adapters that can support a new VLAN.

        :param nb: The NetBridge to search through.
        :returns: A set of trunk adapters that can support the new VLAN.  If
                  None are found, then None is returned.
        """
        # Only provision to the Additional Trunks.
        for trunk in nb.seas[0].addl_adpts:
            if len(trunk.tagged_vlans) < _MAX_VLANS_PER_VEA:
                return self._trunk_list(nb, trunk)
        return None
