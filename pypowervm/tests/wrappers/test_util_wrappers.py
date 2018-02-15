# Copyright 2018 IBM Corp.
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

import pypowervm.tests.test_utils.test_wrapper_abc as twrap
from pypowervm.utils import wrappers
import pypowervm.wrappers.virtual_io_server as vios


class TestFilteredWrapperElemList(twrap.TestWrapper):
    file = 'fake_vios_feed.txt'
    wrapper_class_to_test = vios.VIOS

    href = ('https://9.1.2.3:12443/rest/api/uom/ManagedSystem/'
            'e7344c5b-79b5-3e73-8f64-94821424bc25/LogicalPartition/'
            '3ADDED46-B3A9-4E12-B6EC-8223421AF49B')
    wwpns = ['C05076079CFF0E56', 'C05076079CFF0E57']

    def test_filter(self):
        filt = wrappers.FilteredWrapperElemList(self.dwrap.vfc_mappings)
        filt.client_lpar_href(self.href)
        expected = [wrap for wrap in self.dwrap.vfc_mappings if
                    wrap.client_lpar_href == self.href]
        self.assertEqual(expected, filt)
        self.assertEqual(4, len(filt))
        filt.client_adapter(wwpns=self.wwpns)
        expected = [wrap for wrap in expected if
                    wrap.client_adapter.wwpns == self.wwpns]
        self.assertEqual(expected, filt)
        self.assertEqual(1, len(filt))

    def test_cumulative(self):
        filt = wrappers.FilteredWrapperElemList(self.dwrap.vfc_mappings)
        self.assertEqual(58, len(filt))
        filt.server_adapter(lpar_slot_num=4)
        self.assertEqual(28, len(filt))
        filt.client_lpar_href(self.href)
        self.assertEqual(3, len(filt))
        # Do the filters in reverse order to prove that they overlap
        filt = wrappers.FilteredWrapperElemList(self.dwrap.vfc_mappings)
        self.assertEqual(58, len(filt))
        filt.client_lpar_href(self.href)
        self.assertEqual(4, len(filt))
        filt.server_adapter(lpar_slot_num=4)
        self.assertEqual(3, len(filt))

    def test_chaining(self):
        filt = wrappers.FilteredWrapperElemList(self.dwrap.vfc_mappings)
        self.assertEqual(
            [wrap for wrap in self.dwrap.vfc_mappings if
             wrap.client_lpar_href == self.href and
             wrap.client_adapter.wwpns == self.wwpns],
            filt.client_lpar_href(
                self.href).client_adapter(wwpns=self.wwpns))
        self.assertEqual(1, len(filt))

    def test_errors(self):
        filt = wrappers.FilteredWrapperElemList(self.dwrap.vfc_mappings)
        # Bogus flat prop
        self.assertRaises(AttributeError, lambda: filt.bogus('foo'))
        # Bogus sub-prop
        self.assertRaises(AttributeError, filt.client_adapter, bogus=1)
        # Can't specify both args and kwargs
        self.assertRaises(ValueError, filt.client_adapter, 'foo', wwpns='bar')
        # Can't specify multiple values
        self.assertRaises(ValueError, filt.client_lpar_href, 'foo', 'bar')
