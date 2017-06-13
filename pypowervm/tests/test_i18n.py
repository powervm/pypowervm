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

import mock
import os
import unittest

from pypowervm.i18n import _


class TranslationTests(unittest.TestCase):
    """Test internationalization library."""

    @mock.patch.dict(os.environ, {
        # Ensure we're using our test message catalog
        'PYPOWERVM_LOCALEDIR': os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'locale'),
        # Ensure we're using the expected language
        'LANG': 'en_US'})
    def test_translate(self):
        self.assertEqual(_("This is a test"), "This is an English test")

        self.assertEqual(
            _("This is a message for which a translation doesn't exist"),
            "This is a message for which a translation doesn't exist")
