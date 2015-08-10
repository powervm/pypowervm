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

import abc
import fixtures
import mock
import six

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

# Thread locking primitives are located slightly differently in py2 vs py3
SEM_ENTER = 'threading.%sSemaphore.__enter__' % ('_' if six.PY2 else '')
SEM_EXIT = 'threading.%sSemaphore.__exit__' % ('_' if six.PY2 else '')


class SimplePatcher(object):
    """Provide a basic mocking patcher on a test fixture."""
    def __init__(self, fx, name, path, side_effect=None, return_value=None):
        """Create a patcher on a given fixture.

        :param fx: The fixtures.Fixture (subclass) on which to register the
                   patcher.
        :param name: String name for the patcher.
        :param path: String python path of the object being mocked.
        :param side_effect: Side effect for the mock created by this patcher.
                            If side_effect is supplied, return_value is
                            ignored.
        :param return_value: Return value for the mock created by this patcher.
                             If side_effect is supplied, return_value is
                             ignored.
        """
        self.fx = fx
        self.name = name
        self.patcher = mock.patch(path)
        self.return_value = return_value
        self.side_effect = side_effect
        self.mock = None

    def start(self):
        """Start the patcher, creating the and setting up the mock."""
        self.mock = self.patcher.start()
        if self.side_effect:
            self.mock.side_effect = self.side_effect
        else:
            self.mock.return_value = self.return_value
        self.fx.addCleanup(self.patcher.stop)


class LoggingPatcher(SimplePatcher):
    """SimplePatcher whose mock logs its name and returns a value."""
    def __init__(self, fx, name, path, return_value=None):
        """Create the logging patcher.

        :param fx: The fixtures.Fixture (subclass) on which to register the
                   patcher.  Must be a fixture providing a .log(msg) method.
        :param name: String name for the patcher.
        :param path: String python path of the object being mocked.
        :param return_value: The return value for the mocked method.
        """
        # This ignores/overrides the superclass's return_value semantic.
        self.ret = return_value
        super(LoggingPatcher, self).__init__(
            fx, name, path, side_effect=self.log_method())

    def log_method(self):
        def _log(*a, **k):
            self.fx.log(self.name)
            return self.ret
        return _log

    @property
    def return_value(self):
        return self.ret

    @return_value.setter
    def return_value(self, ret):
        self.ret = ret
        self.side_effect = self.log_method()


@six.add_metaclass(abc.ABCMeta)
class Logger(object):
    def __init__(self):
        super(Logger, self).__init__()
        self._tx_log = []

    def get_log(self):
        """Retrieve the event log.

        :return: The log, a list of strings in the order they were added.
        """
        return self._tx_log

    def log(self, val):
        """Add a message to the log.

        :param val: String value to append to the log.
        """
        self._tx_log.append(val)

    def reset_log(self):
        """Clear the log."""
        self._tx_log = []


@six.add_metaclass(abc.ABCMeta)
class SimplePatchingFx(fixtures.Fixture):
    def __init__(self):
        super(SimplePatchingFx, self).__init__()
        self.patchers = {}

    def add_patchers(self, *patchers):
        for patcher in patchers:
            self.patchers[patcher.name] = patcher

    def setUp(self):
        super(SimplePatchingFx, self).setUp()
        for patcher in self.patchers.values():
            patcher.start()


class WrapperTaskFx(SimplePatchingFx, Logger):
    """Customizable mocking and pseudo-logging for WrapperTask primitives.

    Provides LoggingPatchers for REST and locking primitives.  By default,
    these patchers simply log their name and return a sensible value (see
    below).

    However, patchers can be added, changed, or removed by name from the
    fixture instance via its 'patchers' dict.  In order to have effect on your
    test case, such modifications must be done between fixture initialization
    and useFixture.  For example:

    # Init the fixture, but do not start it:
    wtfx = WrapperTaskFx(a_wrapper)
    # An existing patcher can be modified:
    upd = wtfx.patchers['update'].side_effect = SomeException()
    # Or deleted:
    del wtfx.patchers['refresh']
    # New patchers can be added.  They must be instances of SimplePatcher (or a
    # subclass).  Add directly to 'patchers':
    wtfx.patchers['foo'] = LoggingPatcher(wtfx, 'frob', 'pypowervm.utils.frob')
    # ...or use add_patchers to add more than one:
    wtfx.add_patchers(p1, p2, p3)

    # Finally, don't forget to start the fixture
    self.useFixture(wtfx)

    # Mocks can be accessed via their patchers and queried during testing as
    # usual:
    wtfx.patchers['foo'].mock.assert_called_with('bar', 'baz')
    self.assertEqual(3, wtfx.patchers['update'].mock.call_count)

    See live examples in pypowervm.tests.utils.test_transaction.TestWrapperTask

    Default mocks:
    'get': Mocks EntyrWrapperGetter.get.
           Logs 'get'.
           Returns the wrapper with which the fixture was initialized.
    'refresh': Mocks EntryWrapper.refresh.
               Logs 'refresh'.
               Returns the wrapper with which the fixture was initialized.
    'update': Mocks EntryWrapper.update.
              Logs 'update'.
              Returns the wrapper with which the fixture was initialized.
    'lock', 'unlock': Mocks semaphore locking (oslo_concurrency.lockutils.lock
                      and @synchronized, ultimately threading.Semaphore)
                      performed by the @entry_transaction decorator.
                      Logs 'lock'/'unlock', respectively.
                      Returns None.

    """
    def __init__(self, wrapper):
        """Create the fixture around a specific EntryWrapper.

        :param wrapper: EntryWrapper instance to be returned by mocked
                        EntryWrapperGetter.get and EntryWrapper.refresh methods
        """
        super(WrapperTaskFx, self).__init__()
        self._wrapper = wrapper
        self.add_patchers(
            LoggingPatcher(
                self, 'get',
                'pypowervm.wrappers.entry_wrapper.EntryWrapperGetter.get',
                return_value=self._wrapper),
            LoggingPatcher(
                self, 'refresh',
                'pypowervm.wrappers.entry_wrapper.EntryWrapper.refresh',
                return_value=self._wrapper),
            LoggingPatcher(
                self, 'update',
                'pypowervm.wrappers.entry_wrapper.EntryWrapper.update',
                return_value=self._wrapper),
            LoggingPatcher(self, 'lock', SEM_ENTER),
            LoggingPatcher(self, 'unlock', SEM_EXIT)
        )


class FeedTaskFx(SimplePatchingFx, Logger):
    """
    !You will have to add the proper return to the 'update' patcher for now!
    """
    def __init__(self, feed):
        super(FeedTaskFx, self).__init__()
        self._feed = feed
        self.add_patchers(
            LoggingPatcher(
                self, 'get',
                'pypowervm.wrappers.entry_wrapper.FeedGetter.get',
                return_value=self._feed),
            LoggingPatcher(
                self, 'refresh',
                'pypowervm.wrappers.entry_wrapper.EntryWrapper.refresh',
                # TODO(efried): How to return 'self' from a mocked method??
                return_value=self._feed[0]),
            LoggingPatcher(
                self, 'update',
                'pypowervm.wrappers.entry_wrapper.EntryWrapper.update',
                # TODO(efried): How to return 'self' from a mocked method??
                return_value=self._feed[0]),
            LoggingPatcher(self, 'lock', SEM_ENTER),
            LoggingPatcher(self, 'unlock', SEM_EXIT)
        )
