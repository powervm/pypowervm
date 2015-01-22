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

import pypowervm.adapter as apt
import pypowervm.wrappers.entry_wrapper as ewrap


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

        # Wipe our entry, add feed.
        resp.entry = None
        resp.feed = apt.Feed([], ['entry', 'entry2'])

        # Validate
        self.assertEqual('entry', ew[0]._entry)
        self.assertEqual('entry2', ew[1]._entry)

        # These are none for now.
        self.assertIsNone(ew[0].etag)
        self.assertIsNone(ew[1].etag)
