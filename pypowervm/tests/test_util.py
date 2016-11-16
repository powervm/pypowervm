# Copyright 2014, 2016 IBM Corp.
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
import six

if six.PY2:
    import __builtin__ as builtins
elif six.PY3:
    import builtins

import unittest

from pypowervm import const
from pypowervm import util

dummyuuid1 = "abcdef01-2345-2345-2345-67890abcdef0"
dummyuuid2 = "67890abc-5432-5432-5432-def0abcdef01"


class TestUtil(unittest.TestCase):
    """Unit tests for pypowervm.util."""

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

        # Low value still honors dp
        self.assertEqual(0.01, util.convert_bytes_to_gb(1, dp=2))

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

    def test_part_id_by_loc_code(self):
        test_loc = 'U8247.22L.2125D6A-V2-C3'
        fail_loc = 'abc1234'
        self.assertEqual(util.part_id_by_loc_code(test_loc), 2)
        self.assertIsNone(util.part_id_by_loc_code(fail_loc))

    def test_xag_attrs(self):
        base = const.DEFAULT_SCHEMA_ATTR
        self.assertEqual(dict(base), util.xag_attrs(''))
        self.assertEqual(dict(base), util.xag_attrs(None))
        self.assertEqual(dict(base, group='foo'), util.xag_attrs('foo'))
        # Test other bases
        self.assertEqual(dict(one=2), util.xag_attrs(None, base=dict(one=2)))
        self.assertEqual(dict(one=2, group='foo'),
                         util.xag_attrs('foo', base=dict(one=2)))

    @mock.patch.object(builtins, 'open')
    def test_my_partition_id(self, m_open):
        """Test my_partition_id."""
        def rit():
            for line in ('foo=bar\n', 'partition_id=1234\n', '\n', 'a=b\n'):
                yield line
        m_open.return_value.__enter__.return_value.__iter__.side_effect = rit
        self.assertEqual(1234, util.my_partition_id())

    def test_parent_spec(self):
        """Test parent_spec."""
        # All params are None (ROOT request)
        self.assertEqual((None, None), util.parent_spec(None, None, None))
        # Get values from parent
        parent = mock.Mock(schema_type='schema_type', uuid='uuid')
        self.assertEqual(('schema_type', 'uuid'), util.parent_spec(
            parent, None, None))
        # Parent overrides parent_type/parent_uuid
        self.assertEqual(('schema_type', 'uuid'), util.parent_spec(
            parent, 'something', 'else'))
        # ValueError if type xor uuid specified
        self.assertRaises(ValueError, util.parent_spec, None, 'one', None)
        self.assertRaises(ValueError, util.parent_spec, None, None, 'two')
        # Non-wrapper, non-string parent type raises ValueError
        self.assertRaises(ValueError, util.parent_spec, None, 42, 'foo')
        # parent_type can be wrapper or string
        self.assertEqual(('schema_type', 'uuid2'), util.parent_spec(
            None, parent, 'uuid2'))
        self.assertEqual(('schema_type2', 'uuid2'), util.parent_spec(
            None, 'schema_type2', 'uuid2'))

    def test_retry_io_command(self):
        class MyOSError(OSError):
            def __init__(self, errno):
                super(MyOSError, self).__init__()
                self.errno = errno

        class MyIOError(IOError):
            def __init__(self, errno):
                super(MyIOError, self).__init__()
                self.errno = errno

        class MyValError(ValueError):
            def __init__(self, errno):
                super(MyValError, self).__init__()
                self.errno = errno

        func = mock.Mock()
        mock_os_intr = MyOSError(4)
        mock_io_intr = MyIOError(4)
        mock_val_intr = MyValError(4)
        mock_os_hup = MyOSError(1)
        mock_io_hup = MyIOError(1)
        func.side_effect = [mock_os_intr, mock_io_intr, mock_val_intr]
        self.assertRaises(MyValError, util.retry_io_command, func)
        self.assertEqual(3, func.call_count)
        func.reset_mock()
        func.side_effect = mock_os_hup
        self.assertRaises(MyOSError, util.retry_io_command, func, 1, 'a')
        func.assert_called_once_with(1, 'a')
        func.reset_mock()
        func.side_effect = mock_io_hup
        self.assertRaises(MyIOError, util.retry_io_command, func)
        func.assert_called_once_with()


class TestAllowedList(unittest.TestCase):
    def test_all_none(self):
        for cls in (util.VLANList, util.MACList):
            for val in ('ALL', 'NONE'):
                self.assertEqual(val, cls.unmarshal(val))
            for val in ('ALL', 'NONE', 'all', 'none', 'aLl', 'nOnE'):
                self.assertEqual(val.upper(), cls.marshal(val))
                self.assertEqual(val.upper(), cls.const_or_list(val))
                self.assertEqual(val.upper(), cls.marshal([val]))
                self.assertEqual(val.upper(), cls.const_or_list([val]))

    def test_unmarshal(self):
        # Test VLAN lists
        self.assertEqual([1, 2], util.VLANList.unmarshal('1 2'))
        self.assertEqual([0], util.VLANList.unmarshal('0'))
        self.assertEqual([5, 6, 2230, 3340],
                         util.VLANList.unmarshal('5 6 2230 3340'))

        # Test MAC lists
        self.assertEqual(['AB12CD34EF56', '12AB34CD56EF'],
                         util.MACList.unmarshal('AB12CD34EF56 12AB34CD56EF'))
        self.assertEqual(['AB12CD34EF56'],
                         util.MACList.unmarshal('AB12CD34EF56'))

    def test_marshal(self):
        # Test VLAN lists
        self.assertEqual('1 2', util.VLANList.marshal([1, 2]))
        self.assertEqual('0', util.VLANList.marshal([0]))
        self.assertEqual('5 6 2230 3340',
                         util.VLANList.marshal([5, 6, '2230', 3340]))

        # Test MAC lists
        self.assertEqual('AB12CD34EF56 12AB34CD56EF', util.MACList.marshal(
            ['aB:12:Cd:34:eF:56', '12Ab34cD56Ef']))
        self.assertEqual('AB12CD34EF56', util.MACList.marshal(
            ['Ab:12:cD:34:Ef:56']))

        # Test error cases
        for cls in (util.VLANList, util.MACList):
            self.assertRaises(ValueError, cls.marshal, None)
            self.assertRaises(ValueError, cls.marshal, '')
            self.assertRaises(ValueError, cls.marshal, ' ')
            self.assertRaises(ValueError, cls.marshal, 'bogus')

    def test_const_or_list(self):
        # Test VLAN lists
        for l2t in ([1, 2], [0], [5, 6, 2230, 3340]):
            self.assertEqual(l2t, util.VLANList.const_or_list(l2t))

        # Test MAC lists
        self.assertEqual(['AB12CD34EF56', '12AB34CD56EF'],
                         util.MACList.const_or_list(
                             ['aB:12:Cd:34:eF:56', '12Ab34cD56Ef']))
        self.assertEqual(['AB12CD34EF56'], util.MACList.const_or_list(
            ['Ab:12:cD:34:Ef:56']))

        # Test error cases
        for cls in (util.VLANList, util.MACList):
            for meth in (cls.marshal, cls.const_or_list):
                self.assertRaises(ValueError, meth, None)
                self.assertRaises(ValueError, meth, '')
                self.assertRaises(ValueError, meth, ' ')
                self.assertRaises(ValueError, meth, 'bogus')
        self.assertRaises(ValueError, util.VLANList.marshal, ['1', 'NaN', 2])
        self.assertRaises(ValueError, util.VLANList.const_or_list, ['1', 'NaN',
                                                                    2])
