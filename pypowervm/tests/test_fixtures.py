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

import fixtures
import mock

from pypowervm import traits as trt


class SessionFx(fixtures.Fixture):
    """Patch pypowervm.adapter.Session."""

    def __init__(self, traits=None):
        """Create Session patcher with traits.

        :param traits: APITraits instance to be assigned to the .traits
                       attribute of the mock Session.  If not specified,
                       sess.traits will be None. LocalPVMTraits,
                       RemotePVMTraits, and RemoteHMCTraits are provided below
                       for convenience.
        :return:
        """
        self.traits = traits
        self._patcher = mock.patch('pypowervm.adapter.Session')

    def setUp(self):
        super(SessionFx, self).setUp()
        self.sess = self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.sess.traits = self.traits


class AdapterFx(fixtures.Fixture):
    """Patch pypowervm.adapter.Adapter."""

    def __init__(self, session=None, traits=None):
        """Create Adapter and/or Session patchers with traits.

        :param session: A pypowervm.adapter.Session instance or mock with which
                        to back this mocked Adapter.  If not specified, a new
                        SessionFx fixture is created and used.
        :param traits: APITraits instance to be assigned to the .traits
                       attribute of the Session and/or Adapter mock.  If
                       not specified, session.traits will be used.  If both
                       session and traits are specified, the session's traits
                       will be overwritten with the traits parameter.
                       LocalPVMTraits, RemotePVMTraits, and RemoteHMCTraits are
                       provided below for convenience.
        """
        super(AdapterFx, self).__init__()
        self.session = session
        self.traits = traits
        self._patcher = mock.patch('pypowervm.adapter.Adapter')

    def setUp(self):
        super(AdapterFx, self).setUp()
        if not self.session:
            self.session = self.useFixture(SessionFx(self.traits))

        self.adpt = self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.adpt.session = self.session
        self.set_traits(self.traits)

    def set_traits(self, traits):
        # Mocked Adapter needs to see both routes to traits.
        self.adpt.session.traits = traits
        self.adpt.traits = traits


def _mk_traits(local, hmc):
    """Mock a single APITraits configuration.

    :param local: Should the APITraits pretend to be local?  True or False.
    :param hmc: Should the APITraits pretend to be running against HMC (True)
                or PVM (False)?
    :return: APITraits instance with the specified behavior.
    """
    _sess = mock.Mock()
    _sess.use_file_auth = local
    _sess.mc_type = 'HMC' if hmc else 'PVM'
    return trt.APITraits(_sess)

LocalPVMTraits = _mk_traits(local=True, hmc=False)
RemotePVMTraits = _mk_traits(local=False, hmc=False)
RemoteHMCTraits = _mk_traits(local=False, hmc=True)
