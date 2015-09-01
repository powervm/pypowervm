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

from pypowervm import const
from pypowervm import util

dummyuuid1 = "abcdef01-2345-2345-2345-67890abcdef0"
dummyuuid2 = "67890abc-5432-5432-5432-def0abcdef01"


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
            "/rest/api/uom/Cluster/" + dummyuuid1, False, "V1_0")
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
            "/rest/api/uom/ManagedSystem/" + dummyuuid1, False, "V2_0")
        self.assertEqual(
            i, 30, "Bad max age for ManagedSystem/{uuid} (no events, V2_0)")
        # LogicalPartition, but not feed, hits the default
        i = util.get_max_age(
            "/rest/api/uom/LogicalPartition/" + dummyuuid1, False, "V2_0")
        self.assertEqual(
            i, 0, "Bad max age for LogicalPartition/{uuid} (no events, V2_0)")
        # VIOS, but not feed, hits the default
        i = util.get_max_age(
            "/rest/api/uom/VirtualIOServer/" + dummyuuid1, False, "V2_0")
        self.assertEqual(
            i, 0, "Bad max age for VirtualIOServer/{uuid} (no events, V2_0)")
        # SPP, but not feed, hits the default
        i = util.get_max_age(
            "/rest/api/uom/SharedProcessorPool/" + dummyuuid1, False, "V2_0")
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

        # Round up
        self.assertEqual(1.15, util.convert_bytes_to_gb(1224067890, dp=2))

    def test_round_gb_size_up(self):
        self.assertEqual(12.35, util.round_gb_size_up(12.34000000001))
        self.assertEqual(12.34000000001, util.round_gb_size_up(12.34000000001,
                                                               dp=11))
        self.assertEqual(1048576, util.round_gb_size_up(1048576.0, dp=0))
        self.assertEqual(1048576, util.round_gb_size_up(1048575.1, dp=0))
        self.assertEqual(1048576, util.round_gb_size_up(1048576, dp=0))
        self.assertEqual(1048600, util.round_gb_size_up(1048576.1234, dp=-2))

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

    def test_dice_href(self):
        href = 'https://server:1234/rest/api/uom/Obj/UUID//?group=One,Two#frag'
        self.assertEqual(util.dice_href(href),
                         '/rest/api/uom/Obj/UUID?group=One,Two#frag')
        self.assertEqual(util.dice_href(href, include_query=True),
                         '/rest/api/uom/Obj/UUID?group=One,Two#frag')
        self.assertEqual(util.dice_href(href, include_fragment=False),
                         '/rest/api/uom/Obj/UUID?group=One,Two')
        self.assertEqual(util.dice_href(href, include_query=False),
                         '/rest/api/uom/Obj/UUID#frag')
        self.assertEqual(util.dice_href(href, include_fragment=True),
                         '/rest/api/uom/Obj/UUID?group=One,Two#frag')
        self.assertEqual(util.dice_href(href, include_query=False,
                                        include_fragment=True),
                         '/rest/api/uom/Obj/UUID#frag')
        self.assertEqual(util.dice_href(href, include_scheme_netloc=True,
                                        include_query=False,
                                        include_fragment=False),
                         'https://server:1234/rest/api/uom/Obj/UUID')

    def test_get_req_path_uuid_and_is_instance_path(self):
        # Fail: no '/'
        path = dummyuuid1
        self.assertIsNone(util.get_req_path_uuid(path))
        self.assertRaises(IndexError, util.is_instance_path, path)
        path = '/' + dummyuuid1
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(path))
        self.assertTrue(util.is_instance_path(path))
        path = 'https://server:1234/rest/api/uom/Obj/' + dummyuuid1
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(path))
        self.assertTrue(util.is_instance_path(path))
        # Fail: last path element is not a UUID
        path = 'https://server:1234/rest/api/uom/Obj/' + dummyuuid1 + '/Child'
        self.assertIsNone(util.get_req_path_uuid(path))
        self.assertFalse(util.is_instance_path(path))
        # Fail: last path element is not quiiiite a UUID
        path = 'https://server:1234/rest/api/uom/Obj/' + dummyuuid1[1:]
        self.assertIsNone(util.get_req_path_uuid(path))
        self.assertFalse(util.is_instance_path(path))
        # Ignore query/fragment
        path = ('https://server:1234/rest/api/uom/Obj/' + dummyuuid1 +
                '?group=One,Two#frag')
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(path))
        self.assertTrue(util.is_instance_path(path))
        # Fail: last path element (having removed query/fragment) is not a UUID
        path = ('https://server:1234/rest/api/uom/Obj/' + dummyuuid1 +
                '/Child?group=One,Two#frag')
        self.assertIsNone(util.get_req_path_uuid(path))
        self.assertFalse(util.is_instance_path(path))
        # Default case conversion
        path = 'https://server:1234/rest/api/uom/Obj/' + dummyuuid1.upper()
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(path))
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(
            path, preserve_case=False))
        self.assertTrue(util.is_instance_path(path))
        # Force no case conversion
        self.assertEqual(dummyuuid1.upper(), util.get_req_path_uuid(
            path, preserve_case=True))
        # Child URI gets child UUID by default
        path = ('https://server:1234/rest/api/uom/Obj/' + dummyuuid1 +
                '/Child/' + dummyuuid2)
        self.assertEqual(dummyuuid2, util.get_req_path_uuid(path))
        self.assertTrue(util.is_instance_path(path))
        # Get root UUID from child URI
        path = ('https://server:1234/rest/api/uom/Obj/' + dummyuuid1 +
                '/Child/' + dummyuuid2)
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(path, root=True))
        self.assertTrue(util.is_instance_path(path))
        # root=True redundant on a root path
        path = '/' + dummyuuid1
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(path, root=True))
        path = 'https://server:1234/rest/api/uom/Obj/' + dummyuuid1
        self.assertEqual(dummyuuid1, util.get_req_path_uuid(path, root=True))

    def test_extend_basepath(self):
        ext = '/foo'
        # Various forms without query params or fragments
        for path in (dummyuuid1, '/' + dummyuuid1,
                     'https://server:1234/rest/api/uom/Obj/' + dummyuuid1,
                     'https://server:1234/rest/api/uom/Obj/' + dummyuuid1 +
                     '/Child'):
            self.assertEqual(path + ext, util.extend_basepath(path, ext))

        basepath = 'https://server:1234/rest/api/uom/Obj/' + dummyuuid1
        qp = '?foo=bar,baz&blah=123'
        frag = '#frag'
        # Query params
        self.assertEqual(basepath + ext + qp,
                         util.extend_basepath(basepath + qp, ext))
        # Fragment
        self.assertEqual(basepath + ext + frag,
                         util.extend_basepath(basepath + frag, ext))
        # Query params & fragment
        self.assertEqual(basepath + ext + qp + frag,
                         util.extend_basepath(basepath + qp + frag, ext))

    def test_sanitize_file_name_for_api(self):
        allc = ''.join(map(chr, range(256)))
        self.assertEqual('foo', util.sanitize_file_name_for_api('foo'))
        self.assertEqual(
            'config_foo.iso', util.sanitize_file_name_for_api(
                'foo', prefix='config_', suffix='.iso'))
        self.assertEqual(
            '______________________________________________._0123456789_______'
            'ABCDEFGHIJKLMN',
            util.sanitize_file_name_for_api(allc))
        self.assertEqual(
            'OPQRSTUVWXYZ______abcdefghijklmnopqrstuvwxyz_____________________'
            '______________',
            util.sanitize_file_name_for_api(allc[79:])
        )
        self.assertEqual(
            '_________________________________________________________________'
            '______________',
            util.sanitize_file_name_for_api(allc[158:])
        )
        self.assertEqual('___________________',
                         util.sanitize_file_name_for_api(allc[237:]))
        self.assertEqual(
            (dummyuuid1 + dummyuuid2[:7] + dummyuuid1).replace('-', '_'),
            util.sanitize_file_name_for_api(
                dummyuuid2, prefix=dummyuuid1, suffix=dummyuuid1))
        self.assertEqual('I____________',
                         util.sanitize_file_name_for_api(
                             u'I \u611B \u01A4\u0177\u03C1\uFF4F\u05E9\u5DF3'
                             u'\u5C3A\uFF56\uFF4D'))
        self.assertRaises(ValueError, util.sanitize_file_name_for_api, allc,
                          prefix=allc, suffix=allc)
        self.assertRaises(ValueError, util.sanitize_file_name_for_api, '')
        # Non-default max_len values
        self.assertEqual('abcdefghijklmno', util.sanitize_file_name_for_api(
            'abcdefghijklmnopqrstuvwxyz', max_len=const.MaxLen.VDISK_NAME))
        self.assertEqual(
            'abcdefghijklmnopqrstuvwxyz0123456789A',
            util.sanitize_file_name_for_api(
                'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNO',
                max_len=const.MaxLen.VOPT_NAME))

    def test_sanitize_partition_name_for_api(self):
        allc = ''.join(map(chr, range(256)))
        self.assertEqual('foo', util.sanitize_partition_name_for_api('foo'))
        self.assertEqual('_______________________________',
                         util.sanitize_partition_name_for_api(allc))
        self.assertEqual('_ !_#_%_____+,-./0123456789:;_=',
                         util.sanitize_partition_name_for_api(allc[31:]))
        self.assertEqual('__@ABCDEFGHIJKLMNOPQRSTUVWXYZ__',
                         util.sanitize_partition_name_for_api(allc[62:]))
        self.assertEqual('_^__abcdefghijklmnopqrstuvwxyz{',
                         util.sanitize_partition_name_for_api(allc[93:]))
        self.assertEqual('_}_____________________________',
                         util.sanitize_partition_name_for_api(allc[124:]))
        for start in (155, 186, 217):
            self.assertEqual(
                '_______________________________',
                util.sanitize_partition_name_for_api(allc[start:]))
        self.assertEqual('________',
                         util.sanitize_partition_name_for_api(allc[248:]))
        self.assertEqual('I _ _________',
                         util.sanitize_partition_name_for_api(
                             u'I \u611B \u01A4\u0177\u03C1\uFF4F\u05E9\u5DF3'
                             u'\u5C3A\uFF56\uFF4D'))

        self.assertRaises(ValueError, util.sanitize_partition_name_for_api,
                          allc, trunc_ok=False)
        self.assertRaises(ValueError, util.sanitize_partition_name_for_api, '')
        self.assertRaises(ValueError, util.sanitize_partition_name_for_api,
                          None)

    # Tests for check_and_apply_xag covered by
    # test_adapter.TestAdapter.test_extended_path
