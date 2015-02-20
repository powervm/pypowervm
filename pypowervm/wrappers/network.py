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

import copy
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
SEA_DEV_NAME = 'DeviceName'
SEA_VIO_HREF = 'AssignedVirtualIOServer'
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

VNET_ROOT = c.VNET
VNETS_ROOT = 'VirtualNetworks'
VNET_ASSOC_SW = 'AssociatedSwitch'
VNET_NET_NAME = 'NetworkName'
VNET_VLAN_ID = 'NetworkVLANID'
VNET_SW_ID = 'VswitchID'
VNET_TAG = 'TaggedNetwork'

LOCATION_CODE = 'LocationCode'

VADPT_ROOT = c.CNA
VADPT_SLOT_NUM = 'VirtualSlotNumber'
VADPT_MAC_ADDR = 'MACAddress'
VADPT_TAGGED_VLANS = 'TaggedVLANIDs'
VADPT_TAGGED_VLAN_SUPPORT = 'TaggedVLANSupported'
VADPT_VSWITCH = 'AssociatedVirtualSwitch'
VADPT_VSWITCH_ID = 'VirtualSwitchID'
VADPT_PVID = 'PortVLANID'
VADPT_USE_NEXT_AVAIL_SLOT = 'UseNextAvailableSlotID'


def crt_load_group(pvid, vnet_uris):
    """Create the LoadGroup element that can be used for a create operation.

    This is used when adding a Load Group to a NetworkBridge.

    :param pvid: The primary VLAN ID (ex. 1) for the Load Group.
    :param vnet_uris: The virtual network URI list (mapping to each additional
                      VLAN/vswitch combo).
    :returns: The Element that represents the new LoadGroup.
    """
    vnet_elem_list = [adpt.Element('link',
                                   attrib={'href': uri, 'rel': 'related'})
                      for uri in vnet_uris]
    children = [adpt.Element(LG_PVID, text=str(pvid)),
                adpt.Element(LG_VNETS, children=vnet_elem_list)]
    return adpt.Element(LG_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
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
        name = self._get_val_str(VSW_NAME)
        if name == _VSW_DEFAULT_VSWITCH_API:
            return VSW_DEFAULT_VSWITCH
        return name

    @property
    def switch_id(self):
        """The internal ID (not UUID) for the Virtual Switch."""
        return self._get_val_int(VSW_ID)

    @property
    def mode(self):
        """The mode that the switch is in (ex. VEB)."""
        return self._get_val_str(VSW_MODE)


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
        return self._get_val_int(NB_PVID)

    @property
    def virtual_network_uri_list(self):
        """Returns a list of the Virtual Network URIs.

        This is a READ-ONLY list.  Modification should take place through the
        LoadGroup virtual_network_uri_list.  As the LoadGroups are modified,
        this list will be dynamically updated.
        """
        return self.get_href(NB_VNETS + c.DELIM + c.LINK)

    def _rebuild_vnet_list(self):
        """A callback from the Load Group to rebuild the virtual network list.

        Needed due to the API using both the LoadGroup and Network Bridge
        as a source.  But usage at an API level should be through Load
        Groups.
        """
        # Find all the children Virtual Networks.
        search = c.DELIM.join(['.', NB_LGS, LG_ROOT, LG_VNETS, c.LINK])
        new_vnets = copy.deepcopy(self._element.findall(search))
        # Find and replace the current element.
        cur_vnets = self._element.find(c.ROOT + NB_VNETS)
        self._element.replace(cur_vnets,
                              adpt.Element(NB_VNETS, children=new_vnets))

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
                                     NB_LG, LoadGroup, nb_root=self)

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

    def list_vlans(self, pvid=True, arbitrary=False):
        """Lists all of the VLANs on the Network Bridge.

        :param pvid: True if the primary VLAN ID should be included in the
                     response.  Defaults to True.
        :param arbitrary: If True, the arbitrary PVIDs (see arbitrary_pvids
                          property) will be included in the response.
        :response: A list of all the VLANs.
        """
        resp = []

        # Loop through all load groups (even primary) and add the VLANs.
        for ld_grp in self.load_grps:
            trunk = ld_grp.trunk_adapters[0]
            if arbitrary:
                resp.append(trunk.pvid)
            resp.extend(trunk.tagged_vlans)

        # Depending on if the arbitrary flag was set, the primary VLAN may
        # be in already.  This is odd logic here...but keeps the code
        # efficient.
        if not pvid and arbitrary:
            resp.remove(self.pvid)
        elif pvid and not arbitrary:
            resp.append(self.pvid)
        return resp

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
        return self._get_val_int(c.PORT_VLAN_ID)

    @property
    def dev_name(self):
        return self._get_val_str(SEA_DEV_NAME)

    @property
    def vio_uri(self):
        """The URI to the corresponding VIOS."""
        return self.get_href(SEA_VIO_HREF, one_result=True)

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
        return self._get_val_int(TA_PVID)

    @pvid.setter
    def pvid(self, value):
        self.set_parm_value_int(TA_PVID, value)

    @property
    def dev_name(self):
        """Returns the name of the device as represented by the hosting VIOS.

        If RMC is down, will not be available.
        """
        return self._get_val_str(TA_DEV_NAME)

    @property
    def has_tag_support(self):
        """Does this Trunk Adapter support Tagged VLANs passing through it?"""
        return self._get_val_bool(TA_TAG_SUPP)

    @has_tag_support.setter
    def has_tag_support(self, new_val):
        self.set_parm_value(TA_TAG_SUPP, str(new_val))

    @property
    def tagged_vlans(self):
        """Returns the tagged VLAN IDs that are allowed to pass through.

        Assumes has_tag_support() returns True.  If not, an empty list will
        be returned.
        """
        addl_vlans = self._get_val_str(TA_VLAN_IDS, '')
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
        return self._get_val_int(TA_VS_ID)

    @property
    def trunk_pri(self):
        """Returns the trunk priority of the adapter."""
        return self._get_val_int(TA_TRUNK_PRI)


class LoadGroup(ewrap.ElementWrapper):
    """Load Group (how the I/O load should be distributed) for a Network Bridge.

    If using failover or load balancing, then the Load Group will have pairs of
    Trunk Adapters, each with their own unique Trunk Priority.
    """

    def __init__(self, element, **kwargs):
        super(LoadGroup, self).__init__(element)

        # If created from a Network Bridge this will be set.  Else it will
        # be None (ex. crt_load_group method)
        self._nb_root = kwargs.get('nb_root')

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Load Group."""
        return self._get_val_int(LG_PVID)

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
            new_elems.append(adpt.Element('link', attrib={'href': item,
                                                          'rel': 'related'}))
        new_vnet_elem = adpt.Element('VirtualNetworks', children=new_elems)
        old_elems = self._element.find(LG_VNETS)
        # This is a bug where the API isn't returning vnets if just a PVID
        # on additional VEA
        if old_elems is not None:
            self._element.replace(old_elems, new_vnet_elem)
        else:
            self._element.append(new_vnet_elem)

        # If the Network Bridge was set, tell it to rebuild its VirtualNetwork
        # list.
        if self._nb_root is not None:
            self._nb_root._rebuild_vnet_list()

    @property
    def tagged_vlans(self):
        """The VLANs supported by this Load Group.  Does not include PVID."""
        return self.trunk_adapters[0].tagged_vlans


class VNet(ewrap.EntryWrapper):
    """The overall definition of a VLAN network within the hypervisor."""

    schema_type = c.VNET
    has_metadata = True

    @classmethod
    def new(cls, name=None, vlan_id=None, vswitch_uri=None, tagged=None):
        """Creates a VirtualNetwork that can be used for a create operation.

        This is used when creating a new Virtual Network within the system

        :param name: The name for the virtual network.
        :param vlan_id: The VLAN identifier (1 to 4094) for the network.
        :param vswitch_uri: The URI that points to the appropriate vSwitch.
        :param tagged: True if packets should have VLAN tags when they leave
                       the system.  False if tags should only be on the packets
                       while in the system (but tag-less when on the physical
                       network).
        :returns: The ElementWrapper that represents the new VirtualNetwork.
        """
        vnet = cls()
        # Assignment order matters
        if vswitch_uri is not None:
            vnet.associated_switch_uri = vswitch_uri
        if name is not None:
            vnet.name = name
        if vlan_id is not None:
            vnet.vlan = vlan_id
        if tagged is not None:
            vnet.tagged = tagged
        return vnet

    @property
    def associated_switch_uri(self):
        return self.get_href(VNET_ASSOC_SW, one_result=True)

    @associated_switch_uri.setter
    def associated_switch_uri(self, uri):
        self.set_href(VNET_ASSOC_SW, uri)

    @property
    def name(self):
        return self._get_val_str(VNET_NET_NAME)

    @name.setter
    def name(self, value):
        self.set_parm_value(VNET_NET_NAME, value)

    @property
    def vlan(self):
        return self._get_val_int(VNET_VLAN_ID)

    @vlan.setter
    def vlan(self, vlan_id):
        self.set_parm_value(VNET_VLAN_ID, vlan_id)

    @property
    def vswitch_id(self):
        """The vSwitch identifier (int).  0 through 15 (max number vSwitches).

        Is not a UUID.
        """
        return self._get_val_int(VNET_SW_ID)

    @property
    def tagged(self):
        """If True, the VLAN tag is preserved when the packet leaves system."""
        return self._get_val_bool(VNET_TAG)

    @tagged.setter
    def tagged(self, is_tagged):
        self.set_parm_value(VNET_TAG, util.sanitize_bool_for_api(is_tagged))


class CNA(ewrap.EntryWrapper):
    """Wrapper object for ClientNetworkAdapter schema."""

    schema_type = c.CNA
    has_metadata = True

    @classmethod
    def new(cls, pvid=None, vswitch_href=None, slot_num=None, mac_addr=None,
            addl_tagged_vlans=None):
        """Creates a fresh CNA EntryWrapper.

        This is used when creating a new CNA for a client partition.  This
        can be PUT to LogicalPartition/<UUID>/ClientNetworkAdapter.

        :param pvid: The Primary VLAN ID to use.
        :param vswitch_href: The URI that points to the Virtual Switch that
                             will support this adapter.
        :param slot_num: The Slot on the Client LPAR that should be used.  This
                         defaults to 'None', which means the next available
                         slot will be used.
        :param mac_addr: Optional user specified mac address to use.  If left
                         as None, the system will generate one.
        :param addl_tagged_vlans: A set of additional tagged VLANs that can be
                                  passed through this adapter (with client VLAN
                                  adapters).

                                  Input should be a list of int (or int string)
                                  Example: [51, 52, 53]
                                  Note: The limit is ~18 additional VLANs
        :returns: A CNA EntryWrapper that can be used for create.
        """
        cna = cls()
        # Assignment order matters
        if slot_num is not None:
            cna.slot = slot_num
        else:
            cna.use_next_avail_slot_id = True

        if mac_addr is not None:
            cna.mac = mac_addr

        #  The primary VLAN ID
        if pvid is not None:
            cna.pvid = pvid

        # Additional VLANs
        if addl_tagged_vlans is not None:
            cna.tagged_vlans = addl_tagged_vlans
            cna.is_tagged_vlan_supported = True
        else:
            cna.is_tagged_vlan_supported = False

        # vSwitch URI
        if vswitch_href is not None:
            cna.vswitch_uri = vswitch_href

        return cna

    @property
    def slot(self):
        return self._get_val_int(c.VIR_SLOT_NUM)

    @slot.setter
    def slot(self, sid):
        self.set_parm_value(c.VIR_SLOT_NUM, sid)

    @property
    def use_next_avail_slot_id(self):
        return self._get_val_bool(VADPT_USE_NEXT_AVAIL_SLOT)

    @use_next_avail_slot_id.setter
    def use_next_avail_slot_id(self, unasi):
        """Param unasi is bool (True or False)."""
        self.set_parm_value(VADPT_USE_NEXT_AVAIL_SLOT,
                            util.sanitize_bool_for_api(unasi))

    @property
    def mac(self):
        """Returns the Mac Address for the adapter.

        Typical format would be: AABBCCDDEEFF
        The API returns a format with no colons and is upper cased.
        """
        return self._get_val_str(VADPT_MAC_ADDR)

    @mac.setter
    def mac(self, new_val):
        new_mac = util.sanitize_mac_for_api(new_val)
        self.set_parm_value(VADPT_MAC_ADDR, new_mac)

    @property
    def pvid(self):
        """Returns the Port VLAN ID (int value)."""
        return self._get_val_int(VADPT_PVID)

    @pvid.setter
    def pvid(self, new_val):
        self.set_parm_value(VADPT_PVID, new_val)

    @property
    def loc_code(self):
        """The device's location code."""
        return self._get_val_str(LOCATION_CODE)

    @property
    def tagged_vlans(self):
        """Returns a list of additional VLANs on this adapter.

        Only valid if tagged vlan support is on.
        """
        addl_vlans = self._get_val_str(VADPT_TAGGED_VLANS, '')
        list_data = []
        if addl_vlans != '':
            list_data = [int(i) for i in addl_vlans.split(' ')]

        def update_list(new_list):
            data = ' '.join([str(j) for j in new_list])
            self.set_parm_value(VADPT_TAGGED_VLANS, data)

        return ewrap.ActionableList(list_data, update_list)

    @tagged_vlans.setter
    def tagged_vlans(self, new_list):
        data = ' '.join([str(i) for i in new_list])
        self.set_parm_value(VADPT_TAGGED_VLANS, data)

    @property
    def is_tagged_vlan_supported(self):
        """Returns if addl tagged VLANs are supported (bool value)."""
        return self._get_val_bool(VADPT_TAGGED_VLAN_SUPPORT)

    @is_tagged_vlan_supported.setter
    def is_tagged_vlan_supported(self, new_val):
        """Parameter new_val is a bool (True or False)."""
        self.set_parm_value(VADPT_TAGGED_VLAN_SUPPORT,
                            util.sanitize_bool_for_api(new_val))

    @property
    def vswitch_uri(self):
        """Returns the URI for the associated vSwitch."""
        return self.get_href(VADPT_VSWITCH + c.DELIM + 'link', one_result=True)

    @vswitch_uri.setter
    def vswitch_uri(self, new_val):
        self.set_href(VADPT_VSWITCH + c.DELIM + 'link', new_val)
