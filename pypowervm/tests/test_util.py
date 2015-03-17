# Copyright 2014, 2015 IBM Corp.
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

from pypowervm import util

dummyuuid = "abcdef01-2345-2345-2345-67890abcdef0"


class TestUtil(unittest.TestCase):
    """Unit tests for pypowervm.util."""

    def test_get_max_age(self):
        """Clear-box unit test coverage for pypowervm.util.get_max_age().

        Explicitly cover all conditions and defaults.
        """

        # >>> Cover first branch: max age for Cluster and SharedStoragePool,
        #     for which there are no Events as yet
        i = util.get_max_age("/rest/api/uom/Cluster", False, "V1_0")
        self.assertEqual(i, 15, "Bad max age for Cluster")

        i = util.get_max_age(
            "/rest/api/uom/Cluster/" + dummyuuid, False, "V1_0")
        self.assertEqual(i, 15, "Bad max age for Cluster with UUID")

        i = util.get_max_age("/rest/api/uom/SharedStoragePool", False, "V1_0")
        self.assertEqual(i, 15, "Bad max age for SharedStoragePool")
        # <<<

        # >>> Cover the second branch: when [not using events] or [schema
        #     version V1_0]
        # LogicalPartition feed, trigger on [not using events]
        i = util.get_max_age("/rest/api/uom/LogicalPartition", False, "V2_0")
        self.assertEqual(
            i, 30, "Bad max age for LogicalPartition (no events, V2_0)")
        # LogicalPartitionFeed, trigger on [schema version V1_0]
        i = util.get_max_age("/rest/api/uom/LogicalPartition", True, "V1_0")
        self.assertEqual(
            i, 30, "Bad max age for LogicalPartition (with events, V1_0)")
        # VIOS feed
        i = util.get_max_age("/rest/api/uom/VirtualIOServer", False, "V2_0")
        self.assertEqual(
            i, 90, "Bad max age for VirtualIOServer (no events, V2_0)")
        # ManagedSystem entry
        i = util.get_max_age(
            "/rest/api/uom/ManagedSystem/" + dummyuuid, False, "V2_0")
        self.assertEqual(
            i, 30, "Bad max age for ManagedSystem/{uuid} (no events, V2_0)")
        # LogicalPartition, but not feed, hits the default
        i = util.get_max_age(
            "/rest/api/uom/LogicalPartition/" + dummyuuid, False, "V2_0")
        self.assertEqual(
            i, 0, "Bad max age for LogicalPartition/{uuid} (no events, V2_0)")
        # VIOS, but not feed, hits the default
        i = util.get_max_age(
            "/rest/api/uom/VirtualIOServer/" + dummyuuid, False, "V2_0")
        self.assertEqual(
            i, 0, "Bad max age for VirtualIOServer/{uuid} (no events, V2_0)")
        # SPP, but not feed, hits the default
        i = util.get_max_age(
            "/rest/api/uom/SharedProcessorPool/" + dummyuuid, False, "V2_0")
        self.assertEqual(
            i, 0,
            "Bad max age for SharedProcessorPool/{uuid} (no events, V2_0)")
        # ManagedSystem, but not entry, hits the default
        i = util.get_max_age(
            "/rest/api/uom/ManagedSystem", False, "V2_0")
        self.assertEqual(
            i, 0, "Bad max age for ManagedSystem (no events, V2_0)")
        # <<<

        # >>> Cover the third branch: overall defaults when using events
        # and/or later schema versions
        i = util.get_max_age("/rest/api/uom/LogicalPartition", True, "V2_0")
        self.assertEqual(
            i, 600, "Bad max age for LogicalPartition (with events, V2_0)")

        i = util.get_max_age("/rest/api/uom/SharedProcessorPool",
                             False, "V2_0")
        self.assertEqual(
            i, 600, "Bad max age for SharedProcessorPool (no events, V2_0)")
        # <<<

    def test_convert_bytes_to_gb(self):
        # A round 1 GB
        test = util.convert_bytes_to_gb(1024 * 1024 * 1024)
        self.assertEqual(1.0, test)

        # A single MB
        test = util.convert_bytes_to_gb(1024 * 1024.0)
        self.assertEqual(0.0009765625, test)

        # A single byte - should be the low Value
        self.assertEqual(.0001, util.convert_bytes_to_gb(1))

        # Try changing the low value
        self.assertEqual(.0005, util.convert_bytes_to_gb(1, .0005))

    def test_sanitize_bool_for_api(self):
        self.assertEqual('true', util.sanitize_bool_for_api(True))
        self.assertEqual('false', util.sanitize_bool_for_api(False))
        self.assertEqual('true', util.sanitize_bool_for_api('True'))
        self.assertEqual('false', util.sanitize_bool_for_api('False'))

    def test_find_wrapper(self):
        wrap1 = mock.MagicMock()
        wrap1.uuid = 'a'
        wrap2 = mock.MagicMock()
        wrap2.uuid = 'b'
        wraps = [wrap1, wrap2]

        self.assertEqual(wrap1, util.find_wrapper(wraps, 'a'))
        self.assertEqual(wrap2, util.find_wrapper(wraps, 'b'))
        self.assertIsNone(util.find_wrapper(wraps, 'c'))

    def test_path_from_href(self):
        href = 'https://server:1234/rest/api/uom/Obj/UUID?group=One,Two#frag'
        self.assertEqual(util.path_from_href(href),
                         '/rest/api/uom/Obj/UUID?group=One,Two')
        self.assertEqual(util.path_from_href(href, include_query=True),
                         '/rest/api/uom/Obj/UUID?group=One,Two')
        self.assertEqual(util.path_from_href(href, include_fragment=False),
                         '/rest/api/uom/Obj/UUID?group=One,Two')
        self.assertEqual(util.path_from_href(href, include_query=False),
                         '/rest/api/uom/Obj/UUID')
        self.assertEqual(util.path_from_href(href, include_fragment=True),
                         '/rest/api/uom/Obj/UUID?group=One,Two#frag')
        self.assertEqual(util.path_from_href(href, include_query=False,
                                             include_fragment=True),
                         '/rest/api/uom/Obj/UUID#frag')

if __name__ == "__main__":
    unittest.main()
