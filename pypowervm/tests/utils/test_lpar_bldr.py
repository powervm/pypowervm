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

import six

from pypowervm.tests.wrappers.util import xml_sections
from pypowervm.utils import lpar_builder as lpar_bldr
from pypowervm.wrappers import logical_partition as lpar

import unittest


class TestLPARBuilder(unittest.TestCase):
    """Unit tests for the lpar builder."""

    def setUp(self):
        super(TestLPARBuilder, self).setUp()
        self.sections = xml_sections.load_xml_sections('lpar_builder.txt')

    def assert_xml(self, entry, string):
        self.assertEqual(entry.element.toxmlstring(),
                         six.b(string.rstrip('\n')))

    def test_builder(self):
        # Build the minimum attributes, Shared Procs
        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertNotEqual(bldr, None)

        new_lpar = bldr.build()
        self.assertNotEqual(new_lpar, None)
        self.assert_xml(new_lpar, self.sections['shared_lpar'])

        # Build the minimum attributes, Shared Procs
        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1, dedicated_proc=True)
        stdz = lpar_bldr.DefaultStandardize(attr)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertNotEqual(bldr, None)

        new_lpar = bldr.build()
        self.assertNotEqual(new_lpar, None)
        self.assert_xml(new_lpar.entry, self.sections['dedicated_lpar'])

        # Leave out memory
        attr = dict(name=lpar, env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr)
        self.assertRaises(lpar_bldr.LPARBuilderException,
                          lpar_bldr.LPARBuilder, attr, stdz)
