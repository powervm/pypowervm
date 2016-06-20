# Copyright 2015, 2016 IBM Corp.
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

"""Tasks specific to partitions (LPARs and VIOSes)."""

from oslo_log import log as logging
import retrying

import pypowervm.const as c
import pypowervm.exceptions as ex
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.utils.transaction as tx
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.virtual_io_server as vios

LOG = logging.getLogger(__name__)

# RMC must be either active or busy.  Busy is allowed because that simply
# means that something is running against the VIOS at the moment...but
# it should recover shortly.
VALID_RMC_STATES = [bp.RMCState.ACTIVE, bp.RMCState.BUSY]

# Only a running state is OK for now.
VALID_VM_STATES = [bp.LPARState.RUNNING]


def get_mgmt_partition(adapter):
    """Get the LPAR wrapper representing the PowerVM management partition.

    :param adapter: The pypowervm.adapter.Adapter through which to query the
                    REST API.
    :return: pypowervm.wrappers.logical_partition.LPAR wrapper representing the
             management partition.
    :raise ManagementPartitionNotFoundException: if we don't find exactly one
                                                 management partition.
    """
    wraps = lpar.LPAR.search(adapter, is_mgmt_partition=True)
    if len(wraps) != 1:
        raise ex.ManagementPartitionNotFoundException(count=len(wraps))
    return wraps[0]


def get_this_partition(adapter):
    """Get the LPAR wrapper representing the node on which this method runs.

    :param adapter: The pypowervm.adapter.Adapter through which to query the
                    REST API.
    :return: pypowervm.wrappers.logical_partition.LPAR wrapper representing the
             local partition.
    :raise LocalPartitionNotFoundException: if we don't find exactly one LPAR
                                            with the local VM's short ID.
    """
    myid = u.my_partition_id()
    wraps = lpar.LPAR.search(adapter, id=myid)
    if len(wraps) != 1:
        raise ex.ThisPartitionNotFoundException(lpar_id=myid, count=len(wraps))
    return wraps[0]


def get_active_vioses(adapter, xag=(), vios_wraps=None):
    """Returns a list of active Virtual I/O Server Wrappers for a host.

    Active is defined by powered on and RMC state being 'active'.

    :param adapter: The pypowervm adapter for the query.
    :param xag: (Optional, Default: ()) Iterable of extended attributes to use.
    :param vios_wraps: (Optional, Default: None) A list of VIOS wrappers. If
                       specified, the method will check for active VIOSes
                       in this list instead of issuing a GET.
    :return: List of VIOS wrappers.
    """
    if not vios_wraps:
        vios_wraps = vios.VIOS.get(adapter, xag=xag)

    return [vio for vio in vios_wraps if vio.rmc_state in VALID_RMC_STATES and
            vio.state in VALID_VM_STATES]


def _get_inactive_running_vioses(vios_wraps):
    """Method to get RMC inactive but powered on VIOSes

    Not waiting for VIOS RMC states to go active when the host boots up
    may result in stale adapter mappings from evacuated instances.

    :param vios_wraps: A list of VIOS wrappers.
    :return: List of RMC inactive but powered on VIOSes from the list.
    """
    inactive_running_vioses = []
    for vwrap in vios_wraps:
        if (vwrap.rmc_state not in VALID_RMC_STATES and
            vwrap.state not in [bp.LPARState.NOT_ACTIVATED,
                                bp.LPARState.ERROR,
                                bp.LPARState.NOT_AVAILBLE,
                                bp.LPARState.SHUTTING_DOWN,
                                bp.LPARState.SUSPENDED,
                                bp.LPARState.SUSPENDING,
                                bp.LPARState.UNKNOWN]):
            inactive_running_vioses.append(vwrap)

    return inactive_running_vioses


def get_physical_wwpns(adapter):
    """Returns the active WWPNs of the FC ports across all VIOSes on system.

    :param adapter: pypowervm.adapter.Adapter for REST API communication.
    """
    vios_feed = vios.VIOS.get(adapter, xag=[c.XAG.VIO_STOR])
    wwpn_list = []
    for vwrap in vios_feed:
        wwpn_list.extend(vwrap.get_active_pfc_wwpns())
    return wwpn_list


def build_active_vio_feed_task(adapter, name='vio_feed_task', xag=(
        c.XAG.VIO_STOR, c.XAG.VIO_SMAP, c.XAG.VIO_FMAP)):
    """Builds the a FeedTask for all active VIOSes.

    The transaction FeedTask enables users to collect a set of 'WrapperTasks'
    against a feed of entities (in this case a set of active VIOSes). The
    WrapperTask (within the FeedTask) handles lock and retry.

    This is useful to batch together a set of updates across a feed of elements
    (and multiple updates within a given wrapper).  This allows for significant
    performance improvements.

    :param adapter: The pypowervm adapter for the query.
    :param name: (Optional) The name of the feed manager.  Defaults to
                 vio_feed_task.
    :param xag: (Optional) Iterable of extended attributes to use.  If not
                specified, defaults to all mapping/storage options (as this is
                most common case for using a transaction manager).
    """
    active_vio_feed = get_active_vioses(adapter, xag=xag)
    if not active_vio_feed:
        raise ex.NoActiveVios()

    return tx.FeedTask(name, active_vio_feed)


def validate_vios_ready(adapter, max_wait_time=300):
    """Check whether VIOS rmc is up and running on this host.

    Will query the VIOSes for a period of time attempting to ensure all
    running VIOSes get an active RMC.  If no VIOSes are ready by the timeout,
    ViosNotAvailable is raised.  If only some of the VIOSes had RMC go active
    by the end of the wait period, the method will complete.

    :param adapter: The pypowervm adapter for the query.
    :param max_wait_time: Maximum number of seconds to wait for running VIOSes
                          to get an active RMC connection.  Defaults to 300
                          (five minutes).
    :raises: A ViosNotAvailable exception if a VIOS is not available by a
             given timeout.
    """
    # Used to keep track of VIOSes and reduce queries to API
    vios_wraps = []
    rmc_down_vioses = []

    @retrying.retry(retry_on_result=lambda result: len(result) > 0,
                    wait_fixed=5 * 1000,
                    stop_max_delay=max_wait_time * 1000)
    def _wait_for_active_vioses():
        try:
            # Update the wrappers list and get the list of inactive
            # running VIOSes
            del vios_wraps[:]
            vios_wraps.extend(vios.VIOS.get(adapter))
            return _get_inactive_running_vioses(vios_wraps)
        except Exception as e:
            LOG.exception(e)
            # If we errored then we want to keep retrying so return something
            # with a length greater than zero
            return [None]

    try:
        rmc_down_vioses = _wait_for_active_vioses()
    except retrying.RetryError:
        # This is thrown if we've hit our max retry count.  If so, no
        # issue... just continue
        pass

    if len(rmc_down_vioses) > 0 and rmc_down_vioses != [None]:
        LOG.warning(
            _('Timed out waiting for the RMC state of all the powered on '
              'Virtual I/O Servers to be active. Wait time was: %(time)s '
              'seconds. VIOSes that did not go active were: %(vioses)s.'),
            {'time': max_wait_time,
             'vioses': ', '.join([
                 vio.name for vio in rmc_down_vioses if vio is not None])})

    # If we didn't get a single active VIOS then raise an exception
    if not get_active_vioses(adapter, vios_wraps=vios_wraps):
        raise ex.ViosNotAvailable(wait_time=max_wait_time)
