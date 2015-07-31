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
from taskflow import task as tf_task

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
class TransactionSubtask(object):
    """A single EntryWrapper modification to be performed within a Transaction.

    A subclass performs its work by overriding the execute method.  That method
    may or may not make changes to the EntryWrapper, which is its first
    argument.  It should internally invoke the update_needed setter to indicate
    whether changes were made to the wrapper.

    See Transaction for example usage.
    """
    def __init__(self, *save_args, **save_kwargs):
        """Create the TransactionSubtask, saving execute's arguments for later.

        :param save_args: Positional arguments to be passed to the execute
                          method - *after* the wrapper - when it is invoked
                          under a Transaction.
        :param save_kwargs: Keyword arguments to be passed to the execute
                            method when it is invoked under a Transaction
        """
        self.save_args = save_args
        self.save_kwargs = save_kwargs
        self._update_needed = False

    @abc.abstractmethod
    def execute(self, *args, **kwargs):
        """Modify the EntryWrapper (must be overridden by the subclass).

        The execute method has two responsibilities:
        1) Performs the modification to the EntryWrapper which is passed as its
        first argument.
        2) Indicates, via the update_needed setter, whether any modifications
        were performed.

        Example:
        def execute(thingy_wrapper, primary_widget, widget_list, option=True):
            if primary_widget not in thingy_wrapper.widgets:
                thingy_wrapper.set_primary_widget(primary_widget)
                self.update_needed = True
            for widget in widget_list:
                thingy_wrapper.widgets.append(widget)
                self.update_needed = True
            return thingy_wrapper

        :param args: Positional arguments accepted by the execute method.  The
                     first argument will always be the EntryWrapper.  Overrides
                     may define their signatures using explicit parameter
                     names.
        :param kwargs: Keyword arguments accepted by the execute method.
                       Overrides may use explicit parameter names.
        :return: The (possibly modified) wrapper.
        """

    @property
    def update_needed(self):
        """Indicates whether an update (POST) of the EntryWrapper is needed.

        This TransactionSubtask's execute method should use the update_needed
        setter to indicate whether it thinks the wrapper needs to be POSTed
        back to the REST server.  By setting update_needed = True, this
        TransactionSubtask guarantees that the Transaction to which it belongs
        will attempt such a POST at the end of the Transaction.

        :return: Boolean True if this TransactionSubtask thinks the
                 EntryWrapper needs to be POSTed back to the REST server; False
                 otherwise.
        """
        return self._update_needed

    @update_needed.setter
    def update_needed(self, needed):
        """Indicates whether an update (POST) of the EntryWrapper is needed.

        This TransactionSubtask's execute method should use the update_needed
        setter to indicate whether it thinks the wrapper needs to be POSTed
        back to the REST server.  By setting update_needed = True, this
        TransactionSubtask guarantees that the Transaction to which it belongs
        will attempt such a POST at the end of the Transaction.

        The TransactionSubtask base class defaults update_needed to False, so
        a direct subclass's execute method need only set it if it should be
        True.  (Note that intervening subclasses may change this default
        behavior, though this is not recommended.)

        :param needed: Boolean True if this TransactionSubtask thinks the
                       EntryWrapper needs to be POSTed back to the REST server;
                       False otherwise.
        """
        self._update_needed = needed


class Transaction(tf_task.BaseTask):
    """An atomic modify-and-POST transaction Task over a single EntryWrapper.

    The modifications should comprise some number of TransactionSubtask
    instances, added to this Transaction via the add_task method.  These
    TransactionSubtasks should only modify the EntryWrapper, and should not
    POST (.update()) it back to the REST Server.  The Transaction will decide
    whether a POST is needed based on TransactionSubtasks setting
    update_needed, and perform it if indicated.

    The Transaction's execute method is encompassed by @entry_transaction,
    meaning that:
    1) The initial GET of the EntryWrapper may be deferred until after the lock
    is acquired.
    2) The Transaction is locked on the UUID of the Entry in question.
    3) If the final update (POST) fails due to etag mismatch, the EntryWrapper
    is refetched and the entire Transaction is redriven from the start.

    Usage:
    class ModifyGizmos(TransactionSubtask):
        def execute(self, wrapper, gizmo_list):
            if gizmo_list:
                wrapper.gizmos.append(gizmo_list)
                self.update_needed = True
            return wrapper
    ...
    tx = Transaction("do_lpar_things", LPAR.getter(lpar_uuid))
    ...
    tx.add_task(ModifyGizmos([giz1, giz2]))
    ...
    tx.add_functor_task(add_widget, widget, frob=True)
    ...
    finalized_lpar = tx.execute()
    """
    def __init__(self, name, wrapper_or_getter):
        super(Transaction, self).__init__(name)
        if isinstance(wrapper_or_getter, ewrap.EntryWrapperGetter):
            self._wrapper = None
            self._getter = wrapper_or_getter
        elif isinstance(wrapper_or_getter, ewrap.EntryWrapper):
            self._wrapper = wrapper_or_getter
            self._getter = None
        else:
            raise ValueError(_("Must supply either EntryWrapper or "
                               "EntryWrapperGetter"))
        self._uuid = wrapper_or_getter.uuid
        self._tasks = []
        self.provides = 'wrapper_%s' % self._uuid

    def add_task(self, task):
        """Add a TransactionSubtask to this Transaction.

        TransactionSubtasks will be invoked serially and synchronously in the
        order in which they are added.

        :param task: A TransactionSubtask subclass containing the logic to
                     invoke.
        :return: self, for chaining convenience.
        """
        if not isinstance(task, TransactionSubtask):
            raise ValueError(_("Must supply a valid TransactionSubtask."))
        self._tasks.append(task)
        return self

    def add_functor_task(self, func, *args, **kwargs):
        """Create/add a TransactionSubtask for an already-defined method.

        :param func: A callable to be the core of the TransactionSubtask.  Note
                     that the contract is slightly different from that of
                     TransactionSubtask.execute in an attempt to facilitate
                     using already-written methods which return some structure
                     indicating the changes made to the wrapper. The boolean
                     evaluation of the return value is translated into
                     update_needed.  Full specification:
            def func(wrapper, *args, **kwargs):
                :param wrapper: EntryWrapper on which to operate.  Do not POST
                                this back to the REST server - only modify the
                                wrapper itself.
                :param *args, **kwargs: Additional arguments to be passed to
                                        the callable when it is executed.
                :return: Any value which evaluates to True will cause the
                         surrounding Transaction to assume update_needed = True
                         and ensure a POST of the EntryWrapper back to the REST
                         server at the end of the Transaction.
        :param args: Positional arguments to be passed to the callable func
                     (after the EntryWrapper parameter) when it is executed
                     within the Transaction.
        :param kwargs: Keyword arguments to be passed to the callable func when
                       it is executed within the Transaction.
        :return: self, for chaining convenience.
        """
        class _FunctorTransactionSubtask(TransactionSubtask):
            """Shim to create a TransactionSubtask around existing callable."""
            def __init__(self, _func, *save_args, **save_kwargs):
                """Save the callable as well as the arguments.

                :param _func: Callable to be invoked under the Transaction.
                :param save_args: See TransactionSubtask.__init__(save_args).
                :param save_kwargs: See
                                    TransactionSubtask.__init__(save_kwargs).
                """
                super(_FunctorTransactionSubtask, self).__init__(
                    *save_args, **save_kwargs)
                self._func = _func

            def execute(self, wrapper, *_args, **_kwargs):
                """Invoke saved callable; interpret return as update_needed."""
                ret = self._func(wrapper, *_args, **_kwargs)
                self.update_needed = True if ret else False
                return wrapper

        return self.add_task(_FunctorTransactionSubtask(func, *args, **kwargs))

    @property
    def wrapper(self):
        """(Fetches and) returns the EntryWrapper.

        Use this only if you need the EntryWrapper outside of the Transaction's
        execution itself.

        Note that this guarantees a GET outside of lock, and should therefore
        be used only if absolutely necessary.
        """
        if not self._wrapper:
            self._wrapper = self._getter.get()
        return self._wrapper

    def execute(self):
        @entry_transaction
        def _execute(wrapper):
            update_needed = False
            # Used to validate returns from TransactionSubtasks
            orig_class = wrapper.__class__
            for task in self._tasks:
                wrapper = task.execute(wrapper, *task.save_args,
                                       **task.save_kwargs)
                assert wrapper.__class__ is orig_class, _(
                    "Wrapper class changed from %(orig_class)s to "
                    "%(new_class)s!") % {'orig_class': orig_class,
                                         'new_class': wrapper.__class__}
                if task.update_needed:
                    update_needed = True
            if update_needed:
                wrapper = wrapper.update()
            return wrapper
        return _execute(self._wrapper)
