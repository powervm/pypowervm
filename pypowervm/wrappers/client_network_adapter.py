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

from pypowervm import util as u
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

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


class ClientNetworkAdapter(ewrap.EntryWrapper):
    """Wrapper object for ClientNetworkAdapter schema."""

    schema_type = c.CNA
    has_metadata = True

    @classmethod
    def new_instance(cls, pvid=None, vswitch_href=None, slot_num=None,
                     mac_addr=None, addl_tagged_vlans=None):
        """Creates a fresh ClientNetworkAdapter EntryWrapper.

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
        :returns: An ClientNetworkAdapter EntryWrapper that can be used for
                  create.
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
                            u.sanitize_bool_for_api(unasi))

    @property
    def mac(self):
        """Returns the Mac Address for the adapter.

        Typical format would be: AABBCCDDEEFF
        The API returns a format with no colons and is upper cased.
        """
        return self._get_val_str(VADPT_MAC_ADDR)

    @mac.setter
    def mac(self, new_val):
        new_mac = u.sanitize_mac_for_api(new_val)
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
            data = ' '.join([str(i) for i in new_list])
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
                            u.sanitize_bool_for_api(new_val))

    @property
    def vswitch_uri(self):
        """Returns the URI for the associated vSwitch."""
        return self.get_href(VADPT_VSWITCH + c.DELIM + 'link', one_result=True)

    @vswitch_uri.setter
    def vswitch_uri(self, new_val):
        self.set_href(VADPT_VSWITCH + c.DELIM + 'link', new_val)
