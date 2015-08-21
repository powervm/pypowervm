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
                         max_sys_vcpus_limit=15):
            # Build a fake managed system wrapper
            mngd_sys = mock.MagicMock()
            mngd_sys.system_name = system_name
            mngd_sys.proc_units_avail = proc_units_avail
            mngd_sys.memory_free = mem_free
            mngd_sys.max_procs_per_aix_linux_lpar =\
                max_procs_per_aix_linux_lpar
            mngd_sys.max_sys_procs_limit =\
                max_sys_procs_limit
            mngd_sys.max_vcpus_per_aix_linux_lpar =\
                max_vcpus_per_aix_linux_lpar
            mngd_sys.max_sys_vcpus_limit =\
                max_sys_vcpus_limit
            mocked = mock.MagicMock(spec=mgd_sys.System, return_value=mngd_sys)
            return mocked()

        def _bld_lpar(proc_units=1.0, des_mem=2048, has_dedicated=False,
                      name='default', rmc_state='active', state='running',
                      des_vcpus=2, max_vcpus=4):
            lpar_w = mock.MagicMock()
            # name, states, etc.
            lpar_w.name = name
            lpar_w.state = state
            lpar_w.rmc_state = rmc_state
            # Proc
            lpar_w.proc_config.has_dedicated = has_dedicated
            if has_dedicated:
                lpar_w.proc_config.dedicated_proc_cfg.desired = proc_units
                lpar_w.proc_config.dedicated_proc_cfg.max = max_vcpus
            else:
                lpar_w.proc_config.shared_proc_cfg.desired_units = proc_units
                lpar_w.proc_config.shared_proc_cfg.desired_virtual = des_vcpus
                lpar_w.proc_config.shared_proc_cfg.max_virtual = max_vcpus
            # Mem
            lpar_w.mem_config.desired = des_mem
            mocked = mock.MagicMock(spec_set=lpar.LPAR, return_value=lpar_w)
            return mocked()

        self.mngd_sys = _bld_mgd_sys()
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
        self.lpar_48g_mem = _bld_lpar(des_mem=48000, name='lpar_48g_mem')

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
