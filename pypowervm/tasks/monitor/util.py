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

"""Utilities to query and parse the metrics data."""


import abc
import datetime

from oslo_concurrency import lockutils
from oslo_log import log as logging
import six

from pypowervm import adapter as pvm_adpt
from pypowervm.i18n import _
from pypowervm.tasks.monitor import lpar as lpar_mon
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import monitor as pvm_mon
from pypowervm.wrappers.pcm import lpar as lpar_pcm
from pypowervm.wrappers.pcm import phyp as phyp_mon
from pypowervm.wrappers.pcm import vios as vios_mon


LOG = logging.getLogger(__name__)

RAW_METRICS = 'RawMetrics'


@six.add_metaclass(abc.ABCMeta)
class MetricCache(object):
    """Provides a cache of the metrics data.

    The core LongTermMetrics API only refreshes its internal metric data once
    (generally) every 30 seconds.  This class provides a generalized cache
    of the metrics.  It stores both the raw phyp and vios metrics (if
    available) and will only refresh them after a specified time period has
    elapsed (30 seconds by default).
    """

    def __init__(self, adapter, host_uuid, refresh_delta=30, include_vio=True):
        """Creates an instance of the cache.

        :param adapter: The pypowervm Adapter.
        :param host_uuid: The UUID of the host CEC to maintain a metrics
                          cache for.
        :param refresh_delta: (Optional) The interval at which the metrics
                              should be updated.  Will only update if the
                              interval has been passed and the user invokes a
                              cache query.  Will not update in the background,
                              only if the cache is used.
        :param include_vio: (Optional) Defaults to True.  If set to false, the
                            cur_vioses and prev_vioses will always be
                            unavailable.  This increases the speed for refresh.
        """
        # Ensure that the metric monitoring is enabled.
        ensure_ltm_monitors(adapter, host_uuid)

        # Save the data
        self.adapter = adapter
        self.host_uuid = host_uuid
        self.refresh_delta = datetime.timedelta(seconds=refresh_delta)
        self.include_vio = include_vio

        # Ensure these elements are defined up front.
        self.cur_date, self.cur_phyp, self.cur_vioses, self.cur_lpars = (
            None, None, None, None)
        self.prev_date, self.prev_phyp, self.prev_vioses = (
            None, None, None)

        # Run a refresh up front.
        self._refresh_if_needed()

    def _refresh_if_needed(self):
        """Refreshes the cache if needed."""
        # The refresh is needed is the current date is none, or if the refresh
        # time delta has been crossed.
        refresh_needed = self.cur_date is None

        # This is put into an if block so that we don't run the logic if
        # cur_date is in fact None...
        if not refresh_needed:
            diff_date = datetime.datetime.now() - self.cur_date
            refresh_needed = diff_date > self.refresh_delta

        # At this point, if a refresh isn't needed, then exit.
        if not refresh_needed:
            return

        # Refresh is needed...get the next metric.
        self.prev_date, self.prev_phyp, self.prev_vioses = (
            self.cur_date, self.cur_phyp, self.cur_vioses)

        self.cur_date, self.cur_phyp, self.cur_vioses, self.cur_lpars = (
            latest_stats(self.adapter, self.host_uuid,
                         include_vio=self.include_vio))

        # Have the class that is implementing the cache update its simplified
        # representation of the data.  Ex. LparMetricCache
        self._update_internal_metric()

    def _update_internal_metric(self):
        """Save the raw metric to the transformed values.

        Implemented by the child class.  Should transform the phyp and
        vios data into the format required by the implementor.
        """
        raise NotImplementedError()


class LparMetricCache(MetricCache):
    """Provides a cache of metrics on a per LPAR level.

    Metrics are expensive to gather and to parse.  It is expensive because
    the backing API gathers all of the metrics at the Hypervisor and Virtual
    I/O Server levels.  This returns all of the LPARs.  Therefore, this cache
    parses in all of the data once, and allows the invoker to get individual
    LPAR metrics without having to re-query the API server.

    This class provides a caching mechanism along with a built in refresh
    mechanism if enough time has passed since last gathering the metrics.

    This cache will obtain the metrics for a given system, separate them out
    into an individual LparMetric cache.  If another LPAR is required, the
    cache will be used (so a subsequent API call is not required).

    There is a refresh_interval as well.  If the interval is passed, a
    subsequent query of the metrics will force a refresh of the cache.

    The previous metric is also saved within the cache.  This is useful for
    generating rates on the metrics (a previous element to compare against).

    The cache will only contain the last two samples of hypervisor/vios data.
    This is so that the current sample and the previous sample are maintained.
    The data is maintained for all of the systems that metrics data has data
    for - but this is still quite thin.  This cache does not have support
    to maintain additional samples.

    Trimming is done upon each refresh (which is triggered by the
    get_latest_metric).  To wipe the cache, the user should just have the cache
    go out of scope and it will be cleared.  No manual clean up is required.
    """

    def __init__(self, adapter, host_uuid, refresh_delta=30):
        """Creates an instance of the cache.

        :param adapter: The pypowervm Adapter.
        :param host_uuid: The UUID of the host CEC to maintain a metrics
                          cache for.
        :param refresh_delta: (Optional) The interval at which the metrics
                              should be updated.  Will only update if the
                              interval has been passed and the user invokes a
                              cache query.  Will not update in the background,
                              only if the cache is used.
        """
        # Ensure these elements are defined up front so that references don't
        # error out if they haven't been set yet.  These will be the results
        # from the vm_metrics method.
        self.cur_metric, self.prev_metric = None, None

        # Invoke the parent to seed the metrics.
        super(LparMetricCache, self).__init__(adapter, host_uuid,
                                              refresh_delta=refresh_delta)

    @lockutils.synchronized('pvm_lpar_metrics_get')
    def get_latest_metric(self, lpar_uuid):
        """Returns the latest metrics for a given LPAR.

        This will pull from the cache, but will refresh the cache if the
        refresh interval has passed.

        :param lpar_uuid: The UUID of the LPAR to query for the metrics.
        :return: Two elements.
                  - First is the date of the metric.
                  - Second is the LparMetric

                 Note that both of these can be None.  If the date of the
                 metric is None, that indicates that there was no previous
                 metric (or something is wrong with the gather flow).

                 If the date of the metric is None, then the second value will
                 be None as well.

                 If the date of the metric is set, but None is returned for
                 the value then the LPAR had no metrics for it.  Scenarios can
                 occur where the current metric may have a value but not the
                 previous (ex. when a LPAR was just created).
        """
        # Refresh if needed.  Will no-op if no refresh is required.
        self._refresh_if_needed()

        # No metric, no operation.
        if self.cur_metric is None:
            return self.cur_date, None

        return self.cur_date, self.cur_metric.get(lpar_uuid)

    @lockutils.synchronized('pvm_lpar_metrics_get')
    def get_previous_metric(self, lpar_uuid):
        """Returns the previous metric for a given LPAR.

        This will NOT update the cache.  That can only be triggered from the
        get_latest_metric method.

        :param lpar_uuid: The UUID of the LPAR to query for the metrics.
        :return: Two elements.
                  - First is the date of the metric.
                  - Second is the LparMetric

                 Note that both of these can be None.  If the date of the
                 metric is None, that indicates that there was no previous
                 metric (or something is wrong with the gather flow).

                 If the date of the metric is None, then the second value will
                 be None as well.

                 If the date of the metric is set, but None is returned for
                 the value then the LPAR had no metrics for it.  Scenarios can
                 occur where the current metric may have a value but not the
                 previous (ex. when a LPAR was just created).
        """
        # No metric, no operation.
        if self.prev_metric is None:
            return self.prev_date, None

        return self.prev_date, self.prev_metric.get(lpar_uuid)

    def _update_internal_metric(self):
        self.prev_metric = self.cur_metric
        self.cur_metric = vm_metrics(self.cur_phyp, self.cur_vioses,
                                     self.cur_lpars)


def latest_stats(adapter, host_uuid, include_vio=True):
    """Returns the latest PHYP and (optionally) VIOS statistics.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host system's UUID.
    :param include_vio: (Optional) Defaults to True.  If set to false, the
                        VIO metrics will always be returned as an empty list.
    :return: datetime - When the metrics were pulled.
    :return: phyp_data - The PhypInfo object for the raw metrics.  May be None
             if there are issues gathering the metrics.
    :return: vios_datas - The list of ViosInfo objects.  May be empty if the
             metrics are unavailable or if the include_vio flag is False.  Is
             a list as the system may have many Virtual I/O Servers.
    :return: lpar_metrics - The list of Lpar metrics received from querying
             IBM.Host Resource Manager via RMC. It may be empty is the
             metrics are unavailable or if the include_lpars flag is False.
             lpar_metrics are generally collected once every two minutes, as
             opposed to the other data which is collected every 30 seconds.
    """
    ltm_metrics = query_ltm_feed(adapter, host_uuid)

    latest_phyp = None

    # Get the latest PHYP metric
    for metric in ltm_metrics:
        if metric.category != 'phyp':
            continue

        if (latest_phyp is None or
                latest_phyp.updated_datetime < metric.updated_datetime):
            latest_phyp = metric

    # If there is no current metric, return None.
    if latest_phyp is None:
        return datetime.datetime.now(), None, None, None

    phyp_json = adapter.read_by_href(latest_phyp.link, xag=[]).body
    phyp_metric = phyp_mon.PhypInfo(phyp_json)

    # Now find the corresponding VIOS metrics for this.
    vios_ltms = []
    for metric in ltm_metrics:
        # The VIOS metrics start with the key 'vios_'
        if not metric.category.startswith('vios_'):
            continue

        if metric.updated_datetime == latest_phyp.updated_datetime:
            vios_ltms.append(metric)

    if include_vio:
        vios_metrics = [vios_mon.ViosInfo(adapter.read_by_href(x.link).body)
                        for x in vios_ltms]
    else:
        vios_metrics = []

    # Now find the corresponding LPAR metrics for this.
    lpar_metrics = get_lpar_metrics(ltm_metrics, adapter)

    return datetime.datetime.now(), phyp_metric, vios_metrics, lpar_metrics


def get_lpar_metrics(ltm_metrics, adapter):
    """This method returns LPAR metrics of type LparInfo

    :param ltm_metrics: The LTM metrics
    :param adapter: The pypowervm adapter.
    :return: LparInfo object representing the LPAR metrics. None is returned
             if there are no LTM metrics collected.
    """
    latest_lpar = None
    for metric in ltm_metrics:
        # The Lpar metrics have category lpar
        if metric.category != 'lpar':
            continue

        if (latest_lpar is None or
                latest_lpar.updated_datetime < metric.updated_datetime):
            latest_lpar = metric

    # If there is no current metric, return None for lpar metrics.
    lpar_metrics = None
    if latest_lpar is not None:
        lpar_json = adapter.read_by_href(latest_lpar.link, xag=[]).body
        lpar_metrics = lpar_pcm.LparInfo(lpar_json)

    return lpar_metrics


def query_ltm_feed(adapter, host_uuid):
    """Will query the long term metrics feed for a given host.

    This method is useful due to the difference in nature of the pcm URIs
    compared to the standard uom.

    PCM URI: ManagedSystem/host_uuid/RawMetrics/LongTermMonitor

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host system's UUID.
    :return: A list of the LTMMetrics.  Note that both PHYP and VIOS entries
             are returned (assuming both are enabled).
    """
    path = pvm_adpt.Adapter.build_path(
        pvm_mon.PCM_SERVICE, pvm_ms.System.schema_type, root_id=host_uuid,
        child_type=RAW_METRICS, child_id=pvm_mon.LONG_TERM_MONITOR, xag=[])
    resp = adapter.read_by_path(path)
    return pvm_mon.LTMMetrics.wrap(resp)


def ensure_ltm_monitors(adapter, host_uuid, override_to_default=False,
                        compute_ltm=False):
    """Ensures that the Long Term Monitors are enabled.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host systems UUID.
    :param override_to_default: (Optional) If True will ensure that the
                                defaults are set on the system.  This means:
                                - Short Term Metrics - disabled
                                - Aggregation - turned on
                                If left off, the previous values will be
                                adhered to.
    :param compute_ltm: (Optional - Defaults to False) If set, will turn on
                        only the compute long term metrics, and the VIOS
                        and network metrics will not be considered.
    """
    # Read from the feed.  PCM preferences appear to be odd.  If you don't
    # query the feed or update the feed directly, it will fail.  This means
    # you can't even query the element or update it direct.
    href = adapter.build_href(pvm_ms.System.schema_type, root_id=host_uuid,
                              child_type=pvm_mon.PREFERENCES,
                              service=pvm_mon.PCM_SERVICE)
    resp = adapter.read_by_href(href)

    # Wrap it to our wrapper.  There is only one element in the feed.
    pref = pvm_mon.PcmPref.wrap(resp)[0]
    pref.compute_ltm_enabled = compute_ltm
    pref.ltm_enabled = True
    if override_to_default:
        pref.stm_enabled = False
        pref.aggregation_enabled = True

    # This updates the backing entry.  This is part of the jankiness.  We have
    # to use the element from the preference, but then the etag from the feed.
    adapter.update(pref.entry.element, resp.etag,
                   pvm_ms.System.schema_type, root_id=host_uuid,
                   child_type=pvm_mon.PREFERENCES, service=pvm_mon.PCM_SERVICE)


def vm_metrics(phyp, vioses, lpars):
    """Reduces the metrics to a per VM basis.

    The metrics returned by PCM are on a global level.  The anchor points are
    PHYP and the Virtual I/O Servers.

    Typical consumption models for metrics are on a 'per-VM' basis.  The
    dictionary returned contains the LPAR UUID and a LparMetric object.  That
    object breaks down the PHYP and VIOS statistics to be approached on a LPAR
    level.

    :param phyp: The PhypInfo for the metrics.
    :param vioses: A list of the ViosInfos for the Virtual I/O Server
                   components.
    :param lpars: The LparInfo object representing Lpar metrics collected
                  via RMC.
    :return vm_data: A dictionary where the UUID is the client LPAR UUID, but
                     the data is a LparMetric for that VM.

                     Note: Data can not be guaranteed.  It may exist in one
                     sample, but then not in another (ex. VM was powered off
                     between gathers).  Always validate that data is 'not
                     None' before use.
    """

    # If the metrics just started, there may not be data yet.  Log this, but
    # return no data
    if phyp is None:
        LOG.warning(_("Metric data is not available.  This may be due to "
                      "the metrics being recently initialized."))
        return {}

    vm_data = {}
    for lpar_sample in phyp.sample.lpars:
        lpar_metric = lpar_mon.LparMetric(lpar_sample.uuid)

        # Fill in the Processor data.
        lpar_metric.processor = lpar_mon.LparProc(lpar_sample.processor)

        # Fill in the Memory data.
        memory_metric = lpars.find(lpar_sample.uuid) if lpars else None
        lpar_metric.memory = lpar_mon.LparMemory(
            lpar_sample.memory, memory_metric)

        # All partitions require processor and memory.  They may not have
        # storage (ex. network boot) or they may not have network.  Therefore
        # these metrics can not be guaranteed like the others.

        # Fill in the Network data.
        if lpar_sample.network is None:
            lpar_metric.network = None
        else:
            lpar_metric.network = lpar_mon.LparNetwork(lpar_sample.network)

        # Fill in the Storage metrics
        if lpar_sample.storage is None:
            lpar_metric.storage = None
        else:
            lpar_metric.storage = lpar_mon.LparStorage(lpar_sample.storage,
                                                       vioses)

        vm_data[lpar_metric.uuid] = lpar_metric
    return vm_data
