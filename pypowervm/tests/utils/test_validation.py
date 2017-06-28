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

import mock
import testtools

from pypowervm.utils import validation as vldn
from pypowervm.wrappers import base_partition as bp
from pypowervm.wrappers import logical_partition as lpar
from pypowervm.wrappers import managed_system as mgd_sys


class TestValidator(testtools.TestCase):
    """Unit tests for validation."""

    def setUp(self):
        super(TestValidator, self).setUp()

        def _bld_mgd_sys(proc_units_avail=20.0, mem_free=32768,
                         system_name='default_sys_name',
                         max_procs_per_aix_linux_lpar=10,
                         max_sys_procs_limit=15,
                         max_vcpus_per_aix_linux_lpar=10,
                         max_sys_vcpus_limit=15,
                         dynamic_srr_capable=True):
            # Build a fake managed system wrapper
            mngd_sys = mock.MagicMock(spec=mgd_sys.System)
            mngd_sys.system_name = system_name
            mngd_sys.proc_units_avail = proc_units_avail
            mngd_sys.memory_free = mem_free
            mngd_sys.max_procs_per_aix_linux_lpar = (
                max_procs_per_aix_linux_lpar)
            mngd_sys.max_sys_procs_limit = max_sys_procs_limit
            mngd_sys.max_vcpus_per_aix_linux_lpar = (
                max_vcpus_per_aix_linux_lpar)
            mngd_sys.max_sys_vcpus_limit = max_sys_vcpus_limit
            mngd_sys.get_capability.return_value = dynamic_srr_capable
            return mngd_sys

        def _bld_lpar(proc_units=1.0, min_mem=512, des_mem=2048, max_mem=4096,
                      has_dedicated=False, name='default', rmc_state='active',
                      mem_dlpar=True, proc_dlpar=True, state='running',
                      env='AIX/Linux', proc_compat='Default', srr_enabled=True,
                      min_vcpus=1, des_vcpus=2, max_vcpus=4,
                      min_proc_units=0.1, max_proc_units=1.0, pool_id=None,
                      exp_factor=0.0, ame_enabled=False):
            lpar_w = mock.MagicMock()
            # name, states, env, etc.
            lpar_w.name = name
            lpar_w.state = state
            lpar_w.rmc_state = rmc_state
            lpar_w.env = env
            lpar_w.proc_compat_mode = proc_compat
            lpar_w.srr_enabled = srr_enabled
            # Proc
            lpar_w.proc_config.has_dedicated = has_dedicated
            if has_dedicated:
                lpar_w.proc_config.dedicated_proc_cfg.desired = proc_units
                lpar_w.proc_config.dedicated_proc_cfg.max = max_vcpus
                lpar_w.proc_config.dedicated_proc_cfg.min = min_vcpus
            else:
                lpar_w.proc_config.shared_proc_cfg.desired_units = proc_units
                lpar_w.proc_config.shared_proc_cfg.desired_virtual = des_vcpus
                lpar_w.proc_config.shared_proc_cfg.max_virtual = max_vcpus
                lpar_w.proc_config.shared_proc_cfg.min_virtual = min_vcpus
                lpar_w.proc_config.shared_proc_cfg.pool_id = (
                    pool_id if pool_id else 0)
                lpar_w.proc_config.shared_proc_cfg.min_units = min_proc_units
                lpar_w.proc_config.shared_proc_cfg.max_units = max_proc_units
            # Mem
            lpar_w.mem_config.desired = des_mem
            lpar_w.mem_config.min = min_mem
            lpar_w.mem_config.max = max_mem
            lpar_w.mem_config.exp_factor = exp_factor
            # Can Modify
            if (state != bp.LPARState.NOT_ACTIVATED
               and rmc_state != bp.RMCState.ACTIVE):
                    lpar_w.can_modify_proc.return_value = (False, 'Bad RMC')
                    lpar_w.can_modify_mem.return_value = (False, 'Bad RMC')
            else:
                # Doesn't matter what the message is unless it's bad
                # so always make it bad
                lpar_w.can_modify_proc.return_value = (proc_dlpar,
                                                       'Bad proc DLPAR')
                lpar_w.can_modify_mem.return_value = (mem_dlpar,
                                                      'Bad mem DLPAR')
            mocked = mock.MagicMock(spec_set=lpar.LPAR, return_value=lpar_w)
            return mocked()

        self.mngd_sys = _bld_mgd_sys()
        self.mngd_sys_no_dyn_srr = _bld_mgd_sys(dynamic_srr_capable=False)
        self.lpar_21_procs = _bld_lpar(proc_units=21.0, name='lpar_21_procs')
        self.lpar_1_proc = _bld_lpar()
        self.lpar_11_vcpus = _bld_lpar(des_vcpus=11, name='11_vcpus')
        self.lpar_16_max_vcpus = _bld_lpar(max_vcpus=16, name='16_max_vcpus')
        self.lpar_1_proc_ded = _bld_lpar(has_dedicated=True, name='1_proc_ded')
        self.lpar_11_proc_ded = _bld_lpar(proc_units=11, has_dedicated=True,
                                          name='11_proc_ded')
        self.lpar_16_proc_max_ded = _bld_lpar(max_vcpus=16, has_dedicated=True,
                                              name='16_proc_max_ded')
        self.lpar_21_proc_ded = _bld_lpar(proc_units=21, has_dedicated=True,
                                          name='21_proc_ded')
        self.lpar_no_rmc = _bld_lpar(rmc_state='inactive')
        self.lpar_bad_mem_dlpar = _bld_lpar(mem_dlpar=False)
        self.lpar_bad_proc_dlpar = _bld_lpar(proc_dlpar=False)
        self.lpar_48g_mem = _bld_lpar(des_mem=48000, name='lpar_48g_mem')

        self.lpar_1_min_vcpus = _bld_lpar(min_vcpus=1, name='1_min_vcpus')
        self.lpar_2_min_vcpus = _bld_lpar(min_vcpus=2, name='2_min_vcpus')
        self.lpar_1_min_proc_units = _bld_lpar(min_proc_units=0.1,
                                               name='0.1_min_procs')
        self.lpar_3_min_proc_units = _bld_lpar(min_proc_units=0.3,
                                               name='0.3_min_procs')
        self.lpar_6_max_proc_units = _bld_lpar(max_proc_units=0.6,
                                               name='0.6_max_procs')
        self.lpar_9_max_proc_units = _bld_lpar(max_proc_units=0.9,
                                               name='0.9_max_procs')
        self.lpar_6_max_vcpus = _bld_lpar(max_vcpus=6, name='6_max_vcpus')
        self.lpar_8_max_vcpus = _bld_lpar(max_vcpus=8, name='8_max_vcpus')
        self.lpar_512mb_min_mem = _bld_lpar(min_mem=512, name='512_min_mem')
        self.lpar_1gb_min_mem = _bld_lpar(min_mem=1024, name='1gb_min_mem')
        self.lpar_6g_max_mem = _bld_lpar(max_mem=6144, name='6gb_max_mem')
        self.lpar_8g_max_mem = _bld_lpar(max_mem=8192, name='8gb_max_mem')
        self.lpar_default_spp = _bld_lpar(pool_id=0, name='default_spp')
        self.lpar_non_default_spp = _bld_lpar(pool_id=2,
                                              name='non_default_spp')
        self.lpar_power8_proc_compat = _bld_lpar(proc_compat="POWER8",
                                                 name='power8_compat_mode')
        self.lpar_srr_disabled = _bld_lpar(srr_enabled=False,
                                           name='srr_disabled')
        self.lpar_1_proc_ded_inactive = _bld_lpar(has_dedicated=True,
                                                  name='1_proc_ded_inactive',
                                                  state='not activated')
        self.lpar_22_procs = _bld_lpar(proc_units=22.0, name='lpar_22_procs')
        self.lpar_4_proc_ded = _bld_lpar(proc_units=4.0,
                                         has_dedicated=True, name='4_proc_ded')
        self.lpar_22_proc_ded = _bld_lpar(proc_units=22, has_dedicated=True,
                                          name='21_proc_ded')
        self.lpar_4g_mem = _bld_lpar(des_mem=4096, name='4gb_mem')
        self.lpar_6g_mem = _bld_lpar(des_mem=6144, name='6gb_mem')
        self.lpar_1dot6_proc_units = _bld_lpar(proc_units=1.6,
                                               name='1.6_procs')
        self.lpar_2dot2_proc_units = _bld_lpar(proc_units=2.2,
                                               name='2.2_procs')
        self.lpar_1_vcpus = _bld_lpar(des_vcpus=1, name='lpar_1_vcpus')
        self.lpar_not_activated = _bld_lpar(name='lpar_not_activated',
                                            state='not activated')
        self.lpar_running = _bld_lpar(name='lpar_running', state='running')
        self.lpar_starting = _bld_lpar(name='lpar_starting', state='starting')
        self.lpar_ame_2 = _bld_lpar(name='ame_2', exp_factor=2.0,
                                    ame_enabled=True)
        self.lpar_ame_3 = _bld_lpar(name='ame_3', exp_factor=3.0,
                                    ame_enabled=True)

    def test_validator(self):
        # Test desired proc units > host avail proc units fails for shared
        vldr = vldn.LPARWrapperValidator(self.lpar_21_procs, self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)

        # Test desired proc units < host avail proc units passes for shared
        vldn.LPARWrapperValidator(self.lpar_1_proc,
                                  self.mngd_sys).validate_all()

        # Test desired proc units > host avail proc units fails for dedicated
        vldr = vldn.LPARWrapperValidator(self.lpar_21_proc_ded, self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)

        # Test desired proc units < host avail proc units passes for dedicated
        vldn.LPARWrapperValidator(self.lpar_1_proc_ded,
                                  self.mngd_sys).validate_all()

        # Test resize fails with inactive rmc
        vldr = vldn.LPARWrapperValidator(self.lpar_1_proc, self.mngd_sys,
                                         cur_lpar_w=self.lpar_no_rmc)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test resize fails with no mem dlpar
        vldr = vldn.LPARWrapperValidator(self.lpar_1_proc, self.mngd_sys,
                                         cur_lpar_w=self.lpar_bad_mem_dlpar)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test resize fails with no proc dlpar
        vldr = vldn.LPARWrapperValidator(self.lpar_1_proc, self.mngd_sys,
                                         cur_lpar_w=self.lpar_bad_proc_dlpar)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)

        # Test dedicated procs > host max allowed procs per lpar fails
        vldr = vldn.LPARWrapperValidator(self.lpar_11_proc_ded, self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test dedicated max procs > host max sys procs limit fails
        vldr = vldn.LPARWrapperValidator(self.lpar_16_proc_max_ded,
                                         self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test shared desired vcpus > host max allowed vcpus per lpar fails
        vldr = vldn.LPARWrapperValidator(self.lpar_11_vcpus, self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test shared desired max vcpus > host max sys vcpus limit fails
        vldr = vldn.LPARWrapperValidator(self.lpar_16_max_vcpus, self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)

        # Test desired memory > host available memory fails
        vldr = vldn.LPARWrapperValidator(self.lpar_48g_mem, self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)

        # Test changing min vcpus fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_1_min_vcpus, self.mngd_sys,
                                         cur_lpar_w=self.lpar_2_min_vcpus)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing max vcpus fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_8_max_vcpus, self.mngd_sys,
                                         cur_lpar_w=self.lpar_6_max_vcpus)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing min proc units fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_3_min_proc_units,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_min_proc_units)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing max proc units fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_9_max_proc_units,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_6_max_proc_units)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing min memory fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_512mb_min_mem,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_1gb_min_mem)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing max memory fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_8g_max_mem, self.mngd_sys,
                                         cur_lpar_w=self.lpar_6g_max_mem)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing AME expansion factor from 2 to 3 fails active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_ame_3, self.mngd_sys,
                                         cur_lpar_w=self.lpar_ame_2)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test toggling AME fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_ame_2, self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_proc)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test resizing lpar from defaultSPP to non-defaultSPP passes
        vldr = vldn.LPARWrapperValidator(self.lpar_non_default_spp,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_default_spp)
        vldr.validate_all()
        # Test resizing lpar from non-defaultSPP to defaultSPP passes
        vldr = vldn.LPARWrapperValidator(self.lpar_default_spp,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_non_default_spp)
        vldr.validate_all()
        # Test changing from dedicated to non-defaultSPP passes
        vldr = vldn.LPARWrapperValidator(self.lpar_non_default_spp,
                                         self.mngd_sys,
                                         self.lpar_1_proc_ded_inactive)
        vldr.validate_all()
        # Test changing processor mode (shared -> ded) fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_1_proc_ded,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_proc)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing processor mode (ded to shared) fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_1_proc,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_proc_ded)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing processor compatibility mode fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_power8_proc_compat,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_proc)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test changing SRR capabilty fails for active resize
        vldr = vldn.LPARWrapperValidator(self.lpar_srr_disabled,
                                         self.mngd_sys_no_dyn_srr,
                                         cur_lpar_w=self.lpar_1_proc)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # ...unless dynamic_srr_capable
        vldr = vldn.LPARWrapperValidator(self.lpar_srr_disabled,
                                         self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_proc)
        vldr.validate_all()
        # Test desired delta proc units > host avail proc units fails
        # during resize (shared -> shared)
        vldr = vldn.LPARWrapperValidator(self.lpar_22_procs, self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_proc)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test desired delta proc units <= host avail proc units passes
        # during resize (shared -> shared)
        vldn.LPARWrapperValidator(self.lpar_21_procs,
                                  self.mngd_sys,
                                  cur_lpar_w=self.lpar_1_proc).validate_all()
        # Test desired delta proc units > host avail proc units fails
        # during resize (dedicated -> dedicated)
        vldr = vldn.LPARWrapperValidator(self.lpar_22_proc_ded, self.mngd_sys,
                                         cur_lpar_w=self.lpar_1_proc_ded)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)
        # Test desired delta proc units <= host avail proc units passes
        # during resize (dedicated -> dedicated)
        vldn.LPARWrapperValidator(self.lpar_4_proc_ded,
                                  self.mngd_sys,
                                  self.lpar_1_proc_ded).validate_all()
        # Test resize delta mem
        mem_vldr = vldn.MemValidator(self.lpar_6g_mem, self.mngd_sys,
                                     cur_lpar_w=self.lpar_4g_mem)
        mem_vldr._populate_new_values()
        mem_vldr._populate_resize_diffs()
        self.assertEqual(2048, mem_vldr.delta_des_mem,
                         'Incorrect resize delta memory calculation')
        # Test resize delta procs
        proc_vldr = vldn.ProcValidator(self.lpar_4_proc_ded, self.mngd_sys,
                                       cur_lpar_w=self.lpar_1_proc_ded)
        proc_vldr._populate_new_values()
        proc_vldr._populate_resize_diffs()
        self.assertEqual(3, proc_vldr.delta_des_vcpus,
                         'Incorrect resize delta proc calculation'
                         ' in dedicated mode')
        proc_vldr = vldn.ProcValidator(self.lpar_2dot2_proc_units,
                                       self.mngd_sys,
                                       cur_lpar_w=self.lpar_1dot6_proc_units)
        proc_vldr._populate_new_values()
        proc_vldr._populate_resize_diffs()
        self.assertEqual(0.60, proc_vldr.delta_des_vcpus,
                         'Incorrect resize delta proc calculation in'
                         ' shared mode')
        proc_vldr = vldn.ProcValidator(self.lpar_1dot6_proc_units,
                                       self.mngd_sys,
                                       cur_lpar_w=self.lpar_1_proc_ded)
        proc_vldr._populate_new_values()
        proc_vldr._populate_resize_diffs()
        self.assertEqual(0.60, proc_vldr.delta_des_vcpus,
                         'Incorrect delta proc calculation while resizing '
                         'from dedicated to shared mode')
        proc_vldr = vldn.ProcValidator(self.lpar_4_proc_ded, self.mngd_sys,
                                       cur_lpar_w=self.lpar_1dot6_proc_units)
        proc_vldr._populate_new_values()
        proc_vldr._populate_resize_diffs()
        self.assertEqual(2.40, proc_vldr.delta_des_vcpus,
                         'Incorrect delta proc calculation while resizing '
                         'from shared to dedicated mode')
        # Test resizing not activated state lpar makes inactive_resize_checks
        with mock.patch('pypowervm.utils.validation.ProcValidator.'
                        '_validate_inactive_resize') as inactive_resize_checks:
            proc_vldr = vldn.ProcValidator(self.lpar_not_activated,
                                           self.mngd_sys,
                                           cur_lpar_w=self.lpar_not_activated)
            proc_vldr.validate()
            self.assertTrue(inactive_resize_checks.called,
                            'Inactive resize validations not performed.')
        # Test resizing running state lpar makes active_resize_checks
        with mock.patch('pypowervm.utils.validation.ProcValidator.'
                        '_validate_active_resize') as active_resize_checks:
            proc_vldr = vldn.ProcValidator(self.lpar_running, self.mngd_sys,
                                           cur_lpar_w=self.lpar_running)
            proc_vldr.validate()
            self.assertTrue(active_resize_checks.called,
                            'Active resize validations not performed.')
        # Test resizing starting state lpar makes active_resize_checks
        with mock.patch('pypowervm.utils.validation.ProcValidator.'
                        '_validate_active_resize') as active_resize_checks:
            proc_vldr = vldn.ProcValidator(self.lpar_starting, self.mngd_sys,
                                           cur_lpar_w=self.lpar_starting)
            proc_vldr.validate()
            self.assertTrue(active_resize_checks.called,
                            'Active resize validations not performed.')
