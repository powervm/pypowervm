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
import json
import six

from pypowervm.wrappers import network as net
from pypowervm.wrappers import storage as stor


class IO_CLASS(object):
    """Enumeration of differently-handled I/O classes."""
    VFC = 'VFC'
    LU = stor.LU.__class__.__name__
    VDISK = stor.VDisk.__class__.__name__
    VOPT = stor.VOptMedia.__class__.__name__
    PV = stor.PV.__class__.__name__
    CNA = net.CNA.__class__.__name__


@six.add_metaclass(abc.ABCMeta)
class SlotMapBase(object):
    """Save/fetch slot-to-I/O topology for an instance."""

    def __init__(self, inst_key):
        """Load (or create) a SlotMap for a given instance key.

        :param inst_key: Unique key (e.g. LPAR UUID) by which the slot map for
                         a given instance is referenced in storage.
        """
        self.inst_key = inst_key
        map_str = self.load(inst_key)
        # Deserialize or initialize
        self._slot_topo = json.loads(map_str) if map_str else {}
        self._vswitch_map = None

    def __str__(self):
        """An opaque string representation of the data in this class."""
        # Serialize to a JSON string
        return json.dumps(self._slot_topo)

    @abc.abstractmethod
    def load(self):
        """Load the slot map for an instance from storage.

        The subclass must implement this method to retrieve the slot map - an
        opaque data string - from a storage back-end, where it was stored keyed
        on self.inst_key.

        :return: Opaque data string loaded from storage.  If no value exists in
                 storage for self.inst_key, this method should return None.
        """
        pass

    @abc.abstractmethod
    def save(self):
        """Save the slot map for an instance to storage.

        The subclass must implement this method to save str(self) - an opaque
        data string - to a storage back-end.  The object must be retrievable
        subsequently via the key self.inst_key.  If the back-end already
        contains a value for self.inst_key, this method must overwrite it.
        """
        pass

    @abc.abstractmethod
    def delete(self):
        """Remove the back-end storage for this slot map.

        The subclass must implement this method to remove the opaque data
        string associated with self.inst_key from the storage back-end.
        """
        pass

    def register_cna(self, cna):
        """Register the slot and switch topology of a client network adapter.

        :param cna: CNA EntryWrapper to register.
        """
        cna_map = self._vswitch_id2name(cna.adapter)
        self._reg_slot(IO_CLASS.CNA, cna.mac, cna.slot,
                       extra_spec=cna_map[cna.vswitch_id])

    def register_vfc_mapping(self, vfcmap, fab):
        """Incorporate the slot topology associated with a VFC mapping.

        :param vfcmap: VFCMapping ElementWrapper representing the mapping to
                       be incorporated.
        :param fab: The fabric name associated with the mapping.
        """
        self._reg_slot(IO_CLASS.VFC, fab, vfcmap.server_adapter.lpar_slot_num)

    def register_vscsi_mapping(self, vscsimap):
        """Incorporate the slot topology associated with a VSCSI mapping.

        :param vscsimap: VSCSIMapping ElementWrapper to be incorporated into
                         the slot topology.
        """
        extra_spec = None
        bstor = vscsimap.backing_storage
        cslot = vscsimap.server_adapter.lpar_slot_num
        if isinstance(bstor, stor.VOptMedia):
            # There's only one VOptMedia per VIOS.  Key is a constant.
            stg_key = IO_CLASS.VOPT
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

        self._reg_slot(bstor.__class__.__name__, stg_key, cslot,
                       extra_spec=extra_spec)

    @property
    def topology(self):
        """Produce the slot-to-I/O topology structure from this SlotMap.

        :return: A dict of the form:

        { slot_num: { IO_CLASS: { io_key: extra_spec } } }

        ...where:

        - slot_num: Integer client slot ID.
        - IO_CLASS: The IO_CLASS enum indicating the type of I/O.  Each
                    IO_CLASS enum is only present if the source had at least
                    one I/O element of that type.
        - io_key: The unique identifier of the mapped I/O element.  This
                  differs by IO_CLASS type - see below.
        - extra_spec: Additional information about the I/O element.  This
                      differs by IO_CLASS type - see below.

        IO_CLASS    stg_key                     extra_spec
        ==============================================================
        CNA         CNA.mac                     VSwitch.name
        VDISK       VDisk.udid                  VDisk.capacity (float)
        PV          PV.udid                     None
        LU          LU.udid                     None
        VFC         fabric name                 None
        VOPT        IO_CLASS.VOPT (constant)    None
        """
        return self._slot_topo

    def _vswitch_id2name(self, adap):
        """(Cache and) return a map of VSwitch short ID to VSwitch name.

        :param adap: pypowervm.adapter.Adapter through which to query the
                     VSwitch topology.
        :return: Dict of { vswitch_short_id: vswitch_name }
        """
        if self._vswitch_map is None:
            self._vswitch_map = {vsw.switch_id: vsw.name for vsw in
                                 net.VSwitch.get(adap)}
        return self._vswitch_map

    def _reg_slot(self, io_class, io_key, client_slot, extra_spec=None):
        """Register a slot ID where an I/O key can be connected to many slots.

        :param io_class: Outer key representing one of the major classes of I/O
                         handled by SlotMapBase.  Must be one of the IO_CLASS
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
        # { slot_num: { IO_CLASS: { io_key: extra_spec } } }
        if client_slot not in self._slot_topo:
            self._slot_topo[client_slot] = {}
        if io_class not in self._slot_topo[client_slot]:
            self._slot_topo[client_slot][io_class] = {}
        # Always overwrite the extra_spec
        self._slot_topo[client_slot][io_class][io_key] = extra_spec
