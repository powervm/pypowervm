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

import pypowervm.const as pc
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.vios_file as vf


class TestVIOSFile(twrap.TestWrapper):

    file = 'file_feed.txt'
    wrapper_class_to_test = vf.File

    def test_wrapper_class(self):
        self.assertEqual(vf.File.schema_type, 'File')
        self.assertEqual(vf.File.schema_ns, pc.WEB_NS)
        self.assertTrue(vf.File.has_metadata)
        self.assertEqual(vf.File.default_attrib, pc.DEFAULT_SCHEMA_ATTR)

    def test_file(self):
        self.assertTrue(len(self.entries) > 0)

        vio_file = self.entries[0]
        self.assertEqual(vio_file.schema_type, 'File')
        self.assertEqual('boot_9699a0f5', vio_file.file_name)
        self.assertEqual('1421736166276', vio_file.date_modified)
        self.assertEqual('application/octet-stream',
                         vio_file.internet_media_type)
        self.assertEqual('5cd8e4b0-083e-4c71-bcff-2432807cfdcc',
                         vio_file.file_uuid)
        self.assertEqual(25165824, vio_file.expected_file_size)
        self.assertEqual(25165824, vio_file.current_file_size)
        self.assertEqual(vf.FileType.DISK_IMAGE, vio_file.enum_type)
        self.assertEqual('14B854F7-42CE-4FF0-BD57-1D117054E701',
                         vio_file.vios_uuid)
        self.assertEqual('0300f8d6de00004b000000014a54555cd9.28',
                         vio_file.tdev_udid)
