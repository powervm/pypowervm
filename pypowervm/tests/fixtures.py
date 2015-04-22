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
#

from __future__ import absolute_import

import fixtures
import mock


class AdapterFx(fixtures.Fixture):
    """Patch out Session and Adapter."""

    def __init__(self):
        pass

    def setUp(self):
        super(AdapterFx, self).setUp()
        self._sess_patcher = mock.patch('pypowervm.adapter.Session')
        self._adpt_patcher = mock.patch('pypowervm.adapter.Adapter')
        self.sess = self._sess_patcher.start()
        self.adpt = self._adpt_patcher.start()

        self.addCleanup(self._sess_patcher.stop)
        self.addCleanup(self._adpt_patcher.stop)
