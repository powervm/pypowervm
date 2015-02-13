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

import unittest

import pypowervm.adapter as apt
from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.entry_wrapper as ewrap

NET_BRIDGE_FILE = 'fake_network_bridge.txt'


class TestEntryWrapper(unittest.TestCase):

    def test_etag(self):
        etag = '1234'
        ew = ewrap.EntryWrapper('fake_entry', etag=etag)
        self.assertEqual(etag, ew.etag)

        ew = ewrap.EntryWrapper('fake_entry')
        self.assertEqual(None, ew.etag)

    def test_load(self):
        etag = '1234'
        resp = apt.Response('reqmethod', 'reqpath', 'status',
                            'reason', dict(etag=etag))

        # Entry or Feed is not set, so expect an exception
        self.assertRaises(KeyError,
                          ewrap.EntryWrapper.load_from_response, resp)

        # Set an entry...
        resp.entry = 'entry'

        # Run
        ew = ewrap.EntryWrapper.load_from_response(resp)

        # Validate
        self.assertEqual('entry', ew._entry)
        self.assertEqual(etag, ew.etag)

        # Create a response with no headers
        resp2 = apt.Response('reqmethod', 'reqpath', 'status', 'reason', {})
        resp2.entry = 'entry'
        # Run
        ew = ewrap.EntryWrapper.load_from_response(resp2)
        # Validate the etag is None since there were no headers
        self.assertEqual(None, ew.etag)

        # Wipe our entry, add feed.
        resp.entry = None
        e1 = apt.Entry({'etag': '1'}, None)
        e2 = apt.Entry({'etag': '2'}, None)
        resp.feed = apt.Feed([], [e1, e2])

        # Run
        ew = ewrap.EntryWrapper.load_from_response(resp)

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
        self.nb1 = ewrap.EntryWrapper(self.resp.feed.entries[0])
        self.resp2 = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        self.nb2 = ewrap.EntryWrapper(self.resp2.feed.entries[0])

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
        sea_trunk = sea2._element.findall('./TrunkAdapters/TrunkAdapter')[1]
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
        myel = MyElement(None)
        self.assertEqual(myel.pvm_type, 'SomePowerObject')
        self.assertEqual(
            myel._element.toxmlstring(),
            '<uom:SomePowerObject xmlns:uom="http://www.ibm.com/xmlns/systems'
            '/power/firmware/uom/mc/2012_10/" schemaVersion="V1_0"/>'
            .encode("utf-8"))

        # Can't use no-arg constructor if schema_type isn't overridden
        class MyElement2(ewrap.ElementWrapper):
            pass
        self.assertRaises(NotImplementedError, MyElement2)

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


class TestWrapperElemList(unittest.TestCase):
    """Tests for the WrapperElemList class."""

    def setUp(self):
        super(TestWrapperElemList, self).setUp()
        resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        nb = resp.feed.entries[0]
        self.wrapper = ewrap.EntryWrapper(nb)
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
        sea_add = ewrap.ElementWrapper(apt.Element('SharedEthernetAdapter'))
        self.assertEqual(1, len(self.elem_set))

        # Test Append
        self.elem_set.append(sea_add)
        self.assertEqual(2, len(self.elem_set))

        # Make sure we can also remove what was just added.
        self.elem_set.remove(sea_add)
        self.assertEqual(1, len(self.elem_set))

    def test_extend(self):
        seas = [
            ewrap.ElementWrapper(apt.Element('SharedEthernetAdapter')),
            ewrap.ElementWrapper(apt.Element('SharedEthernetAdapter'))
        ]
        self.assertEqual(1, len(self.elem_set))
        self.elem_set.extend(seas)
        self.assertEqual(3, len(self.elem_set))

        # Make sure that we can also remove what we added.  We remove a
        # logically identical element to test the equivalence function
        e = ewrap.ElementWrapper(apt.Element('SharedEthernetAdapter'))
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
