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
"""Utilities to map slot numbers to I/O elements.

These utilities facilitate rebuilding the storage/network topology of an LPAR
e.g. on the target system of a remote rebuild.
"""

import abc
import ast
import collections
import copy
import pickle
import six

from pypowervm import exceptions as pvm_ex
from pypowervm import util as pvm_util
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


@six.add_metaclass(abc.ABCMeta)
class SlotMapBase(object):
    """Save/fetch slot-to-I/O topology for an instance.

    This class must be extended by something that can interact with a
    persistent storage device to implement the save, load, and delete methods.
    The slot metadata is used during a rebuild operation (e.g. Remote Restart)
    to ensure that the client devices are in the same slots on the target.
    Typically this map is constructed on the source system and then saved.  It
    is loaded on the target system and used to rebuild an instance the same
    way.
    """

    def __init__(self, inst_key, load=True):
        """Load (or create) a SlotMap for a given instance key.

        :param inst_key: Unique key (e.g. LPAR UUID) by which the slot map for
                         a given instance is referenced in storage.
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
        self._slot_topo = ast.literal_eval(map_str) if map_str else {}

    def __str__(self):
        """An opaque string representation of the data in this class.

        When implementing the save method, use str to serialize the slot map
        data to an opaque string to write to external storage.
        """
        # Serialize to a JSON string
        return pickle.dumps(self.topology)

    @abc.abstractmethod
    def load(self):
        """Load the slot map for an instance from storage.

        The subclass must implement this method to retrieve the slot map - an
        opaque data string - from a storage back-end, where it was stored keyed
        on self.inst_key.

        :return: Opaque data string loaded from storage.  If no value exists in
                 storage for self.inst_key, this method should return None.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def save(self):
        """Save the slot map for an instance to storage.

        The subclass must implement this method to save str(self) - an opaque
        data string - to a storage back-end.  The object must be retrievable
        subsequently via the key self.inst_key.  If the back-end already
        contains a value for self.inst_key, this method must overwrite it.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def delete(self):
        """Remove the back-end storage for this slot map.

        The subclass must implement this method to remove the opaque data
        string associated with self.inst_key from the storage back-end.
        """
        raise NotImplementedError()

    def initialize_on_target(self, vios_wraps, pv_vscsi_vol_to_vio,
                             npiv_fabric_map):
        """Initializes the rebuild map.

        Only to be used when an instance is being recreated.  Will set up the
        data structure so that slots can be retrieved.

        If this is not a recreate, then this method should not be called.
        Instead all slots will be None (indicating normal code path) and this
        object is used to store any new slot information.

        This method will flag to the system that this is a rebuild operation
        and rather than use 'next available slot', we are rebuilding and need
        to use the exact previous slots.

        :param vios_wraps: The Virtual I/O Server Wrappers.  Should have the
                           appropriate XAGs.
        :param pv_vscsi_vol_to_vio: The physical volume to virtual I/O server
                                    mapping.  Of the following format:
                                    { 'udid' : [ 'vios_uuid', 'vios_uuid'] }
        :param npiv_fabric_map: The map of vFC mappings.  Of the following
                                format:
                                { 'fabric': {'slots': [slot1, slot2, etc...],
                                             'phys_wwpns': ['aa', 'bb'] } }
        """
        # Lets first get the vea's built
        self._vea_build_out()

        # Next up is vSCSI
        self._pv_vscsi_build_out(pv_vscsi_vol_to_vio)

        # And finally vFC (npiv)
        self._npiv_build_out(npiv_fabric_map, vios_wraps)

    def _pv_vscsi_build_out(self, vol_to_vio):
        """Builds the 'rebuild_map' for the PV physical volumes."""
        slots_order = {}
        for slot in self.topology:
            io_dict = self.topology[slot]
            # There are multiple types of things that can go into the vSCSI
            # map.  Some are not supported for rebuild.
            if io_dict.get(IOCLASS.VDisk):
                raise pvm_ex.InvalidHostForRebuildInvalidIOType(
                    io_type='Virtual Disk')
            elif io_dict.get(IOCLASS.LU):
                # TODO(thorst) fix in future version.  Should be supported.
                raise pvm_ex.InvalidHostForRebuildInvalidIOType(
                    io_type='Logical Unit')
            elif io_dict.get(IOCLASS.VOPT):
                raise pvm_ex.InvalidHostForRebuildInvalidIOType(
                    io_type='Virtual Optical Media')

            # Create a dictionary of slots to the number of mappings per
            # slot. This will determine which slots we assign first.
            slots_order[slot] = len(io_dict.get(IOCLASS.PV).keys())

        # For VSCSI we need to figure out which slot numbers have the most
        # mappings and assign these ones to VIOSes first in descending order.
        #
        # We do this because if we have 4 mappings for storage elements 1
        # through 4 on slot X and 5 mappings for storage elements 1 through 5
        # on slot Y, then we must ensure the VIOS that has storage elements 1
        # through 5 gets slot Y (even though it's a candidate for slot X). We
        # solve this by assigning the most used slot numbers first.
        slots_order = collections.OrderedDict(
            sorted(slots_order.items(), key=lambda t: t[1], reverse=True))

        for slot in slots_order:
            # Initialize the set of candidate VIOSes. We don't want it empty
            # initially or else we'll inner join an empty set and have no
            # candidate VIOSes.
            candidate_vioses = set(
                vol_to_vio[self.topology[slot].get(IOCLASS.PV).keys()[0]])

            for udid in self.topology[slot].get(IOCLASS.PV).keys():
                # Inner Join. The goal is to end up with a set that only has
                # VIOSes which can see every backing storage elem for this
                # slot.
                candidate_vioses &= set(vol_to_vio[udid])

                # If the set of candidate VIOSes is empty then this host is
                # not a candidate for rebuild.
                if not candidate_vioses:
                    raise pvm_ex.InvalidHostForRebuildNotEnoughVIOS()

            # Just take one, doesn't matter which one.
            vios_uuid_for_slot = candidate_vioses.pop()

            for udid in self.topology[slot].get(IOCLASS.PV).keys():

                self._put_pv_vscsi_slot(self, vios_uuid_for_slot, udid, slot)

                # There's somewhat of a problem with this. We want to remove
                # the VIOS UUID we're picking from this list so that other
                # VIOSes will pick up the other mappings for this storage, but
                # it may be the case that the original storage actually
                # belonged to more than one mapping on a single VIOS. It's not
                # clear if this is allowed, and if it is the backing storage
                # can potentially be corrupted.
                #
                # If there were multiple mappings for the same vSCSI storage
                # element on the same VIOS then the topology could not
                # identify it. We may hit an invalid host for rebuild exception
                # if this happens or we may not. It depends on the differences
                # between source and destination VIOSes.
                vol_to_vio[udid].remove(vios_uuid_for_slot)

    def _vea_build_out(self):
        """Builds the 'rebuild_map' for the veas."""
        for slot, io_dict in self.topology:
            for mac, vswitch in io_dict.get(IOCLASS.CNA, {}):
                if vswitch == 'MGMTSWITCH':
                    self._put_mgmt_vea_slot(mac, slot)
                else:
                    self._put_vea_slot(mac, slot)

    def _npiv_build_out(self, fabric_slot_map, vios_wraps):
        """Builds the rebuild map for the NPIV fabrics."""
        for fabric in fabric_slot_map:
            slots = fabric.get('slots', [])
            phys_wwpns = fabric.get('phys_wwpns', [])

            # Get a copy of the VIOSes that we can work off of.
            fabric_vioses = copy.copy(vios_wraps)

            # See if we can get enough viable VIOSes for the slots.  One client
            # slot per VIOS.
            necessary_slots = len(slots)
            for vios in fabric_vioses:

                # If we don't need any more slots, we can just break out.
                if len(necessary_slots) == 0:
                    break

                # We need another port off the vioses...
                for phys_ports in phys_wwpns:
                    if phys_ports in vios.get_pfc_wwpns():
                        # Found a good physical port in the VIOS
                        slot = necessary_slots.pop()
                        self._put_npiv_slot(vios, fabric, slot)
                        break

            # If there are still necessary slots, we need to break out of the
            # remote rebuild operation.  This is not a valid host.
            if len(necessary_slots) > 0:
                raise pvm_ex.InvalidHostForRebuildNotEnoughVIOS()

            # We reverse the VIOSes for the next fabric.  This is so that we
            # map to a different VIOS for the next slot.  We don't want them
            # to land all on the same VIOS as before.
            #
            # TODO(efried/thorst) Would be good to store the number of VIOSes
            # the fabric was attached to initially.
            vios_wraps.reverse()

    def _put_vfc_slot(self, vios_w, fabric, slot):
        if 'npiv' not in self.rebuild_map:
            self.rebuild_map['npiv'] = {}
        if fabric not in self.rebuild_map['npiv']:
            self.rebuild_map['npiv'][vios_w.uuid] = {}
        self.rebuild_map['npiv'][vios_w.uuid][fabric] = slot

    def _put_vea_slot(self, mac, slot):
        if 'vea' not in self.rebuild_map:
            self.rebuild_map['vea'] = {}
        self.rebuild_map['vea'][pvm_util.sanitize_mac_for_api(mac)] = slot

    def _put_mgmt_vea_slot(self, mac, slot):
        if 'mgmt_vea' not in self.rebuild_map:
            self.rebuild_map['mgmt_vea'] = {}
        self.rebuild_map['mgmt_vea'] = {
            'mac': pvm_util.sanitize_mac_for_api(mac), 'slot': slot}

    def _put_pv_vscsi_slot(self, vios_uuid, udid, slot):
        if 'pv_vscsi' not in self.rebuild_map:
            self.rebuild_map['pv_vscsi'] = {}
        if vios_uuid not in self.rebuild_map['pv_vscsi']:
            self.rebuild_map['pv_vscsi'][vios_uuid] = {}
        self.rebuild_map['pv_vscsi'][vios_uuid][udid] = slot

    def get_pv_vscsi_slot(self, vios_w, udid):
        """Gets the vSCSI client slot for the PV."""
        # Pull from the rebuild map.  Will default to None (indicating to
        # fuse an existing vscsi mapping or use next available slot for the
        # mapping).
        pv_vscsi_map = self.rebuild_map.get('pv_vscsi', {})
        return pv_vscsi_map.get(vios_w.uuid, {}).get(udid, None)

    def get_vea_slot(self, mac):
        """Gets the client slot for the VEA."""
        # Pull from the rebuild map.  Will default to None (indicating to use
        # the next available high slot).
        return self.rebuild_map.get('vea', {}).get(
            pvm_util.sanitize_mac_for_api(mac), None)

    def get_mgmt_vea_slot(self):
        """Gets the client slot and mac for the mgmt VEA.

        :return: Mac Address for the NIC
        :return: Slot for the NIC
        """
        mgmt_vea = self.rebuild_map.get('mgmt_vea', {})
        return mgmt_vea.get('mac', None), mgmt_vea.get('slot', None)

    def get_vfc_slot(self, vios_w, fabric):
        """Gets the client slot for a given VIOS and fabric."""
        npiv_map = self.rebuild_map.get('npiv', {})
        return npiv_map.get(vios_w.uuid, {}).get(fabric, None)

    def register_cna(self, cna):
        """Register the slot and switch topology of a client network adapter.

        :param cna: CNA EntryWrapper to register.
        """
        cna_map = self._vswitch_id2name(cna.adapter)
        self._reg_slot(IOCLASS.CNA, cna.mac, cna.slot,
                       extra_spec=cna_map[cna.vswitch_id])

    def drop_cna(self, cna):
        """Drops the client network adapter from the slot topology.

        :param cna: CNA EntryWrapper to drop.
        """
        self._drop_slot(IOCLASS.CNA, cna.mac, cna.slot)

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

    def _inspect_vscsi_mapping(self, vscsimap):
        # Must have backing storage and a server adapter to register
        if any(attr is None for attr in (vscsimap.backing_storage,
                                         vscsimap.server_adapter)):
            return None, None, None, None

        extra_spec = None
        bstor = vscsimap.backing_storage
        cslot = vscsimap.server_adapter.lpar_slot_num
        if isinstance(bstor, stor.VOptMedia):
            # There's only one VOptMedia per VIOS.  Key is a constant.
            stg_key = IOCLASS.VOPT
        else:
            # PV, LU, VDisk
            stg_key = bstor.udid
        if isinstance(bstor, stor.VDisk):
            # Local disk - the IDs will be different on the target (because
            # it's different storage) and the data will be gone (likewise).
            # Key on the UDID (above) in case it's a local rebuild.
            # For remote, the only thing we need to make sure of is that disks
            # of (at least) the right *size* end up in the right slots.
            extra_spec = bstor.capacity

        return bstor, stg_key, cslot, extra_spec

    def register_vscsi_mapping(self, vscsimap):
        """Incorporate the slot topology associated with a VSCSI mapping.

        :param vscsimap: VSCSIMapping ElementWrapper to be incorporated into
                         the slot topology.
        """
        bstor, stg_key, cslot, extra_spec = self._inspect_vscsi_mapping(
            vscsimap)
        if bstor:
            self._reg_slot(bstor.__class__.__name__, stg_key, cslot,
                           extra_spec=extra_spec)

    def drop_vscsi_mapping(self, vscsimap):
        """Drops the vscsi mapping from the slot topology.

        :param vscsimap: VSCSIMapping ElementWrapper to be removed from the
                         slot topology.
        """
        bstor, stg_key, cslot, extra_spec = self._inspect_vscsi_mapping(
            vscsimap)

        if bstor:
            self._drop_slot(bstor.__class__.__name__, stg_key, cslot)

    @property
    def topology(self):
        """Produce the slot-to-I/O topology structure from this SlotMap.

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
        VDISK       VDisk.udid                  VDisk.capacity (float)
        PV          PV.udid                     None
        LU          LU.udid                     None
        VFC         fabric name                 None
        VOPT        IOCLASS.VOPT (constant)     None
        """
        return self._slot_topo

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
                         handled by SlotMapBase.  Must be one of the IOCLASS
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
        """Drops a slot ID where an I/O key.

        :param io_class: Outer key representing one of the major classes of I/O
                         handled by SlotMapBase.  Must be one of the IOCLASS
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
