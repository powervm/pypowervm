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
from pypowervm.wrappers.logical_partition import LPAR
from pypowervm.wrappers.managed_system import System


class TestValidator(testtools.TestCase):
    """Unit tests for validation."""

    def setUp(self):
        super(TestValidator, self).setUp()

        def _bld_mgd_sys(proc_units_avail, mem_free):
            # Build a fake managed system wrapper
            mngd_sys = mock.MagicMock()
            mngd_sys.proc_units_avail = proc_units_avail
            mngd_sys.memory_free = mem_free
            mngd_sys.glarbsnarb = "WHAT"
            mocked = mock.MagicMock(spec=System, return_value=mngd_sys)
            return mocked()

        def _bld_lpar(proc_units, des_mem, has_dedicated=False,
                      name='default'):
            lpar_w = mock.MagicMock()
            lpar_w.proc_config.has_dedicated = has_dedicated
            lpar_w.name = name
            if has_dedicated:
                lpar_w.proc_config.dedicated_proc_cfg.desired = proc_units
            else:
                lpar_w.proc_config.shared_proc_cfg.desired_units = proc_units
            mocked = mock.MagicMock(spec_set=LPAR, return_value=lpar_w)
            return mocked()

        self.mngd_sys = _bld_mgd_sys(20.0, 32768)
        self.lpar_21_procs = _bld_lpar(21.0, 2048, name='lpar_21_procs')
        self.lpar_1_proc = _bld_lpar(1.0, 2048, name='lpar_1_proc')

    def test_validator(self):
        vldr = vldn.LPARWrapperValidator(self.lpar_21_procs, self.mngd_sys)
        self.assertRaises(vldn.ValidatorException, vldr.validate_all)

        vldr = vldn.LPARWrapperValidator(self.lpar_1_proc, self.mngd_sys)
