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

import abc
import oslo_concurrency.lockutils as lock
import six
from taskflow import engines as tf_eng
from taskflow.patterns import unordered_flow as tf_uf
from taskflow import task as tf_task

import pypowervm.exceptions as ex
from pypowervm.i18n import _
from pypowervm.utils import retry
import pypowervm.wrappers.entry_wrapper as ewrap


def entry_transaction(func):
    """Decorator to facilitate transaction semantics on a PowerVM object.

    Typically, a method thus decorated will make some set of changes to an
    EntryWrapper and then perform one or more REST operations thereon.

    The *consumer* of the decorated method may pass either an EntryWrapper or
    an EntryWrapperGetter as the first argument.  The *developer* of the
    decorated method is guaranteed that the first argument is an EntryWrapper.

    This decorator provides three things:
    1) The decorated method may be invoked with either an EntryWrapper or an
    EntryWrapperGetter as its first argument.  However, within the body of the
    method, that argument is guaranteed to be the appropriate EntryWrapper.
    2) The decorated method is locked on the UUID of the PowerVM object on
    which it operates (represented by its first argument).  Only one method
    thus decorated can operate on that PowerVM object at one time.
    3) If the decorated method fails due to an etag mismatch - indicating that
    the wrapper was updated out-of-band between when it was retrieved and when
    it was updated - the wrapper is refreshed and the entire method is
    redriven.

    Example usage:

    @entry_transaction
    def add_gizmos_to_vios_wrapper(vios_wrapper, gizmos):
        vios_wrapper.gizmo_list.extend(gizmos)
        return vios_wrapper.update()

    This method can then be invoked either as:

    add_gizmos_to_vios_wrapper(existing_vios_wrapper, gizmos)

    or as:

    add_gizmos_to_vios_wrapper(pvm_vios.VIOS.getter(adapter, uuid), gizmos)
    """
    def _synchronize(wrp_or_spec, *a1, **k1):
        """Returned method is synchronized on the object's UUID."""
        @lock.synchronized(wrp_or_spec.uuid)
        def _resolve_wrapper(wos, *a2, **k2):
            """Returned method guaranteed to be called with a wrapper."""
            if isinstance(wos, ewrap.EntryWrapperGetter):
                wos = wos.get()

            @retry.retry(argmod_func=retry.refresh_wrapper)
            def _retry_refresh(wrapper, *a3, **k3):
                """Retry as needed, refreshing its wrapper each time."""
                return func(wrapper, *a3, **k3)
            return _retry_refresh(wos, *a2, **k2)
        return _resolve_wrapper(wrp_or_spec, *a1, **k1)
    return _synchronize


@six.add_metaclass(abc.ABCMeta)
class Subtask(object):
    """A single EntryWrapper modification to be performed within a WrapperTask.

    A subclass performs its work by overriding the execute method.  That method
    may or may not make changes to the EntryWrapper, which is its first
    argument.  Its return value must indicate whether changes were made to the
    wrapper: this is the trigger used by WrapperTask to determine whether to
    POST the changes back to the REST server via update().

    A Subtask should never update() or refresh() the wrapper.  That is handled
    by the surrounding WrapperTask.

    See WrapperTask for example usage.
    """
    def __init__(self, *save_args, **save_kwargs):
        """Create the Subtask, saving execution arguments for later.

        :param save_args: Positional arguments to be passed to the execute
                          method - *after* the wrapper - when it is invoked
                          under a WrapperTask.
        :param save_kwargs: Keyword arguments to be passed to the execute
                            method when it is invoked under a WrapperTask
        """
        self.save_args = save_args
        self.save_kwargs = save_kwargs

    @abc.abstractmethod
    def execute(self, *args, **kwargs):
        """Modify the EntryWrapper (must be overridden by the subclass).

        The execute method has two responsibilities:
        1) Performs the modification to the EntryWrapper which is passed as its
        first argument.
        2) Indicates whether any modifications were performed.

        Example:
        def execute(thingy_wrapper, primary_widget, widget_list, option=True):
            update_needed = False
            if primary_widget not in thingy_wrapper.widgets:
                thingy_wrapper.set_primary_widget(primary_widget)
                update_needed = True
            for widget in widget_list:
                thingy_wrapper.widgets.append(widget)
                update_needed = True
            return update_needed

        :param args: Positional arguments accepted by the execute method.  The
                     first argument will always be the EntryWrapper.  Overrides
                     may define their signatures using explicit parameter
                     names.
        :param kwargs: Keyword arguments accepted by the execute method.
                       Overrides may use explicit parameter names.
        :return: The return value must be a single value (this may be a list,
                 but not a tuple) which evaluates to True or False.  Any True
                 value indicates that the wrapper was modified and should be
                 POSTed back to the REST server via update().  Any False value
                 (including None, [], {}, etc) indicates that this Subtask did
                 not modify the wrapper.  (Note that it may still be POSTed if
                 modified by other Subtasks in the same WrapperTask.)
        """


class _FunctorSubtask(Subtask):
    """Shim to create a Subtask around an existing callable."""
    def __init__(self, _func, *save_args, **save_kwargs):
        """Save the callable as well as the arguments.

        :param _func: Callable to be invoked under the WrapperTask.
        :param save_args: See Subtask.__init__(save_args).
        :param save_kwargs: See Subtask.__init__(save_kwargs).
        """
        super(_FunctorSubtask, self).__init__(*save_args, **save_kwargs)
        self._func = _func

    def execute(self, wrapper, *_args, **_kwargs):
        """Invoke saved callable with saved args."""
        return self._func(wrapper, *_args, **_kwargs)


class WrapperTask(tf_task.BaseTask):
    """An atomic modify-and-POST transaction Task over a single EntryWrapper.

    The modifications should comprise some number of Subtask instances, added
    to this WrapperTask via the add_subtask and/or add_functor_subtask methods.
    These Subtasks should only modify the EntryWrapper, and should not POST
    (.update()) it back to the REST Server.  The WrapperTask will decide
    whether a POST is needed based on the returns from the Subtasks' execute
    methods, and perform it if indicated.

    The WrapperTask's execute method is encompassed by @entry_transaction,
    meaning that:
    1) The initial GET of the EntryWrapper may be deferred until after the lock
    is acquired.
    2) The execute method is locked on the UUID of the Entry in question.
    3) If the final update (POST) fails due to etag mismatch, the EntryWrapper
    is refetched and the entire transaction is redriven from the start.

    Usage:
        class ModifyGizmos(Subtask):
            def execute(self, wrapper, gizmo_list):
                update_needed = False
                if gizmo_list:
                    wrapper.gizmos.append(gizmo_list)
                    update_needed = True
                return update_needed
        ...
        tx = WrapperTask("do_lpar_things", LPAR.getter(adapter, lpar_uuid))
      or
        tx = WrapperTask("do_lpar_things", LPAR.getter(adapter, lpar_uuid),
                         subtasks=existing_wrapper_task.subtasks)
      or
        # Not recommended - increased probability of retry
        wrapper = LPAR.wrap(adapter.read(LPAR.schema_type, lpar_uuid))
        tx = WrapperTask("do_lpar_things", wrapper)
        ...
        tx.add_subtask(ModifyGizmos([giz1, giz2]))
        ...
        tx.add_functor_subtask(add_widget, widget, frob=True)
        ...
        finalized_lpar = tx.execute()
    """
    def __init__(self, name, wrapper_or_getter, subtasks=None):
        """Initialize this WrapperTask.

        :param name: A descriptive string name for the WrapperTask.
        :param wrapper_or_getter: An EntryWrapper or EntryWrapperGetter
                                  representing the PowerVM object on which this
                                  WrapperTask is to be performed.
        :param subtasks: (Optional) Iterable of Subtask subclass instances with
                         which to seed this WrapperTask.
        """
        super(WrapperTask, self).__init__(name)
        if isinstance(wrapper_or_getter, ewrap.EntryWrapperGetter):
            self._wrapper = None
            self._getter = wrapper_or_getter
        elif isinstance(wrapper_or_getter, ewrap.EntryWrapper):
            self._wrapper = wrapper_or_getter
            self._getter = None
        else:
            raise ValueError(_("Must supply either EntryWrapper or "
                               "EntryWrapperGetter"))
        self._tasks = [] if subtasks is None else list(subtasks)
        self.provides = 'wrapper_%s' % wrapper_or_getter.uuid

    def add_subtask(self, task):
        """Add a Subtask to this WrapperTask.

        Subtasks will be invoked serially and synchronously in the order in
        which they are added.

        :param task: Instance of a Subtask subclass containing the logic to
                     invoke.
        :return: self, for chaining convenience.
        """
        if not isinstance(task, Subtask):
            raise ValueError(_("Must supply a valid Subtask."))
        self._tasks.append(task)
        return self

    def add_functor_subtask(self, func, *args, **kwargs):
        """Create and add a Subtask for an already-defined method.

        :param func: A callable to be the core of the Subtask.  The contract
                     for this method is identical to that of Subtask.execute -
                     see that method's docstring for details.
        :param args: Positional arguments to be passed to the callable func
                     (after the EntryWrapper parameter) when it is executed
                     within the WrapperTask.
        :param kwargs: Keyword arguments to be passed to the callable func when
                       it is executed within the WrapperTask.
        :return: self, for chaining convenience.
        """
        return self.add_subtask(_FunctorSubtask(func, *args, **kwargs))

    @property
    def wrapper(self):
        """(Fetches and) returns the EntryWrapper.

        Use this only if you need the EntryWrapper outside of the WrapperTask's
        execution itself.

        Note that this guarantees a GET outside of lock, and should therefore
        be used only if absolutely necessary.
        """
        if not self._wrapper:
            self._wrapper = self._getter.get()
        return self._wrapper

    @property
    def subtasks(self):
        """Return the sequence of Subtasks registered with this WrapperTask.

        This is returned as a tuple (not modifiable).  To add subtasks, use the
        add_[functor_]subtask method.
        """
        return tuple(self._tasks)

    def execute(self):
        """Invoke subtasks and update under @entry_transaction.

        The flow is as follows:

        1 Lock on wrapper UUID
        2 GET wrapper if necessary
        3 For each registered Subtask:
            - Invoke the Subtask to modify the wrapper
        4 If update is necessary, POST the wrapper.  If POST fails with etag
          mismatch:
            - Refresh the wrapper
            - goto 2
        5 Unlock
        """
        if len(self._tasks) == 0:
            raise ex.WrapperTaskNoSubtasks(name=self.name)

        @entry_transaction
        def _execute(wrapper):
            update_needed = False
            for task in self._tasks:
                if task.execute(wrapper, *task.save_args, **task.save_kwargs):
                    update_needed = True
            if update_needed:
                wrapper = wrapper.update()
            return wrapper
        # Use the wrapper if already fetched, or the getter if not
        self._wrapper = _execute(self._wrapper or self._getter)
        return self._wrapper


class FeedTask(tf_task.BaseTask):
    """Invokes WrapperTasks in parallel over each EntryWrapper in a feed.

    Usage
      Creation:
        # Preferred
        fm = FeedTask('lpar_frobnicate', LPAR.getter(adapter))
      or
        # Non-preferred.  See 'Greedy Methods' warning below
        feed = LPAR.wrap(adapter.read(LPAR.schema_type, ...))
        fm = FeedTask('lpar_frobnicate', feed)

      Adding Subtasks:
        # Preferred
        fm.add_subtask(FrobnicateLpar(foo, bar))
        fm.add_functor_subtask(frobnify, abc, xyz)
      and/or
        # Non-preferred.  See 'Greedy Methods' warning below
        for uuid, txn in fm.wrapper_tasks.items():
            if meets_criteria(txn.wrapper, uuid):
                txn.add_subtask(FrobnicateLpar(baz, blah))
        fm.get_wrapper_task(known_uuid).add_subtask(FrobnicateLpar(baz, blah)

      Execution/TaskFlow management:
        main_flow.add(fm)
        ...
        taskflow.engines.run(main_flow)

    Warning: Greedy Methods
    This implementation makes every effort to defer the feed GET as long as
    possible.  The more time passes between the GET and the execution of the
    WrapperTasks, the more likely it is that some out-of-band change will have
    modified one of the objects represented in the feed. This will cause an
    etag mismatch on that WrapperTask's update (POST), resulting in that
    WrapperTask being redriven, which costs an extra GET+POST to the REST
    server.

    Consumers of this class can thwart these efforts by:
    a) Initializing the FeedTask with an already-retrieved feed instead of a
       FeedGetter; or
    b) Using any of the following methods/properties prior to execution.  All
       of these will trigger a GET of the feed if not already fetched:

    .wrapper_tasks
    .get_wrapper_task(uuid)
    .feed

    The cost is incurred only the first time one of these is used.  If your
    workflow requires calling one of these early, it is not necessary to
    avoid them subsequently.
    """
    def __init__(self, name, feed_or_getter, max_workers=10):
        """Create a FeedTask with a FeedGetter (preferred) or existing feed.

        :param name: A descriptive string name.  This will be used along with
                     each wrapper's UUID to generate the name for that
                     wrapper's WrapperTask.
        :param feed_or_getter: pypowervm.wrappers.entry_wrapper.FeedGetter or
                               an already-fetched feed (list of EntryWrappers)
                               over which to operate.
        :param max_workers: (Optional) Integer indicating the maximum number of
                            worker threads to run in parallel within the .flow
                            or by the .execute method. See
                            concurrent.futures.ThreadPoolExecutor(max_workers).
        """
        super(FeedTask, self).__init__(name)
        if isinstance(feed_or_getter, ewrap.FeedGetter):
            self._feed = None
            self._getter = feed_or_getter
        elif isinstance(feed_or_getter, list):
            # Make sure the feed has something in it.
            if len(feed_or_getter) == 0:
                raise ex.FeedTaskEmptyFeed()
            # Make sure it's a list of EntryWrapper
            if [i for i in feed_or_getter
                    if not isinstance(i, ewrap.EntryWrapper)]:
                raise ValueError("List must contain EntryWrappers "
                                 "exclusively.")
            self._feed = feed_or_getter
            self._getter = None
        else:
            raise ValueError(_("Must supply either a list of EntryWrappers or "
                               "a FeedGetter."))
        # Max WrapperTasks to run in parallel
        self.max_workers = max_workers
        # Map of {uuid: WrapperTask}.  We keep this empty until we need the
        # individual WraperTasks.  This is triggered by .wrapper_tasks and
        # .get_wrapper_task(uuid) (and obviously executing).
        self._tx_by_uuid = {}
        # Until we *need* individual WrapperTasks, save subtasks in one place.
        # EntryWrapperGetter is a cheat to allow us to build the WrapperTask.
        self._common_tx = WrapperTask(
            'internal', ewrap.EntryWrapperGetter(None, None, None))

    @property
    def wrapper_tasks(self):
        """(Greedy) Dictionary of {uuid: WrapperTask} for all wrappers.

        The first access of this property triggers a GET of the feed if it has
        not already been fetched, so use judiciously.
        """
        if not self._tx_by_uuid:
            # Create a separate WrapperTask for each wrapper in the feed.
            # As long as the consumer uses FeedTask.add_[functor_]subtask
            # and doesn't ask for .wrapper_tasks, we keep only one copy of the
            # subtask list.  Once the consumer "breaks the seal" and requests
            # individual WrapperTasks per wrapper, we need to (GET the feed -
            # this is triggered by .feed - and) create them based on this
            # common subtask list.
            # This is only done once.  Thereafter, .add_[functor_]subtask will
            # add separately to each WrapperTask.
            for entry in self.feed:
                name = '%s_%s' % (self.name, entry.uuid)
                self._tx_by_uuid[entry.uuid] = WrapperTask(
                    name, entry, subtasks=self._common_tx.subtasks)
        return self._tx_by_uuid

    def get_wrapper_task(self, uuid):
        """(Greedy) Finds the WrapperTask for a wrapper with a particular UUID.

        Note that this method triggers a GET of the feed if it has not already
        been fetched, so use judiciously.

        :param uuid: The UUID of the wrapper of interest.
        :return: The WrapperTask instance for that particular wrapper.
        :raise KeyError: If there's no WrapperTask for a wrapper with the
                         specified UUID.
        """
        return self.wrapper_tasks[uuid]

    def add_subtask(self, task):
        """Add a Subtask to *all* WrapperTasks in this FeedTask.

        To add Subtasks to individual WrapperTasks, iterate over the result of
        the 'wrapper_tasks' property.

        Specification is the same as for WrapperTask.add_subtask.
        """
        if self._tx_by_uuid:
            # _tx_by_uuid is guaranteed to have WrapperTasks for all UUIDs,
            # including this one
            for txn in self._tx_by_uuid.values():
                txn.add_subtask(task)
        else:
            self._common_tx.add_subtask(task)
        return self

    def add_functor_subtask(self, func, *args, **kwargs):
        """Add a functor Subtask to *all* WrapperTasks in this FeedTask.

        To add Subtasks to individual WrapperTasks, iterate over the result of
        the 'wrapper_tasks' property.

        Specification is the same as for WrapperTask.add_functor_subtask.
        """
        return self.add_subtask(_FunctorSubtask(func, *args, **kwargs))

    @property
    def feed(self):
        """(Greedy) Returns this FeedTask's feed (list of wrappers).

        The first access of this property triggers a GET of the feed if it has
        not already been fetched, so use this only if you need the
        EntryWrappers outside of the execution itself.
        """
        if self._feed is None:
            self._feed = self._getter.get()
        if len(self._feed) == 0:
            raise ex.FeedTaskEmptyFeed()
        # Do we need to refresh the feed based on having been run?
        # If we haven't replicated WrapperTasks yet, there's no chance we're
        # out of sync - and we don't want to trigger GET/replication.
        if self._tx_by_uuid:
            # TODO(efried): This has scary synchronization implications if it
            # happens while WrapperTasks are running.  Figure out an
            # appropriate sempaphore.
            for wrap in self._feed:
                if self.get_wrapper_task(wrap.uuid).wrapper.etag != wrap.etag:
                    break
            else:
                # Refresh needed
                self._feed = [tx.wrapper for tx in self.wrapper_tasks.values()]
        return self._feed

    def execute(self):
        """Run this FeedTask's WrapperTasks in parallel TaskFlow engine."""
        pflow = tf_uf.Flow("%s_parallel_flow" % self.name)
        # Calling .wrapper_tasks will cause the feed to be fetched and
        # WrapperTasks to be replicated, if not already done.
        pflow.add(*self.wrapper_tasks.values())
        tf_eng.run(pflow, engine='parallel', max_workers=self.max_workers)
