# Copyright 2017 IBM Corp.
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

"""Complex tasks around I/O slots and (non-SR-IOV) PCI devices."""

import pypowervm.exceptions as exc
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as msys
import pypowervm.wrappers.virtual_io_server as vios


class _SlotAssignment(object):
    """IOSlot "subclass" with info about the partition to which it is assigned.

    We don't actually subclass IOSlot because there are two different IOSlot
    wrappers: base_partition.IOSlot and managed_system.IOSlot.  They have most
    of the same methods, so the consumer generally won't know or care which one
    they're getting.
    """
    def __init__(self, ioslot_w, part_uuid=None, part_w=None):
        self._ioslot_w = ioslot_w
        self._adap = ioslot_w.adapter
        self.part_uuid = part_uuid
        self._part_w = part_w

    def __getattr__(self, item):
        """Any properties not defined below are on the IOSlot."""
        return getattr(self._ioslot_w, item)

    def _get_part(self, klass, uuid):
        try:
            return klass.get(self._adap, uuid=uuid)
        except exc.HttpNotFound:
            return None

    @property
    def part_w(self):
        """The wrapper of the LPAR or VIOS to which this slot is assigned.

        Will return None if the slot is unassigned.

        :raise: NoPartitionForSlotAssignment if a partition UUID is associated
                with this slot, but no partition exists for that UUID.  This
                *should* mean that the SlotInfo is stale (the slot was
                unassigned from the partition and the partition deleted since
                the SlotInfo was retrieved).
        """
	# NOTE(efried): This lazy-load should be unused until ManagedSystem's
	# IOSlots have partition information.
        if self._part_w is None:
            if self.part_uuid is None:
                return None
            self._part_w = (self._get_part(lpar.LPAR, self.part_uuid) or
                            self._get_part(vios.VIOS, self.part_uuid))
            if self._part_w is None:
                # This is an error.  It either means the SlotInfo needs to be
                # refreshed; or there's really an assignment to a partition
                # that doesn't exist.
                raise exc.NoPartitionForSlotAssignment(
                    uuid=self.part_uuid, drc_name=self._ioslot_w.drc_name)
        return self._part_w

    @property
    def assigned(self):
        return self.part_uuid is not None


class SlotInfo(tuple):
    """Information about IOSlots and the partitions to which they are assigned.

    Usage:
    # Set it up
    slotinfo = SlotInfo(adapter, sys_w=my_sys_wrapper)
    # Or to have SlotInfo retrieve the Managed System wrapper:
    slotinfo = SlotInfo(adapter)

    The result is a tuple - it cannot be modified (or "refreshed") once
    created.  However, the order of the slots therein is not significant.

    # How many slots?
    numslots = len(slotinfo)
    # Only unassigned slots
    freeslots = [si for si in slotinfo if not si.assigned]
    # First slot's partition UUID (will be None if unassigned)
    part_uuid = slotinfo[0].part_uuid
    # First slot's partition wrapper (will be None if unassigned)
    part_w = slotinfo[0].part_w
    # First slot's DRC index.
    drc_index = slotinfo[0].drc_index
    """
    def __new__(cls, adap, sys_w=None):
        """Create a new instance of SlotInfo.

        :param adap: pypowervm.adapter.Adapter for REST API communication.
        :param sys_w: pypowervm.wrappers.managed_system.System wrapper.  If not
                      supplied, it will be retrieved afresh.
        :return: A newly-initialized instance of SlotInfo.
        """
        if not sys_w:
            sys_w = msys.System.get(adap)[0]
        # List of _SlotAssignment.  Will be used to initialize this tuple.
        sa_list = []
        # TODO(efried) Redo this when sys_w's IOSlots contain partition info.
        # Get all the partitions.
        lfeed = lpar.LPAR.get(adap)
        vfeed = vios.VIOS.get(adap)
        # Set of DRC indices for filtering assigned slots out of sys_w later
        seen_slots = set()
        for part_w in lfeed + vfeed:
            for slot in part_w.io_config.io_slots:
                sa_list.append(_SlotAssignment(slot, part_uuid=part_w.uuid,
                                               part_w=part_w))
                # These should never duplicate for assigned slots.
                seen_slots.add(slot.drc_index)
        # Now go through the Managed System and add only unassigned slots
        for slot in sys_w.asio_config.io_slots:
            if slot.drc_index not in seen_slots:
                sa_list.append(_SlotAssignment(slot))

        # Construct the tuple
        return super(SlotInfo, cls).__new__(cls, tuple(sa_list))
