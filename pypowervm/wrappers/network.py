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

"""Wrappers for virtual networking objects."""

import copy
import logging

import pypowervm.const as c
import pypowervm.entities as ent
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

_PVID = 'PortVLANID'

_VSW_NAME = 'SwitchName'
_VSW_ID = 'SwitchID'
_VSW_MODE = 'SwitchMode'
_VSW_VIRT_NETS = 'VirtualNetworks'
VSW_DEFAULT_VSWITCH = 'ETHERNET0'
VSW_DEFAULT_VSWITCH_ID = 0
_VSW_DEFAULT_VSWITCH_API = 'ETHERNET0(Default)'
_VSW_EL_ORDER = (_VSW_ID, _VSW_MODE, _VSW_NAME, _VSW_VIRT_NETS)

SHARED_ETH_ADPT = 'SharedEthernetAdapter'

_NB_FAILOVER = 'FailoverEnabled'
_NB_LOADBALANCE = 'LoadBalancingEnabled'
_NB_LGS = 'LoadGroups'
_NB_PVID = _PVID
NB_SEAS = 'SharedEthernetAdapters'
_NB_DEV_ID = 'UniqueDeviceID'
_NB_VNETS = 'VirtualNetworks'
_NB_LG = 'LoadGroup'
_NB_EL_ORDER = (_NB_FAILOVER, _NB_LOADBALANCE, _NB_LGS, _NB_PVID, NB_SEAS,
                _NB_DEV_ID, _NB_VNETS)

ETH_BACK_DEV = 'EthernetBackingDevice'

_SEA_VIO_HREF = 'AssignedVirtualIOServer'
_SEA_CONTROL_CHANNEL = 'ControlChannelInterfaceName'
_SEA_BACKING_DEV = 'BackingDeviceChoice'
_SEA_ETH_BACK_DEV = ETH_BACK_DEV
_SEA_HA_MODE = 'HighAvailabilityMode'
_SEA_DEV_NAME = 'DeviceName'
_SEA_JUMBO_FRAMES = 'JumboFramesEnabled'
_SEA_PVID = _PVID
_SEA_QOS_MODE = 'QualityOfServiceMode'
_SEA_QUEUE_SIZE = 'QueueSize'
_SEA_THREAD_MODE = 'ThreadModeEnabled'
_SEA_IP_INTERFACE = 'IPInterface'
_SEA_DEV_ID = 'UniqueDeviceID'
_SEA_LARGE_SEND = 'LargeSend'
_SEA_ADDRESS_TO_PING = 'AddressToPing'
_SEA_IIDP_SERVICE = 'IIDPService'
SEA_TRUNKS = 'TrunkAdapters'
_SEA_PRIMARY = 'IsPrimary'
_SEA_EL_ORDER = (_SEA_VIO_HREF, _SEA_CONTROL_CHANNEL, _SEA_BACKING_DEV,
                 _SEA_HA_MODE, _SEA_DEV_NAME, _SEA_JUMBO_FRAMES, _SEA_PVID,
                 _SEA_QOS_MODE, _SEA_QUEUE_SIZE, _SEA_THREAD_MODE,
                 _SEA_IP_INTERFACE, _SEA_DEV_ID, _SEA_LARGE_SEND,
                 _SEA_ADDRESS_TO_PING, _SEA_IIDP_SERVICE, SEA_TRUNKS,
                 _SEA_PRIMARY)

_SEA_EBD_ADAPTER_ID = 'AdapterID'
_SEA_EBD_DESCRIPTION = 'Description'
_SEA_EBD_DEV_NAME = 'DeviceName'
_SEA_EBD_DEV_TYPE = 'DeviceType'
_SEA_EBD_DYN_CONN_NAME = 'DynamicReconfigurationConnectorName'
_SEA_EBD_PHYS_LOC = 'PhysicalLocation'
_SEA_EBD_UDID = 'UniqueDeviceID'
_SEA_EBD_ORDER = (_SEA_EBD_ADAPTER_ID, _SEA_EBD_DESCRIPTION,
                  _SEA_EBD_DEV_NAME, _SEA_EBD_DEV_TYPE,
                  _SEA_EBD_DYN_CONN_NAME, _SEA_EBD_PHYS_LOC,
                  _SEA_EBD_UDID)

TA_ROOT = 'TrunkAdapter'
_TA_CONN_NAME = 'DynamicReconfigurationConnectorName'
_TA_LOC_CODE = 'LocationCode'
_TA_REQUIRED = 'RequiredAdapter'
_TA_VARIED_ON = 'VariedOn'
_TA_VIRTUAL_SLOT = 'VirtualSlotNumber'
_TA_USE_NEXT_AVAIL_SLOT = 'UseNextAvailableSlotID'
_TA_ALLOWED_MAC = 'AllowedOperatingSystemMACAddresses'
_TA_MAC = 'MACAddress'
_TA_PVID = _PVID
_TA_QOS_PRI = 'QualityOfServicePriorityEnabled'
_TA_VLAN_IDS = 'TaggedVLANIDs'
_TA_TAG_SUPP = 'TaggedVLANSupported'
_TA_VS_ID = 'VirtualSwitchID'
_TA_DEV_NAME = 'DeviceName'
_TA_TRUNK_PRI = 'TrunkPriority'
_TA_ASSOC_VSWITCH = 'AssociatedVirtualSwitch'
_TA_EL_ORDER = (_TA_CONN_NAME, _TA_LOC_CODE, _TA_REQUIRED, _TA_VARIED_ON,
                _TA_USE_NEXT_AVAIL_SLOT, _TA_VIRTUAL_SLOT, _TA_ALLOWED_MAC,
                _TA_MAC, _TA_PVID, _TA_QOS_PRI, _TA_VLAN_IDS, _TA_TAG_SUPP,
                _TA_ASSOC_VSWITCH, _TA_VS_ID, _TA_DEV_NAME, _TA_TRUNK_PRI)

_LG_PVID = _PVID
_LG_TRUNKS = 'TrunkAdapters'
_LG_VNETS = 'VirtualNetworks'

_VNET_ASSOC_SW = 'AssociatedSwitch'
_VNET_NET_NAME = 'NetworkName'
_VNET_VLAN_ID = 'NetworkVLANID'
_VNET_SW_ID = 'VswitchID'
_VNET_TAG = 'TaggedNetwork'

_VADPT_LOCATION_CODE = 'LocationCode'
_VADPT_MAC_ADDR = 'MACAddress'
_VADPT_TAGGED_VLANS = 'TaggedVLANIDs'
_VADPT_TAGGED_VLAN_SUPPORT = 'TaggedVLANSupported'
_VADPT_VSWITCH = 'AssociatedVirtualSwitch'
_VADPT_PVID = _PVID
_VADPT_SLOT_NUM = 'VirtualSlotNumber'
_VADPT_USE_NEXT_AVAIL_SLOT = 'UseNextAvailableSlotID'


class VSwitchMode(object):
    VEB = "Veb"
    VEPA = "Vepa"


@ewrap.EntryWrapper.pvm_type('VirtualSwitch', has_metadata=True,
                             child_order=_VSW_EL_ORDER)
class VSwitch(ewrap.EntryWrapper):
    """Wraps the Virtual Switch entries.

    The virtual switch in PowerVM is an independent plane of traffic.  If
    Ethernet packets are traveling on different virtual switches, the only
    time they can communicate is on the physical network plane (or if two
    logical adapters are bridged together).  They are important for data
    plane segregation.
    """

    @classmethod
    def bld(cls, adapter, name, switch_mode=VSwitchMode.VEB):
        """Creates a VSwitch that can be used for a create operation.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name for the virtual switch.  Must be unique.
        :param switch_mode: The mode of virtual switch (see VSwitchMode).
        :returns: The ElementWrapper that represents the new VSwitch.
        """
        vswitch = super(VSwitch, cls)._bld(adapter)
        vswitch.name = name
        vswitch._mode(switch_mode)
        vswitch.vnet_uri_list = []
        return vswitch

    @property
    def name(self):
        """The name associated with the Virtual Switch."""
        name = self._get_val_str(_VSW_NAME)
        if name == _VSW_DEFAULT_VSWITCH_API:
            return VSW_DEFAULT_VSWITCH
        return name

    @name.setter
    def name(self, new_name):
        self.set_parm_value(_VSW_NAME, new_name)

    @property
    def switch_id(self):
        """The internal ID (not UUID) for the Virtual Switch."""
        return self._get_val_int(_VSW_ID)

    @property
    def mode(self):
        """The mode that the switch is in (ex. Veb).

        This is a string value that represents one of the values in the
        VSwitchMode enumeration.
        """
        return self._get_val_str(_VSW_MODE)

    def _mode(self, new_mode):
        self.set_parm_value(_VSW_MODE, new_mode)

    @property
    def vnet_uri_list(self):
        """Returns a list of the Virtual Network URIs.

        If the vnet_aware trait (see traits.py) is set to False, the user
        should not modify this.  Virtual Networks become 'realized' off of
        the system's VLANs/vSwitches.  However, if set to True, one can add
        a Virtual Network to the vSwitch before it is used.

        The task classes (cna.py and network_bridger.py) should abstract the
        user away from these deviations in traits.
        """
        uri_resp_list = list(self.get_href(u.xpath(_LG_VNETS, c.LINK)))
        return ewrap.ActionableList(uri_resp_list, self.__update_uri_list)

    @vnet_uri_list.setter
    def vnet_uri_list(self, new_list):
        self.__update_uri_list(new_list)

    def __update_uri_list(self, new_list):
        new_vnet_elem = self._bld_link_list(_VSW_VIRT_NETS, new_list)
        self.inject(new_vnet_elem)


@ewrap.EntryWrapper.pvm_type('NetworkBridge', child_order=_NB_EL_ORDER)
class NetBridge(ewrap.EntryWrapper):
    """Wrapper object for the NetBridge entry.

    A NetworkBridge represents an aggregate entity comprising Shared
    Ethernet Adapters.  If Failover or Load-Balancing is in use, the
    Network Bridge will have two identically structured Shared Ethernet
    Adapters belonging to different Virtual I/O Servers.
    """

    @classmethod
    def bld(cls, adapter, pvid, vios_to_backing_adpts, vlan_ids, vswitch):
        """Create the NetBridge entry that can be used for a create operation.

        This is used when creating a NetBridge.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param pvid: The primary VLAN ID (ex. 1) for the Network Bridge.
        :param vios_to_backing_adpts: An argument containing a list of tuples
                                      between VIOS href and the VIOS backing
                                      trunk adapter names for 1 or 2 VIOS
                                      servers, depending whether failover is
                                      required.
        :param vlan_ids: List of Additional VLAN ids for the trunk adapters.
                         Maximum of 20.
        :param vswitch: The vswitch wrapper to retrieve ID and href.
        :returns: A new NetBridge EntryWrapper that represents the new
                  NetBridge.
        """
        nb = super(NetBridge, cls)._bld(adapter)

        if not vios_to_backing_adpts:
            raise ValueError()

        # Set required failover flag based on number of VIOSs. True for 2,
        # False for 1. We can determine this based on the number of provided
        # backing adpts. If its 0 we should throw an exception, 1 means only
        # 1 VIOS, 2 or more means we are defaulting to failover.
        nb._failover(len(vios_to_backing_adpts) != 1)

        # Set required load balancing flag to false as default. Based on
        # Load Group configuration.
        nb._load_balanced(False)

        # Collection must be set based on schema requirements.
        nb.replace_list(_NB_LGS, [])

        # Set PVID to user provided value.
        nb._pvid(pvid)

        # There should never be more than two VIOSes specified.  However, the
        # API should validate this.  Therefore we can loop through and assert
        # that only the first VIOS is the primary.
        primary = True
        nb.seas = []
        for vio_tuple in vios_to_backing_adpts:
            nb.seas.append(SEA.bld(adapter, pvid, vio_tuple[0], vio_tuple[1],
                                   vlan_ids, vswitch, primary=primary))
            primary = False

        return nb

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Network Bridge."""
        return self._get_val_int(_NB_PVID)

    def _pvid(self, value):
        """Private setter for the PVID used by Network Bridge builder."""
        self.set_parm_value(_NB_PVID, value)

    @property
    def vnet_uri_list(self):
        """Returns a list of the Virtual Network URIs.

        This is a READ-ONLY list.  Modification should take place through the
        LoadGroup vnet_uri_list.  As the LoadGroups are modified,
        this list will be dynamically updated.
        """
        return self.get_href(u.xpath(_NB_VNETS, c.LINK))

    def _rebuild_vnet_list(self):
        """A callback from the Load Group to rebuild the virtual network list.

        Needed due to the API using both the LoadGroup and Network Bridge
        as a source.  But usage at an API level should be through Load
        Groups.
        """
        # Find all the children Virtual Networks.
        search = u.xpath(_NB_LGS, _NB_LG, _NB_VNETS, c.LINK)
        new_vnets = copy.deepcopy(self.element.findall(search))
        # Find and replace the current element.
        cur_vnets = self.element.find(_NB_VNETS)
        self.element.replace(
            cur_vnets, ent.Element(_NB_VNETS, self.adapter,
                                   children=new_vnets))

    @property
    def seas(self):
        """Returns a list of SEA wrappers."""
        return ewrap.WrapperElemList(self.entry.element.find(NB_SEAS), SEA)

    @seas.setter
    def seas(self, new_list):
        self.replace_list(NB_SEAS, new_list)

    @property
    def load_grps(self):
        """Returns the load groups.  The first in the list is the primary."""
        return ewrap.WrapperElemList(self.entry.element.find(_NB_LGS),
                                     LoadGroup, nb_root=self)

    @load_grps.setter
    def load_grps(self, new_list):
        self.replace_list(_NB_LGS, new_list)

    @property
    def vswitch_id(self):
        return self.seas[0].primary_adpt.vswitch_id

    @property
    def arbitrary_pvids(self):
        """Lists all of the network bridges' arbitrary PVIDs.

        An arbitrary PVID is a 'primary VLAN ID' attached to an additional
        Load Group or Trunk Adapter.  These typically do not send traffic
        through them, and are placeholder VLANs required by the backing
        'additional' Trunk Adapters.

        :return: List of arbitrary PVIDs
        """
        if self.traits.vnet_aware:
            return [x.pvid for x in self.load_grps[1:]]
        else:
            return [x.pvid for x in self.seas[0].addl_adpts]

    def list_vlans(self, pvid=True, arbitrary=False):
        """Lists all of the VLANs on the Network Bridge.

        :param pvid: True if the primary VLAN ID should be included in the
                     response.  Defaults to True.
        :param arbitrary: If True, the arbitrary PVIDs (see arbitrary_pvids
                          property) will be included in the response.

        :response: A list of all the VLANs.
        """
        resp = []
        if self.traits.vnet_aware:
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
        else:
            # Loop through the first SEA's trunks
            sea = self.seas[0]
            if pvid:
                resp.append(sea.primary_adpt.pvid)
            resp.extend(sea.primary_adpt.tagged_vlans)

            for trunk in sea.addl_adpts:
                if arbitrary:
                    resp.append(trunk.pvid)
                resp.extend(trunk.tagged_vlans)

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

        return vlan in self.list_vlans()

    def _failover(self, value):
        """Private setter for the failover attr.

        Determined by backing adapters on NetworkBridge creation.
        """
        self.set_parm_value(_NB_FAILOVER, u.sanitize_bool_for_api(value))

    def _load_balanced(self, value):
        """Private setter for the failover attr.

        False by default on Network Bridge creation.
        """
        self.set_parm_value(_NB_LOADBALANCE, u.sanitize_bool_for_api(value))


@ewrap.ElementWrapper.pvm_type(SHARED_ETH_ADPT, has_metadata=True,
                               child_order=_SEA_EL_ORDER)
class SEA(ewrap.ElementWrapper):
    """Represents the Shared Ethernet Adapter within a NetworkBridge."""

    @classmethod
    def bld(cls, adapter, pvid, vios_href, adpt_name, vlan_ids, vswitch,
            primary=True):
        """Create the SEA entry that can be used for NetBridge creation.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param pvid: The primary VLAN ID (ex. 1) for the Network Bridge.
        :param vios_href: The Assigned VIOS href.
        :param adpt_name: Name of the physical adapter or ether channel that
                          will back the SEA.
        :param vlan_ids: Additional VLAN ids for the trunk adapters.
        :param vswitch: The vswitch wrapper to retrieve ID and href.
        :param primary: Used in a dual Virtual I/O Server environment.  If
                        set to True, indicates it is running on the I/O Server
                        that the traffic should run through by default.  False
                        indicates it is the SEA on the fail over Virtual I/O
                        Server.  If single Virtual I/O Server environment,
                        always set this to True.
        :returns: A new SEA ElementWrapper that represents the new SEA.
        """
        sea = super(SEA, cls)._bld(adapter)
        sea._pvid(pvid)

        sea._vio_uri(vios_href)
        sea._backing_device(EthernetBackingDevice.bld(adapter, adpt_name))

        trunk_pri = 1 if primary else 2
        sea._primary_adpt(TrunkAdapter.bld(adapter, pvid, vlan_ids, vswitch,
                                           trunk_pri=trunk_pri))
        sea._is_primary(primary)

        return sea

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Shared Ethernet Adapter."""
        return self._get_val_int(_SEA_PVID)

    def _pvid(self, value):
        self.set_parm_value(_SEA_PVID, value)

    @property
    def dev_name(self):
        return self._get_val_str(_SEA_DEV_NAME)

    @property
    def vio_uri(self):
        """The URI to the corresponding VIOS."""
        return self.get_href(_SEA_VIO_HREF, one_result=True)

    def _vio_uri(self, value):
        self.set_href(_SEA_VIO_HREF, value)

    @property
    def is_primary(self):
        """Returns if this is the primary SEA.

        Only valuable in dual Virtual I/O Server environments where a
        NetBridge spans multiple I/O Servers.  The primary SEA is the one
        the traffic runs through by default unless in a fail over scenario.
        """
        return self._get_val_bool(_SEA_PRIMARY)

    def _is_primary(self, val):
        self.set_parm_value(_SEA_PRIMARY, u.sanitize_bool_for_api(val))

    @property
    def addl_adpts(self):
        """Non-primary TrunkAdapters on this Shared Ethernet Adapter.

        If the vnet_aware trait (see traits.py) is set to True, then the
        modification of a Network Bridge should be driven via the LoadGroup.
        If set to False, the LoadGroups simply reflect the state of the
        system and can't be used for modification.

        In those scenarios, modification should be done directly against the
        Trunk Adapters.

        :return: List of TrunkAdapter wrappers.  May be the empty list.
        """
        # TODO(thorst): Second return unreachable!  Use self.traits.vnet_aware.
        return ewrap.ActionableList(self._get_trunks()[1:],
                                    self._addl_adpts)
        return tuple(self._get_trunks()[1:])

    @addl_adpts.setter
    def addl_adpts(self, value):
        self._addl_adpts(value)

    def _addl_adpts(self, value):
        """Sets the additional Trunk Adapters on this SEA."""
        # TODO(thorst): Condition on self.traits.vnet_aware.
        new_list = [self.primary_adpt]
        new_list.extend(value)
        self.replace_list(SEA_TRUNKS, new_list)

    @property
    def primary_adpt(self):
        """Returns the primary TrunkAdapter for this Shared Ethernet Adapter.

        Can not be None.
        """
        return self._get_trunks()[0]

    def _primary_adpt(self, value):
        new_list = [value]
        if self._get_trunks() and len(self._get_trunks()) > 1:
            # Drop the original primary adapter.
            new_list.extend(self._get_trunks()[1:])

        self.replace_list(SEA_TRUNKS, new_list)

    def _get_trunks(self):
        """Returns all of the trunk adapters.

        The first is the primary adapter.  All others are the additional
        adapters.
        """
        trunk_elem_list = self.element.findall(u.xpath(SEA_TRUNKS, TA_ROOT))
        trunks = []
        for trunk_elem in trunk_elem_list:
            trunks.append(TrunkAdapter.wrap(trunk_elem))
        return trunks

    @property
    def backing_device(self):
        """The BackingDeviceChoice for this SEA."""
        elem = self.element.find(_SEA_BACKING_DEV)
        if elem is None:
            return None
        return ewrap.ElementWrapper.wrap(elem[0])

    def _backing_device(self, eth_back_dev):
        """The BackingDeviceChoice for this SEA.

        :param eth_back_dev: The EthernetBackingDevice for this
                             BackingDeviceChoice.
        """
        stor_elem = ent.Element(_SEA_BACKING_DEV, self.adapter, attrib={},
                                children=[])
        stor_elem.inject(eth_back_dev.element)
        self.inject(stor_elem)


@ewrap.ElementWrapper.pvm_type('TrunkAdapter', child_order=_TA_EL_ORDER)
class TrunkAdapter(ewrap.ElementWrapper):
    """Represents a Trunk Adapter, either within a LoadGroup or a SEA."""

    @classmethod
    def bld(cls, adapter, pvid, vlan_ids, vswitch, trunk_pri=1):
        """Create the TrunkAdapter element that can be used for SEA creation.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param pvid: The primary VLAN ID (ex. 1) for the Network Bridge.
        :param vlan_ids: Additional VLAN ids for the trunk adapters.
        :param vswitch: The vswitch wrapper to retrieve ID and href.
        :param trunk_pri: Trunk priority of this adapter. Defaults to 1.
        :returns: A new TrunkAdapter ElementWrapper that represents the new
                  TrunkAdapter.
        """
        ta = super(TrunkAdapter, cls)._bld(adapter)

        ta._required(True)
        ta.pvid = pvid
        ta.tagged_vlans = vlan_ids
        ta.has_tag_support = True if vlan_ids else False
        ta._vswitch_id(vswitch.switch_id)
        ta._trunk_pri(trunk_pri)

        ta.set_parm_value(_TA_USE_NEXT_AVAIL_SLOT,
                          u.sanitize_bool_for_api(True))
        ta._associated_vswitch_uri(vswitch.related_href)

        return ta

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Trunk Adapter."""
        return self._get_val_int(_TA_PVID)

    @pvid.setter
    def pvid(self, value):
        self.set_parm_value(_TA_PVID, value)

    @property
    def dev_name(self):
        """Returns the name of the device as represented by the hosting VIOS.

        If RMC is down, will not be available.
        """
        return self._get_val_str(_TA_DEV_NAME)

    @property
    def has_tag_support(self):
        """Does this Trunk Adapter support Tagged VLANs passing through it?"""
        return self._get_val_bool(_TA_TAG_SUPP)

    @has_tag_support.setter
    def has_tag_support(self, new_val):
        self.set_parm_value(_TA_TAG_SUPP, u.sanitize_bool_for_api(new_val))

    @property
    def tagged_vlans(self):
        """Returns the tagged VLAN IDs that are allowed to pass through.

        Assumes has_tag_support() returns True.  If not, an empty list will
        be returned.
        """
        addl_vlans = self._get_val_str(_TA_VLAN_IDS, '')
        list_data = []
        if addl_vlans != '':
            list_data = [int(i) for i in addl_vlans.split(' ')]

        def update_list(new_list):
            data = ' '.join([str(j) for j in new_list])
            self.set_parm_value(_TA_VLAN_IDS, data)

        return ewrap.ActionableList(list_data, update_list)

    @tagged_vlans.setter
    def tagged_vlans(self, new_list):
        data = ' '.join([str(i) for i in new_list])
        self.set_parm_value(_TA_VLAN_IDS, data)

    @property
    def vswitch_id(self):
        """Returns the virtual switch identifier."""
        return self._get_val_int(_TA_VS_ID)

    def _vswitch_id(self, value):
        self.set_parm_value(_TA_VS_ID, value)

    @property
    def trunk_pri(self):
        """Returns the trunk priority of the adapter."""
        return self._get_val_int(_TA_TRUNK_PRI)

    def _trunk_pri(self, value):
        self.set_parm_value(_TA_TRUNK_PRI, value)

    def _required(self, value):
        self.set_parm_value(_TA_REQUIRED, u.sanitize_bool_for_api(value))

    @property
    def virtual_slot_number(self):
        """Returns the virtual slot number for this adapter."""
        return self._get_val_int(_TA_VIRTUAL_SLOT)

    @property
    def associated_vswitch_uri(self):
        """Returns the associated vswitch href."""
        return self.get_href(u.xpath(_TA_ASSOC_VSWITCH, c.LINK),
                             one_result=True)

    def _associated_vswitch_uri(self, href):
        self.set_href(u.xpath(_TA_ASSOC_VSWITCH, c.LINK), href)


@ewrap.ElementWrapper.pvm_type('LoadGroup', has_metadata=True)
class LoadGroup(ewrap.ElementWrapper):
    """Load Group (how the I/O load should be distributed) for a Network Bridge.

    If using failover or load balancing, then the Load Group will have pairs of
    Trunk Adapters, each with their own unique Trunk Priority.
    """

    @classmethod
    def bld(cls, adapter, pvid, vnet_uris):
        """Create the LoadGroup element that can be used for a create operation.

        This is used when adding a Load Group to a NetBridge.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param pvid: The primary VLAN ID (ex. 1) for the Load Group.
        :param vnet_uris: The virtual network URI list (mapping to each
                          additional VLAN/vswitch combo).
        :returns: A new LoadGroup ElementWrapper that represents the new
                  LoadGroup.
        """
        lg = super(LoadGroup, cls)._bld(adapter)
        lg._pvid(pvid)
        lg.vnet_uri_list.extend(vnet_uris)
        return lg

    @classmethod
    def wrap(cls, element, **kwargs):
        wrap = super(LoadGroup, cls).wrap(element)

        # If created from a Network Bridge this will be set.  Else it will
        # be None (ex. crt_load_group method)
        wrap._nb_root = kwargs.get('nb_root')
        return wrap

    @property
    def pvid(self):
        """Returns the Primary VLAN ID of the Load Group."""
        return self._get_val_int(_LG_PVID)

    def _pvid(self, new_pvid):
        self.set_parm_value(_LG_PVID, new_pvid)

    @property
    def trunk_adapters(self):
        """Returns the Trunk Adapters for the Load Group.

        There is either one (no redundancy/wrap balancing) or two (typically
        the case in a multi VIOS scenario).

        :return: list of TrunkAdapter objects.
        """
        return ewrap.WrapperElemList(self.element.find(_LG_TRUNKS),
                                     TrunkAdapter)

    @trunk_adapters.setter
    def trunk_adapters(self, new_list):
        self.replace_list(_LG_TRUNKS, new_list)

    @property
    def vnet_uri_list(self):
        """Returns a list of the Virtual Network URIs.

        If the vnet_aware trait (see traits.py) is set, then the addition
        of VLANs is driven via virtual networks rather than straight VLAN
        modification.  This uri list is what drives the modification.

        If the trait is set to false, then the modification should be driven
        via the trunk adapters on the SEA directly.  This list will also
        be empty.

        The task classes (cna.py and network_bridger.py) should abstract the
        user away from these deviations in traits.
        """
        uri_resp_list = list(self.get_href(u.xpath(_LG_VNETS, c.LINK)))
        return ewrap.ActionableList(uri_resp_list, self.__update_uri_list)

    @vnet_uri_list.setter
    def vnet_uri_list(self, new_list):
        self.__update_uri_list(new_list)

    def __update_uri_list(self, new_list):
        new_vnet_elem = self._bld_link_list(_VSW_VIRT_NETS, new_list)
        old_elems = self.element.find(_LG_VNETS)
        # This is a bug where the API isn't returning vnets if just a PVID
        # on additional VEA
        if old_elems is not None:
            self.element.replace(old_elems, new_vnet_elem)
        else:
            self.element.append(new_vnet_elem)

        # If the Network Bridge was set, tell it to rebuild its VirtualNetwork
        # list.
        try:
            self._nb_root._rebuild_vnet_list()
        except AttributeError:
            # Network Bridge was not set - ignore
            pass

    @property
    def tagged_vlans(self):
        """The VLANs supported by this Load Group.  Does not include PVID."""
        return self.trunk_adapters[0].tagged_vlans


@ewrap.EntryWrapper.pvm_type('VirtualNetwork')
class VNet(ewrap.EntryWrapper):
    """The overall definition of a VLAN network within the hypervisor."""

    @classmethod
    def bld(cls, adapter, name, vlan_id, vswitch_uri, tagged):
        """Creates a VirtualNetwork that can be used for a create operation.

        This is used when creating a new Virtual Network within the system

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name for the virtual network.
        :param vlan_id: The VLAN identifier (1 to 4094) for the network.
        :param vswitch_uri: The URI that points to the appropriate vSwitch.
        :param tagged: True if packets should have VLAN tags when they leave
                       the system.  False if tags should only be on the packets
                       while in the system (but tag-less when on the physical
                       network).
        :returns: The ElementWrapper that represents the new VirtualNetwork.
        """
        vnet = super(VNet, cls)._bld(adapter)
        # Assignment order matters
        vnet.associated_switch_uri = vswitch_uri
        vnet.name = name
        vnet.vlan = vlan_id
        vnet.tagged = tagged
        return vnet

    @property
    def associated_switch_uri(self):
        return self.get_href(_VNET_ASSOC_SW, one_result=True)

    @associated_switch_uri.setter
    def associated_switch_uri(self, uri):
        self.set_href(_VNET_ASSOC_SW, uri)

    @property
    def name(self):
        return self._get_val_str(_VNET_NET_NAME)

    @name.setter
    def name(self, value):
        self.set_parm_value(_VNET_NET_NAME, value)

    @property
    def vlan(self):
        return self._get_val_int(_VNET_VLAN_ID)

    @vlan.setter
    def vlan(self, vlan_id):
        self.set_parm_value(_VNET_VLAN_ID, vlan_id)

    @property
    def vswitch_id(self):
        """The vSwitch identifier (int).  0 through 15 (max number vSwitches).

        Is not a UUID.
        """
        return self._get_val_int(_VNET_SW_ID)

    @property
    def tagged(self):
        """If True, the VLAN tag is preserved when the packet leaves system."""
        return self._get_val_bool(_VNET_TAG)

    @tagged.setter
    def tagged(self, is_tagged):
        self.set_parm_value(_VNET_TAG, u.sanitize_bool_for_api(is_tagged))


@ewrap.EntryWrapper.pvm_type('ClientNetworkAdapter')
class CNA(ewrap.EntryWrapper):
    """Wrapper object for ClientNetworkAdapter schema."""

    @classmethod
    def bld(cls, adapter, pvid, vswitch_href, slot_num=None, mac_addr=None,
            addl_tagged_vlans=None):
        """Creates a fresh CNA EntryWrapper.

        This is used when creating a new CNA for a client partition.  This
        can be PUT to LogicalPartition/<UUID>/ClientNetworkAdapter.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
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
        cna = super(CNA, cls)._bld(adapter)
        # Assignment order matters
        if slot_num is not None:
            cna._slot(slot_num)
        else:
            cna._use_next_avail_slot_id = True

        if mac_addr is not None:
            cna.mac = mac_addr

        #  The primary VLAN ID
        cna.pvid = pvid

        # Additional VLANs
        if addl_tagged_vlans is not None:
            cna.tagged_vlans = addl_tagged_vlans
            cna.is_tagged_vlan_supported = True
        else:
            cna.is_tagged_vlan_supported = False

        # vSwitch URI
        cna.vswitch_uri = vswitch_href

        return cna

    @property
    def slot(self):
        return self._get_val_int(_VADPT_SLOT_NUM)

    def _slot(self, sid):
        self.set_parm_value(_VADPT_SLOT_NUM, sid)

    @property
    def _use_next_avail_slot_id(self):
        return self._get_val_bool(_VADPT_USE_NEXT_AVAIL_SLOT)

    @_use_next_avail_slot_id.setter
    def _use_next_avail_slot_id(self, unasi):
        """Param unasi is bool (True or False)."""
        self.set_parm_value(_VADPT_USE_NEXT_AVAIL_SLOT,
                            u.sanitize_bool_for_api(unasi))

    @property
    def mac(self):
        """Returns the Mac Address for the adapter.

        Typical format would be: AABBCCDDEEFF
        The API returns a format with no colons and is upper cased.
        """
        return self._get_val_str(_VADPT_MAC_ADDR)

    @mac.setter
    def mac(self, new_val):
        new_mac = u.sanitize_mac_for_api(new_val)
        self.set_parm_value(_VADPT_MAC_ADDR, new_mac)

    @property
    def pvid(self):
        """Returns the Port VLAN ID (int value)."""
        return self._get_val_int(_VADPT_PVID)

    @pvid.setter
    def pvid(self, new_val):
        self.set_parm_value(_VADPT_PVID, new_val)

    @property
    def loc_code(self):
        """The device's location code."""
        return self._get_val_str(_VADPT_LOCATION_CODE)

    @property
    def tagged_vlans(self):
        """Returns a list of additional VLANs on this adapter.

        Only valid if tagged vlan support is on.
        """
        addl_vlans = self._get_val_str(_VADPT_TAGGED_VLANS, '')
        list_data = []
        if addl_vlans != '':
            list_data = [int(i) for i in addl_vlans.split(' ')]

        def update_list(new_list):
            data = ' '.join([str(j) for j in new_list])
            self.set_parm_value(_VADPT_TAGGED_VLANS, data)

        return ewrap.ActionableList(list_data, update_list)

    @tagged_vlans.setter
    def tagged_vlans(self, new_list):
        data = ' '.join([str(i) for i in new_list])
        self.set_parm_value(_VADPT_TAGGED_VLANS, data)

    @property
    def is_tagged_vlan_supported(self):
        """Returns if addl tagged VLANs are supported (bool value)."""
        return self._get_val_bool(_VADPT_TAGGED_VLAN_SUPPORT)

    @is_tagged_vlan_supported.setter
    def is_tagged_vlan_supported(self, new_val):
        """Parameter new_val is a bool (True or False)."""
        self.set_parm_value(_VADPT_TAGGED_VLAN_SUPPORT,
                            u.sanitize_bool_for_api(new_val))

    @property
    def vswitch_uri(self):
        """Returns the URI for the associated vSwitch."""
        return self.get_href(u.xpath(_VADPT_VSWITCH, c.LINK), one_result=True)

    @vswitch_uri.setter
    def vswitch_uri(self, new_val):
        self.set_href(u.xpath(_VADPT_VSWITCH, c.LINK), new_val)


@ewrap.ElementWrapper.pvm_type(_SEA_ETH_BACK_DEV, has_metadata=True,
                               child_order=_SEA_EBD_ORDER)
class EthernetBackingDevice(ewrap.ElementWrapper):
    """Represents the SEA EthernetBackingDevice."""

    @classmethod
    def bld(cls, adapter, dev_name):
        """Creates the EthernetBackingDevice element.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param dev_name: The device name (e.g. eth0).
        :returns: The EthernetBackingDevice element for SEAs.
        """
        cfg = super(EthernetBackingDevice, cls)._bld(adapter)
        cfg._dev_name(dev_name)

        # This is required by the schema, setting it to 1
        # just for legacy support.
        cfg._adapter_id(1)

        return cfg

    @property
    def dev_name(self):
        return self._get_val_str(_SEA_DEV_NAME)

    def _dev_name(self, dev_name):
        self.set_parm_value(_SEA_DEV_NAME, str(dev_name))

    @property
    def adapter_id(self):
        return self._get_val_int(_SEA_EBD_ADAPTER_ID)

    def _adapter_id(self, value):
        # TODO(IBM) remove this once the schema no longer requires it.
        return self.set_parm_value(_SEA_EBD_ADAPTER_ID, value)
