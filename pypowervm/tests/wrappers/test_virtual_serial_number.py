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

import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.virtual_serial_number as vsn

SHRPROC_HTTPRESP_FILE = "vsn.txt"


class TestShrPrcPoolTestCase(twrap.TestWrapper):

    file = 'vsn.txt'
    wrapper_class_to_test = vsn.VirtualSerialNumber

    def test_validate_attribues(self):
        self.assertEqual('ZCE0HF0', self.dwrap.vsn)
        self.assertEqual("-", self.dwrap.assoc_partition_id)
        self.assertEqual(True, self.dwrap.auto_assign)

        n_vsn = self.entries[1]
        self.assertEqual('WXYZHF0', n_vsn.vsn)
        self.assertEqual("-", n_vsn.assoc_partition_id)
        self.assertEqual(True, n_vsn.auto_assign)

        n_vsn = self.entries[2]
        self.assertEqual('ZCE0HD0', n_vsn.vsn)
        self.assertEqual("-", n_vsn.assoc_partition_id)
        self.assertEqual(True, n_vsn.auto_assign)

        n_vsn = self.entries[3]
        self.assertEqual('WXYZHD0', n_vsn.vsn)
        self.assertEqual("-", n_vsn.assoc_partition_id)
        self.assertEqual(True, n_vsn.auto_assign)
