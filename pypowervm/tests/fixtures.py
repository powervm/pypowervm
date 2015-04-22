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

from pypowervm import traits


class AdapterFx(fixtures.Fixture):
    """Patch out Session and Adapter."""

    def __init__(self, patch_sess=True, patch_adpt=True):
        super(AdapterFx, self).__init__()
        self._sess_patcher = mock.patch('pypowervm.adapter.Session')
        self._adpt_patcher = mock.patch('pypowervm.adapter.Adapter')
        self.patch_sess = patch_sess
        self.patch_adpt = patch_adpt

    def setUp(self):
        super(AdapterFx, self).setUp()
        if self.patch_sess:
            self.sess = self._sess_patcher.start()
            self.addCleanup(self._sess_patcher.stop)
        if self.patch_adpt:
            self.adpt = self._adpt_patcher.start()
            self.addCleanup(self._adpt_patcher.stop)


class _TraitsFx(fixtures.Fixture):
    def __init__(self, local, hmc):
        self._sess = mock.patch('pypowervm.adapter.Session')
        self._sess.use_file_auth = local
        self._sess.mc_type = 'HMC' if hmc else 'PVM'
        self.traits = None

    def setUp(self):
        super(_TraitsFx, self).setUp()
        self.traits = traits.APITraits(self._sess)
        self.addCleanup(delattr, self, 'traits')

LocalPVMTraitsFx = _TraitsFx(local=True, hmc=False)
RemotePVMTraitsFx = _TraitsFx(local=False, hmc=False)
RemoteHMCTraitsFx = _TraitsFx(local=False, hmc=True)
