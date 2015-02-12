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

from pypowervm import adapter as adpt
from pypowervm import util
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

VSW_ROOT = 'VirtualSwitch'
VSW_NAME = 'SwitchName'
VSW_ID = 'SwitchID'
VSW_MODE = 'SwitchMode'
VSW_DEFAULT_VSWITCH = 'ETHERNET0'
_VSW_DEFAULT_VSWITCH_API = 'ETHERNET0(Default)'

NB_ROOT = 'NetworkBridge'
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

VNET_ROOT = 'VirtualNetwork'
VNETS_ROOT = 'VirtualNetworks'
VNET_ASSOC_SW = 'AssociatedSwitch'
VNET_NET_NAME = 'NetworkName'
VNET_VLAN_ID = 'NetworkVLANID'
VNET_SW_ID = 'VswitchID'
VNET_TAG = 'TaggedNetwork'


def crt_vnet(name, vlan_id, vswitch_uri, tagged):
    """Creates the VirtualNetwork that can be used for a create operation.

    This is used when creating a new Virtual Network within the system

    :param name: The name for the virtual network.
    :param vlan_id: The VLAN identifier (1 to 4094) for the network.
    :param vswitch_uri: The URI that points to the appropriate vSwitch.
    :param tagged: True if the packet should have the VLAN tag when it leaves
                   the system.  False if the tag should only be on the packets
                   while in the system (but tag-less when on the physical
                   network).
    :returns: The Element that represents the new VirtualNetwork.
    """
    tagged = util.sanitize_bool_for_api(tagged)
    children = [adpt.Element(VNET_ASSOC_SW, attrib={'href': vswitch_uri,
                                                    'rel': 'related'}),
                adpt.Element(VNET_NET_NAME, text=name),
                adpt.Element(VNET_VLAN_ID, text=str(vlan_id)),
                adpt.Element(VNET_TAG, text=tagged)]
    return adpt.Element(VNET_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=children)


class VirtualSwitch(ewrap.EntryWrapper):
    """Wraps the Virtual Switch entries.

    The virtual switch in PowerVM is an independent plane of traffic.  If
    Ethernet packets are traveling on different virtual switches, the only
    time they can communicate is on the physical network plane (or if two
    logical adapters are bridged together).  They are important for data
    plane segregation.
    """

    @property
    def name(self):
        """The name associated with the Virtual Switch."""
        name = self.get_parm_value(VSW_NAME)
        if name == _VSW_DEFAULT_VSWITCH_API:
            return VSW_DEFAULT_VSWITCH
        return name

    @property
    def switch_id(self):
        """The internal ID (not UUID) for the Virtual Switch."""
        return self.get_parm_value_int(VSW_ID)

    @property
    def mode(self):
        """The mode that the switch is in (ex. VEB)."""
        return self.get_parm_value(VSW_MODE)


class NetworkBridge(ewrap.EntryWrapper):
    """Wrapper object for the NetworkBridge entry.

    A NetworkBridge represents an aggregate entity comprising Shared
    Ethernet Adapters.  If Failover or Load-Balancing is in use, the
    Network Bridge will have two identically structured Shared Ethernet
    Adapters belonging to different Virtual I/O Servers.
    """

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Network Bridge."""
        return self.get_parm_value_int(NB_PVID)

    @property
    def virtual_network_uri_list(self):
        """Returns a list of the Virtual Network URIs.

        This is a READ-ONLY list.  Modification should take place through the
        LoadGroup virtual_network_uri_list.
        """
        return self.get_href(NB_VNETS + c.DELIM + c.LINK)

    @property
    def seas(self):
        """Returns a list of SharedEthernetAdapter wrappers."""
        return ewrap.WrapperElemList(self._entry.element.find(NB_SEAS),
                                     NB_SEA, SharedEthernetAdapter)

    @seas.setter
    def seas(self, new_list):
        self.replace_list(NB_SEAS, new_list)

    @property
    def load_grps(self):
        """Returns the load groups.  The first in the list is the primary."""
        return ewrap.WrapperElemList(self._entry.element.find(NB_LGS),
                                     NB_LG, LoadGroup)

    @load_grps.setter
    def load_grps(self, new_list):
        self.replace_list(NB_LGS, new_list)

    @property
    def vswitch_id(self):
        return self.seas[0].primary_adpt.vswitch_id

    @property
    def arbitrary_pvids(self):
        """Lists all of the network bridges' arbitrary PVIDs.

        An arbitrary PVID is a 'primary VLAN ID' attached to an additional
        Load Group.  These typically do not send traffic through them, and
        are placeholder VLANs required by the backing 'additional' Trunk
        Adapters.

        :return: List of arbitrary PVIDs
        """
        return [x.pvid for x in self.load_grps[1:]]

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
        ld_grps = self.load_grps

        # First load group is the primary
        if ld_grps[0].pvid == vlan:
            return True

        # Now walk through all the load groups and check the adapters' vlans
        for ld_grp in ld_grps:
            # All load groups have at least one trunk adapter.  Those
            # are kept in sync, so we only need to look at the first
            # trunk adapter.
            trunk = ld_grp.trunk_adapters[0]
            if vlan in trunk.tagged_vlans:
                return True

        # Wasn't found,
        return False


class SharedEthernetAdapter(ewrap.ElementWrapper):
    """Represents the Shared Ethernet Adapter within a NetworkBridge."""

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Shared Ethernet Adapter."""
        return self.get_parm_value_int(c.PORT_VLAN_ID)

    @property
    def addl_adpts(self):
        """Non-primary TrunkAdapters on this Shared Ethernet Adapter.

        READ ONLY - modification is done through the Load Groups.

        :return: List of TrunkAdapter wrappers.  May be the empty list.
        """
        return tuple(self._get_trunks()[1:])

    @property
    def primary_adpt(self):
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

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Trunk Adapter."""
        return self.get_parm_value_int(TA_PVID)

    @pvid.setter
    def pvid(self, value):
        self.set_parm_value_int(TA_PVID, value)

    @property
    def dev_name(self):
        """Returns the name of the device as represented by the hosting VIOS.

        If RMC is down, will not be available.
        """
        return self.get_parm_value(TA_DEV_NAME)

    @property
    def has_tag_support(self):
        """Does this Trunk Adapter support Tagged VLANs passing through it?"""
        return self.get_parm_value_bool(TA_TAG_SUPP)

    @has_tag_support.setter
    def has_tag_support(self, new_val):
        self.set_parm_value(TA_TAG_SUPP, str(new_val))

    @property
    def tagged_vlans(self):
        """Returns the tagged VLAN IDs that are allowed to pass through.

        Assumes has_tag_support() returns True.  If not, an empty list will
        be returned.
        """
        addl_vlans = self.get_parm_value(TA_VLAN_IDS, '')
        list_data = []
        if addl_vlans != '':
            list_data = [int(i) for i in addl_vlans.split(' ')]

        def update_list(new_list):
            data = ' '.join([str(i) for i in new_list])
            self.set_parm_value(TA_VLAN_IDS, data)

        return ewrap.ActionableList(list_data, update_list)

    @tagged_vlans.setter
    def tagged_vlans(self, new_list):
        data = ' '.join([str(i) for i in new_list])
        self.set_parm_value(TA_VLAN_IDS, data)

    @property
    def vswitch_id(self):
        """Returns the virtual switch identifier."""
        return int(self.get_parm_value_int(TA_VS_ID))

    @property
    def trunk_pri(self):
        """Returns the trunk priority of the adapter."""
        return int(self.get_parm_value_int(TA_TRUNK_PRI))


class LoadGroup(ewrap.ElementWrapper):
    """Load Group (how the I/O load should be distributed) for a Network Bridge.

    If using failover or load balancing, then the Load Group will have pairs of
    Trunk Adapters, each with their own unique Trunk Priority.
    """

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Load Group."""
        return self.get_parm_value_int(LG_PVID)

    @property
    def trunk_adapters(self):
        """Returns the Trunk Adapters for the Load Group.

        There is either one (no redundancy/load balancing) or two (typically
        the case in a multi VIOS scenario).

        :return: list of TrunkAdapter objects.
        """
        return ewrap.WrapperElemList(self._element.find(LG_TRUNKS),
                                     TA_ROOT, TrunkAdapter)

    @trunk_adapters.setter
    def trunk_adapters(self, new_list):
        self.replace_list(LG_TRUNKS, new_list)

    @property
    def virtual_network_uri_list(self):
        """Returns a list of the Virtual Network URIs.

        If a VLAN/Virtual Network should be added, it should be done here.
        """
        uri_resp_list = list(self.get_href(LG_VNETS + c.DELIM + c.LINK))
        return ewrap.ActionableList(uri_resp_list, self.__update_uri_list)

    @virtual_network_uri_list.setter
    def virtual_network_uri_list(self, new_list):
        self.__update_uri_list(new_list)

    def __update_uri_list(self, new_list):
        new_elems = []
        for item in new_list:
            new_elems.append(adpt.Element('link', attrib={'href': item}))
        new_vnet_elem = adpt.Element('VirtualNetworks', children=new_elems)
        self._element.replace(self._element.find(LG_VNETS), new_vnet_elem)


class VirtualNetwork(ewrap.EntryWrapper):
    """The overall definition of a VLAN network within the hypervisor."""

    @property
    def associated_switch_uri(self):
        return self.get_href(VNET_ASSOC_SW, one_result=True)

    @property
    def name(self):
        return self.get_parm_value(VNET_NET_NAME)

    @name.setter
    def name(self, value):
        self.set_parm_value(VNET_NET_NAME, value)

    @property
    def vlan(self):
        return self.get_parm_value_int(VNET_VLAN_ID)

    @property
    def vswitch_id(self):
        """The vSwitch identifier.  0 through 15 (max number vSwitches).

        Is not a UUID.
        """
        return self.get_parm_value_int(VNET_SW_ID)

    @property
    def tagged(self):
        """If true, the VLAN tag is preserved when the packet leaves system."""
        return self.get_parm_value_bool(VNET_TAG)
