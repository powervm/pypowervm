# Copyright 2016 IBM Corp.
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
"""Test pypowervm.tasks.slot_map."""

import mock
import testtools

from pypowervm.tasks import slot_map
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers import virtual_io_server as vios
from pypowervm.wrappers import network as net

# Load data files just once, since the wrappers will be read-only
vfeed = vios.VIOS.wrap(pvmhttp.load_pvm_resp('fake_vios_ssp_npiv.txt'))
cnafeed1 = net.CNA.wrap(pvmhttp.load_pvm_resp('cna_feed1.txt'))
cnafeed2 = net.CNA.wrap(pvmhttp.load_pvm_resp('cna_feed2.txt'))
vswitchfeed = net.VSwitch.wrap(pvmhttp.load_pvm_resp('vswitch_feed.txt'))


class TestSlotMapBase(testtools.TestCase):
    pass
