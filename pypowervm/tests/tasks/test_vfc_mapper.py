# Copyright 2015 IBM Corp.
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

import unittest

import mock

from pypowervm import exceptions as e
from pypowervm.tasks import vfc_mapper
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIOS_FILE = 'fake_vios.txt'
VIOS_FEED = 'fake_vios_feed.txt'

FAKE_UUID = '42DF39A2-3A4A-4748-998F-25B15352E8A7'


class TestVFCMapper(unittest.TestCase):

    def test_find_vios_for_wwpn(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_feed_w = [vios_w]

        # Basic test
        vio_resp, p_resp = vfc_mapper.find_vios_for_wwpn(
            vios_feed_w, '10000090FA45473B')
        self.assertEqual(vios_w, vio_resp)
        self.assertIsNotNone(p_resp)

        # Validates the sanitized input
        vio_resp, p_resp = vfc_mapper.find_vios_for_wwpn(
            vios_feed_w, '10:00:00:90:fa:45:47:3b')
        self.assertEqual(vios_w, vio_resp)
        self.assertIsNotNone(p_resp)

        # Make sure a bad WWPN returns no result
        vio_resp, p_resp = vfc_mapper.find_vios_for_wwpn(
            vios_feed_w, '10:00:00:90:fa:45:47:3f')
        self.assertIsNone(vio_resp)
        self.assertIsNone(p_resp)

    def test_intersect_wwpns(self):
        list1 = ['AA:BB:CC:DD:EE:FF']
        list2 = {'aabbccddeeff', '1234567890'}
        self.assertEqual(list1, vfc_mapper.intersect_wwpns(list1, list2))

        # Full match
        list1 = {'aabbccddeeff', '1234567890'}
        list2 = ['AA:BB:CC:DD:EE:FF', '12:34:56:78:90']
        self.assertEqual(list1, set(vfc_mapper.intersect_wwpns(list1, list2)))

        # Second set as the limiter
        list1 = ['AA:BB:CC:DD:EE:FF', '12:34:56:78:90']
        list2 = {'aabbccddeeff'}
        self.assertEqual(['AA:BB:CC:DD:EE:FF'],
                         vfc_mapper.intersect_wwpns(list1, list2))

    def test_derive_npiv_map(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_wraps = [vios_w]

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA45473B', '10:00:00:90:fa:45:17:58']

        # Virtual WWPNs can be faked, and simplified.
        v_port_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

        # Run the derivation now
        resp = vfc_mapper.derive_npiv_map(vios_wraps, p_wwpns, v_port_wwpns)
        self.assertIsNotNone(resp)
        self.assertEqual(5, len(resp))

        # Make sure we only get two unique keys back.
        unique_keys = set([i[0] for i in resp])
        self.assertEqual({'10000090FA45473B', '10000090FA451758'}, unique_keys)

    def test_derive_base_npiv_map(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_wraps = [vios_w]

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA45473B', '10:00:00:90:fa:45:17:58']

        # Run the derivation now
        resp = vfc_mapper.derive_base_npiv_map(vios_wraps, p_wwpns, 5)
        self.assertIsNotNone(resp)
        self.assertEqual(5, len(resp))

        # Make sure we only get two unique keys back.
        unique_keys = set([i[0] for i in resp])
        self.assertEqual({'10000090FA45473B', '10000090FA451758'}, unique_keys)

        # Make sure we get the 'marker' back for the values.  Should now be
        # fused.
        values = set(i[1] for i in resp)
        self.assertEqual({vfc_mapper._FUSED_ANY_WWPN}, values)

    def test_derive_npiv_map_multi_vio(self):
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FEED))

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA5371F2', '10000090FA53720A']

        # Virtual WWPNs can be faked, and simplified.
        v_port_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

        # Run the derivation now
        resp = vfc_mapper.derive_npiv_map(vios_wraps, p_wwpns, v_port_wwpns)
        self.assertIsNotNone(resp)
        self.assertEqual(5, len(resp))

        # Make sure we only get two unique keys back.
        unique_keys = set([i[0] for i in resp])
        self.assertEqual(set(p_wwpns), unique_keys)

    def test_derive_npiv_map_failure(self):
        """Make sure we get a failure in the event of no candidates."""
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_wraps = [vios_w]

        # Subset the WWPNs on that VIOS.  These WWPNs don't actually exist,
        # so the VIOSes passed in won't have these as candidate ports.
        p_wwpns = ['10000090FA45473bA', '10:00:00:90:fa:45:17:58A']

        # Virtual WWPNs can be faked, and simplified.
        v_port_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

        # Run the derivation now
        self.assertRaises(e.UnableToFindFCPortMap, vfc_mapper.derive_npiv_map,
                          vios_wraps, p_wwpns, v_port_wwpns)

    def test_find_map_port(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)

        # Happy path, should find the first port on the VIOS
        p1 = vfc_mapper._find_map_port(vios_w.pfc_ports, [])
        self.assertIsNotNone(p1)

        # Lets add a mapping where P1 is used.  Should not get that result
        # back.
        p2 = vfc_mapper._find_map_port(vios_w.pfc_ports, [(p1.wwpn, '')])
        self.assertIsNotNone(p2)
        self.assertNotEqual(p1, p2)

        # Now add a third and fourth port.  Same assertions.
        p3 = vfc_mapper._find_map_port(vios_w.pfc_ports, [(p1.wwpn, ''),
                                                          (p2.wwpn, '')])
        self.assertIsNotNone(p3)
        self.assertNotIn(p3, [p1, p2])

        p4 = vfc_mapper._find_map_port(vios_w.pfc_ports, [(p1.wwpn, ''),
                                                          (p2.wwpn, ''),
                                                          (p3.wwpn, '')])
        self.assertIsNotNone(p4)
        self.assertNotIn(p4, [p1, p2, p3])

        # Artificially inflate the use of other ports.
        port_use = [(p1.wwpn, ''), (p2.wwpn, ''), (p3.wwpn, ''), (p4.wwpn, ''),
                    (p1.wwpn, ''), (p2.wwpn, ''), (p4.wwpn, '')]
        p_temp = vfc_mapper._find_map_port(vios_w.pfc_ports, port_use)
        self.assertIsNotNone(p_temp)
        self.assertNotIn(p_temp, [p1, p2, p4])

    def test_fuse_vfc_ports(self):
        self.assertEqual(['A B'], vfc_mapper._fuse_vfc_ports(['a', 'b']))
        self.assertEqual(['AA BB'], vfc_mapper._fuse_vfc_ports(['a:a', 'b:b']))
        self.assertEqual(['A B', 'C D'],
                         vfc_mapper._fuse_vfc_ports(['a', 'b', 'c', 'd']))

    @mock.patch('pypowervm.tasks.vfc_mapper.derive_base_npiv_map')
    def test_build_migration_mappings_for_fabric(self, mock_derive):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_wraps = [vios_w]

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA45473B', '10:00:00:90:fa:45:17:58']
        client_slots = ['1', '2']

        # The derive is non-deterministic.  That makes testing odd.  Force
        # a deterministic result.
        mock_derive.return_value = [('10000090FA451758', 'A A'),
                                    ('10000090FA45473B', 'B B')]

        # Build migration mappings success case
        resp = vfc_mapper.build_migration_mappings_for_fabric(
            vios_wraps, p_wwpns, client_slots)
        self.assertEqual(2, len(resp))
        self.assertEqual({'1/IO Server/1//fcs2', '2/IO Server/1//fcs1'},
                         set(resp))

    def test_build_migration_mappings_for_fabric_invalid_physical_port(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_wraps = [vios_w]

        # Invalid WWPNs should raise an error.
        p_wwpns = ['10000090FA45477B']
        client_slots = ['1', '2']

        # Build migration mappings success case
        self.assertRaises(e.UnableToFindFCPortMap,
                          vfc_mapper.build_migration_mappings_for_fabric,
                          vios_wraps, p_wwpns, client_slots)


class TestPortMappings(twrap.TestWrapper):
    file = VIOS_FEED
    wrapper_class_to_test = pvm_vios.VIOS
    mock_adapter_fx_args = {}

    def setUp(self):
        super(TestPortMappings, self).setUp()
        href_p = mock.patch('pypowervm.wrappers.virtual_io_server.VFCMapping.'
                            '_client_lpar_href')
        href = href_p.start()
        self.addCleanup(href_p.stop)
        href.return_value = 'fake_href'
        self.adpt.read.return_value = self.resp

    def test_find_vios_for_port_map(self):
        """Tests the find_vios_for_port_map method."""
        # Try off of the client WWPNs
        e0 = ('bad', 'c05076079cff08da c05076079cff08db')
        self.assertEqual(self.entries[0],
                         vfc_mapper.find_vios_for_port_map(self.entries, e0))

        # This WWPN is on the first VIOS
        e1 = ('10000090FA5371f1', 'a b')
        self.assertEqual(self.entries[0],
                         vfc_mapper.find_vios_for_port_map(self.entries, e1))

        # This WWPN is on the second VIOS
        e2 = ('10000090FA537209', 'a b')
        self.assertEqual(self.entries[1],
                         vfc_mapper.find_vios_for_port_map(self.entries, e2))

        # Try with a bad WWPN
        e3 = ('BAD', 'a b')
        self.assertIsNone(vfc_mapper.find_vios_for_port_map(self.entries, e3))

    def test_find_vios_for_vfc_wwpns(self):
        """Tests the find_vios_for_vfc_wwpns method."""
        # This WWPN is on the first VIOS
        v_wwpns = ['c05076079cff0e56', 'c05076079cff0e57']
        vios, vmap = vfc_mapper.find_vios_for_vfc_wwpns(self.entries, v_wwpns)
        self.assertEqual(self.entries[0], vios)
        self.assertEqual('10000090FA5371F2', vmap.backing_port.wwpn)

        # Have one of the ports be wrong
        v_wwpns = ['c05076079cff0e56', 'c05076079cff0e59']
        vios, vmap = vfc_mapper.find_vios_for_vfc_wwpns(self.entries, v_wwpns)
        self.assertIsNone(vios)
        self.assertIsNone(vmap)

        # Try odd formatting
        v_wwpns = ['C05076079cff0E56', 'c0:50:76:07:9c:ff:0E:57']
        vios, vmap = vfc_mapper.find_vios_for_vfc_wwpns(self.entries, v_wwpns)
        self.assertEqual(self.entries[0], vios)
        self.assertEqual('10000090FA5371F2', vmap.backing_port.wwpn)

        # Second VIOS
        v_wwpns = ['c05076079cff07ba', 'c05076079cff07bb']
        vios, vmap = vfc_mapper.find_vios_for_vfc_wwpns(self.entries, v_wwpns)
        self.assertEqual(self.entries[1], vios)
        self.assertEqual('10000090FA53720A', vmap.backing_port.wwpn)

        # Reverse WWPNs
        v_wwpns = ['c05076079cff07bb', 'c05076079cff07ba']
        vios, vmap = vfc_mapper.find_vios_for_vfc_wwpns(self.entries, v_wwpns)
        self.assertEqual(self.entries[1], vios)
        self.assertEqual('10000090FA53720A', vmap.backing_port.wwpn)

        # Set Type
        v_wwpns = {'c05076079cff07bb', 'c05076079cff07ba'}
        vios, vmap = vfc_mapper.find_vios_for_vfc_wwpns(self.entries, v_wwpns)
        self.assertEqual(self.entries[1], vios)
        self.assertEqual('10000090FA53720A', vmap.backing_port.wwpn)

    def test_add_port_mapping_multi_vios(self):
        """Validates that the port mappings are added cross VIOSes."""
        # Determine the vios original values
        vios_wraps = self.entries
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)
        vios2_name = vios_wraps[1].name
        vios2_orig_map_count = len(vios_wraps[1].vfc_mappings)

        def mock_update(*kargs, **kwargs):
            vios_w = pvm_vios.VIOS.wrap(kargs[0].entry)
            if vios1_name == vios_w.name:
                self.assertEqual(vios1_orig_map_count + 5,
                                 len(vios_w.vfc_mappings))
                # Note the spacing cross VIOS per fabric.
                self.ensure_has_wwpns(
                    vios_w, ['0', '1', '4', '5', '8', '9', 'C', 'D', 'G', 'H'])
            elif vios2_name == vios_w.name:
                self.assertEqual(vios2_orig_map_count + 5,
                                 len(vios_w.vfc_mappings))
                # Note the spacing cross VIOS per fabric.
                self.ensure_has_wwpns(
                    vios_w, ['2', '3', '6', '7', 'A', 'B', 'E', 'F', 'I', 'J'])
            else:
                self.fail("Unknown VIOS!")

            return vios_w.entry
        self.adpt.update_by_path.side_effect = mock_update

        # Subset the WWPNs on that VIOS
        fabric_A_wwpns = ['10000090FA5371f2', '10000090FA53720A']
        fabric_B_wwpns = ['10000090FA5371F1', '10000090FA537209']

        # Fake Virtual WWPNs.  Fabric B has an existing mapping that should
        # just get re-used.
        v_fabric_A_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        v_fabric_B_wwpns = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
                            'C05076079CFF045E', 'C05076079CFF045F']

        # Get the mappings
        fabric_A_maps = vfc_mapper.derive_npiv_map(vios_wraps, fabric_A_wwpns,
                                                   v_fabric_A_wwpns)
        vios_wraps.reverse()
        fabric_B_maps = vfc_mapper.derive_npiv_map(vios_wraps, fabric_B_wwpns,
                                                   v_fabric_B_wwpns)
        full_map = fabric_A_maps + fabric_B_maps

        # Now call the add action
        resp = vfc_mapper.add_npiv_port_mappings(self.adpt, 'host_uuid',
                                                 FAKE_UUID, full_map)

        # The update should have been called twice.  Once for each VIOS.
        self.assertEqual(2, self.adpt.update_by_path.call_count)

        # Validate the responses.  These should not be in there because they
        # were there already.  The first was explicitly added (see
        # fabric_b_wwpns).  The second happens to already exist in the test
        # data, but isn't part of the return.
        e_resp = [('10000090FA5371F1', 'C05076079CFF045E C05076079CFF045F'),
                  ('10000090FA53720A', 'C05076079CFF07BB C05076079CFF07BA')]
        for needle in resp:
            self.assertNotIn(needle, e_resp)

        # NOTE - The newly added maps are verified in the update method.  But
        # they aren't part of the response as that would require a new VIOS
        # payload or extensive patching.  Since we know that the updates are
        # called, this would provide little value.
        self.assertEqual(2, self.adpt.update_by_path.call_count)

    def test_add_port_mapping_single_vios(self):
        """Validates that the port mappings are added on single VIOS.

        Specifically ensures that the port mappings are not added to the second
        VIOS.  No unnecessary VIOS updates...
        """
        # Determine the vios original values
        vios_wraps = self.entries
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)

        def mock_update(*kargs, **kwargs):
            vios_w = pvm_vios.VIOS.wrap(kargs[0].entry)
            if vios1_name == vios_w.name:
                self.assertEqual(vios1_orig_map_count + 10,
                                 len(vios_w.vfc_mappings))
                self.ensure_has_wwpns(
                    vios_w, ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                             'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'])
            else:
                self.fail("Unknown VIOS!")

            return vios_w.entry
        self.adpt.update_by_path.side_effect = mock_update

        # Subset the WWPNs on that VIOS
        fabric_A_wwpns = ['10000090FA5371F2']
        fabric_B_wwpns = ['10000090FA5371F1']

        # Fake Virtual WWPNs.  Include some existing WWPNs to make sure they
        # do NOT get added.  mock_update will ensure they don't get added.
        v_fabric_A_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                            'c05076079cff0e56', 'c05076079cff0e57']

        # Throw the existing into the front, to catch any edge cases.
        v_fabric_B_wwpns = ['c05076079cff08da', 'c05076079cff08db',
                            'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']

        # Get the mappings
        fabric_A_maps = vfc_mapper.derive_npiv_map(vios_wraps, fabric_A_wwpns,
                                                   v_fabric_A_wwpns)
        vios_wraps.reverse()
        fabric_B_maps = vfc_mapper.derive_npiv_map(vios_wraps, fabric_B_wwpns,
                                                   v_fabric_B_wwpns)
        full_map = fabric_A_maps + fabric_B_maps

        # Now call the add action
        vfc_mapper.add_npiv_port_mappings(self.adpt, 'host_uuid', FAKE_UUID,
                                          full_map)

        # The update should have been called once.
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_find_pfc_wwpn_by_name(self):
        vio_w = self.entries[0]
        self.assertEqual('10000090FA5371F1',
                         vfc_mapper._find_pfc_wwpn_by_name(vio_w, 'fcs0'))
        self.assertIsNone(vfc_mapper._find_pfc_wwpn_by_name(vio_w, 'fcsX'))

    def test_add_port_bad_pfc(self):
        """Validates that an error will be thrown with a bad pfc port."""
        # Build the mappings - the provided WWPN is bad
        vfc_map = ('10000090FA5371F9', '0 1')

        # Now call the add action.  This should log a warning.
        with self.assertLogs(vfc_mapper.__name__, level='WARNING'):
            self.assertRaises(e.UnableToDerivePhysicalPortForNPIV,
                              vfc_mapper.add_map,
                              self.entries[0], 'host_uuid', FAKE_UUID, vfc_map)

    def test_add_port_mapping_generated_wwpns(self):
        """Validates that the port mappings with generated wwpns works."""
        # Determine the vios original values
        vios_wraps = self.entries
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)

        def mock_update(*kargs, **kwargs):
            vios_w = pvm_vios.VIOS.wrap(kargs[0].entry)
            if vios1_name == vios_w.name:
                self.assertEqual(vios1_orig_map_count + 8,
                                 len(vios_w.vfc_mappings))
            else:
                self.fail("Unknown VIOS!")

            return vios_w.entry
        self.adpt.update_by_path.side_effect = mock_update

        # Subset the WWPNs on that VIOS
        fabric_A_wwpns = ['10000090FA5371F2']
        fabric_B_wwpns = ['10000090FA5371F1']

        # Get the mappings
        fabric_A_maps = vfc_mapper.derive_base_npiv_map(
            vios_wraps, fabric_A_wwpns, 4)
        vios_wraps.reverse()
        fabric_B_maps = vfc_mapper.derive_base_npiv_map(
            vios_wraps, fabric_B_wwpns, 4)
        full_map = fabric_A_maps + fabric_B_maps

        # Now call the add action
        vfc_mapper.add_npiv_port_mappings(self.adpt, 'host_uuid', FAKE_UUID,
                                          full_map)

        # The update should have been called once.
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_remove_port_mapping_multi_vios(self):
        """Validates that the port mappings are removed cross VIOSes."""
        # Determine the vios original values
        vios_wraps = self.entries
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)
        vios2_name = vios_wraps[1].name
        vios2_orig_map_count = len(vios_wraps[1].vfc_mappings)

        def mock_update(*kargs, **kwargs):
            vios_w = pvm_vios.VIOS.wrap(kargs[0].entry)
            if vios1_name == vios_w.name:
                self.assertEqual(vios1_orig_map_count - 1,
                                 len(vios_w.vfc_mappings))
            elif vios2_name == vios_w.name:
                self.assertEqual(vios2_orig_map_count - 1,
                                 len(vios_w.vfc_mappings))
            else:
                self.fail("Unknown VIOS!")

            self.ensure_does_not_have_wwpns(
                vios_w, ['C05076079CFF0E56', 'C05076079CFF0E57',
                         'C05076079CFF0E58', 'C05076079CFF0E59'])

            return vios_w.entry
        self.adpt.update_by_path.side_effect = mock_update

        p_map_vio1 = ('10000090FA5371F2', 'C05076079CFF0E56 C05076079CFF0E57')
        p_map_vio2 = ('10000090FA537209', 'C05076079CFF0E58 C05076079CFF0E59')
        maps = [p_map_vio1, p_map_vio2]

        # Now call the remove action
        vfc_mapper.remove_npiv_port_mappings(
            self.adpt, 'host_uuid', '3ADDED46-B3A9-4E12-B6EC-8223421AF49B',
            maps)

        # The update should have been called twice.  Once for each VIOS.
        self.assertEqual(2, self.adpt.update_by_path.call_count)

    def test_remove_port_mapping_single_vios(self):
        """Validates that the port mappings are removed on single VIOS.

        Note: This indirectly calls the find_maps method via the
        remove_npiv_port_mappings method.
        """
        # Determine the vios original values
        vios_wraps = self.entries
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)

        def mock_update(*kargs, **kwargs):
            vios_w = pvm_vios.VIOS.wrap(kargs[0].entry)
            if vios1_name == vios_w.name:
                self.assertEqual(vios1_orig_map_count - 1,
                                 len(vios_w.vfc_mappings))
            else:
                self.fail("Unknown VIOS!")

            self.ensure_does_not_have_wwpns(vios_w, ['C05076079CFF0E56',
                                                     'C05076079CFF0E57'])

            return vios_w.entry
        self.adpt.update_by_path.side_effect = mock_update

        maps = [('10000090FA5371F2', 'C05076079CFF0E56 C05076079CFF0E57')]

        # Now call the remove action
        vfc_mapper.remove_npiv_port_mappings(
            self.adpt, 'host_uuid', '3ADDED46-B3A9-4E12-B6EC-8223421AF49B',
            maps)

        # The update should have been called once.
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def test_remove_port_mapping_single_vios_order_agnostic(self):
        """Validates that the port mappings are removed with reverse order.

        Note: This indirectly calls the find_maps method via the
        remove_npiv_port_mappings method.
        """
        # Determine the vios original values
        vios_wraps = self.entries
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)

        def mock_update(*kargs, **kwargs):
            vios_w = pvm_vios.VIOS.wrap(kargs[0].entry)
            if vios1_name == vios_w.name:
                self.assertEqual(vios1_orig_map_count - 1,
                                 len(vios_w.vfc_mappings))
            else:
                self.fail("Unknown VIOS!")

            self.ensure_does_not_have_wwpns(vios_w, ['C05076079CFF0E56',
                                                     'C05076079CFF0E57'])

            return vios_w.entry
        self.adpt.update_by_path.side_effect = mock_update

        maps = [('10000090FA5371F2', 'C05076079CFF0E57 C05076079CFF0E56')]

        # Now call the remove action
        vfc_mapper.remove_npiv_port_mappings(
            self.adpt, 'host_uuid', '3ADDED46-B3A9-4E12-B6EC-8223421AF49B',
            maps)

        # The update should have been called once.
        self.assertEqual(1, self.adpt.update_by_path.call_count)

    def ensure_does_not_have_wwpns(self, vios_w, wwpns):
        for vfc_map in vios_w.vfc_mappings:
            if vfc_map.client_adapter is None:
                continue
            for c_wwpn in vfc_map.client_adapter.wwpns:
                if c_wwpn in wwpns:
                    self.fail("WWPN %s in client adapter" % vfc_mapper)

    def ensure_has_wwpns(self, vios_w, wwpns):
        for my_wwpn in wwpns:
            has_wwpn = False
            for vfc_map in vios_w.vfc_mappings:
                if vfc_map.client_adapter is None:
                    continue
                for c_wwpn in vfc_map.client_adapter.wwpns:
                    if c_wwpn == my_wwpn:
                        has_wwpn = True
                        break
            if not has_wwpn:
                self.fail("Unable to find WWPN %s" % my_wwpn)

    def test_find_maps(self):
        vwrap = self.entries[0]
        matches = vfc_mapper.find_maps(vwrap.vfc_mappings, 10)
        # Make sure we got the right ones
        self.assertEqual(
            ['U7895.43X.21EF9FB-V63-C3', 'U7895.43X.21EF9FB-V66-C4',
             'U7895.43X.21EF9FB-V62-C4', 'U7895.43X.21EF9FB-V10-C4'],
            [match.client_adapter.loc_code for match in matches])
        # Bogus LPAR ID
        self.assertEqual([], vfc_mapper.find_maps(vwrap.vfc_mappings, 1000))

        # Now try with UUID
        matches = vfc_mapper.find_maps(vwrap.vfc_mappings,
                                       '3ADDED46-B3A9-4E12-B6EC-8223421AF49B')
        self.assertEqual(
            ['U7895.43X.21EF9FB-V63-C3', 'U7895.43X.21EF9FB-V66-C4',
             'U7895.43X.21EF9FB-V62-C4', 'U7895.43X.21EF9FB-V10-C4'],
            [match.client_adapter.loc_code for match in matches])
        # Bogus LPAR UUID
        self.assertEqual([], vfc_mapper.find_maps(
            vwrap.vfc_mappings, '4BEEFD00-B3A9-4E12-B6EC-8223421AF49B'))

    def test_remove_maps(self):
        v_wrap = self.entries[0]
        len_before = len(v_wrap.vfc_mappings)
        resp_list = vfc_mapper.remove_maps(v_wrap, 10)
        expected_removals = {
            'U7895.43X.21EF9FB-V63-C3', 'U7895.43X.21EF9FB-V66-C4',
            'U7895.43X.21EF9FB-V62-C4', 'U7895.43X.21EF9FB-V10-C4'}
        self.assertEqual(
            set([el.client_adapter.loc_code for el in resp_list]),
            expected_removals)
        self.assertEqual(len_before - 4, len(v_wrap.vfc_mappings))

        # Make sure the remaining adapters do not have the remove codes.
        for remaining_map in v_wrap.vfc_mappings:
            if remaining_map.client_adapter is not None:
                self.assertNotIn(remaining_map.client_adapter.loc_code,
                                 expected_removals)

    def test_remove_maps_client_adpt(self):
        """Tests the remove_maps method, with the client_adpt input."""
        v_wrap = self.entries[0]
        len_before = len(v_wrap.vfc_mappings)

        c_adpt = vfc_mapper.find_maps(
            v_wrap.vfc_mappings, 10)[0].client_adapter

        resp_list = vfc_mapper.remove_maps(v_wrap, 10, client_adpt=c_adpt)
        expected_removals = {'U7895.43X.21EF9FB-V63-C3'}
        self.assertEqual(
            set([el.client_adapter.loc_code for el in resp_list]),
            expected_removals)
        self.assertEqual(len_before - 1, len(v_wrap.vfc_mappings))

        # Make sure the remaining adapters do not have the remove codes.
        for remaining_map in v_wrap.vfc_mappings:
            if remaining_map.client_adapter is not None:
                self.assertNotIn(remaining_map.client_adapter.loc_code,
                                 expected_removals)

    def test_has_client_wwpns(self):
        v_wrap_1 = self.entries[0]
        v_wrap_2 = self.entries[1]
        vio_w, vfc_map = vfc_mapper.has_client_wwpns(
            self.entries, ['c05076079cff0e56', 'c05076079cff0e57'])
        self.assertEqual(v_wrap_1, vio_w)
        self.assertEqual('10000090FA5371F2', vfc_map.backing_port.wwpn)

        # Second vios.  Reversed WWPNs.  Mixed Case.
        vio_w, vfc_map = vfc_mapper.has_client_wwpns(
            self.entries, ['c05076079cff0e83', 'c05076079cff0E82'])
        self.assertEqual(v_wrap_2, vio_w)
        self.assertEqual('10000090FA537209', vfc_map.backing_port.wwpn)

        # Not found.
        vio_w, vfc_map = vfc_mapper.has_client_wwpns(
            self.entries, ['AAA', 'bbb'])
        self.assertIsNone(vio_w)
        self.assertIsNone(vfc_map)


class TestAddRemoveMap(twrap.TestWrapper):
    file = VIOS_FEED
    wrapper_class_to_test = pvm_vios.VIOS
    mock_adapter_fx_args = {}

    def setUp(self):
        super(TestAddRemoveMap, self).setUp()
        href_p = mock.patch('pypowervm.wrappers.virtual_io_server.VFCMapping.'
                            'crt_related_href')
        href = href_p.start()
        self.addCleanup(href_p.stop)
        href.return_value = (
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
            'e7344c5b-79b5-3e73-8f64-94821424bc25/LogicalPartition/'
            '3ADDED46-B3A9-4E12-B6EC-8223421AF49B')
        self.adpt.read.return_value = self.resp

        self.lpar_uuid = '3ADDED46-B3A9-4E12-B6EC-8223421AF49B'

    def test_add_remove_map_any_wwpn(self):
        """Tests a loop of add map/remove map when using _ANY_WWPN."""
        v_wrap = self.entries[0]
        len_before = len(v_wrap.vfc_mappings)

        # A fake mapping to the first IO Server
        p_map_vio1 = ('10000090FA5371F2', vfc_mapper._FUSED_ANY_WWPN)
        vfc_mapper.add_map(v_wrap, 'host_uuid', self.lpar_uuid, p_map_vio1)
        self.assertEqual(len_before + 1, len(v_wrap.vfc_mappings))

        # See if we can find that mapping.
        maps = vfc_mapper.find_maps(v_wrap.vfc_mappings, self.lpar_uuid,
                                    port_map=p_map_vio1)
        self.assertEqual(1, len(maps))

        # Even though we were searching for a 'FUSED' wwpn, the mapping itself
        # will have nothing on it, to indicate that the API should generate
        # the WWPNs.  Therefore, we validate that we found the mapping without
        # any WWPNs on it.
        self.assertEqual([], maps[0].client_adapter.wwpns)

        # Now try to remove it...
        vfc_mapper.remove_maps(v_wrap, self.lpar_uuid, port_map=p_map_vio1)
        self.assertEqual(len_before, len(v_wrap.vfc_mappings))

    def test_add_map(self):
        """Validates the add_map method."""
        # Determine the vios original values
        vios_wrap = self.entries[0]
        vios1_orig_map_count = len(vios_wrap.vfc_mappings)

        # Subset the WWPNs on that VIOS
        fabric_wwpns = ['10000090FA5371F2']

        # Fake Virtual WWPNs
        v_fabric_wwpns = ['0', '1']

        # Get the mappings
        fabric_map = vfc_mapper.derive_npiv_map([vios_wrap], fabric_wwpns,
                                                v_fabric_wwpns)[0]

        # Make sure the map was not there initially.
        maps = vfc_mapper.find_maps(vios_wrap.vfc_mappings, self.lpar_uuid,
                                    port_map=fabric_map)
        self.assertEqual(0, len(maps))

        # Now call the add action
        resp = vfc_mapper.add_map(vios_wrap, 'host_uuid', self.lpar_uuid,
                                  fabric_map)
        self.assertIsNotNone(resp)
        self.assertIsInstance(resp, pvm_vios.VFCMapping)

        # Verify the update is now found.
        maps = vfc_mapper.find_maps(vios_wrap.vfc_mappings, self.lpar_uuid,
                                    port_map=fabric_map)
        self.assertEqual(1, len(maps))
        self.assertEqual(vios1_orig_map_count + 1, len(vios_wrap.vfc_mappings))

        # Try to add it again...it shouldn't re-add it because its already
        # there.
        resp = vfc_mapper.add_map(vios_wrap, 'host_uuid', self.lpar_uuid,
                                  fabric_map)
        self.assertIsNone(resp)
        self.assertEqual(vios1_orig_map_count + 1, len(vios_wrap.vfc_mappings))

        # We should only find one here...the original add.  Not two even though
        # we've called add twice.
        maps = vfc_mapper.find_maps(vios_wrap.vfc_mappings, self.lpar_uuid,
                                    port_map=fabric_map)
        self.assertEqual(1, len(maps))
