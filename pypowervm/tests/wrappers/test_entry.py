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

    def setUp(self):
        super(TestEntryWrapper, self).setUp()

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
        resp.feed = apt.Feed([], ['entry', 'entry2'])

        # Run
        ew = ewrap.EntryWrapper.load_from_response(resp)

        # Validate
        self.assertEqual('entry', ew[0]._entry)
        self.assertEqual('entry2', ew[1]._entry)

        # These are none for now.
        self.assertIsNone(ew[0].etag)
        self.assertIsNone(ew[1].etag)


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

        # Reload, but change some text
        self.nb2 = ewrap.EntryWrapper(self.resp2.feed.entries[0])
        sea2 = self._find_seas(self.nb2._entry)[0]
        sea_trunk = sea2._element.findall('./TrunkAdapters/TrunkAdapter')[1]
        pvid = sea_trunk.find('PortVLANID')
        pvid.text = '1'
        self.assertFalse(sea1 == sea2)

    def _find_seas(self, entry):
        """Wrapper for the SEAs."""
        return ewrap.ElementSet(entry.element.find('SharedEthernetAdapters'),
                                'SharedEthernetAdapter', ewrap.ElementWrapper)


class TestElementList(unittest.TestCase):
    """Tests for the ElementList class."""

    def setUp(self):
        super(TestElementList, self).setUp()
        resp = pvmhttp.load_pvm_resp(NET_BRIDGE_FILE).get_response()
        nb = resp.feed.entries[0]
        self.wrapper = ewrap.EntryWrapper(nb)
        sea_elem = self.wrapper._element.find('SharedEthernetAdapters')

        self.list = ewrap.ElementSet(sea_elem, 'SharedEthernetAdapter',
                                     ewrap.ElementWrapper)

    def test_get(self):
        self.assertIsNotNone(self.list[0])
        self.assertRaises(IndexError, lambda a, i: a[i], self.list, 1)

    def test_length(self):
        self.assertEqual(1, len(self.list))

    def test_append(self):
        sea_add = ewrap.ElementWrapper(apt.Element('SharedEthernetAdapter'))
        self.assertEqual(1, len(self.list))

        # Test Append
        self.list.append(sea_add)
        self.assertEqual(2, len(self.list))

        # Make sure we can also remove what was just added.
        self.list.remove(sea_add)
        self.assertEqual(1, len(self.list))

    def test_extend(self):
        seas = [
            ewrap.ElementWrapper(apt.Element('SharedEthernetAdapter')),
            ewrap.ElementWrapper(apt.Element('SharedEthernetAdapter'))
        ]
        self.assertEqual(1, len(self.list))
        self.list.extend(seas)
        self.assertEqual(3, len(self.list))

        # Make sure that we can also remove what we added.  We remove a
        # logically identical element to test the equivalence function
        e = ewrap.ElementWrapper(
            apt.Element('SharedEthernetAdapter'))
        self.list.remove(e)
        self.list.remove(e)
        self.assertEqual(1, len(self.list))


class TestActionableList(unittest.TestCase):
    """Tests for the Actionable List class."""

    def setUp(self):
        super(TestActionableList, self).setUp()

    def test_higher_func(self):
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
