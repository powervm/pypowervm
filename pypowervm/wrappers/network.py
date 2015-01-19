# Copyright 2014, 2015 IBM Corp.
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

import logging

import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

VSW_NAME = 'SwitchName'
VSW_ID = 'SwitchID'
VSW_MODE = 'SwitchMode'

NB_PVID = 'PortVLANID'
NB_VNETS = 'VirtualNetworks'
NB_SEAS = 'SharedEthernetAdapters'
NB_SEA = 'SharedEthernetAdapter'
NB_LG = 'LoadGroup'
NB_LGS = 'LoadGroups'

SEA_ROOT = 'SharedEthernetAdapter'
SEA_TRUNKS = 'TrunkAdapters'

TA_ROOT = 'TrunkAdapter'
TA_PVID = 'PortVLANID'
TA_DEV_NAME = 'DeviceName'
TA_TAG_SUPP = 'TaggedVLANSupported'
TA_VLAN_IDS = 'TaggedVLANIDs'
TA_VS_ID = 'VirtualSwitchID'
TA_TRUNK_PRI = 'TrunkPriority'

LG_ROOT = 'LoadGroup'
LG_PVID = 'PortVLANID'
LG_TRUNKS = 'TrunkAdapters'
LG_VNETS = 'VirtualNetworks'


class VirtualSwitch(ewrap.EntryWrapper):
    """Wraps the Virtual Switch entries.

    The virtual switch in PowerVM is an independent plan of traffic.  If
    Ethernet packets are traveling on different virtual switches, the only
    time they can communicate is on the physical network plane (or if two
    logical adapters are bridged together).  They are important for data
    plan segregation.
    """

    def get_name(self):
        """The name associated with the Virtual Switch."""
        name = self.get_parm_value(VSW_NAME)
        if name == 'ETHERNET0(Default)':
            return 'ETHERNET0'
        return name

    def get_switch_id(self):
        """The internal ID (not UUID) for the Virtual Switch."""
        return self.get_parm_value_int(VSW_ID)

    def get_mode(self):
        """The mode that the switch is in (ex. VEB)."""
        return self.get_parm_value(VSW_MODE)


class NetworkBridge(ewrap.EntryWrapper):
    """Wrapper object for the NetworkBridge entry.

    A NetworkBridge represents an aggregate entity comprising Shared
    Ethernet Adapters.  If Failover or Load-Balancing is in use, the
    Network Bridge will have two identically structured Shared Ethernet
    Adapters belonging to different Virtual I/O Servers.
    """

    def get_pvid(self):
        """Returns the Primary VLAN ID of the Network Bridge."""
        return self.get_parm_value_int(NB_PVID)

    def get_virtual_network_uri_list(self):
        """Returns a list of the Virtual Network URIs."""
        virt_net_list = self._entry.element.find(NB_VNETS)
        uri_resp_list = []
        for virt_net in virt_net_list.findall(c.LINK):
            uri_resp_list.append(virt_net.get('href'))
        return uri_resp_list

    def get_seas(self):
        """Returns a list of SharedEthernetAdapter wrappers."""
        sea_elem_list = self._entry.element.findall(NB_SEAS + c.DELIM + NB_SEA)
        sea_list = []
        for sea_elem in sea_elem_list:
            sea_list.append(SharedEthernetAdapter(sea_elem))
        return sea_list

    def get_prim_load_grp(self):
        """Returns the primary Load Group for the Network Bridge."""
        return self._get_load_grps()[0]

    def get_addl_load_grps(self):
        """Ordered list of additional Load Groups on the Network Bridge.

        Does not include the primary Load Group.
        """

        return self._get_load_grps()[1:]

    def _get_load_grps(self):
        """Returns all of the Load Groups.

        The first element is the primary Load Group.  All others are
        subordinates.
        """
        ld_grp_list = self._entry.element.findall(NB_LGS + c.DELIM + NB_LG)
        ld_grps = []
        for ld_grp in ld_grp_list:
            ld_grps.append(LoadGroup(ld_grp))
        return ld_grps

    def supports_vlan(self, vlan):
        """Determines if the VLAN can flow through the Network Bridge.

        The VLAN can flow through if either of the following applies:
         - It is the primary VLAN of the primary Load Group
         - It is an additional VLAN on any Load Group

        Therefore, the inverse is true and the VLAN is not supported by the
        Network Bridge if the following:
         - The VLAN is not on the Network Bridge
         - The VLAN is a primary VLAN on a NON-primary Load Group

        :param vlan: The VLAN to query for.  Can be a string or a number.
        :returns: True or False based on the previous criteria.
        """
        # Make sure we're using string
        vlan = int(vlan)

        # Load groups - pull once for speed
        ld_grps = self._get_load_grps()

        # First load group is the primary
        if ld_grps[0].get_pvid() == vlan:
            return True

        # Now walk through all the load groups and check the adapters' vlans
        for ld_grp in ld_grps:
            # All load groups have at least one trunk adapter.  Those
            # are kept in sync, so we only need to look at the first
            # trunk adapter.
            trunk = ld_grp.get_trunk_adapters()[0]
            tagged_vlans = trunk.get_tagged_vlans()
            if vlan in tagged_vlans:
                return True

        # Wasn't found,
        return False


class SharedEthernetAdapter(ewrap.ElementWrapper):
    """Represents the Shared Ethernet Adapter within a NetworkBridge."""

    def get_pvid(self):
        """Returns the Primary VLAN ID of the Shared Ethernet Adapter."""
        return self.get_parm_value_int(c.PORT_VLAN_ID)

    def get_addl_adpts(self):
        """Non-primary TrunkAdapters on this Shared Ethernet Adapter.

        :return: List of TrunkAdapter wrappers.  May be the empty list.
        """
        return self._get_trunks()[1:]

    def get_primary_adpt(self):
        """Returns the primary TrunkAdapter for this Shared Ethernet Adapter.

        Can not be None.
        """
        return self._get_trunks()[0]

    def _get_trunks(self):
        """Returns all of the trunk adapters.

        The first is the primary adapter.  All others are the additional
        adapters.
        """
        trunk_elem_list = self._element.findall(SEA_TRUNKS + c.DELIM + TA_ROOT)
        trunks = []
        for trunk_elem in trunk_elem_list:
            trunks.append(TrunkAdapter(trunk_elem))
        return trunks


class TrunkAdapter(ewrap.ElementWrapper):
    """Represents a Trunk Adapter, either within a LoadGroup or a SEA."""

    def get_pvid(self):
        """Returns the Primary VLAN ID of the Trunk Adapter."""
        return self.get_parm_value_int(TA_PVID)

    def get_dev_name(self):
        """Returns the name of the device as represented by the hosting VIOS.

        If RMC is down, will not be available.
        """
        return self.get_parm_value(TA_DEV_NAME)

    def has_tag_support(self):
        """Does this Trunk Adapter support Tagged VLANs passing through it?"""
        return self.get_parm_value_bool(TA_TAG_SUPP)

    def get_tagged_vlans(self):
        """Returns the tagged VLAN IDs that are allowed to pass through.

        Assumes has_tag_support() returns True.  If not, an empty list will
        be returned.
        """
        vids = self.get_parm_value(TA_VLAN_IDS)
        if vids is None:
            return []
        return [int(vid) for vid in vids.split()]

    def get_vswitch_id(self):
        """Returns the virtual switch identifier."""
        return int(self.get_parm_value_int(TA_VS_ID))

    def get_trunk_pri(self):
        """Returns the trunk priority of the adapter."""
        return int(self.get_parm_value_int(TA_TRUNK_PRI))


class LoadGroup(ewrap.ElementWrapper):
    """Load Group (how the I/O load should be distributed) for a Network Bridge.

    If using failover or load balancing, then the Load Group will have pairs of
    Trunk Adapters, each with their own unique Trunk Priority.
    """

    def get_pvid(self):
        """Returns the Primary VLAN ID of the Load Group."""
        return self.get_parm_value_int(LG_PVID)

    def get_trunk_adapters(self):
        """Returns the Trunk Adapters for the Load Group.

        There is either one (no redundancy/load balancing) or two (typically
        the case in a multi VIOS scenario).

        :return: list of TrunkAdapter objects.
        """
        trunk_elem_list = self._element.findall(LG_TRUNKS + c.DELIM + TA_ROOT)
        trunks = []
        for trunk_elem in trunk_elem_list:
            trunks.append(TrunkAdapter(trunk_elem))
        return trunks

    def get_virtual_network_uri_list(self):
        """Returns a list of the Virtual Network URIs."""
        virt_net_list = self._element.find(LG_VNETS)
        uri_resp_list = []
        for virt_net in virt_net_list.findall(c.LINK):
            uri_resp_list.append(virt_net.get('href'))
        return uri_resp_list
