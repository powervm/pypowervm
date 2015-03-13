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

import os
import unittest

import mock
import six

from pypowervm.tests.wrappers.util import xml_sections
from pypowervm.utils import lpar_builder as lpar_bldr
from pypowervm.wrappers import logical_partition as lpar


_MS_HTTPRESP_FILE = "managedsystem.txt"


class TestLPARBuilder(unittest.TestCase):
    """Unit tests for the lpar builder."""

    def setUp(self):
        super(TestLPARBuilder, self).setUp()
        dirname = os.path.dirname(__file__)
        file_name = os.path.join(dirname, 'data', 'lpar_builder.txt')
        self.sections = xml_sections.load_xml_sections(file_name)

        # Build a fake managed system wrapper
        self.mngd_sys = mock.Mock()
        type(self.mngd_sys).proc_units_avail = (
            mock.PropertyMock(return_value=20.0))
        type(self.mngd_sys).memory_region_size = (
            mock.PropertyMock(return_value=128))

    def assert_xml(self, entry, string):
        self.assertEqual(entry.element.toxmlstring(),
                         six.b(string.rstrip('\n')))

    def test_builder(self):
        # Build the minimum attributes, Shared Procs
        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertNotEqual(bldr, None)

        new_lpar = bldr.build()
        self.assertNotEqual(new_lpar, None)
        self.assert_xml(new_lpar, self.sections['shared_lpar'])

        # Build the minimum attributes, Dedicated Procs
        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1, dedicated_proc=True)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertNotEqual(bldr, None)

        new_lpar = bldr.build()
        self.assertNotEqual(new_lpar, None)
        self.assert_xml(new_lpar.entry, self.sections['dedicated_lpar'])

        # Build the minimum attributes, Dedicated Procs = 'true'
        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1, dedicated_proc='true')
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar.entry, self.sections['dedicated_lpar'])

        # Leave out memory
        attr = dict(name=lpar, env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        self.assertRaises(lpar_bldr.LPARBuilderException,
                          lpar_bldr.LPARBuilder, attr, stdz)

        # Bad memory lmb multiple
        attr = dict(name='lpar', memory=3333,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(ValueError, bldr.build)

        # Check the validation of the LPAR type when not specified
        attr = dict(name='TheName', memory=1024, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar, self.sections['shared_lpar'])

        # LPAR name too long
        attr = dict(name='lparlparlparlparlparlparlparlparlparlparlparlpar'
                    'lparlparlparlparlparlparlparlparlparlparlparlparlparlpar',
                    memory=1024,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(lpar_bldr.LPARBuilderException, bldr.build)

        # Bad LPAR type
        attr = dict(name='lpar', memory=1024,
                    env='BADLPARType', vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(TypeError, bldr.build)

        # Bad IO Slots
        attr = dict(name='lpar', memory=1024, max_io_slots=0,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(ValueError, bldr.build)

        attr = dict(name='lpar', memory=1024, max_io_slots=(65534+1),
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(ValueError, bldr.build)

        # Good non-defaulted IO Slots
        attr = dict(name='lpar', memory=1024, max_io_slots=64,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assert_xml(new_lpar, self.sections['shared_lpar'])

        # Uncapped / capped shared procs
        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1,
                    sharing_mode=lpar.SharingModesEnum.CAPPED)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar, self.sections['capped_lpar'])

        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1,
                    sharing_mode=lpar.SharingModesEnum.UNCAPPED,
                    uncapped_weight=100)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar, self.sections['uncapped_lpar'])

        # Build dedicated but only via dedicated attributes
        m = lpar.DedicatedSharingModesEnum.SHARE_IDLE_PROCS_ALWAYS
        attr = dict(name='TheName', env=lpar.LPARTypeEnum.AIXLINUX,
                    memory=1024, vcpu=1, sharing_mode=m)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar.entry,
                        self.sections['ded_lpar_sre_idle_procs_always'])

        # Desired mem outside min
        attr = dict(name='lpar', memory=1024,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1,
                    min_mem=2048)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(ValueError, bldr.build)

        # Desired mem outside max
        attr = dict(name='lpar', memory=5000,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1,
                    max_mem=2048)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(ValueError, bldr.build)

        # Desired vcpu outside min
        attr = dict(name='lpar', memory=2048,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=1,
                    min_vcpu=2)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(ValueError, bldr.build)

        # Desired vcpu outside max
        attr = dict(name='lpar', memory=2048,
                    env=lpar.LPARTypeEnum.AIXLINUX, vcpu=3,
                    max_vcpu=2)
        stdz = lpar_bldr.DefaultStandardize(attr, self.mngd_sys)
        bldr = lpar_bldr.LPARBuilder(attr, stdz)
        self.assertRaises(ValueError, bldr.build)
