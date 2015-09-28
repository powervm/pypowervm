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


from pypowervm.utils import uuid as uuid_utils

import unittest


class TestUUID(unittest.TestCase):
    """Unit tests for the uuid."""

    def test_uuid_conversion(self):
        # Bit 0 must be 0
        uuid = '989ffb20-5d19-4a8c-7b80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual('1' + uuid[1:], pvm_uuid)
        uuid = 'c89ffb20-5d19-4a8c-7b80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual('4' + uuid[1:], pvm_uuid)

        # Bits 1-47 can't be zero
        uuid = '00000000-0000-4a8c-7b80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid[:12] + '1' + uuid[13:], pvm_uuid)

        # Bits 48-51 must be 0100 (4)
        uuid = '489ffb20-5d19-7a8c-7b80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid[:14] + '4' + uuid[15:], pvm_uuid)

        # Bits 52-63 can't all be zero.
        uuid = '189ffb20-5d19-4000-7b80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid[:17] + '1' + uuid[18:], pvm_uuid)

        # Bits 64-65 must be 2
        uuid = '089ffb20-5d19-4a8c-bb80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid[:19] + '7' + uuid[20:], pvm_uuid)

        # Last 62 bits can't be zero
        uuid = '489ffb20-5d19-4a8c-4000-000000000000'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid[:-1] + '1', pvm_uuid)

        # Hit all the rules
        uuid = '80000000-0000-F000-8000-000000000000'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual('00000000-0001-4001-4000-000000000001', pvm_uuid)

        # Case is preserved
        uuid = 'C89FFB20-5D19-FA8C-7B80-13650627D985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual('4' + uuid[1:14] + '4' + uuid[15:], pvm_uuid)

        # This one's compliant
        uuid = '489ffb20-5d19-4a8c-7b80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid, pvm_uuid)
        # ...in uppercase too
        uuid = '489FFB20-5D19-4A8C-7B80-13650627D985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid, pvm_uuid)

    def test_id_or_uuid(self):
        self.assertEqual((False, 123), uuid_utils.id_or_uuid(123))
        self.assertEqual((False, 123), uuid_utils.id_or_uuid('123'))
        self.assertEqual(
            (True, '12345678-abcd-ABCD-0000-0a1B2c3D4e5F'),
            uuid_utils.id_or_uuid('12345678-abcd-ABCD-0000-0a1B2c3D4e5F'))
        self.assertRaises(ValueError, uuid_utils.id_or_uuid,
                          '12345678abcdABCD00000a1B2c3D4e5F')
        # This one has too many digits
        self.assertRaises(ValueError, uuid_utils.id_or_uuid,
                          '12345678-abcd-ABCD-0000-0a1B2c3D4e5F0')
