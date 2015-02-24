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

from lxml import etree
import mock
import six

import unittest

import pypowervm.adapter as apt
from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.entry_wrapper as ewrap

NET_BRIDGE_FILE = 'fake_network_bridge.txt'


class SubWrapper(ewrap.Wrapper):
    schema_type = 'SubWrapper'
    type_and_uuid = 'SubWrapper_TestClass'

    def __init__(self, **kwargs):
        class Txt(object):
            def __init__(self, val):
                self.text = val

        super(SubWrapper, self).__init__()
        self.data = dict((k, Txt(v)) for k, v in six.iteritems(kwargs))

    def _find(self, prop_name, use_find_all=False):
        try:
            return self.data[prop_name]
        except KeyError:
            return None


class TestWrapper(unittest.TestCase):
    def test_get_val_str(self):
        w = SubWrapper(one='1', foo='foo', empty='')
        self.assertEqual(w._get_val_str('one'), '1')
        self.assertEqual(w._get_val_str('foo'), 'foo')
        self.assertEqual(w._get_val_str('empty'), '')
        self.assertIsNone(w._get_val_str('nonexistent'))
        self.assertEqual(w._get_val_str('nonexistent', default='10'), '10')

    def test_get_val_int(self):
        w = SubWrapper(one='1', nan='foo', empty='')
        self.assertEqual(w._get_val_int('one'), 1)
        self.assertIsNone(w._get_val_int('nan'))
        self.assertIsNone(w._get_val_int('empty'))
        self.assertIsNone(w._get_val_int('nonexistent'))
        self.assertEqual(w._get_val_int('nonexistent', default=10), 10)

    def test_get_val_float(self):
        w = SubWrapper(one='1', two_point_two='2.2', nan='foo', empty='')
        self.assertAlmostEqual(w._get_val_float('one'), 1)
        self.assertAlmostEqual(w._get_val_float('two_point_two'), 2.2)
        self.assertIsNone(w._get_val_float('nan'))
        self.assertIsNone(w._get_val_float('empty'))
        self.assertIsNone(w._get_val_float('nonexistent'))
        self.assertAlmostEqual(w._get_val_float('one', default=2), 1)
        self.assertAlmostEqual(w._get_val_float('two_point_two', default=3),
                               2.2)
        self.assertAlmostEqual(w._get_val_float('nan', default=1), 1)
        self.assertAlmostEqual(w._get_val_float('empty', default=1), 1)
        self.assertAlmostEqual(w._get_val_int('nonexistent', default=1.7), 1.7)

    def test_get_val_bool(self):
        w = SubWrapper(one='1', t='true', T='TRUE', f='false', F='FALSE',
                       empty='')
        self.assertTrue(w._get_val_bool('t'))
        self.assertTrue(w._get_val_bool('T'))
        self.assertFalse(w._get_val_bool('one'))
        self.assertFalse(w._get_val_bool('empty'))
        self.assertFalse(w._get_val_bool('f'))
        self.assertFalse(w._get_val_bool('F'))
        self.assertFalse(w._get_val_bool('nonexistent'))
        self.assertTrue(w._get_val_bool('t', default=False))
        self.assertTrue(w._get_val_bool('T', default=False))
        self.assertFalse(w._get_val_bool('one', default=True))
        self.assertFalse(w._get_val_bool('empty', default=True))
        self.assertFalse(w._get_val_bool('f', default=True))
        self.assertFalse(w._get_val_bool('F', default=True))
        self.assertTrue(w._get_val_bool('nonexistent', default=True))


class TestEntryWrapper(unittest.TestCase):

    def test_etag(self):
        fake_entry = apt.Entry({}, apt.Element('fake_entry'))
        etag = '1234'
        ew = ewrap.EntryWrapper.wrap(fake_entry, etag=etag)
        self.assertEqual(etag, ew.etag)

        ew = ewrap.EntryWrapper.wrap(fake_entry)
        self.assertEqual(None, ew.etag)

    def test_load(self):
        etag = '1234'
        resp = apt.Response('reqmethod', 'reqpath', 'status',
                            'reason', dict(etag=etag))

        # Entry or Feed is not set, so expect an exception
        self.assertRaises(KeyError, ewrap.EntryWrapper.wrap, resp)

        # Set an entry...
        entry = apt.Entry({}, apt.Element('entry'))
        resp.entry = entry

        # Run
        ew = ewrap.EntryWrapper.wrap(resp)

        # Validate
        self.assertEqual(entry, ew._entry)
        self.assertEqual(etag, ew.etag)

        # Create a response with no headers
        resp2 = apt.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp2.entry = entry
        # Run
        ew = ewrap.EntryWrapper.wrap(resp2)
        # Validate the etag is None since there were no headers
        self.assertEqual(None, ew.etag)

        # Wipe our entry, add feed.
        resp.entry = None
        e1 = apt.Entry({'etag': '1'}, None)
        e2 = apt.Entry({'etag': '2'}, None)
        resp.feed = apt.Feed({}, [e1, e2])

        # Run
        ew = ewrap.EntryWrapper.wrap(resp)

        # Validate
        self.assertEqual(e1, ew[0]._entry)
        self.assertEqual('1', ew[0].etag)
        self.assertEqual(e2, ew[1]._entry)
        self.assertEqual('2', ew[1].etag)


class TestElementWrapper(unittest.TestCase):
    """Tests for the ElementWrapper class."""

    def setUp(self):
        super(TestElementWrapper, self).setUp()
        self.resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb1 = ewrap.EntryWrapper.wrap(self.resp.feed.entries[0])
        self.resp2 = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb2 = ewrap.EntryWrapper.wrap(self.resp2.feed.entries[0])

    def test_equality(self):
        """Validates that two elements loaded from the same data is equal."""
        sea1 = self._find_seas(self.nb1._entry)[0]
        sea2 = self._find_seas(self.nb2._entry)[0]
        self.assertTrue(sea1 == sea2)

        # Change the other SEA
        sea2._element._element.append(etree.Element('Bob'))
        self.assertFalse(sea1 == sea2)

    def test_inequality_by_subelem_change(self):
        sea1 = self._find_seas(self.nb1._entry)[0]
        sea2 = self._find_seas(self.nb2._entry)[0]
        sea_trunk = sea2._element.findall('TrunkAdapters/TrunkAdapter')[1]
        pvid = sea_trunk.find('PortVLANID')
        pvid.text = '1'
        self.assertFalse(sea1 == sea2)

    def _find_seas(self, entry):
        """Wrapper for the SEAs."""
        found = entry.element.find('SharedEthernetAdapters')
        return ewrap.WrapperElemList(found, 'SharedEthernetAdapter',
                                     ewrap.ElementWrapper)

    def test_fresh_element(self):
        # Default: UOM namespace, no <Metadata/>
        class MyElement(ewrap.ElementWrapper):
            schema_type = 'SomePowerObject'
        myel = MyElement()
        self.assertEqual(myel.pvm_type, 'SomePowerObject')
        self.assertEqual(
            myel._element.toxmlstring(),
            '<uom:SomePowerObject xmlns:uom="http://www.ibm.com/xmlns/systems'
            '/power/firmware/uom/mc/2012_10/" schemaVersion="V1_0"/>'
            .encode("utf-8"))

        # Can't use no-arg constructor if schema_type isn't overridden
        class MyElement2(ewrap.ElementWrapper):
            pass
        self.assertRaises(TypeError, MyElement2)

        # Can override namespace and attrs and trigger inclusion of <Metadata/>
        class MyElement3(ewrap.ElementWrapper):
            schema_type = 'SomePowerObject'
            default_attrib = {'foo': 'bar'}
            schema_ns = 'baz'
            has_metadata = True
        myel = MyElement3()
        self.assertEqual(
            myel._element.toxmlstring(),
            '<ns0:SomePowerObject xmlns:ns0="baz" foo="bar"><ns0:Metadata>'
            '<ns0:Atom/></ns0:Metadata></ns0:SomePowerObject>'.encode("utf-8"))

    def test_href(self):
        path = 'LoadGroups/LoadGroup/VirtualNetworks/link'
        # Get all
        hrefs = self.nb1.get_href(path)
        self.assertEqual(len(hrefs), 13)
        self.assertEqual(
            hrefs[2],
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/726e9cb3-6576-3d'
            'f5-ab60-40893d51d074/VirtualNetwork/f417df1f-ff3a-35e5-a428-ab3b8'
            '2be7717')
        # Request one - should return None
        hrefs = self.nb1.get_href(path, one_result=True)
        self.assertIsNone(hrefs)
        # set_href should refuse to set multiple links
        self.assertRaises(ValueError, self.nb1.set_href, path, 'foo')

        # Drill down to the (only) SEA
        sea = ewrap.ElementWrapper.wrap(
            self.nb1._find('SharedEthernetAdapters/SharedEthernetAdapter'))
        path = 'AssignedVirtualIOServer'
        hrefs = sea.get_href(path)
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(
            hrefs[0],
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/726e9cb3-6576-3d'
            'f5-ab60-40893d51d074/VirtualIOServer/691019AF-506A-4896-AADE-607E'
            '21FA93EE')
        # Now make sure one_result returns the string (not a list)
        href = sea.get_href(path, one_result=True)
        self.assertEqual(
            href,
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/726e9cb3-6576-3d'
            'f5-ab60-40893d51d074/VirtualIOServer/691019AF-506A-4896-AADE-607E'
            '21FA93EE')
        # Test setter
        sea.set_href(path, 'foo')
        self.assertEqual(sea.get_href(path, one_result=True), 'foo')
        # Now try setting one that doesn't exist.  First on a top-level path.
        path = 'NewElement'
        sea.set_href(path, 'bar')
        self.assertEqual(sea.get_href(path, one_result=True), 'bar')
        # ...and now on a nested path.
        path = 'BackingDeviceChoice/EthernetBackingDevice/NewLink'
        sea.set_href(path, 'baz')
        self.assertEqual(sea.get_href(path, one_result=True), 'baz')


class TestWrapperElemList(unittest.TestCase):
    """Tests for the WrapperElemList class."""

    def setUp(self):
        super(TestWrapperElemList, self).setUp()
        resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        nb = resp.feed.entries[0]
        self.wrapper = ewrap.EntryWrapper.wrap(nb)
        sea_elem = self.wrapper._element.find('SharedEthernetAdapters')

        self.elem_set = ewrap.WrapperElemList(sea_elem,
                                              'SharedEthernetAdapter',
                                              ewrap.ElementWrapper)

    def test_get(self):
        self.assertIsNotNone(self.elem_set[0])
        self.assertRaises(IndexError, lambda a, i: a[i], self.elem_set, 1)

    def test_length(self):
        self.assertEqual(1, len(self.elem_set))

    def test_append(self):
        sea_add = ewrap.ElementWrapper.wrap(
            apt.Element('SharedEthernetAdapter'))
        self.assertEqual(1, len(self.elem_set))

        # Test Append
        self.elem_set.append(sea_add)
        self.assertEqual(2, len(self.elem_set))

        # Make sure we can also remove what was just added.
        self.elem_set.remove(sea_add)
        self.assertEqual(1, len(self.elem_set))

    def test_extend(self):
        seas = [
            ewrap.ElementWrapper.wrap(apt.Element('SharedEthernetAdapter')),
            ewrap.ElementWrapper.wrap(apt.Element('SharedEthernetAdapter'))
        ]
        self.assertEqual(1, len(self.elem_set))
        self.elem_set.extend(seas)
        self.assertEqual(3, len(self.elem_set))

        # Make sure that we can also remove what we added.  We remove a
        # logically identical element to test the equivalence function
        e = ewrap.ElementWrapper.wrap(apt.Element('SharedEthernetAdapter'))
        self.elem_set.remove(e)
        self.elem_set.remove(e)
        self.assertEqual(1, len(self.elem_set))


class TestActionableList(unittest.TestCase):
    """Tests for the Actionable List class."""

    def setUp(self):
        super(TestActionableList, self).setUp()

    def test_extend(self):
        def test(new_list):
            self.assertEqual([1, 2, 3, 4, 5], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Extend here.
        l.extend([4, 5])
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

    def test_append(self):
        def test(new_list):
            self.assertEqual([1, 2, 3, 4], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Append here.
        l.append(4)
        self.assertEqual(4, len(l))
        self.assertEqual(4, l[3])

    def test_remove(self):
        def test(new_list):
            self.assertEqual([1, 3], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Remove here.
        l.remove(2)
        self.assertEqual(2, len(l))
        self.assertEqual(3, l[1])

    def test_insert(self):
        def test(new_list):
            self.assertEqual([1, 2, 3, 4], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Insert here.
        l.insert(3, 4)
        self.assertEqual(4, len(l))
        self.assertEqual(4, l[3])

    def test_pop(self):
        def test(new_list):
            self.assertEqual([1, 2], new_list)
        l = ewrap.ActionableList([1, 2, 3], test)

        # Pop here.
        l.pop(2)
        self.assertEqual(2, len(l))
        self.assertEqual(2, l[1])

    def test_complex_path(self):
        function = mock.MagicMock()

        l = ewrap.ActionableList([1, 2, 3], function)
        self.assertEqual(3, len(l))
        self.assertEqual(3, l[2])

        # Try extending
        l.extend([4, 5])
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

        # Try appending
        l.append(6)
        self.assertEqual(6, len(l))
        self.assertEqual(6, l[5])

        # Try removing
        l.remove(6)
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

        # Try inserting
        l.insert(5, 6)
        self.assertEqual(6, len(l))
        self.assertEqual(6, l[5])

        # Try popping
        self.assertEqual(6, l.pop(5))
        self.assertEqual(5, len(l))
        self.assertEqual(5, l[4])

        # Make sure our function was called each time
        self.assertEqual(5, function.call_count)

if __name__ == '__main__':
    unittest.main()