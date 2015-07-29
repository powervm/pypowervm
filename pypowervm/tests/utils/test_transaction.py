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

"""Tests for pypoowervm.utils.transaction."""

import mock
import six

import pypowervm.const as c
import pypowervm.exceptions as ex
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.utils.transaction as tx
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.logical_partition as lpar

# Thread locking primitives are located slightly differently in py2 vs py3
SEM_ENTER = 'threading.%sSemaphore.__enter__' % ('_' if six.PY2 else '')
SEM_EXIT = 'threading.%sSemaphore.__exit__' % ('_' if six.PY2 else '')


class TestEntryTransaction(twrap.TestWrapper):
    file = 'lpar.txt'
    wrapper_class_to_test = lpar.LPAR

    def setUp(self):
        super(TestEntryTransaction, self).setUp()
        self.mock_wrapper = self.dwrap
        self.mock_spec = ewrap.EntryWrapperGetSpec(self.adpt, lpar.LPAR,
                                                   'mock_spec_uuid')
        # Set this up for mock_spec.get()
        self.adpt.read.return_value = self.dwrap.entry

    @mock.patch('oslo_concurrency.lockutils.Semaphores.get')
    def test_synchronized_called_with_uuid(self, mock_semget):
        """Ensure the synchronizer is locking with the first arg's .uuid."""
        @tx.entry_transaction
        def foo(wrapper_or_spec):
            pass

        # At this point, the outer decorator has been invoked, but the
        # synchronizing decorator has not.
        self.assertEqual(0, mock_semget.call_count)

        # If we call the decorated method with an EntryWrapper, synchronize
        # should be invoked with the EntryWrapper's UUID
        foo(self.mock_wrapper)
        self.assertEqual(1, mock_semget.call_count)
        mock_semget.assert_called_with('089FFB20-5D19-4A8C-BB80-13650627D985')

        # Calling with an EntryWrapperGetSpec should synchronize on the spec's
        # registered UUID.  (IRL, this will match the wrapper's UUID.  Here we
        # are making sure the right code path is being taken.)
        mock_semget.reset_mock()
        foo(self.mock_spec)
        self.assertEqual(1, mock_semget.call_count)
        mock_semget.assert_called_with('mock_spec_uuid')

    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapper.refresh')
    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapperGetSpec.get')
    @mock.patch(SEM_EXIT)
    @mock.patch(SEM_ENTER)
    def test_sequence(self, mock_lock, mock_unlock, mock_get, mock_refresh):
        """Prove the sequence of events on a transaction-decorated method.

        We expect it to look like:
        lock
        get the wrapper if necessary
        invoke the method
        while the method raises etag error, refresh the wrapper and re-invoke
        unlock
        """
        registry = []

        mock_lock.side_effect = lambda *a, **k: registry.append('lock')
        mock_unlock.side_effect = lambda *a, **k: registry.append('unlock')

        def _spec_get():
            registry.append('get')
            return self.mock_wrapper
        mock_get.side_effect = _spec_get

        def _refresh():
            registry.append('refresh')
            return self.mock_wrapper
        mock_refresh.side_effect = _refresh

        tracker = mock.Mock(counter=0)
        tracker.counter = 0

        @tx.entry_transaction
        def foo(wrapper_or_spec):
            # Always converted by now
            self.assertIsInstance(wrapper_or_spec, ewrap.EntryWrapper)
            # Force a couple of retries
            tracker.counter += 1
            registry.append('foo %d' % tracker.counter)
            if tracker.counter < 3:
                raise ex.HttpError(
                    "mismatch", mock.Mock(status=c.HTTPStatus.ETAG_MISMATCH))
            return True

        # With an EntryWrapperGetSpec, get() is invoked
        self.assertTrue(foo(self.mock_spec))
        self.assertEqual(['lock', 'get', 'foo 1', 'refresh', 'foo 2',
                          'refresh', 'foo 3', 'unlock'], registry)

        # With an EntryWrapper, get() is not invoked
        tracker.counter = 0
        registry = []
        self.assertTrue(foo(self.mock_wrapper))
        self.assertEqual(['lock', 'foo 1', 'refresh', 'foo 2', 'refresh',
                          'foo 3', 'unlock'], registry)
