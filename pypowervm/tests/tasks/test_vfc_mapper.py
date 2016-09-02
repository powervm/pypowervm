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

from pypowervm import const as c
from pypowervm import exceptions as e
from pypowervm.tasks import vfc_mapper
from pypowervm.tests.tasks import util as tju
from pypowervm.tests.test_utils import test_wrapper_abc as twrap
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIOS_FILE = 'fake_vios.txt'
VIOS_FEED = 'fake_vios_feed.txt'

FAKE_UUID = '42DF39A2-3A4A-4748-998F-25B15352E8A7'


class TestVFCMapper(unittest.TestCase):

    @mock.patch('pypowervm.wrappers.job.Job')
    def test_build_wwpn_pair(self, mock_job):
        mock_adpt = mock.MagicMock()
        mock_adpt.read.return_value = mock.Mock()

        # Mock out the job response
        job_w = mock.MagicMock()
        mock_job.wrap.return_value = job_w
        job_w.get_job_results_as_dict.return_value = {'wwpnList':
                                                      'a,b,c,d,e,f,g,h'}

        # Invoke and validate
        resp = vfc_mapper.build_wwpn_pair(mock_adpt, 'host_uuid', pair_count=4)
        self.assertEqual(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], resp)

        # Make sure that the job was built properly
        mock_adpt.read.assert_called_once_with(
            'ManagedSystem', root_id='host_uuid', suffix_type=c.SUFFIX_TYPE_DO,
            suffix_parm=vfc_mapper._GET_NEXT_WWPNS)
        job_w.create_job_parameter.assert_called_once_with(
            'numberPairsRequested', '4')

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

    def test_derive_npiv_map_existing_preserve(self):
        # Use sample vios data with mappings.
        vios_file = 'fake_vios_mappings.txt'
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(vios_file).entry)
        vios_wraps = [vios_w]

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA1B6898', '10000090FA1B6899']
        v_port_wwpns = ['c05076065a7c02e4', 'c05076065a7c02e5']
        candidates = vfc_mapper._find_ports_on_vio(vios_w, p_wwpns)
        for p_port in candidates:
            if p_port.wwpn == p_wwpns[1]:
                # Artificially inflate the free ports so that it would get
                # chosen for a newly created mapping, but first in list
                # would show up for a preserved mapping.
                p_port.set_parm_value('AvailablePorts', '64')

        # Run the derivation now
        resp = vfc_mapper.derive_npiv_map(vios_wraps, p_wwpns, v_port_wwpns,
                                          preserve=True)
        self.assertIsNotNone(resp)
        self.assertEqual(1, len(resp))

        # Make sure we only got the one phys port key back that has the
        # existing mapping.
        unique_keys = set([i[0] for i in resp])
        self.assertEqual({'10000090FA1B6898'}, unique_keys)

    def test_derive_npiv_map_existing_no_preserve(self):
        # Use sample vios data with mappings.
        vios_file = 'fake_vios_mappings.txt'
        vios_w = pvm_vios.VIOS.wrap(tju.load_file(vios_file).entry)
        vios_wraps = [vios_w]

        # Subset the WWPNs on that VIOS
        p_wwpns = ['10000090FA1B6898', '10000090FA1B6899']
        v_port_wwpns = ['c05076065a7c02e4', 'c05076065a7c02e5']
        candidates = vfc_mapper._find_ports_on_vio(vios_w, p_wwpns)
        for p_port in candidates:
            if p_port.wwpn == p_wwpns[1]:
                # Artificially inflate the free ports so that it would get
                # chosen for a newly created mapping.
                p_port.set_parm_value('AvailablePorts', '64')

        # Run the derivation now
        resp = vfc_mapper.derive_npiv_map(vios_wraps, p_wwpns, v_port_wwpns,
                                          preserve=False)
        self.assertIsNotNone(resp)
        self.assertEqual(1, len(resp))

        # Make sure we only got one phys port key back and it should *not*
        # match the existing mapping of 'preserve' testcase.
        unique_keys = set([i[0] for i in resp])
        self.assertEqual({'10000090FA1B6899'}, unique_keys)

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

    def test_build_migration_mappings(self):
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(VIOS_FEED))
        fabric_data = {'A': {'slots': [3, 4],
                             'p_port_wwpns': ["10000090FA5371F1",
                                              "10000090FA53720A"]},
                       'B': {'slots': [5, 6],
                             'p_port_wwpns': ["10000090FA5371F2",
                                              "10000090FA537209"]}}
        slot_peers = [[3, 5], [4, 6]]
        resp = vfc_mapper.build_migration_mappings(vios_wraps, fabric_data,
                                                   slot_peers)
        self.assertEqual(4, len(resp))
        self.assertEqual(set(resp), {'4/nimbus-ch03-p2-vios1/1//fcs1',
                                     '6/nimbus-ch03-p2-vios1/1//fcs0',
                                     '3/nimbus-ch03-p2-vios2/2//fcs0',
                                     '5/nimbus-ch03-p2-vios2/2//fcs1'})

        fabric_data = {'A': {'slots': [3],
                             'p_port_wwpns': ["10000090FA5371F1"]},
                       'B': {'slots': [5, 6],
                             'p_port_wwpns': ["10000090FA5371F2",
                                              "10000090FA537209"]}}
        slot_peers = [[3, 5], [6]]
        resp = vfc_mapper.build_migration_mappings(vios_wraps, fabric_data,
                                                   slot_peers)
        self.assertEqual(3, len(resp))
        self.assertEqual(set(resp), {'5/nimbus-ch03-p2-vios2/2//fcs1',
                                     '3/nimbus-ch03-p2-vios2/2//fcs0',
                                     '6/nimbus-ch03-p2-vios1/1//fcs0'})
        # Use invalid ports
        fabric_data = {'A': {'slots': [3],
                             'p_port_wwpns': ["10000090FA5371F1"]},
                       'B': {'slots': [5],
                             'p_port_wwpns': ["10000090FA537209"]}}
        slot_peers = [[3, 5]]
        self.assertRaises(e.UnableToFindFCPortMap,
                          vfc_mapper.build_migration_mappings,
                          vios_wraps, fabric_data, slot_peers)


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

    def test_find_pfc_wwpn_by_name(self):
        vio_w = self.entries[0]
        self.assertEqual('10000090FA5371F1',
                         vfc_mapper._find_pfc_wwpn_by_name(vio_w, 'fcs0'))
        self.assertIsNone(vfc_mapper._find_pfc_wwpn_by_name(vio_w, 'fcsX'))

    @mock.patch('lxml.etree.tostring')
    def test_add_port_bad_pfc(self, mock_tostring):
        """Validates that an error will be thrown with a bad pfc port."""
        # Build the mappings - the provided WWPN is bad
        vfc_map = ('10000090FA5371F9', '0 1')

        # Now call the add action.  This should log a warning.
        with self.assertLogs(vfc_mapper.__name__, level='WARNING'):
            self.assertRaises(e.UnableToDerivePhysicalPortForNPIV,
                              vfc_mapper.add_map,
                              self.entries[0], 'host_uuid', FAKE_UUID, vfc_map)
        mock_tostring.assert_called_once_with(
            self.entries[0].entry.element.element, pretty_print=True)

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
        # there.  Flip WWPNs to verify set query.
        fabric_map = ('10000090FA5371F2', '1 0')
        resp = vfc_mapper.add_map(vios_wrap, 'host_uuid', self.lpar_uuid,
                                  fabric_map)
        self.assertIsNone(resp)
        self.assertEqual(vios1_orig_map_count + 1, len(vios_wrap.vfc_mappings))

        # We should only find one here...the original add.  Not two even though
        # we've called add twice.
        maps = vfc_mapper.find_maps(vios_wrap.vfc_mappings, self.lpar_uuid,
                                    port_map=fabric_map)
        self.assertEqual(1, len(maps))

        # This time, remove the backing port of the existing mapping and try
        # the add again. It should return an updated mapping that contains the
        # backing port. This simulates a VM migrating with a vfc mapping, but
        # no volume had been previously detached.
        maps[0].element.remove(maps[0].backing_port.element)
        resp = vfc_mapper.add_map(vios_wrap, 'host_uuid', self.lpar_uuid,
                                  fabric_map)
        self.assertIsNotNone(resp)
        self.assertIsInstance(resp, pvm_vios.VFCMapping)
        self.assertIsNotNone(resp.backing_port)
        self.assertIn('Port', resp.child_order)

        # Pass in slot number to be set on the VFC adapter
        fabric_map = ('10000090FA5371F1', '2 3')
        resp = vfc_mapper.add_map(vios_wrap, 'host_uuid', self.lpar_uuid,
                                  fabric_map, lpar_slot_num=3)
        self.assertIsNotNone(resp)
        self.assertEqual(vios1_orig_map_count + 2, len(vios_wrap.vfc_mappings))
        # Verify the update is now found.
        maps = vfc_mapper.find_maps(vios_wrap.vfc_mappings, self.lpar_uuid,
                                    port_map=fabric_map)
        self.assertEqual(1, len(maps))
        self.assertEqual(3, maps[0].client_adapter.lpar_slot_num)
