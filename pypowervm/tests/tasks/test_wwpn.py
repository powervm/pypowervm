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

import mock

import unittest

from pypowervm import exceptions as e
from pypowervm.tasks import wwpn
import pypowervm.tests.tasks.util as tju
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIOS_FILE = 'fake_vios.txt'
VIOS_FEED = 'fake_vios_feed.txt'


class TestWWPN(unittest.TestCase):

    def test_build_wwpn_pair(self):
        # By its nature, this is a random generation algorithm.  Run it
        # several times...just to increase probability of issues.
        i = 0
        while i < 100:
            wwpn_pair = wwpn.build_wwpn_pair(None, None)
            self.assertIsNotNone(wwpn_pair)
            self.assertEqual(2, len(wwpn_pair))
            for elem in wwpn_pair:
                self.assertEqual(16, len(elem))
                int(elem, 16)  # Would throw ValueError if not hex.
            i += 1

    def test_find_vio_for_wwpn(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_feed_w = [vios_w]

        # Basic test
        vio_resp, p_resp = wwpn.find_vio_for_wwpn(vios_feed_w,
                                                  '10000090FA45473B')
        self.assertEqual(vios_w, vio_resp)
        self.assertIsNotNone(p_resp)

        # Validates the sanitized input
        vio_resp, p_resp = wwpn.find_vio_for_wwpn(vios_feed_w,
                                                  '10:00:00:90:fa:45:47:3b')
        self.assertEqual(vios_w, vio_resp)
        self.assertIsNotNone(p_resp)

        # Make sure a bad WWPN returns no result
        vio_resp, p_resp = wwpn.find_vio_for_wwpn(vios_feed_w,
                                                  '10:00:00:90:fa:45:47:3f')
        self.assertIsNone(vio_resp)
        self.assertIsNone(p_resp)

    def test_intersect_wwpns(self):
        list1 = ['AA:BB:CC:DD:EE:FF']
        list2 = {'aabbccddeeff', '1234567890'}
        self.assertEqual(list1, wwpn.intersect_wwpns(list1, list2))

        # Full match
        list1 = {'aabbccddeeff', '1234567890'}
        list2 = ['AA:BB:CC:DD:EE:FF', '12:34:56:78:90']
        self.assertEqual(list1, set(wwpn.intersect_wwpns(list1, list2)))

        # Second set as the limiter
        list1 = ['AA:BB:CC:DD:EE:FF', '12:34:56:78:90']
        list2 = {'aabbccddeeff'}
        self.assertEqual(['AA:BB:CC:DD:EE:FF'],
                         wwpn.intersect_wwpns(list1, list2))

    def test_derive_npiv_map(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)
        vios_wraps = [vios_w]

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA45473B', '10:00:00:90:fa:45:17:58']

        # Virtual WWPNs can be faked, and simplified.
        v_port_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

        # Run the derivation now
        resp = wwpn.derive_npiv_map(vios_wraps, p_wwpns, v_port_wwpns)
        self.assertIsNotNone(resp)
        self.assertEqual(5, len(resp))

        # Make sure we only get two unique keys back.
        unique_keys = set([i[0] for i in resp])
        self.assertEqual({'10000090FA45473B', '10000090FA451758'}, unique_keys)

    def test_derive_npiv_map_multi_vio(self):
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FEED))

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA5371F2', '10000090FA53720A']

        # Virtual WWPNs can be faked, and simplified.
        v_port_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

        # Run the derivation now
        resp = wwpn.derive_npiv_map(vios_wraps, p_wwpns, v_port_wwpns)
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
        self.assertRaises(e.UnableToFindFCPortMap, wwpn.derive_npiv_map,
                          vios_wraps, p_wwpns, v_port_wwpns)

    def test_find_map_port(self):
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FILE).entry)

        # Happy path, should find the first port on the VIOS
        p1 = wwpn._find_map_port(vios_w.pfc_ports, [])
        self.assertIsNotNone(p1)

        # Lets add a mapping where P1 is used.  Should not get that result
        # back.
        p2 = wwpn._find_map_port(vios_w.pfc_ports, [(p1.wwpn, '')])
        self.assertIsNotNone(p2)
        self.assertNotEqual(p1, p2)

        # Now add a third and fourth port.  Same assertions.
        p3 = wwpn._find_map_port(vios_w.pfc_ports, [(p1.wwpn, ''),
                                                    (p2.wwpn, '')])
        self.assertIsNotNone(p3)
        self.assertNotIn(p3, [p1, p2])

        p4 = wwpn._find_map_port(vios_w.pfc_ports, [(p1.wwpn, ''),
                                                    (p2.wwpn, ''),
                                                    (p3.wwpn, '')])
        self.assertIsNotNone(p4)
        self.assertNotIn(p4, [p1, p2, p3])

        # Artificially inflate the use of other ports.
        port_use = [(p1.wwpn, ''), (p2.wwpn, ''), (p3.wwpn, ''), (p4.wwpn, ''),
                    (p1.wwpn, ''), (p2.wwpn, ''), (p4.wwpn, '')]
        p_temp = wwpn._find_map_port(vios_w.pfc_ports, port_use)
        self.assertIsNotNone(p_temp)
        self.assertNotIn(p_temp, [p1, p2, p4])

    def test_fuse_vfc_ports(self):
        self.assertEqual(['A B'], wwpn._fuse_vfc_ports(['a', 'b']))
        self.assertEqual(['AA BB'], wwpn._fuse_vfc_ports(['a:a', 'b:b']))
        self.assertEqual(['A B', 'C D'],
                         wwpn._fuse_vfc_ports(['a', 'b', 'c', 'd']))

    @mock.patch('pypowervm.wrappers.virtual_io_server.VFCMapping.'
                '_client_lpar_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_add_port_mapping_multi_vios(self, mock_adapter,
                                         mock_client_lpar_href):
        """Validates that the port mappings are added cross VIOSes."""
        # Determine the vios original values
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FEED, mock_adapter))
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)
        vios2_name = vios_wraps[1].name
        vios2_orig_map_count = len(vios_wraps[1].vfc_mappings)

        # Mock data/functions
        mock_adapter.read.return_value = tju.load_file(VIOS_FEED, mock_adapter)
        mock_client_lpar_href.return_value = 'fake_href'

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
        mock_adapter.update_by_path.side_effect = mock_update

        # Subset the WWPNs on that VIOS
        fabric_A_wwpns = ['10000090FA5371f2', '10000090FA53720A']
        fabric_B_wwpns = ['10000090FA5371F1', '10000090FA537209']

        # Fake Virtual WWPNs
        v_fabric_A_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        v_fabric_B_wwpns = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']

        # Get the mappings
        fabric_A_maps = wwpn.derive_npiv_map(vios_wraps, fabric_A_wwpns,
                                             v_fabric_A_wwpns)
        vios_wraps.reverse()
        fabric_B_maps = wwpn.derive_npiv_map(vios_wraps, fabric_B_wwpns,
                                             v_fabric_B_wwpns)
        full_map = fabric_A_maps + fabric_B_maps

        # Now call the add action
        wwpn.add_npiv_port_mappings(mock_adapter, 'host_uuid', 'vm_uuid',
                                    full_map)

        # The update should have been called twice.  Once for each VIOS.
        self.assertEqual(2, mock_adapter.update_by_path.call_count)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VFCMapping.'
                '_client_lpar_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_add_port_mapping_single_vios(self, mock_adapter,
                                          mock_client_lpar_href):
        """Validates that the port mappings are added on single VIOS.

        Specifically ensures that the port mappings are not added to the second
        VIOS.  No unnecessary VIOS updates...
        """
        # Determine the vios original values
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FEED, mock_adapter))
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)

        # Mock data/functions
        mock_adapter.read.return_value = tju.load_file(VIOS_FEED, mock_adapter)
        mock_client_lpar_href.return_value = 'fake_href'

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
        mock_adapter.update_by_path.side_effect = mock_update

        # Subset the WWPNs on that VIOS
        fabric_A_wwpns = ['10000090FA5371F2']
        fabric_B_wwpns = ['10000090FA5371F1']

        # Fake Virtual WWPNs
        v_fabric_A_wwpns = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        v_fabric_B_wwpns = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']

        # Get the mappings
        fabric_A_maps = wwpn.derive_npiv_map(vios_wraps, fabric_A_wwpns,
                                             v_fabric_A_wwpns)
        vios_wraps.reverse()
        fabric_B_maps = wwpn.derive_npiv_map(vios_wraps, fabric_B_wwpns,
                                             v_fabric_B_wwpns)
        full_map = fabric_A_maps + fabric_B_maps

        # Now call the add action
        wwpn.add_npiv_port_mappings(mock_adapter, 'host_uuid', 'vm_uuid',
                                    full_map)

        # The update should have been called once.
        self.assertEqual(1, mock_adapter.update_by_path.call_count)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VFCMapping.'
                '_client_lpar_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_port_mapping_multi_vios(self, mock_adapter,
                                            mock_client_lpar_href):
        """Validates that the port mappings are removed cross VIOSes."""
        # Determine the vios original values
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FEED, mock_adapter))
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)
        vios2_name = vios_wraps[1].name
        vios2_orig_map_count = len(vios_wraps[1].vfc_mappings)

        # Mock data/functions
        mock_adapter.read.return_value = tju.load_file(VIOS_FEED, mock_adapter)
        mock_client_lpar_href.return_value = 'fake_href'

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
        mock_adapter.update_by_path.side_effect = mock_update

        p_map_vio1 = ('10000090FA5371F2', 'C05076079CFF0E56 C05076079CFF0E57')
        p_map_vio2 = ('10000090FA537209', 'C05076079CFF0E58 C05076079CFF0E59')
        maps = [p_map_vio1, p_map_vio2]

        # Now call the add action
        wwpn.remove_npiv_port_mappings(mock_adapter, 'host_uuid', maps)

        # The update should have been called twice.  Once for each VIOS.
        self.assertEqual(2, mock_adapter.update_by_path.call_count)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VFCMapping.'
                '_client_lpar_href')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_port_mapping_single_vios(self, mock_adapter,
                                             mock_client_lpar_href):
        """Validates that the port mappings are removed on single VIOS."""
        # Determine the vios original values
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FEED, mock_adapter))
        vios1_name = vios_wraps[0].name
        vios1_orig_map_count = len(vios_wraps[0].vfc_mappings)

        # Mock data/functions
        mock_adapter.read.return_value = tju.load_file(VIOS_FEED, mock_adapter)
        mock_client_lpar_href.return_value = 'fake_href'

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
        mock_adapter.update_by_path.side_effect = mock_update

        maps = [('10000090FA5371F2', 'C05076079CFF0E56 C05076079CFF0E57')]

        # Now call the add action
        wwpn.remove_npiv_port_mappings(mock_adapter, 'host_uuid', maps)

        # The update should have been called once.
        self.assertEqual(1, mock_adapter.update_by_path.call_count)

    def ensure_does_not_have_wwpns(self, vios_w, wwpns):
        for vfc_map in vios_w.vfc_mappings:
            if vfc_map.client_adapter is None:
                continue
            for c_wwpn in vfc_map.client_adapter.wwpns:
                if c_wwpn in wwpns:
                    self.fail("WWPN %s in client adapter" % wwpn)

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
