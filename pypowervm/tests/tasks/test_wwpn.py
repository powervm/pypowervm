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

from pypowervm.tasks import wwpn
import pypowervm.tests.tasks.util as tju
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIOS_FILE = 'fake_vios.txt'


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
        list2 = set(['aabbccddeeff', '1234567890'])
        self.assertEqual(list1, wwpn.intersect_wwpns(list1, list2))

        # Full match
        list1 = set(['aabbccddeeff', '1234567890'])
        list2 = ['AA:BB:CC:DD:EE:FF', '12:34:56:78:90']
        self.assertEqual(list1, set(wwpn.intersect_wwpns(list1, list2)))

        # Second set as the limiter
        list1 = ['AA:BB:CC:DD:EE:FF', '12:34:56:78:90']
        list2 = set(['aabbccddeeff'])
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
        self.assertEqual(set(['10000090FA45473B', '10000090FA451758']),
                         unique_keys)

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
