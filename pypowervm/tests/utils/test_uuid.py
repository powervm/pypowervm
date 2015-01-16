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
        uuid = '089ffb20-5d19-4a8c-bb80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual(uuid, pvm_uuid)

        uuid = '989ffb20-5d19-4a8c-bb80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual('1' + uuid[1:], pvm_uuid)

        uuid = 'c89ffb20-5d19-4a8c-bb80-13650627d985'
        pvm_uuid = uuid_utils.convert_uuid_to_pvm(uuid)
        self.assertEqual('4' + uuid[1:], pvm_uuid)
