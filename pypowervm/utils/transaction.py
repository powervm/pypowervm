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

import oslo_concurrency.lockutils as lock

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
