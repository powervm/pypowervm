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

import uuid

import mock
import six
import testtools

from pypowervm.tests import test_fixtures as fx
from pypowervm.tests.test_utils import xml_sections
from pypowervm.utils import lpar_builder as lpar_bldr
import pypowervm.utils.uuid as pvm_uuid
from pypowervm.wrappers import base_partition as bp
from pypowervm.wrappers import logical_partition as lpar

LPAR_BLDR_DATA = 'lpar_builder.txt'


class TestLPARBuilder(testtools.TestCase):
    """Unit tests for the lpar builder."""

    def setUp(self):
        super(TestLPARBuilder, self).setUp()
        self.sections = xml_sections.load_xml_sections(LPAR_BLDR_DATA)
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

        def _bld_mgd_sys(proc_units, mem_reg, srr, pcm, ame):
            # Build a fake managed system wrapper
            mngd_sys = mock.Mock()
            type(mngd_sys).proc_units_avail = (
                mock.PropertyMock(return_value=proc_units))
            type(mngd_sys).memory_region_size = (
                mock.PropertyMock(return_value=mem_reg))

            def get_cap(cap):
                capabilities = {
                    'simplified_remote_restart_capable': srr,
                    'ibmi_restrictedio_capable': True,
                    'active_memory_expansion_capable': ame
                }
                return capabilities[cap]
            mngd_sys.get_capability.side_effect = get_cap

            type(mngd_sys).proc_compat_modes = (
                mock.PropertyMock(return_value=pcm))
            return mngd_sys

        self.mngd_sys = _bld_mgd_sys(20.0, 128, True,
                                     bp.LPARCompat.ALL_VALUES, False)
        self.mngd_sys_no_srr = _bld_mgd_sys(20.0, 128, False, ['POWER6'],
                                            False)
        self.mngd_sys_ame = _bld_mgd_sys(20.0, 128, True,
                                         bp.LPARCompat.ALL_VALUES, True)
        self.stdz_sys1 = lpar_bldr.DefaultStandardize(self.mngd_sys)
        self.stdz_sys2 = lpar_bldr.DefaultStandardize(self.mngd_sys_no_srr)
        self.stdz_sys3 = lpar_bldr.DefaultStandardize(self.mngd_sys_ame)

    def assert_xml(self, entry, string):
        self.assertEqual(entry.element.toxmlstring(),
                         six.b(string.rstrip('\n')))

    def test_proc_modes(self):
        # Base minimum attrs
        attr = dict(name='TheName', memory=1024, vcpu=1)
        # No proc keys specified
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertFalse(bldr._shared_proc_keys_specified())
        self.assertFalse(bldr._dedicated_proc_keys_specified())
        # Default is shared
        self.assertTrue(bldr._shared_procs_specified())
        # Shared proc keys specified
        for key in ('proc_units', 'max_proc_units', 'min_proc_units',
                    'uncapped_weight'):
            bldr = lpar_bldr.LPARBuilder(self.adpt, dict(attr, **{key: 1}),
                                         self.stdz_sys1)
            self.assertTrue(bldr._shared_proc_keys_specified())
            self.assertFalse(bldr._dedicated_proc_keys_specified())
            self.assertTrue(bldr._shared_procs_specified())
        # Shared modes specified
        for mode in ('capped', 'uncapped'):
            bldr = lpar_bldr.LPARBuilder(
                self.adpt, dict(attr, sharing_mode=mode), self.stdz_sys1)
            self.assertTrue(bldr._shared_proc_keys_specified())
            self.assertFalse(bldr._dedicated_proc_keys_specified())
            self.assertTrue(bldr._shared_procs_specified())
        # Dedicated modes specified
        for mode in ('sre idle proces', 'sre idle procs active',
                     'sre idle procs always', 'keep idle procs'):
            bldr = lpar_bldr.LPARBuilder(
                self.adpt, dict(attr, sharing_mode=mode), self.stdz_sys1)
            self.assertFalse(bldr._shared_proc_keys_specified())
            self.assertTrue(bldr._dedicated_proc_keys_specified())
            self.assertFalse(bldr._shared_procs_specified())
        # Dedicated proc explicitly true
        bldr = lpar_bldr.LPARBuilder(
            self.adpt, dict(attr, dedicated_proc='TRUE'), self.stdz_sys1)
        self.assertFalse(bldr._shared_proc_keys_specified())
        self.assertFalse(bldr._dedicated_proc_keys_specified())
        self.assertFalse(bldr._shared_procs_specified())
        # Dedicated proc explicitly false
        bldr = lpar_bldr.LPARBuilder(
            self.adpt, dict(attr, dedicated_proc='NO'), self.stdz_sys1)
        self.assertFalse(bldr._shared_proc_keys_specified())
        self.assertFalse(bldr._dedicated_proc_keys_specified())
        self.assertTrue(bldr._shared_procs_specified())

    def test_builder(self):
        # Build the minimum attributes, Shared Procs
        attr = dict(name='TheName', env=bp.LPARType.AIXLINUX, memory=1024,
                    vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertIsNotNone(bldr)

        new_lpar = bldr.build()
        self.assertIsNotNone(new_lpar)
        self.assert_xml(new_lpar, self.sections['shared_lpar'])
        self.assertEqual('TheName', new_lpar.name)

        # Rebuild the same lpar with a different name
        attr['name'] = 'NewName'
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        rbld_lpar = bldr.rebuild(new_lpar)
        self.assertEqual('NewName', rbld_lpar.name)

        # Build the minimum attributes, Dedicated Procs
        attr = dict(name='TheName', env=bp.LPARType.AIXLINUX, memory=1024,
                    vcpu=1, dedicated_proc=True)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertIsNotNone(bldr)

        new_lpar = bldr.build()
        self.assertIsNotNone(new_lpar)
        self.assert_xml(new_lpar.entry, self.sections['dedicated_lpar'])

        # Build the minimum attributes, Dedicated Procs = 'true'
        attr = dict(name='TheName', env=bp.LPARType.AIXLINUX, memory=1024,
                    vcpu=1, dedicated_proc='true')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar.entry, self.sections['dedicated_lpar'])

        # Leave out memory
        attr = dict(name=lpar, env=bp.LPARType.AIXLINUX, vcpu=1)
        self.assertRaises(
            lpar_bldr.LPARBuilderException, lpar_bldr.LPARBuilder, self.adpt,
            attr, self.stdz_sys1)

        # Bad memory lmb multiple
        attr = dict(name='lpar', memory=3333, env=bp.LPARType.AIXLINUX, vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Check the validation of the LPAR type when not specified
        attr = dict(name='TheName', memory=1024, vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar, self.sections['shared_lpar'])

        # LPAR name too long
        attr = dict(name='lparlparlparlparlparlparlparlparlparlparlparlpar'
                    'lparlparlparlparlparlparlparlparlparlparlparlparlparlpar',
                    memory=1024, env=bp.LPARType.AIXLINUX, vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(lpar_bldr.LPARBuilderException, bldr.build)

        # Test setting uuid
        uuid1 = pvm_uuid.convert_uuid_to_pvm(str(uuid.uuid4()))
        attr = dict(name='lpar', memory=1024, uuid=uuid1, vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        lpar_w = bldr.build()
        self.assertEqual(uuid1.upper(), lpar_w.uuid)

        # Test setting id
        id1 = 1234
        attr = dict(name='lpar', memory=1024, uuid=uuid1, vcpu=1, id=id1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        lpar_w = bldr.build()
        self.assertEqual(id1, lpar_w.id)

        # Bad LPAR type
        attr = dict(name='lpar', memory=1024, env='BADLPARType', vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Bad IO Slots
        attr = dict(name='lpar', memory=1024, max_io_slots=0,
                    env=bp.LPARType.AIXLINUX, vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        attr = dict(name='lpar', memory=1024, max_io_slots=(65534+1),
                    env=bp.LPARType.AIXLINUX, vcpu=1)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Good non-defaulted IO Slots and SRR
        attr = dict(name='TheName', memory=1024, max_io_slots=64,
                    env=bp.LPARType.AIXLINUX, vcpu=1, srr_capability=False)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar, self.sections['shared_lpar'])

        # Bad SRR value.
        attr = dict(name='lpar', memory=1024, max_io_slots=64,
                    env=bp.LPARType.AIXLINUX, vcpu=1, srr_capability='Frog')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Uncapped / capped shared procs
        attr = dict(name='TheName', env=bp.LPARType.AIXLINUX, memory=1024,
                    vcpu=1, sharing_mode=bp.SharingMode.CAPPED,
                    srr_capability='true')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar, self.sections['capped_lpar'])

        # Uncapped and no SRR capability
        attr = dict(name='TheName', env=bp.LPARType.AIXLINUX, memory=1024,
                    vcpu=1, sharing_mode=bp.SharingMode.UNCAPPED,
                    uncapped_weight=100, processor_compatibility='POWER6')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys2)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar, self.sections['uncapped_lpar'])

        # Build dedicated but only via dedicated attributes
        m = bp.DedicatedSharingMode.SHARE_IDLE_PROCS_ALWAYS
        attr = dict(name='TheName', env=bp.LPARType.AIXLINUX, memory=1024,
                    vcpu=1, sharing_mode=m, processor_compatibility='PoWeR7')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        self.assert_xml(new_lpar.entry,
                        self.sections['ded_lpar_sre_idle_procs_always'])

        # Desired mem outside min
        attr = dict(name='lpar', memory=1024, env=bp.LPARType.AIXLINUX, vcpu=1,
                    min_mem=2048)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Desired mem outside max
        attr = dict(name='lpar', memory=5000, env=bp.LPARType.AIXLINUX, vcpu=1,
                    max_mem=2048)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # AME not supported on host
        attr = dict(name='lpar', memory=1024, env=bp.LPARType.AIXLINUX, vcpu=1,
                    ame_factor='1.5')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # AME outside valid range
        attr = dict(name='lpar', memory=1024, env=bp.LPARType.AIXLINUX, vcpu=1,
                    ame_factor='0.5')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys3)
        self.assertRaises(ValueError, bldr.build)

        # Desired vcpu outside min
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=1,
                    min_vcpu=2)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Desired vcpu outside max
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=3,
                    max_vcpu=2)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Ensure the calculated procs are not below the min
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=3,
                    min_proc_units=3)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        procs = new_lpar.proc_config.shared_proc_cfg
        self.assertEqual(3.0, procs.min_units)

        # Ensure the calculated procs are all 0.5
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=1,
                    proc_units=0.5)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        procs = new_lpar.proc_config.shared_proc_cfg
        self.assertEqual(0.5, procs.min_units)
        self.assertEqual(0.5, procs.max_units)
        self.assertEqual(0.5, procs.desired_units)

        # Create a temp standardizer with a smaller proc units factor
        stdz = lpar_bldr.DefaultStandardize(self.mngd_sys,
                                            proc_units_factor=0.1)
        # Ensure the min, max, and desired proc units works as VCPU is scaled.
        for x in [1, 5, 10, 17, 20]:
            attr = dict(name='lpar', memory=2048, vcpu=x)
            bldr = lpar_bldr.LPARBuilder(self.adpt, attr, stdz)
            new_lpar = bldr.build()
            procs = new_lpar.proc_config.shared_proc_cfg
            self.assertEqual(round(0.1 * x, 2), procs.min_units)
            self.assertEqual(round(0.1 * x, 2), procs.max_units)
            self.assertEqual(round(0.1 * x, 2), procs.desired_units)

        # Ensure the calculated procs are below the max
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=3,
                    max_proc_units=2.1)
        stdz = lpar_bldr.DefaultStandardize(
            self.mngd_sys, proc_units_factor=0.9)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, stdz)
        new_lpar = bldr.build()
        procs = new_lpar.proc_config.shared_proc_cfg
        self.assertEqual(2.1, procs.max_units)

        # Ensure proc units factor is between 0.1 and 1.0
        self.assertRaises(
            lpar_bldr.LPARBuilderException,
            lpar_bldr.DefaultStandardize,
            self.mngd_sys, proc_units_factor=1.01)
        self.assertRaises(
            lpar_bldr.LPARBuilderException,
            lpar_bldr.DefaultStandardize,
            self.mngd_sys, proc_units_factor=0.01)

        # Avail priority outside max
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=3,
                    avail_priority=332)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Avail priority bad parm
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=3,
                    avail_priority='BADVALUE')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertRaises(ValueError, bldr.build)

        # Avail priority at min value
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=3,
                    avail_priority=0)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        self.assertEqual(new_lpar.avail_priority, 0)

        # Avail priority at max value
        attr = dict(name='lpar', memory=2048, env=bp.LPARType.AIXLINUX, vcpu=3,
                    avail_priority=255)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        new_lpar = bldr.build()
        self.assertEqual(new_lpar.avail_priority, 255)

        # Proc compat
        for pc in bp.LPARCompat.ALL_VALUES:
            attr = dict(name='name', memory=1024, vcpu=1,
                        processor_compatibility=pc)
            bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
            new_lpar = bldr.build()
            self.assertEqual(new_lpar.pending_proc_compat_mode, pc)

        attr = dict(name='name', memory=1024, vcpu=1,
                    processor_compatibility='POWER6')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys2)
        new_lpar = bldr.build()
        self.assertEqual(new_lpar.pending_proc_compat_mode, 'POWER6')

        # Ensure failure occurs on validation after the host supported
        # proc modes are loaded and not on convert_value which converts
        # across all acceptable proc modes.
        # This works because 'POWER8' is in LPARCompat.ALL_VALUES
        attr = dict(name='name', memory=1024, vcpu=1,
                    processor_compatibility='POWER8')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys2)
        exp_msg = ("Value 'POWER8' is not valid for field 'Processor "
                   "Compatability Mode' with acceptable choices: ['POWER6']")
        try:
            bldr.build()
        except Exception as e:
            self.assertEqual(six.text_type(e), exp_msg)

        # Build a VIOS
        attr = dict(name='TheName', env=bp.LPARType.VIOS, memory=1024,
                    vcpu=1, dedicated_proc=True)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertIsNotNone(bldr)

        new_lpar = bldr.build()
        self.assertIsNotNone(new_lpar)
        self.assert_xml(new_lpar.entry, self.sections['vios'])

    def test_IBMi(self):
        attr = dict(name='TheName', env=bp.LPARType.OS400, memory=1024,
                    vcpu=1, ame_factor=False)
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertIsNotNone(bldr)

        new_lpar = bldr.build()
        self.assertIsNotNone(new_lpar)
        self.assertTrue(new_lpar.restrictedio)
        tag_io = new_lpar.io_config.tagged_io
        self.assertEqual('HMC', tag_io.console)
        self.assertEqual('0', tag_io.load_src)
        self.assertEqual('NONE', tag_io.alt_load_src)

        attr = dict(name='OS400LPAR', env=bp.LPARType.OS400, memory=1024,
                    vcpu=1, console='CONSOLE', load_src='9', alt_load_src='9')
        bldr = lpar_bldr.LPARBuilder(self.adpt, attr, self.stdz_sys1)
        self.assertIsNotNone(bldr)

        new_lpar = bldr.build()
        self.assertIsNotNone(new_lpar)
        self.assertTrue(new_lpar.restrictedio)
        tag_io = new_lpar.io_config.tagged_io
        self.assertEqual('CONSOLE', tag_io.console)
        self.assertEqual('9', tag_io.load_src)
        self.assertEqual('9', tag_io.alt_load_src)
