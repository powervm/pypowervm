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

import fixtures
import testtools

from pypowervm.tasks import pci
import pypowervm.tests.tasks.util as tutil
from pypowervm.tests import test_fixtures as pvm_fx
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as msys
import pypowervm.wrappers.virtual_io_server as vios


SYS_FILE = 'managedsystem.txt'
VIOS_FILE = 'fake_vios_feed.txt'
LPAR_FILE = 'fake_lpar_feed.txt'

TOTAL_SLOTS = 26
V1_ASSIGNED_SLOTS = 3
V2_ASSIGNED_SLOTS = 3
LPAR_ASSIGNED_SLOTS = 0
ASSIGNED_SLOTS = V1_ASSIGNED_SLOTS + V2_ASSIGNED_SLOTS + LPAR_ASSIGNED_SLOTS
FREE_SLOTS = TOTAL_SLOTS - ASSIGNED_SLOTS
KNOWN_DRC_INDEX = 553975841
KNOWN_DRC_NAME = 'U5294.001.CEC1234-P13-C115'


class TestPCI(testtools.TestCase):
    def setUp(self):
        super(TestPCI, self).setUp()

        self.adap = self.useFixture(pvm_fx.AdapterFx()).adpt
        self.sfeed = msys.System.wrap(tutil.load_file(
            SYS_FILE, adapter=self.adap))
        self.vfeed = vios.VIOS.wrap(tutil.load_file(
            VIOS_FILE, adapter=self.adap))
        self.lfeed = lpar.LPAR.wrap(tutil.load_file(
            LPAR_FILE, adapter=self.adap))

        self.mock_sys = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.pci.msys.System.get')).mock
        self.mock_sys.return_value = self.sfeed

        self.mock_vios = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.pci.vios.VIOS.get')).mock
        self.mock_vios.return_value = self.vfeed

        self.mock_lpar = self.useFixture(fixtures.MockPatch(
            'pypowervm.tasks.pci.lpar.LPAR.get')).mock
        self.mock_lpar.return_value = self.lfeed

    def test_init_fetch(self):
        pci.SlotInfo(self.adap)
        self.mock_sys.assert_called_once_with(self.adap)
        self.mock_vios.assert_called_once_with(self.adap)
        self.mock_lpar.assert_called_once_with(self.adap)

    def test_init_no_fetch(self):
        slot_info = pci.SlotInfo(self.adap, sys_w=self.sfeed[0])
        self.mock_sys.assert_not_called()
        self.mock_vios.assert_called_once_with(self.adap)
        self.mock_lpar.assert_called_once_with(self.adap)
        # Sanity sniff test.
        self.assertEqual(TOTAL_SLOTS, len(slot_info))

    def test_tupleness(self):
        slot_info = pci.SlotInfo(self.adap)
        self.assertIsInstance(slot_info, tuple)
        self.assertEqual(TOTAL_SLOTS, len(slot_info))
        # Verify uniqueness
        self.assertEqual(TOTAL_SLOTS,
                         len({slot.drc_index for slot in slot_info}))
        # Iteration works
        for slot in slot_info:
            self.assertIsInstance(slot, pci._SlotAssignment)
        # Slicing works
        slc = slot_info[4:15]
        self.assertEqual(11, len(slc))
        for slot in slc:
            self.assertIsInstance(slot, pci._SlotAssignment)

    def test_assigned(self):
        assigned = [slot for slot in pci.SlotInfo(self.adap) if slot.assigned]
        self.assertEqual(ASSIGNED_SLOTS, len(assigned))
        for slot in assigned:
            self.assertIsNotNone(slot.part_uuid)
            self.assertIn(slot.part_w, self.vfeed + self.lfeed)
            self.assertIn(slot.part_uuid,
                          [part.uuid for part in self.vfeed + self.lfeed])
        self.assertEqual(V1_ASSIGNED_SLOTS,
                         len([slot for slot in assigned
                              if slot.part_uuid == self.vfeed[0].uuid]))
        self.assertEqual(V2_ASSIGNED_SLOTS,
                         len([slot for slot in assigned
                              if slot.part_uuid == self.vfeed[1].uuid]))
        self.assertEqual(LPAR_ASSIGNED_SLOTS,
                         len([slot for slot in assigned
                              if slot.part_w in self.lfeed]))

    def test_free(self):
        free = [slot for slot in pci.SlotInfo(self.adap) if not slot.assigned]
        self.assertEqual(FREE_SLOTS, len(free))
        for slot in free:
            self.assertIsNone(slot.part_uuid)
            self.assertIsNone(slot.part_w)

    def test_slot_attrs(self):
        slot_info = pci.SlotInfo(self.adap)
        indices = {slot.drc_index for slot in slot_info}
        for index in indices:
            self.assertIsInstance(index, int)
        names = {slot.drc_name for slot in slot_info}
        for name in names:
            self.assertIsInstance(name, str)
        self.assertIn(KNOWN_DRC_INDEX, indices)
        self.assertIn(KNOWN_DRC_NAME, names)
