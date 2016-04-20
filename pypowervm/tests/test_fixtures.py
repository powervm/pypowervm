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
import importlib
import mock
import six

from pypowervm import traits as trt

# An anchor for traits we construct artificially so the session isn't
# garbage collected.
_mk_traits_sessions = []


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

    # Traits use a weak ref to the session to avoid a circular reference
    # so anchor the mock session globally otherwise it'll be gone
    # right after we return it.
    global _mk_traits_sessions
    _mk_traits_sessions.append(_sess)
    return trt.APITraits(_sess)

LocalPVMTraits = _mk_traits(local=True, hmc=False)
RemotePVMTraits = _mk_traits(local=False, hmc=False)
RemoteHMCTraits = _mk_traits(local=False, hmc=True)


class SessionFx(fixtures.Fixture):
    """Patch pypowervm.adapter.Session."""

    def __init__(self, traits=LocalPVMTraits):
        """Create Session patcher with traits.

        :param traits: APITraits instance to be assigned to the .traits
                       attribute of the mock Session.  If not specified,
                       sess.traits will be LocalPVMTraits. LocalPVMTraits,
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
        self.sess.timeout = 1200


class AdapterFx(fixtures.Fixture):
    """Patch pypowervm.adapter.Adapter."""

    def __init__(self, session=None, traits=None):
        """Create Adapter and/or Session patchers with traits.

        :param session: A pypowervm.adapter.Session instance or mock with which
                        to back this mocked Adapter.  If not specified, a new
                        SessionFx fixture is created and used.
        :param traits: APITraits instance to be assigned to the .traits
                       attribute of the Session and/or Adapter mock.  If
                       not specified, LocalPVMTraits will be used.  If both
                       session and traits are specified, the session's traits
                       will be overwritten with the traits parameter.
                       LocalPVMTraits, RemotePVMTraits, and RemoteHMCTraits are
                       provided below for convenience.
        """
        super(AdapterFx, self).__init__()
        self.session = session
        if traits is None and (session is None or session.traits is None):
            self.traits = LocalPVMTraits
        elif traits:
            self.traits = traits
        else:
            self.traits = session.traits
        self._patcher = mock.patch('pypowervm.adapter.Adapter')

    def setUp(self):
        super(AdapterFx, self).setUp()
        if not self.session:
            self.session = self.useFixture(SessionFx(self.traits)).sess

        self.adpt = self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.adpt.session = self.session
        self.set_traits(self.traits)

    def set_traits(self, traits):
        # Mocked Adapter needs to see both routes to traits.
        self.adpt.session.traits = traits
        self.adpt.traits = traits


class SimplePatcher(object):
    """Provide a basic mocking patcher on a test fixture.

    The main purpose of this class is to be used with SimplePatchingFx.

    That said, the following are equivalent:

    @mock.patch('path.to.method')
    def test_foo(self, mock_meth):
        mock_meth.return_value = 'abc'
        # ...

    def test_foo(self):
        mock_meth = SimplePatcher(self, 'whatever', 'path.to.method',
                                  return_value='abc').start()
        # ...
    """
    def __init__(self, fx, name, path, patch_object=False, side_effect=None,
                 return_value=None):
        """Create a patcher on a given fixture.

        :param fx: The fixtures.Fixture (subclass) on which to register the
                   patcher.
        :param name: String name for the patcher.
        :param path: String python path of the object being mocked.
        :param patch_object: If True, the path parameter is parsed to create a
                             mock.patch.object with autospec=True instead of a
                             regular mock.patch.  For example,
                         patch='foo.bar.Baz.meth'
                             would result in
                         mock.patch.object(foo.bar.Baz, 'meth', autospec=True)
                             Note that this means the mock call will include
                             the instance through which it was invoked.
        :param side_effect: Side effect for the mock created by this patcher.
                            If side_effect is supplied, return_value is
                            ignored.
        :param return_value: Return value for the mock created by this patcher.
                             If side_effect is supplied, return_value is
                             ignored.
        """
        self.fx = fx
        self.name = name
        if patch_object:
            modname, klassname, methname = path.rsplit('.', 2)
            module = importlib.import_module(modname)
            klass = getattr(module, klassname)
            self.patcher = mock.patch.object(klass, methname, autospec=True)
        else:
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
        return self.mock


class LoggingPatcher(SimplePatcher):
    """SimplePatcher whose mock logs its name and returns a value."""
    FIRST_ARG = '__MOCK_RETURNS_FIRST_ARGUMENT__'

    def __init__(self, fx, name, path, patch_object=False, return_value=None):
        """Create the logging patcher.

        :param fx: The fixtures.Fixture (subclass) on which to register the
                   patcher.  Must be a fixture providing a .log(msg) method.
        :param name: String name for the patcher.
        :param path: String python path of the object being mocked.
        :param patch_object: If True, the path parameter is parsed to create a
                             mock.patch.object with autospec=True instead of a
                             regular mock.patch.  For example,
                         patch='foo.bar.Baz.meth'
                             would result in
                         mock.patch.object(foo.bar.Baz, 'meth', autospec=True)
                             Note that this means the mock call will include
                             the instance through which it was invoked.
        :param return_value: The return value for the mocked method.
        """
        def _log(*a, **k):
            self.fx.log(self.name)
            return a[0] if self.ret is self.FIRST_ARG else self.ret
        # This ignores/overrides the superclass's return_value semantic.
        self.ret = return_value
        super(LoggingPatcher, self).__init__(
            fx, name, path, patch_object=patch_object, side_effect=_log)


@six.add_metaclass(abc.ABCMeta)
class Logger(object):
    """Base class for mixins wanting simple 'log to a list' semantics."""
    def __init__(self):
        """Create a new Logger."""
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
    """Fixture base class supporting SimplePatcher.

    Subclasses should invoke add_patchers from __init__ after super().__init__,
    but before useFixture.
    """
    def __init__(self):
        """Create the simple-patching fixture."""
        super(SimplePatchingFx, self).__init__()
        self.patchers = {}

    def add_patchers(self, *patchers):
        """Add some number of SimplePatcher instances to the fixture.

        :param patchers: Zero or more SimplePatcher instances to add.
        """
        for patcher in patchers:
            self.patchers[patcher.name] = patcher

    def setUp(self):
        """Start the fixture and its member SimplePatchers.

        This is generally invoked via useFixture and should not be called
        directly.
        """
        super(SimplePatchingFx, self).setUp()
        for patcher in self.patchers.values():
            patcher.start()


class SleepPatcher(SimplePatcher):
    def __init__(self, fx, side_effect=None):
        super(SleepPatcher, self).__init__(fx, 'sleep', 'time.sleep',
                                           side_effect=side_effect)


class SleepFx(SimplePatchingFx):
    """Fixture for time.sleep."""
    def __init__(self, side_effect=None):
        """Create the fixture for time.sleep."""
        super(SleepFx, self).__init__()
        self.add_patchers(SleepPatcher(self, side_effect=side_effect))

# Thread locking primitives are located slightly differently in py2 vs py3
SEM_ENTER = 'threading.%sSemaphore.__enter__' % ('_' if six.PY2 else '')
SEM_EXIT = 'threading.%sSemaphore.__exit__' % ('_' if six.PY2 else '')


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
            LoggingPatcher(self, 'unlock', SEM_EXIT),
            SleepPatcher(self)
        )


class FeedTaskFx(SimplePatchingFx, Logger):
    """Customizable mocking and pseudo-logging for FeedTask primitives.

    Provides LoggingPatchers for REST and locking primitives.  By default,
    these patchers simply log their name and return a sensible value (see
    below).

    However, patchers can be added, changed, or removed by name from the
    fixture instance via its 'patchers' dict.  In order to have effect on your
    test case, such modifications must be done between fixture initialization
    and useFixture.  For example:

    # Init the fixture, but do not start it:
    ftfx = FeedTaskFx(a_feed)
    # An existing patcher can be modified:
    upd = ftfx.patchers['update'].side_effect = SomeException()
    # Or deleted:
    del ftfx.patchers['refresh']
    # New patchers can be added.  They must be instances of SimplePatcher (or a
    # subclass).  Add directly to 'patchers':
    ftfx.patchers['foo'] = LoggingPatcher(ftfx, 'frob', 'pypowervm.utils.frob')
    # ...or use add_patchers to add more than one:
    ftfx.add_patchers(p1, p2, p3)

    # Finally, don't forget to start the fixture
    self.useFixture(ftfx)

    # Mocks can be accessed via their patchers and queried during testing as
    # usual:
    ftfx.patchers['foo'].mock.assert_called_with('bar', 'baz')
    self.assertEqual(3, ftfx.patchers['update'].mock.call_count)

    See live examples in pypowervm.tests.utils.test_transaction.TestWrapperTask

    Default mocks:
    'get': Mocks FeedGetter.get.
           Logs 'get'.
           Returns the feed with which the fixture was initialized.
    'refresh': Mocks EntryWrapper.refresh.
               Logs 'refresh'.
               Returns the wrapper on which the refresh method was called.
    'update': Mocks EntryWrapper.update.
              Logs 'update'.
              Returns the wrapper on which the update method was called.
    'lock', 'unlock': Mocks semaphore locking (oslo_concurrency.lockutils.lock
                      and @synchronized, ultimately threading.Semaphore)
                      performed by the @entry_transaction decorator.
                      Logs 'lock'/'unlock', respectively.
                      Returns None.
    """
    def __init__(self, feed):
        """Create the fixture around a given feed.

        :param feed: The feed (list of EntryWrappers) to be returned from the
                     mocked FeedGetter.get method.
        """
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
                patch_object=True, return_value=LoggingPatcher.FIRST_ARG),
            LoggingPatcher(
                self, 'update',
                'pypowervm.wrappers.entry_wrapper.EntryWrapper.update',
                patch_object=True, return_value=LoggingPatcher.FIRST_ARG),
            LoggingPatcher(self, 'lock', SEM_ENTER),
            LoggingPatcher(self, 'unlock', SEM_EXIT),
            SleepPatcher(self)
        )


class LoggingFx(SimplePatchingFx):
    """Fixture for LOG.*, not to be confused with Logger/LoggingPatcher.

    Provides patches and mocks for LOG.x for x in
    ('info', 'warning', 'debug', 'error', 'exception')
    """
    def __init__(self):
        """Create the fixture for the various logging methods."""
        super(LoggingFx, self).__init__()
        self.add_patchers(
            *(SimplePatcher(self, x, 'oslo_log.log.BaseLoggerAdapter.%s' % x)
              for x in ('info', 'warning', 'debug', 'error', 'exception')))
