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

from pypowervm.tasks import wwpn


class TestWWPN(unittest.TestCase):

    def test_build_wwpn_pair(self):
        # By its nature, this is a random generation algorithm.  Run it
        # several times...just to increase probability of issues.
        i = 0
        while i < 100:
            wwpn_pair = wwpn.build_wwpn_pair(None, None)
            self.assertIsNotNone(wwpn_pair)
            self.assertEqual(2, len(wwpn_pair))
            for elem in wwpn_pair:
                self.assertEqual(16, len(elem))
                int(elem, 16)  # Would throw ValueError if not hex.
            i += 1
