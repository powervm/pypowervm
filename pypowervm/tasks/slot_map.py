# Copyright 2016 IBM Corp.
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
"""Utilities to map slot numbers to I/O elements and vice versa.

These utilities facilitate rebuilding the storage/network topology of an LPAR
e.g. on the target system of a remote rebuild.
"""

import collections
import copy
import pickle
import six
import warnings

from pypowervm import exceptions as pvm_ex
from pypowervm.i18n import _
from pypowervm import util as pvm_util
from pypowervm.utils import lpar_builder as lb
from pypowervm.wrappers import iocard as ioc
from pypowervm.wrappers import managed_system as sys
from pypowervm.wrappers import network as net
from pypowervm.wrappers import storage as stor


class IOCLASS(object):
    """Enumeration of differently-handled I/O classes."""
    VFC = 'VFC'
    LU = stor.LU.__name__
    VDISK = stor.VDisk.__name__
    VOPT = stor.VOptMedia.__name__
    PV = stor.PV.__name__
    CNA = net.CNA.__name__
    MGMT_CNA = 'MGMT' + net.CNA.__name__
    VNIC = ioc.VNIC.__name__


class SlotMapStore(object):
    """Save/fetch slot-to-I/O topology for an LPAR.

    This class should be extended by something that can interact with a
    persistent storage device to implement the save, load, and delete methods.

    The slot metadata is used during a rebuild operation (e.g. Remote Restart)
    to ensure that the client devices are in the same slots on the target.
    Typically this map is constructed on the source system and then saved.  It
    is loaded on the target system and used to rebuild an LPARthe same way.
    """

    def __init__(self, inst_key, load=True):
        """Load (or create) a SlotMapStore for a given LPAR.

        :param inst_key: Unique key (e.g. LPAR UUID) by which the slot map for
                         a given LPAR is referenced in storage.
        :param load: If True (the default), the load method is invoked to
                     retrieve existing data from backing storage.  If False
                     (e.g. if the caller knows there's nothing in the backing
                     store for inst_key; or deliberately wants to replace it),
                     this instance is initialized with an empty topology map.
        """
        self.inst_key = inst_key
        self._vswitch_map = None
        map_str = self.load() if load else None
        # Deserialize or initialize
        self._slot_topo = pickle.loads(map_str) if map_str else {}
        # Save a copy of the topology so we can tell when it has changed
        self._loaded_topo = copy.deepcopy(self._slot_topo)

    @property
    def serialized(self):
        """Internal use only.  Do not override.  Do not invoke."""
        # Used by the save method to serialize the slot map data to an opaque
        # value to write to external storage.
        # Use py2/3-compatible protocol.
        return pickle.dumps(self.topology, protocol=2)

    def load(self):
        """Internal use only.  Do not override.  Do not invoke."""
        # Used by __init__ to bootstrap this instance with saved data, if any.
        return self._load(self.inst_key)

    def _load(self, key):
        """Subclass implementation to load a slot map for an LPAR from storage.

        The subclass must implement this method to retrieve the slot map - an
        opaque data blob - from a storage back-end, where it was stored keyed
        on 'key'.

        :param key: Unique key to associate with this instance in the storage
                    back-end.
        :return: Opaque data blob loaded from storage.  If no value exists in
                 storage for this key, this method should return None.
        """
        return None

    def save(self):
        """Save this slot map to storage, if needed."""
        # Only save if needed.
        if self._slot_topo != self._loaded_topo:
            self._save(self.inst_key, self.serialized)
            # Update the saved version of the loaded topology so a subsequent
            # save (without intervening changes) can condition properly.
            self._loaded_topo = copy.deepcopy(self._slot_topo)

    def _save(self, key, blob):
        """Subclass implementation to write this slot map to storage.

        The subclass must implement this method to save 'blob' - an opaque data
        blob - to a storage back-end, keyed via 'key'.  The object must be
        retrievable subsequently via the same key.  If the back-end already
        contains a value for that key, this method must overwrite it.

        This method need not implement save-only-if-changed logic; that is
        handled by the 'save' method.

        :param key: Unique key to associate with this instance in the storage
                    back-end.
        :param blob: Opaque data blob to save to the storage back-end.  This
                     value is not to be introspected, as its format may change
                     without notice.
        """
        pass

    def delete(self):
        """Remove the back-end storage for this slot map."""
        self._delete(self.inst_key)

    def _delete(self, key):
        """Subclass implementation to delete this slot map from storage.

        The subclass must implement this method to remove the opaque data
        string associated with 'key' from the storage back-end.

        :param key: Unique key to associate with this instance in the storage
                    back-end.
        """
        pass

    def register_max_vslots(self, max_vslots):
        """Register the maximum number of virtual slots on the source LPAR.

        :param max_vslots: The maximum number of virtual slots on the LPAR.
        """
        self._slot_topo['_max_vslots'] = max_vslots

    def register_vnet(self, vnet_w):
        """Register the slot number for a CNA or VNIC.

        :param vnet_w: Either a CNA wrapper or a VNIC wrapper.
        :raises: InvalidVirtualNetworkDeviceType: If the wrapper passed in
                 is not a CNA or VNIC this will be raised.
        """
        if isinstance(vnet_w, net.CNA):
            cna_map = self._vswitch_id2name(vnet_w.adapter)
            self._reg_slot(IOCLASS.CNA, vnet_w.mac, vnet_w.slot,
                           extra_spec=cna_map[vnet_w.vswitch_id])
        elif isinstance(vnet_w, ioc.VNIC):
            self._reg_slot(IOCLASS.VNIC, vnet_w.mac, vnet_w.slot)
        else:
            raise pvm_ex.InvalidVirtualNetworkDeviceType(wrapper=vnet_w)

    def drop_vnet(self, vnet_w):
        """Drops the slot number for a CNA or VNIC.

        :param vnet_w: Either a CNA wrapper or a VNIC wrapper.
        :raises: InvalidVirtualNetworkDeviceType: If the wrapper passed in
                 is not a CNA or VNIC this will be raised.
        """
        if isinstance(vnet_w, net.CNA):
            self._drop_slot(IOCLASS.CNA, vnet_w.mac, vnet_w.slot)
        elif isinstance(vnet_w, ioc.VNIC):
            self._drop_slot(IOCLASS.VNIC, vnet_w.mac, vnet_w.slot)
        else:
            raise pvm_ex.InvalidVirtualNetworkDeviceType(wrapper=vnet_w)

    def register_cna(self, cna):
        """Register the slot and switch topology of a client network adapter.

        :deprecated: Use register_vnet instead.
        :param cna: CNA EntryWrapper to register.
        """
        warnings.warn(_("The register_cna method is deprecated! Please use "
                        "the register_vnet method."), DeprecationWarning)
        self.register_vnet(cna)

    def drop_cna(self, cna):
        """Drops the client network adapter from the slot topology.

        :deprecated: Use drop_vnet instead.
        :param cna: CNA EntryWrapper to drop.
        """
        warnings.warn(_("The drop_cna method is deprecated! Please use "
                        "the drop_vnet method."), DeprecationWarning)
        self.drop_vnet(cna)

    def register_vfc_mapping(self, vfcmap, fab):
        """Incorporate the slot topology associated with a VFC mapping.

        :param vfcmap: VFCMapping ElementWrapper representing the mapping to
                       be incorporated.
        :param fab: The fabric name associated with the mapping.
        """
        self._reg_slot(IOCLASS.VFC, fab, vfcmap.server_adapter.lpar_slot_num)

    def drop_vfc_mapping(self, vfcmap, fab):
        """Drops the client network adapter from the slot topology.

        :param vfcmap: VFCMapping ElementWrapper representing the mapping to
                       be removed.
        :param fab: The fabric name associated with the mapping.
        """
        self._drop_slot(IOCLASS.VFC, fab, vfcmap.server_adapter.lpar_slot_num)

    @staticmethod
    def _parse_vscsi_mapping(vscsimap):
        """Splits out a VSCSIMapping object for use in the internal slot map.

        :param vscsimap: A VSCSIMapping ElementWrapper to process.
        :return: The backing storage element, which may be any of the storage
                 types supported by VSCSIMapping.  None if the vscsimap lacks
                 either backing storage or server adapter.
        :return: The stg_key (storage key) appropriate to the backing storage
                 type.  See the topology @property.  None if the vscsimap lacks
                 either backing storage or server adapter.
        :return: The integer client slot number to which the VSCSIMapping is
                 attached.  None if the vscsimap lacks either backing storage
                 or server adapter.
        :return: The extra_spec (extra specification) value appropriate to the
                 backing storage type.  See the topology @property.  None if
                 the vscsimap lacks either backing storage or server adapter.
        """

        # Must have backing storage and a server adapter to register
        if any(attr is None for attr in (vscsimap.backing_storage,
                                         vscsimap.server_adapter)):
            return None, None, None, None

        extra_spec = None
        bstor = vscsimap.backing_storage
        cslot = vscsimap.server_adapter.lpar_slot_num
        stg_key = bstor.udid
        if isinstance(bstor, stor.VOptMedia):
            # Virtual Optical Media - The IDs will be different on the
            # target.  Using the UDID as a key (above) will at least allow us
            # to determine how many VIOSes should have VOptMedia devices.  For
            # remote rebuild, assuming the consumer uses consistent image
            # naming, we can use the extra_spec to identify which of multiple
            # VOpts we should pick up.
            extra_spec = bstor.name
        else:
            # For shared storage (PV/LU) and for local (VDISK), we need to
            # make sure the LUA (Logical Unit Address) of the device is
            # preserved on the target.  This informs things like boot order.
            extra_spec = vscsimap.target_dev.lua

        return bstor, stg_key, cslot, extra_spec

    def register_vscsi_mapping(self, vscsimap):
        """Incorporate the slot topology associated with a VSCSI mapping.

        :param vscsimap: VSCSIMapping ElementWrapper to be incorporated into
                         the slot topology.
        """
        bstor, stg_key, cslot, extra_spec = self._parse_vscsi_mapping(vscsimap)
        if bstor:
            self._reg_slot(bstor.__class__.__name__, stg_key, cslot,
                           extra_spec=extra_spec)

    def drop_vscsi_mapping(self, vscsimap):
        """Drops the vscsi mapping from the slot topology.

        :param vscsimap: VSCSIMapping ElementWrapper to be removed from the
                         slot topology.
        """
        bstor, stg_key, cslot = self._parse_vscsi_mapping(vscsimap)[:3]

        if bstor:
            self._drop_slot(bstor.__class__.__name__, stg_key, cslot)

    @property
    def topology(self):
        """Produce the slot-to-I/O topology structure from this SlotMapStore.

        :return: A dict of the form:

        { slot_num: { IOCLASS: { io_key: extra_spec } } }

        ...where:

        - slot_num: Integer client slot ID.
        - IOCLASS: The IOCLASS enum indicating the type of I/O.  Each IOCLASS
                   enum is only present if the source had at least one I/O
                   element of that type.
        - io_key: The unique identifier of the mapped I/O element.  This
                  differs by IOCLASS type - see below.
        - extra_spec: Additional information about the I/O element.  This
                      differs by IOCLASS type - see below.

        IOCLASS     stg_key                     extra_spec
        ==============================================================
        CNA         CNA.mac                     VSwitch.name
        VOPT        VOptMedia.udid              Media name
        VDISK       VDisk.udid                  VDisk.capacity (float)
        PV          PV.udid                     LUA
        LU          LU.udid                     LUA
        VFC         fabric name                 None
        VNIC        VNIC.mac                    None
        """
        ret = copy.deepcopy(self._slot_topo)
        ret.pop('_max_vslots', None)
        return ret

    @property
    def max_vslots(self):
        """Returns the highest slot number for the LPAR, or None if not set.

        This number corresponds to base_partition.max_virtual_slots, and
        indicates the maximum number of virtual slots (I/O buses) allowed on
        the LPAR.  If register_max_vslots has never bene called, this value
        will be None.
        """
        return self._slot_topo.get('_max_vslots', None)

    def _vswitch_id2name(self, adap):
        """(Cache and) return a map of VSwitch short ID to VSwitch name.

        :param adap: pypowervm.adapter.Adapter through which to query the
                     VSwitch topology.
        :return: Dict of { vswitch_short_id: vswitch_name }
        """
        if self._vswitch_map is None:
            self._vswitch_map = {
                vsw.switch_id: vsw.name for vsw in net.VSwitch.get(
                    adap, parent=sys.System.get(adap)[0])}
        return self._vswitch_map

    def _reg_slot(self, io_class, io_key, client_slot, extra_spec=None):
        """Register a slot ID where an I/O key can be connected to many slots.

        :param io_class: Outer key representing one of the major classes of I/O
                         handled by SlotMapStore.  Must be one of the IOCLASS
                         enum values.
        :param io_key: Unique identifier of the I/O element to be used as the
                       secondary key.  This differs based on io_class - see the
                       topology @property.
        :param client_slot: The integer slot number by which the I/O element is
                            attached to the client.
        :param extra_spec: Optional extra value to associate with the io_key.
                           This should always be the same for a given io_key.
                           The format/meaning of the value differs based on
                           io_class = see the topology @property.
        """
        # See the topology @property
        # { slot_num: { IOCLASS: { io_key: extra_spec } } }
        if client_slot not in self._slot_topo:
            self._slot_topo[client_slot] = {}
        if io_class not in self._slot_topo[client_slot]:
            self._slot_topo[client_slot][io_class] = {}
        # Always overwrite the extra_spec
        self._slot_topo[client_slot][io_class][io_key] = extra_spec

    def _drop_slot(self, io_class, io_key, client_slot):
        """Drops a client slot ID entry from the topology.

        :param io_class: Outer key representing one of the major classes of I/O
                         handled by SlotMapStore.  Must be one of the IOCLASS
                         enum values.
        :param io_key: Unique identifier of the I/O element to be used as the
                       secondary key.  This differs based on io_class - see the
                       topology @property.
        :param client_slot: The integer slot number by which the I/O element is
                            now detached from the client.
        """
        # See the topology @property
        # { slot_num: { IOCLASS: { io_key: extra_spec } } }
        if client_slot not in self._slot_topo:
            return
        if io_class not in self._slot_topo[client_slot]:
            return
        # Remove the key if it is in the topology
        if io_key in self._slot_topo[client_slot][io_class]:
            del self._slot_topo[client_slot][io_class][io_key]
            # Remove empty internal dicts
            if not self._slot_topo[client_slot][io_class]:
                del self._slot_topo[client_slot][io_class]
            if not self._slot_topo[client_slot]:
                del self._slot_topo[client_slot]


class BuildSlotMap(object):
    """Provides information on which slots should be used for LPAR creates.

    This class takes in a SlotMapStore and provides information on which
    slots should be used on the client adapters.

    If not overridden, this base implementation returns a client slot that
    allows the deploy implementation to choose the 'next available' slot.
    """

    def __init__(self, slot_store):
        """Initializes the slot map.

        :param slot_store: The existing instances SlotMapStore.
        """
        self._slot_store = slot_store
        self._build_map = {}

    def get_vscsi_slot(self, vios_w, udid):
        """Gets the vSCSI client slot and extra spec for the VSCSI device.

        :param vios_w: VIOS wrapper.
        :param udid: UDID of the VSCSI device.
        :return: Integer client slot number on which to create the VSCSIMapping
                 from the specified VIOS for the storage with the specified
                 udid.
        :return: Extra specification appropriate to the storage type.  See the
                 SlotMapStore.topology @property.
        """
        # Pull from the build map.  Will default to None (indicating to
        # fuse an existing vscsi mapping or use next available slot for the
        # mapping).
        # Since the UDID should be universally unique, search all storage types
        for by_vuuid in six.itervalues(self._build_map):
            if vios_w.uuid in by_vuuid and udid in by_vuuid[vios_w.uuid]:
                return by_vuuid[vios_w.uuid][udid]
        return None, None

    def get_pv_vscsi_slot(self, vios_w, udid):
        """DEPRECATED; Gets the vSCSI client slot for the PV.

        Use get_vscsi_slot.  This method will be removed shortly.

        :param vios_w: VIOS wrapper.
        :param udid: UDID of the physical volume.
        :return: Integer client slot number on which to create the VSCSIMapping
                 from the specified VIOS for the PV with the specified udid.
        """
        # Pull from the build map.  Will default to None (indicating to
        # fuse an existing vscsi mapping or use next available slot for the
        # mapping).
        pv_vscsi_map = self._build_map.get(IOCLASS.PV, {})
        return pv_vscsi_map.get(vios_w.uuid, {}).get(udid, (None,))[0]

    def get_vea_slot(self, mac):
        """Gets the client slot for the VEA.

        :param mac: MAC address string to look up.
        :return: Integer client slot number on which to create a CNA with the
                 specified MAC address.
        """
        # Pull from the build map.  Will default to None (indicating to use
        # the next available high slot).
        return self._build_map.get(IOCLASS.CNA, {}).get(
            pvm_util.sanitize_mac_for_api(mac), None)

    def get_mgmt_vea_slot(self):
        """Gets the client slot and MAC for the mgmt VEA.

        :return: MAC Address for the NIC.
        :return: Integer client slot number for the NIC.
        """
        mgmt_vea = self._build_map.get(IOCLASS.MGMT_CNA, {})
        return mgmt_vea.get('mac', None), mgmt_vea.get('slot', None)

    def get_vnet_slot(self, mac):
        """Gets the client slot for the VEA or VNIC, mgmt VEA not included.

        :param mac: MAC address string to look up.
        :return: Integer client slot number on which to create a CNA or VNIC
                 with the specified MAC address.
        """
        # Pull from the build map. Will default to None (indicating to use
        # the next available high slot).
        mac = pvm_util.sanitize_mac_for_api(mac)
        return (self._build_map.get(IOCLASS.CNA, {}).get(mac, None) or
                self._build_map.get(IOCLASS.VNIC, {}).get(mac, None))

    def get_vfc_slots(self, fabric, number_of_slots):
        """Gets the client slot list for a given NPIV fabric.

        :param fabric: Fabric name.
        :param number_of_slots: The number of slots for the specified fabric.
        :return: List of integer client slot numbers on which to map the given
                 fabric.
        :raises: InvalidHostForRebuildSlotMismatch : if the target server
                 requires more or less slots than the source server had.  If
                 this is a first deploy (ex. a standard BuildSlotMap) will not
                 matter, and will return an array of None's (indicating to use
                 the next available slots).
        """
        number_of_map_slots = len(self._build_map.get(IOCLASS.VFC,
                                                      {}).get(fabric, []))
        if not number_of_map_slots:
            return [None] * number_of_slots
        if number_of_map_slots == number_of_slots:
            return self._build_map.get(IOCLASS.VFC, {}).get(fabric, None)
        raise pvm_ex.InvalidHostForRebuildSlotMismatch(
            rebuild_slots=number_of_slots,
            original_slots=number_of_map_slots)

    def get_max_vslots(self):
        """Retrieve or derive the maximum number of virtual slots for the LPAR.

        If the source LPAR's maximum number of virtual slots was registered in
        the source slot map, that value is returned.  Otherwise, we attempt to
        derive a reasonable value based on the highest registered slot number.
        If none was registered, the minimum returned value will be the default
        from pypowervm.utils.lpar_builder.DEF_MAX_SLOT.

        It is the caller's responsibility to determine whether the value
        returned by this method is sufficiently high for the LPAR being
        created.
        """
        # Return the exact value if it was registered
        if self._slot_store.max_vslots is not None:
            return self._slot_store.max_vslots
        # Otherwise, return the higher of
        # - The default from lpar_builder
        # - The highest registered slot, plus 10
        from_hi_slot = (max(self._slot_store.topology.keys())
                        if self._slot_store.topology else 0) + 10
        return max(lb.DEF_MAX_SLOT, from_hi_slot)


class RebuildSlotMap(BuildSlotMap):
    """Used to determine the slot topology when rebuilding a VM.

    A LPAR rebuild needs to configure the client slots with the exact topology
    as their source.  This implementation requires additional details from the
    target server, but then provides the LPAR's appropriate client slot
    layout.
    """

    def __init__(self, slot_store, vios_wraps, vscsi_vol_to_vio,
                 npiv_fabrics):
        """Initializes the rebuild map.

        :param slot_store: The existing instances SlotMapStore.
        :param vios_wraps: List of VIOS EntryWrappers.  Must have been
                           retrieved with the appropriate XAGs.
        :param vscsi_vol_to_vio: The volume to virtual I/O server mapping.
                                 Of the following format:
                                 { 'lu_udid' : [ 'vios_uuid', 'vios_uuid'],
                                   'pv_udid' : [ 'vios_uuid', 'vios_uuid'] }
        :param npiv_fabrics: List of vFC fabric names.
        """
        super(RebuildSlotMap, self).__init__(slot_store)

        self.vios_wraps = vios_wraps

        # Lets first get the VEAs and VNICs built
        self._vea_build_out()
        self._vnic_build_out()

        # Next up is vSCSI
        self._vscsi_build_out(vscsi_vol_to_vio)

        # And finally vFC (npiv)
        self._npiv_build_out(npiv_fabrics)

    def get_mgmt_vea_slot(self):
        """Gets the client slot and MAC for the mgmt VEA.

        There should only be one MGMT VEA per system.  As such, subsequent
        calls to this will return the single MGMT VEA.

        :return: MAC Address for the NIC.
        :return: Integer client slot number for the NIC.
        """
        # On a rebuild specifically, the MGMT VIF may not be there.  If that
        # is the case, we want to make sure that it is the next available slot.
        mgmt_vea = self._build_map.get(IOCLASS.MGMT_CNA, {})
        slot = mgmt_vea.get('slot')

        # If the slot is None, that means the MGMT vif wasn't there initially
        # but its being requested for the rebuild.
        if slot is None:
            # Make sure there were slots, then use the 'next highest' available
            slots_in_use = sorted(self._slot_store.topology, reverse=True)
            if len(slots_in_use) > 0:
                slot = slots_in_use[0] + 1

        return mgmt_vea.get('mac', None), slot

    def _vscsi_build_slot_order(self):
        """Order slots by (descending) number of storage elements they host.

        :return: An ordered dictionary of the form { slot_num: count } where
                 slot_num is the integer slot number and count is the number of
                 supported* storage elements attached to this slot.  The dict
                 is ordered such that an iterator over its keys will return the
                 slot_num with the highest count first, etc.
                 *Only PV and LU are supported at this time.
        """
        slots_order = {}
        for slot in self._slot_store.topology:
            io_dict = self._slot_store.topology[slot]
            # There are multiple types of things that can go into the vSCSI
            # map.  Some are not supported for rebuild.
            if io_dict.get(IOCLASS.VOPT):
                raise pvm_ex.InvalidHostForRebuildInvalidIOType(
                    io_type='Virtual Optical Media')

            # Create a dictionary of slots to the number of mappings per
            # slot. This will determine which slots we assign first.
            slots_order[slot] = (len(io_dict.get(IOCLASS.PV, {})) +
                                 len(io_dict.get(IOCLASS.LU, {})) +
                                 len(io_dict.get(IOCLASS.VDISK, {})))

        # For VSCSI we need to figure out which slot numbers have the most
        # mappings and assign these ones to VIOSes first in descending order.
        #
        # We do this because if we have 4 mappings for storage elements 1
        # through 4 on slot X and 5 mappings for storage elements 1 through 5
        # on slot Y, then we must ensure the VIOS that has storage elements 1
        # through 5 gets slot Y (even though it's a candidate for slot X). We
        # solve this by assigning the most used slot numbers first.
        slots_order = collections.OrderedDict(sorted(
            six.iteritems(slots_order), key=lambda t: t[1], reverse=True))

        return slots_order

    def _vscsi_build_out(self, vol_to_vio):
        """Builds the '_build_map' for physical volumes and logical units."""
        slots_order = self._vscsi_build_slot_order()

        # We're going to use the vol_to_vio dictionary for consistency and
        # remove elements from it. We need to deepcopy so that the original
        # remains the same.
        vol_to_vio_cp = copy.deepcopy(vol_to_vio)

        for slot in slots_order:
            slot_topo = self._slot_store.topology[slot]
            if not any(slot_topo.get(x) for x in
                       (IOCLASS.PV, IOCLASS.LU, IOCLASS.VDISK)):
                continue
            # Initialize the set of candidate VIOSes to all available VIOSes.
            # We'll filter out and remove any VIOSes that can't host any PV or
            # LU for this slot.
            candidate_vioses = set(vio.uuid for vio in self.vios_wraps)

            slot_info = [(udid, lua, IOCLASS.PV) for udid, lua in
                         six.iteritems(slot_topo.get(IOCLASS.PV, {}))]
            slot_info.extend([(udid, lua, IOCLASS.LU) for udid, lua in
                              six.iteritems(slot_topo.get(IOCLASS.LU, {}))])
            slot_info.extend([(udid, lua, IOCLASS.VDISK) for udid, lua in
                              six.iteritems(slot_topo.get(IOCLASS.VDISK, {}))])
            for udid, lua, stg_class in slot_info:

                # If the UDID isn't anywhere to be found on the destination
                # VIOSes then we have a problem.
                if udid not in vol_to_vio_cp:
                    raise pvm_ex.InvalidHostForRebuildNoVIOSForUDID(udid=udid)

                # Inner Join. The goal is to end up with a set that only has
                # VIOSes which can see every backing storage elem for this
                # slot.
                candidate_vioses &= set(vol_to_vio_cp[udid])

                # If the set of candidate VIOSes is empty then this host is
                # not a candidate for rebuild.
                if not candidate_vioses:
                    raise pvm_ex.InvalidHostForRebuildNotEnoughVIOS(udid=udid)

            # Just take one, doesn't matter which one.
            # TODO(IBM): Perhaps find a way to ensure better distribution.
            vios_uuid_for_slot = candidate_vioses.pop()

            for udid, lua, stg_class in slot_info:

                self._put_vios_val(stg_class, vios_uuid_for_slot, udid,
                                   (slot, lua))

                # There's somewhat of a problem with this. We want to remove
                # the VIOS UUID we're picking from this list so that other
                # VIOSes will pick up the other mappings for this storage, but
                # it may be the case that the original storage actually
                # belonged to more than one mapping on a single VIOS. It's not
                # clear if this is allowed, and if it is the backing storage
                # can potentially be corrupted.
                #
                # If there were multiple mappings for the same vSCSI storage
                # element on the same VIOS then the slot store could not
                # identify it. We may hit an invalid host for rebuild exception
                # if this happens or we may not. It depends on the differences
                # between source and destination VIOSes.
                vol_to_vio_cp[udid].remove(vios_uuid_for_slot)

    def _vea_build_out(self):
        """Builds the '_build_map' for the veas."""
        for slot, io_dict in six.iteritems(self._slot_store.topology):
            for mac, vswitch in six.iteritems(io_dict.get(IOCLASS.CNA, {})):
                mac = pvm_util.sanitize_mac_for_api(mac)
                if vswitch == 'MGMTSWITCH':
                    self._put_mgmt_vea_slot(mac, slot)
                else:
                    self._put_novios_val(IOCLASS.CNA, mac, slot)

    def _vnic_build_out(self):
        """Builds the '_build_map' for the vnics."""
        for slot, io_dict in six.iteritems(self._slot_store.topology):
            for mac in io_dict.get(IOCLASS.VNIC, {}):
                self._put_novios_val(
                    IOCLASS.VNIC, pvm_util.sanitize_mac_for_api(mac), slot)

    def _npiv_build_out(self, fabrics):
        """Builds the build map for the NPIV fabrics.

        :param fabrics: List of NPIV fabric names.
        :raise InvalidHostForRebuildFabricsNotFound: If any fabrics in the
                                                     slot_map topology are not
                                                     in fabrics.
        """
        seen_fabrics = set()
        for fabric in fabrics:
            fabric_slots = []
            # Add the slot numbers for this fabric
            for slot, iomap in six.iteritems(self._slot_store.topology):
                if fabric not in iomap.get(IOCLASS.VFC, {}):
                    continue
                fabric_slots.append(slot)
                seen_fabrics.add(fabric)

            self._put_novios_val(IOCLASS.VFC, fabric, fabric_slots)

        # Make sure all the topology's fabrics are accounted for.
        # topo_fabrics is all the fabrics in all the slots from the slot_map
        # topology.
        topo_fabrics = {fab for iomap in self._slot_store.topology.values()
                        for fab in iomap.get(IOCLASS.VFC, {}).keys()}
        if topo_fabrics - seen_fabrics:
            raise pvm_ex.InvalidHostForRebuildFabricsNotFound(
                fabrics=', '.join(topo_fabrics - seen_fabrics))

    def _put_mgmt_vea_slot(self, mac, slot):
        """Store client slot data for the managament VEA.

        There should only ever be one of these.

        Enhances the rebuild map with:
        { IOCLASS_MGMT_CNA: { 'mac': mac, 'slot': 'slot' } }

        :param mac: MAC address (string) of the management VEA.
        :param slot: Client slot number for the management VEA.
        """
        if IOCLASS.MGMT_CNA not in self._build_map:
            self._build_map[IOCLASS.MGMT_CNA] = {}
        self._build_map[IOCLASS.MGMT_CNA] = {'mac': mac, 'slot': slot}

    def _put_novios_val(self, io_class, io_key, val):
        """Store a keyed value not associated with a VIOS.

        This applies to non-management CNAs, VNICs, and NPIV fabrics.
        Enhances the rebuild map with:
        { io_class: { io_key: val } }

        :param io_class: IOCLASS const value representing the type of I/O.
                         Either IOCLASS.CNA, IOCLASS.VNIC, or IOCLASS.NPIV
        :param io_key: Key of the I/O device to be added.  MAC address for
                       IOCLASS.CNA, IOCLASS.VNIC; fabric name for IOCLASS.VFC.
        :param val: The slot value(s) to be added.  A list of slot numbers for
                    IOCLASS.VFC; a single slot number for IOCLASS.CNA and
                    IOCLASS.VNIC.
        """
        if io_class not in self._build_map:
            self._build_map[io_class] = {}
        self._build_map[io_class][io_key] = val

    def _put_vios_val(self, stg_class, vios_uuid, udid, val):
        """Store client slot info associated with a storage dev and VIOS.

        This applies to VSCSI devices.  Enhances the rebuild map with:
        { stg_class: { vios_uuid: { stg_key: val } } }

        :param stg_class: IOCLASS const value representing the type of storage.
        :param vios_uuid: UUID of the VIOS which will host the storage device
                          indicated by stg_key.
        :param udid: UDID of the storage device to be added.
        :param val: The slot data to be added.  For IOCLASS.PV, this is a tuple
                    of (slot, lua).
        """
        if stg_class not in self._build_map:
            self._build_map[stg_class] = {}
        if vios_uuid not in self._build_map[stg_class]:
            self._build_map[stg_class][vios_uuid] = {}
        self._build_map[stg_class][vios_uuid][udid] = val
