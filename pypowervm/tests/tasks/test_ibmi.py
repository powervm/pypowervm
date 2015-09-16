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


import logging
import mock
import testtools

from pypowervm.tasks import ibmi
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as pvm_fx
from pypowervm.tests.wrappers.util import pvmhttp
from pypowervm.wrappers import base_partition as pvm_bp
from pypowervm.wrappers import logical_partition as pvm_lpar
from pypowervm.wrappers import network as pvm_net
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIO_MULTI_MAP_FILE2 = 'fake_vios_mappings.txt'


class TestIBMi(testtools.TestCase):
    """Unit Tests for IBMi changes."""

    def setUp(self):
        super(TestIBMi, self).setUp()
        self.apt = self.useFixture(pvm_fx.AdapterFx(
            traits=pvm_fx.LocalPVMTraits)).adpt

        self.vios_resp = tju.load_file(VIO_MULTI_MAP_FILE2,
                                       self.apt)
        self.viosw = [pvm_vios.VIOS.wrap(self.vios_resp)]

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.wrap')
    def test_update_load_src(self, mock_viosw):
        mock_viosw.return_value = self.viosw
        instance = mock.MagicMock()
        mock_lparw = mock.MagicMock()
        mock_lparw.id = 22
        # Test update load source with vscsi boot
        boot_type = 'vscsi'
        entry = ibmi.update_load_src(self.apt, mock_lparw, boot_type)
        self.assertEqual('b', entry.desig_ipl_src)
        self.assertEqual('normal', entry.keylock_pos)
        self.assertEqual('2', entry.io_config.tagged_io.load_src)
        self.assertEqual('2', entry.io_config.tagged_io.alt_load_src)

        # Test update load source with npiv boot
        boot_type = 'npiv'
        entry = ibmi.update_load_src(self.apt, mock_lparw, boot_type)
        self.assertEqual('b', entry.desig_ipl_src)
        self.assertEqual('normal', entry.keylock_pos)
        self.assertEqual('3', entry.io_config.tagged_io.load_src)
        self.assertEqual('3', entry.io_config.tagged_io.alt_load_src)
