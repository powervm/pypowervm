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

from pypowervm.i18n import _
from pypowervm.wrappers import storage as stor
from pypowervm.wrappers import virtual_io_server as vios


class STORAGE_CLASS(object):
    """Enumeration of differently-handled storage classes."""
    VFC = 'VFC'
    LU = stor.LU.__class__.__name__
    VDISK = stor.VDisk.__class__.__name__
    VOPT = stor.VOptMedia.__class__.__name__
    PV = stor.PV.__class__.__name__


@six.add_metaclass(abc.ABCMeta)
class SlotMapBase(object):
    """Save/fetch slot-to-I/O topology for an instance."""

    def __init__(self, inst_key):
        """Load (or create) a SlotMap for a given instance key.

        :param inst_key: Unique key (e.g. LPAR UUID) by which the slot map for
                         a given instance is referenced in storage.
        """
        # Prefix to avoid collision with other (poorly-planned) keys in the
        # back end.
        self.inst_key = 'SlotMap_%s' % inst_key
        map_str = self.load(inst_key)
        self._map = json.loads(map_str) if map_str else {}

    @property
    def slot_map(self):
        return json.dumps(self._map)

    @abc.abstractmethod
    def load(self, inst_key):
        """Load the slot map for an instance from storage.

        The subclass must implement this method to retrieve the slot map - an
        opaque data string - from a storage back-end.

        :param inst_key: Unique key (e.g. LPAR UUID) by which the slot map for
                         a given instance is referenced in storage.
        :return: Opaque data string loaded from storage.  If no value exists in
                 storage for the given inst_key, this method should return
                 None.
        """
        pass

    @abc.abstractmethod
    def save(self):
        """Save the slot map for an instance to storage.

        The subclass must implement this method to save self.slot_map - an
        opaque data string - to a storage back-end.  The object must be
        retrievable subsequently via the key self.inst_key.  If the back-end
        already contains a value for self.inst_key, this method must overwrite
        it.
        """
        pass

    @abc.abstractmethod
    def delete(self):
        """Remove the back-end storage for this SlotMap.

        The subclass must implement this method to remove the opaque data
        string associated with self.inst_key from the storage back-end.
        """
        pass

    def register_cna(self, cna):
        """Register the slot and switch topology of a client network adapter.

        :param cna: CNA EntryWrapper to register.
        """
        pass

    def register_mapping(self, map_wrap, stg_key=None):
        """Incorporate the slot topology associated with a mapping.

        :param map_wrap: VStorageMapping subclass (VSCSIMapping or VFCMapping)
                         to be incorporated into the slot topology.
        :param stg_key: Required in the following scenarios:
                            - If map_wrap is a VFCMapping, storage_key is the
                              fabric name associated with the mapping.
        """
        if not isinstance(map_wrap, vios.VStorageMapping):
            raise ValueError(_("Consumer code error: register_mapping method "
                               "must be invoked with an instance of a "
                               "VStorageMapping subclass."))
        cslot = map_wrap.server_adapter.lpar_id
        if isinstance(map_wrap, vios.VSCSIMapping):
            self._reg_vscsi_map(map_wrap.backing_storage, cslot)
        elif isinstance(map_wrap, vios.VFCMapping):
            if stg_key is None:
                raise ValueError(_(
                    "Consumer code error: fabric name must be specified via "
                    "storage_key to register a VFCMapping."))
            # { 'vfc': { fabric_name: [slot_num1, slot_num2, ...] } }
            self._reg_slot_in_list(STORAGE_CLASS.VFC, stg_key, cslot)
        else:
            raise NotImplementedError(
                _("Implementation error: VStorageMapping subclass %s not "
                  "handled!") % map_wrap.__class__.__name__)

    def _reg_vscsi_map(self, bstor, cslot):
        """Register a VSCSI mapping.

        Different storage types are treated differently.

        { # Only one VOpt per VIOS, but it needs to be in the right slot.
          VOPT: { VOPT: [slot#, ...] }
          # Localdisk won't be restored per se - just need to make sure a disk
          # of the right size is in the right slot.
          VDISK: { capacity: [slot#, ...], ... }
          # Attach volumes and LUs based on their UDID
          PV/LU: { udid: [slot#, ...], ... }
        }
        """
        if isinstance(bstor, stor.VOptMedia):
            # There's only one VOptMedia per VIOS.  Key is a constant.
            stg_key = STORAGE_CLASS.VOPT
        elif isinstance(bstor, stor.VDisk):
            # Local disk - the IDs will be different on the target (because
            # it's different storage) and the data will be gone (likewise).
            # So the only thing we need to make sure of is that disks of
            # (at least) the right *size* end up in the right slots.
            stg_key = str(bstor.capacity)
        else:
            # PV, LU
            stg_key = bstor.udid
        self._reg_slot_in_list(bstor.__class__.__name__, stg_key, cslot)

    def _reg_slot_in_list(self, stg_class, stg_key, client_slot):
        """Register slot ID where storage key can be connected to many slots.

        For the internal data structure:

            { outer_key: { storage_key: [client_slot, ...] } }

        ...appends client_slot to the inner list.  Intervening data structures
        are vivified if they don't already exist.

        :param stg_class:
        :param stg_key:
        :param client_slot:
        """
        if stg_class not in self._map:
            self._map[stg_class] = {}
        if stg_key not in self._map[stg_class]:
            self._map[stg_class][stg_key] = []
        self._map[stg_class][stg_key].append(client_slot)
