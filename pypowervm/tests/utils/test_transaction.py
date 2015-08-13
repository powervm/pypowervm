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

import copy
import mock
import oslo_concurrency.lockutils as lock
from taskflow import task as tf_task

import pypowervm.const as c
import pypowervm.exceptions as ex
import pypowervm.tests.test_fixtures as fx
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.utils.transaction as tx
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.logical_partition as lpar


class TestWrapperTask(twrap.TestWrapper):
    file = 'lpar.txt'
    wrapper_class_to_test = lpar.LPAR

    def setUp(self):
        super(TestWrapperTask, self).setUp()
        self.getter = lpar.LPAR.getter(self.adpt, 'getter_uuid')
        # Set this up for getter.get()
        self.adpt.read.return_value = self.dwrap.entry
        self.tracker = mock.Mock(counter=0)

    class LparNameAndMem(tx.Subtask):
        """Subtask modifying an LPAR's name and desired memory."""
        def execute(self, lpar_wrapper, new_name, des_mem=None, logger=None):
            """Modify an LPAR's name and desired memory.

            :param lpar_wrapper: The LPAR EntryWrapper to update.
            :param new_name: The new name to give the LPAR.
            :param des_mem: (Optional) The new desired memory value, an int.
            :param logger: (Optional) If specified, "log" the class name for
                           test inspection purposes.
            :return: The (possibly modified) lpar_wrapper.
            """
            update_needed = False
            if logger:
                logger.log('LparNameAndMem_%s' % new_name)
            old_name = lpar_wrapper.name
            if old_name != new_name:
                lpar_wrapper.name = new_name
                update_needed = True
            if des_mem is not None:
                orig_mem = lpar_wrapper.mem_config.desired
                if des_mem != orig_mem:
                    lpar_wrapper.mem_config.desired = des_mem
                    update_needed = True
            return update_needed

    @staticmethod
    def retry_twice(wrapper, tracker, logger):
        # Force a couple of retries
        tracker.counter += 1
        logger.log('update %d' % tracker.counter)
        if tracker.counter < 3:
            raise ex.HttpError(
                "mismatch", mock.Mock(status=c.HTTPStatus.ETAG_MISMATCH))
        return wrapper

    @mock.patch('oslo_concurrency.lockutils.Semaphores.get')
    def test_synchronized_called_with_uuid(self, mock_semget):
        """Ensure the synchronizer is locking with the first arg's .uuid."""
        @tx.entry_transaction
        def foo(wrapper_or_getter):
            pass

        # At this point, the outer decorator has been invoked, but the
        # synchronizing decorator has not.
        self.assertEqual(0, mock_semget.call_count)

        # If we call the decorated method with an EntryWrapper, synchronize
        # should be invoked with the EntryWrapper's UUID
        foo(self.dwrap)
        self.assertEqual(1, mock_semget.call_count)
        mock_semget.assert_called_with('089FFB20-5D19-4A8C-BB80-13650627D985')

        # Calling with an EntryWrapperGetter should synchronize on the getter's
        # registered UUID.  (IRL, this will match the wrapper's UUID.  Here we
        # are making sure the right code path is being taken.)
        mock_semget.reset_mock()
        foo(self.getter)
        mock_semget.assert_any_call('getter_uuid')

    def test_sequence(self):
        """Prove the sequence of events on a transaction-decorated method.

        We expect it to look like:
        lock
        get the wrapper if necessary
        invoke the method
        while the method raises etag error, refresh the wrapper and re-invoke
        unlock
        """
        txfx = self.useFixture(fx.WrapperTaskFx(self.dwrap))

        @tx.entry_transaction
        def foo(wrapper_or_getter):
            # Always converted by now
            self.assertIsInstance(wrapper_or_getter, ewrap.EntryWrapper)
            return self.retry_twice(wrapper_or_getter, self.tracker, txfx)

        # With an EntryWrapperGetter, get() is invoked
        self.assertEqual(self.dwrap, foo(self.getter))
        self.assertEqual(['lock', 'get', 'update 1', 'refresh', 'update 2',
                          'refresh', 'update 3', 'unlock'], txfx.get_log())

        # With an EntryWrapper, get() is not invoked
        self.tracker.counter = 0
        txfx.reset_log()
        self.assertEqual(self.dwrap, foo(self.dwrap))
        self.assertEqual(['lock', 'update 1', 'refresh', 'update 2', 'refresh',
                          'update 3', 'unlock'], txfx.get_log())

    @staticmethod
    def tx_subtask_invoke(tst, wrapper):
        """Simulates how Subtasks are invoked by WrapperTask.

        :param tst: A Subtask
        :param wrapper: The wrapper with which to invoke execute()
        :return: The value returned by execute()
        """
        return tst.execute(wrapper, *tst.save_args, **tst.save_kwargs)

    def test_wrapper_task_subtask(self):
        """Tests around Subtask."""
        # Same name, should result in no changes and no update_needed
        txst1 = self.LparNameAndMem('z3-9-5-126-127-00000001')
        self.assertFalse(self.tx_subtask_invoke(txst1, self.dwrap))
        self.assertEqual('z3-9-5-126-127-00000001', self.dwrap.name)
        self.assertEqual(512, self.dwrap.mem_config.desired)
        # New name should prompt update_needed.  Specified-but-same des_mem.
        txst2 = self.LparNameAndMem('new-name', des_mem=512)
        self.assertTrue(self.tx_subtask_invoke(txst2, self.dwrap))
        self.assertEqual('new-name', self.dwrap.name)
        self.assertEqual(512, self.dwrap.mem_config.desired)
        # New name and mem should prompt update_needed
        txst3 = self.LparNameAndMem('newer-name', des_mem=1024)
        self.assertTrue(self.tx_subtask_invoke(txst3, self.dwrap))
        self.assertEqual('newer-name', self.dwrap.name)
        self.assertEqual(1024, self.dwrap.mem_config.desired)
        # Same name and explicit same mem - no update_needed
        txst4 = self.LparNameAndMem('newer-name', des_mem=1024)
        self.assertFalse(self.tx_subtask_invoke(txst4, self.dwrap))
        self.assertEqual('newer-name', self.dwrap.name)
        self.assertEqual(1024, self.dwrap.mem_config.desired)

    def test_wrapper_task_subtask_returns(self):
        """Test that execute methods' return values are processed properly."""
        # Use internal _FunctorSubtask to make this easier.  Bonus: testing
        # _FunctorSubtask at the same time.

        def returns_second_arg(wrapper, boolable):
            """Used to test various boolable single returns."""
            return boolable

        # Various valid 'False' boolables - update not needed
        falseables = (0, '', [], {}, False)
        for falseable in falseables:
            txst = tx._FunctorSubtask(returns_second_arg, falseable)
            self.assertFalse(self.tx_subtask_invoke(txst, self.dwrap))

        # Various valid 'True' boolables - update needed
        trueables = (1, 'string', [0], {'k': 'v'}, True)
        for trueable in trueables:
            txst = tx._FunctorSubtask(returns_second_arg, trueable)
            self.assertTrue(self.tx_subtask_invoke(txst, self.dwrap))

    def test_wrapper_task_allow_empty(self):
        """Test the allow_empty=True condition."""
        # No mocks - no REST calls should be run.
        tx1 = tx.WrapperTask('tx1', self.getter, allow_empty=True)
        # Does not raise, returns None
        self.assertIsNone(tx1.execute())

    def test_wrapper_task1(self):
        txfx = self.useFixture(fx.WrapperTaskFx(self.dwrap))

        # Must supply a wrapper or getter to instantiate
        self.assertRaises(ValueError, tx.WrapperTask, 'foo', 'bar')

        # Create a valid WrapperTask
        tx1 = tx.WrapperTask('tx1', self.getter)
        self.assertEqual('tx1', tx1.name)
        self.assertEqual('wrapper_getter_uuid', tx1.provides)
        # Nothing has been run yet
        self.assertEqual([], txfx.get_log())
        # Try running with no subtasks
        self.assertRaises(ex.WrapperTaskNoSubtasks, tx1.execute)
        # Try adding something that isn't a Subtask
        self.assertRaises(ValueError, tx1.add_subtask, 'Not a Subtask')
        # Error paths don't run anything.
        self.assertEqual([], txfx.get_log())

        # Add a subtask that doesn't change anything
        tx1.add_subtask(self.LparNameAndMem('z3-9-5-126-127-00000001',
                                            logger=txfx))
        # Adding a subtask does not run anything
        self.assertEqual([], txfx.get_log())

        # Get the wrapper - this should invoke GET, but *not* under lock
        self.assertEqual(self.dwrap, tx1.wrapper)
        self.assertEqual(['get'], txfx.get_log())

        # Run the transaction
        lwrap = tx1.execute()
        # The name should be unchanged
        self.assertEqual('z3-9-5-126-127-00000001', lwrap.name)
        # And update should not have been called, which should be reflected in
        # the log.  Note that 'get' is NOT called a second time.
        self.assertEqual([
            'get', 'lock', 'LparNameAndMem_z3-9-5-126-127-00000001', 'unlock'],
            txfx.get_log())

        txfx.reset_log()
        # These subtasks do change the name.
        tx1.add_subtask(self.LparNameAndMem('new_name', logger=txfx))
        tx1.add_subtask(self.LparNameAndMem('newer_name', logger=txfx))
        # But this one doesn't.  We're making sure the last 'no update needed'
        # doesn't make the overall update_needed status False.
        tx1.add_subtask(self.LparNameAndMem('newer_name', logger=txfx))
        # Get the wrapper - this should *not* reinvoke GET
        self.assertEqual(self.dwrap, tx1.wrapper)
        self.assertEqual([], txfx.get_log())
        # Now execute the transaction
        lwrap = tx1.execute()
        # The last change should be the one that stuck
        self.assertEqual('newer_name', lwrap.name)
        # Check the overall order.  Update was called.
        self.assertEqual([
            'lock', 'LparNameAndMem_z3-9-5-126-127-00000001',
            'LparNameAndMem_new_name', 'LparNameAndMem_newer_name',
            'LparNameAndMem_newer_name', 'update', 'unlock'], txfx.get_log())

        # Test 'cloning' the subtask list
        txfx.reset_log()
        tx2 = tx.WrapperTask('tx2', self.getter, subtasks=tx1.subtasks)
        # Add another one to make sure it goes at the end
        tx2.add_subtask(self.LparNameAndMem('newest_name', logger=txfx))
        # Add one to the original transaction to make sure it doesn't affect
        # this one.
        tx1.add_subtask(self.LparNameAndMem('bogus_name', logger=txfx))
        lwrap = tx2.execute()
        # The last change should be the one that stuck
        self.assertEqual('newest_name', lwrap.name)
        # Check the overall order.  This one GETs under lock.  Update called.
        self.assertEqual([
            'lock', 'get', 'LparNameAndMem_z3-9-5-126-127-00000001',
            'LparNameAndMem_new_name', 'LparNameAndMem_newer_name',
            'LparNameAndMem_newer_name', 'LparNameAndMem_newest_name',
            'update', 'unlock'], txfx.get_log())

    def test_wrapper_task2(self):
        # Now:
        # o Fake like update forces retry
        # o Test add_functor_subtask, including chaining
        # o Ensure GET is deferred when .wrapper() is not called ahead of time.
        # o Make sure subtask args are getting to the subtask.
        txfx = fx.WrapperTaskFx(self.dwrap)

        def _update_retries_twice():
            return self.retry_twice(self.dwrap, self.tracker, txfx)
        txfx.patchers['update'].side_effect = _update_retries_twice

        self.useFixture(txfx)

        def functor(wrapper, arg1, arg2, kwarg3=None, kwarg4=None):
            txfx.log('functor')
            # Make sure args are getting here
            self.assertEqual(['arg', 1], arg1)
            self.assertEqual('arg2', arg2)
            self.assertIsNone(kwarg3)
            self.assertEqual('kwarg4', kwarg4)
            return wrapper, True
        # Instantiate-add-execute chain
        tx.WrapperTask('tx2', self.getter).add_functor_subtask(
            functor, ['arg', 1], 'arg2', kwarg4='kwarg4').execute()
        # Check the overall order.  Update should have been called thrice (two
        # retries)
        self.assertEqual(3, txfx.patchers['update'].mock.call_count)
        self.assertEqual([
            'lock', 'get', 'functor', 'update 1', 'refresh', 'functor',
            'update 2', 'refresh', 'functor', 'update 3', 'unlock'],
            txfx.get_log())


class TestFeedTask(twrap.TestWrapper):
    file = 'lpar.txt'
    wrapper_class_to_test = lpar.LPAR

    def setUp(self):
        super(TestFeedTask, self).setUp()
        self.getter = lpar.LPAR.getter(self.adpt)
        # Set this up for getter.get()
        self.adpt.read.return_value = self.resp
        self.feed_task = tx.FeedTask('name', lpar.LPAR.getter(self.adpt))

    def test_invalid_feed_or_getter(self):
        """Various evil inputs to FeedTask.__init__'s feed_or_getter."""
        self.assertRaises(ValueError, tx.FeedTask, 'name', 'something bogus')
        # A "feed" of things that aren't EntryWrappers
        self.assertRaises(ValueError, tx.FeedTask, 'name', [1, 2, 3])
        # This one fails because .getter(..., uuid) produces EntryWrapperGetter
        self.assertRaises(ValueError, tx.FeedTask, 'name',
                          lpar.LPAR.getter(self.adpt, 'a_uuid'))
        # Init with explicit empty feed tested below in test_empty_feed

    @mock.patch('pypowervm.wrappers.entry_wrapper.FeedGetter.get')
    def test_empty_feed(self, mock_get):
        mock_get.return_value = []
        # We're allowed to initialize it with a FeedGetter
        fm = tx.FeedTask('name', ewrap.FeedGetter('mock', 'mock'))
        # But as soon as we call a 'greedy' method, which does a .get, we raise
        self.assertRaises(ex.FeedTaskEmptyFeed, fm.get_wrapper, 'uuid')
        # Init with an explicit empty feed (list) raises right away
        self.assertRaises(ex.FeedTaskEmptyFeed, tx.FeedTask, 'name', [])

    def test_wrapper_task_adds_and_replication(self):
        """Deferred replication of individual WrapperTasks with adds.

        Covers:
        o wrapper_tasks
        o get_wrapper
        o add_subtask
        o add_functor_subtask
        """
        def wt_check(wt1, wt2, len1, len2=None, upto=None):
            """Assert that two WrapperTasks have the same Subtasks.

            :param wt1, wt2: The WrapperTask instances to compare.
            :param len1, len2: The expected lengths of the WrapperTask.subtasks
                               of wt1 and wt2, respectively.  If len2 is None,
                               it is assumed to be the same as len1.
            :param upto: (Optional, int) If specified, only the first 'upto'
                         Subtasks are compared.  Otherwise, the subtask lists
                         are compared up to the lesser of len1 and len2.
            """
            if len2 is None:
                len2 = len1
            self.assertEqual(len1, len(wt1.subtasks))
            self.assertEqual(len2, len(wt2.subtasks))
            if upto is None:
                upto = min(len1, len2)
            for i in range(upto):
                self.assertIs(wt1.subtasks[i], wt2.subtasks[i])

        # "Functors" for easy subtask creation.  Named so we can identify them.
        foo = lambda: None
        bar = lambda: None
        baz = lambda: None
        xyz = lambda: None
        abc = lambda: None
        # setUp's initialization of feed_task creates empty dict and common_tx
        self.assertEqual({}, self.feed_task._tx_by_uuid)
        self.assertEqual(0, len(self.feed_task._common_tx.subtasks))
        # Asking for the feed does *not* replicate the WrapperTasks
        feed = self.feed_task.feed
        self.assertEqual({}, self.feed_task._tx_by_uuid)
        self.assertEqual(0, len(self.feed_task._common_tx.subtasks))
        # Add to the FeedTask
        self.feed_task.add_subtask(tx._FunctorSubtask(foo))
        self.feed_task.add_functor_subtask(bar)
        # Still does not replicate
        self.assertEqual({}, self.feed_task._tx_by_uuid)
        subtasks = self.feed_task._common_tx.subtasks
        # Make sure the subtasks are legit and in order
        self.assertEqual(2, len(subtasks))
        self.assertIsInstance(subtasks[0], tx.Subtask)
        self.assertIsInstance(subtasks[1], tx.Subtask)
        # Yes, these are both _FunctorSubtasks, but the point is verifying that
        # they are in the right order.
        self.assertIs(foo, subtasks[0]._func)
        self.assertIs(bar, subtasks[1]._func)
        # Now call something that triggers replication
        wrap10 = self.feed_task.get_wrapper(feed[10].uuid)
        self.assertEqual(feed[10], wrap10)
        self.assertNotEqual({}, self.feed_task._tx_by_uuid)
        self.assertEqual({lwrap.uuid for lwrap in feed},
                         set(self.feed_task.wrapper_tasks.keys()))
        # Pick a couple of wrapper tasks at random.
        wt5, wt8 = (self.feed_task.wrapper_tasks[feed[i].uuid] for i in (5, 8))
        # They should not be the same
        self.assertNotEqual(wt5, wt8)
        # Their subtasks should not refer to the same lists
        self.assertIsNot(wt5.subtasks, wt8.subtasks)
        # But they should have the same Subtasks (the same actual instances)
        wt_check(wt5, wt8, 2)
        # Adding more subtasks to the feed manager adds to all (and by the way,
        # we don't have to refetch the WrapperTasks).
        self.feed_task.add_functor_subtask(baz)
        wt_check(wt5, wt8, 3)
        self.assertIs(baz, wt5.subtasks[2]._func)
        # Adding to an individual WrapperTask just adds to that one
        wt5.add_functor_subtask(xyz)
        wt_check(wt5, wt8, 4, 3)
        self.assertIs(xyz, wt5.subtasks[3]._func)
        # And we can still add another to both afterward
        self.feed_task.add_functor_subtask(abc)
        wt_check(wt5, wt8, 5, 4, upto=3)
        # Check the last couple by hand
        self.assertIs(xyz, wt5.subtasks[3]._func)
        self.assertIs(wt5.subtasks[4], wt8.subtasks[3])
        self.assertIs(abc, wt5.subtasks[4]._func)

    def test_deferred_feed_get(self):
        """Test deferred and unique GET of the internal feed."""
        # setUp inits self.feed_task with FeedGetter.  This doesn't call read.
        self.assertEqual(0, self.adpt.read.call_count)
        lfeed = self.feed_task.feed
        self.assertEqual(1, self.adpt.read.call_count)
        self.adpt.read.assert_called_with(
            'LogicalPartition', None, child_id=None, child_type=None, xag=None)
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)
        # Getting feed again doesn't invoke GET again.
        lfeed = self.feed_task.feed
        self.assertEqual(1, self.adpt.read.call_count)
        self.assertEqual(21, len(lfeed))
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', lfeed[0].uuid)

        # Init with a feed - read is never called
        self.adpt.read.reset_mock()
        ftsk = tx.FeedTask('name', lfeed)
        self.assertEqual(0, self.adpt.read.call_count)
        nfeed = ftsk.feed
        self.assertEqual(0, self.adpt.read.call_count)
        self.assertEqual(lfeed, nfeed)

    def test_rebuild_feed(self):
        """Feed gets rebuilt when transactions exist and an etag mismatches."""
        # Populate and retrieve the feed
        lfeed = self.feed_task.feed
        # Pick out a wrapper UUID to use, from somewhere in the middle
        uuid = lfeed[13].uuid
        # Populate etags
        for i in range(len(lfeed)):
            lfeed[i]._etag = i + 100
        # This get_wrapper will replicate the UUID-to-WrapperTask dict.
        # Create a *copy* of the wrapper so that changing it will simulate how
        # a WrapperTask modifies its internal EntryWrapper on update() without
        # that change being reflected back to the FeedTask's _feed.  (Current
        # mocks are just returning the same wrapper all the time.)
        lpar13 = copy.deepcopy(self.feed_task.get_wrapper(uuid))
        self.assertNotEqual({}, self.feed_task._tx_by_uuid)
        # Set unique etag.
        lpar13._etag = 42
        # And stuff it back in the WrapperTask
        self.feed_task.wrapper_tasks[uuid]._wrapper = lpar13
        # Now we're set up.  First prove that the feed (as previously grabbed)
        # isn't already reflecting the new entry.
        self.assertNotEqual(lpar13.etag, lfeed[13].etag)
        # Ask for the feed again and this should change
        # The feed may have been reshuffled, so we have to find our LPAR again.
        lfind = None
        for entry in self.feed_task.feed:
            if entry.uuid == uuid:
                lfind = entry
                break
        self.assertEqual(lpar13.etag, lfind.etag)
        # And it is in fact the new one now in the feed.
        self.assertEqual(42, lfind.etag)

    def test_execute(self):
        """Execute a 'real' FeedTask."""
        feed = self.feed_task.feed
        # Initialize expected/actual flags dicts:
        #   {uuid: [ordered, list, of, flags]}
        # The list of flags for a given UUID should be ordered the same as the
        # subtasks, though they may get shotgunned to the dict via parallel
        # execution of the WrapperTasks.
        exp_flags = {ent.uuid: [] for ent in feed}
        act_flags = {ent.uuid: [] for ent in feed}

        # A function that we can run within a Subtask.  No triggering update
        # since we're just making sure the Subtasks run.
        def func(wrapper, flag):
            with lock.lock('act_flags'):
                act_flags[wrapper.uuid].append(flag)
            return False
        # Start with a subtask common to all
        self.feed_task.add_functor_subtask(func, 'common1')
        for ent in feed:
            exp_flags[ent.uuid].append('common1')
        # Add individual separate subtasks to a few of the WrapperTasks
        for i in range(5, 15):
            self.feed_task.wrapper_tasks[
                feed[i].uuid].add_functor_subtask(func, i)
            exp_flags[feed[i].uuid].append(i)
        # Add another common subtask
        self.feed_task.add_functor_subtask(func, 'common2')
        for ent in feed:
            exp_flags[ent.uuid].append('common2')
        # Run it!
        self.feed_task.execute()
        self.assertEqual(exp_flags, act_flags)

    @mock.patch('taskflow.patterns.unordered_flow.Flow.__init__')
    def test_no_subtasks(self, mock_flow):
        """Ensure that a FeedTask with no Subtasks is a no-op."""
        # No REST mocks - any REST calls will blow up.
        # Mocking Flow initializer to fail, ensuring it doesn't get called.
        mock_flow.side_effect = self.fail
        tx.FeedTask('feed_task', lpar.LPAR.getter(None)).execute()

    def test_post_exec(self):
        def log_func(msg):
            def _log(*a, **k):
                ftfx.log(msg)
            return _log

        def log_task(msg):
            return tf_task.FunctorTask(log_func(msg), name='functor_%s' % msg)

        # Limit the feed to two to keep the logging sane
        ftfx = self.useFixture(fx.FeedTaskFx(self.entries[:2]))
        # Make the logging predictable by limiting to one thread
        ftsk = tx.FeedTask('post_exec', lpar.LPAR.getter(None), max_workers=1)

        # First prove that a FeedTask with *only* post-execs can run.
        ftsk.add_post_execute(log_task('post1'))
        ftsk.add_post_execute(log_task('post2'))
        ftsk.execute()
        # Note that no GETs or locks happen
        self.assertEqual(['post1', 'post2'], ftfx.get_log())

        # Now add regular subtasks
        ftfx.reset_log()
        ftsk.add_functor_subtask(log_func('main1'))
        ftsk.add_functor_subtask(log_func('main2'))
        ftsk.execute()
        # One GET, up front.  Posts happen at the end.
        self.assertEqual(['get',
                          'lock', 'main1', 'main2', 'unlock',
                          'lock', 'main1', 'main2', 'unlock',
                          'post1', 'post2'], ftfx.get_log())
