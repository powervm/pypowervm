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

import unittest

import pypowervm.cache as pcache


class TestCache(unittest.TestCase):
    def test_byaccess_order(self):
        self.cache_multicheck('byaccess')

    def test_byadd_order(self):
        self.cache_multicheck('byadd')

    def cache_multicheck(self, order):
        cache = pcache._Cache('myhostname', order=order)
        first = 0
        for x in range(pcache.cachesize):
            cache.set(str(x), str(x))
        self.assertEqual(len(cache._data.keys()),
                         pcache.cachesize,
                         'failed to fill the cache')
        self.assertTrue(cache.get(str(first)) is not None,
                        'failed to find first entry')

        cache.clear()
        self.assertEqual(len(cache._data.keys()), 0,
                         'failed to clear the cache')

        first = 0
        for x in range(pcache.cachesize):
            cache.set(str(x), str(x))
        self.assertEqual(len(cache._data.keys()),
                         pcache.cachesize,
                         'failed to fill the cache after clear')
        self.assertTrue(cache.get(str(first)) is not None,
                        'failed to find first entry after clear/refill')
        if order == 'byaccess':
            first += 1

        cache.set('extra1', 'extra1')
        first += 1
        self.assertEqual(len(cache._data.keys()),
                         pcache.cachesize,
                         'failed to maintain full cache when adding')
        self.assertTrue(cache.get('extra1') is not None,
                        'failed to add to full cache')
        self.assertTrue(cache.get(str(first - 1)) is None,
                        'failed to pop correctly from full cache')

        cache.remove('15')
        self.assertEqual(len(cache._data.keys()),
                         pcache.cachesize - 1,
                         'still have full cache after removal')
        self.assertTrue(cache.get('15') is None,
                        'failed to remove from the middle')

        cache.set('extra2', 'extra2')
        self.assertEqual(len(cache._data.keys()),
                         pcache.cachesize,
                         'failed to fill the cache again with add')
        self.assertTrue(cache.get(str(first)) is not None,
                        'missing first entry on refill')
        if order == 'byaccess':
            first += 1

        cache.set('extra3', 'extra3')
        first += 1
        self.assertEqual(len(cache._data.keys()),
                         pcache.cachesize,
                         'failed to maintain full cache when adding to '
                         'refilled cache')
        self.assertTrue(cache.get('extra3') is not None,
                        'failed to add again to full cache')
        self.assertTrue(cache.get(str(first - 1)) is None,
                        'failed to pop correctly from refilled cache')
