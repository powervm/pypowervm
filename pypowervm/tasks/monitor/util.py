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

"""Utilities to query and parse the metrics data to a per LPAR basis."""


import datetime

from pypowervm.tasks.monitor import lpar as lpar_mon
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import monitor as pvm_mon
from pypowervm.wrappers.pcm import phyp as phyp_mon
from pypowervm.wrappers.pcm import vios as vios_mon

RAW_METRICS = 'RawMetrics'


class LparMetricCache(object):
    """Provides a cache of metrics on a per LPAR level.

    Metrics are expensive to gather and to parse.  It should not be done
    frequently, as this will stress the API and slow down the invoker.

    This class provides a caching mechanism along with a built in refresh
    mechanism.

    This cache will obtain the metrics for a given system, separate them out
    into an individual LparMetric cache.  If another LPAR is required, the
    cache will be used (so a subsequent API call is not required).

    There is a refresh_interval as well.  If the interval is passed, a
    subsequent query of the metrics will force a refresh of the cache.

    The previous metric is also saved within the cache.  This is useful for
    generating rates on the metrics (a previous element to compare against).
    """

    def __init__(self, adapter, host_uuid, refresh_delta=30):
        """Creates an instance of the cache.

        :param adapter: The pypowervm Adapter.
        :param host_uuid: The UUID of the host CEC to maintain a metrics
                          cache for.
        :param refresh_delta: (Optional) The interval at which the metrics
                              should be updated.  Will only update if the
                              interval has been passed an the user invokes a
                              cache query.  Will not update in the background,
                              only if the cache is used.
        """
        # Ensure that the metric monitoring is enabled.
        ensure_ltm_monitors(adapter, host_uuid)

        # Save the data
        self.adapter = adapter
        self.host_uuid = host_uuid
        self.refresh_delta = datetime.timedelta(seconds=refresh_delta)

        # Ensure these elements are defined up front.
        self.cur_date, self.cur_metric = None, None
        self.prev_date, self.prev_metric = None, None

        # Run a refresh up front.
        self._refresh_if_needed()

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
            return None, None

        return self.cur_date, self.cur_metric.get(lpar_uuid)

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
            return None, None

        return self.prev_date, self.prev_metric.get(lpar_uuid)

    def _refresh_if_needed(self):
        """Refreshes the cache if needed."""
        # The refresh is needed is the current date is none, or if the refresh
        # time delta has been crossed.
        refresh_needed = self.cur_date is None

        # This is put into an if block so that we don't run the logic if
        # cur_date is in fact None...
        if not refresh_needed:
            diff_date = self.cur_date - datetime.datetime.now()
            refresh_needed = diff_date > self.refresh_delta

        # At this point, if a refresh isn't needed, then exit.
        if not refresh_needed:
            return

        # Refresh is needed...get the next metric.
        next_date, next_metric = self._parse_current_feed()
        self.prev_date, self.prev_metric = self.cur_date, self.cur_metric
        self.cur_date, self.cur_metric = next_date, next_metric

    def _parse_current_feed(self):
        """Returns the current feed data.

        :return: Two elements.
                 - The date of the metrics gathered.  Guaranteed to be
                   returned.
                 - The result from the vm_metrics method for the latest
                   timestamp within the LTM feed.
        """
        ltm_metrics = query_ltm_feed(self.adapter, self.host_uuid)

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
            return datetime.datetime.now(), {}

        # Now find the corresponding VIOS metrics for this.
        vios_metrics = []
        for metric in ltm_metrics:
            # The VIOS metrics start with the key 'vios_'
            if not metric.category.startswith('vios_'):
                continue

            if metric.updated_datetime == latest_phyp.updated_datetime:
                vios_metrics.append(metric)

        return (latest_phyp.updated_datetime,
                vm_metrics(self.adapter, latest_phyp, vios_metrics))


def query_ltm_feed(adapter, host_uuid):
    """Will query the long term metrics feed for a given host.

    This method is useful due to the difference in nature of the pcm URIs
    compared to the standard uom.

    PCM URI: ManagedSystem/host_uuid/RawMetrics/LongTermMonitor

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host systems UUID.
    :return: A list of the LTMMetrics.
    """
    href = adapter.build_href(pvm_ms.System.schema_type, root_id=host_uuid,
                              child_type=RAW_METRICS,
                              child_id=pvm_mon.LONG_TERM_MONITOR,
                              service=pvm_mon.PCM_SERVICE)
    resp = adapter.read_by_href(href)
    return pvm_mon.LTMMetrics.wrap(resp)


def ensure_ltm_monitors(adapter, host_uuid, override_defaults=False):
    """Ensures that the Long Term Monitors are enabled.

    :param adapter: The pypowervm adapter.
    :param host_uuid: The host systems UUID.
    :param override_defaults: (Optional) If True will ensure that the defaults
                              are set on the system.  This means:
                              - Short Term Metrics - disabled
                              - Aggregation - turned on
                              If left off, the previous values will be adhered
                              to.
    """
    # Read from the feed.  PCM preferences appear to be janky.  If you don't
    # query the feed or update the feed directly, it will fail.  This means
    # you can't even query the element or update it direct.
    #
    # TODO(thorst) investigate API changes to fix this...
    href = adapter.build_href(pvm_ms.System.schema_type, root_id=host_uuid,
                              child_type=pvm_mon.PREFERENCES,
                              service=pvm_mon.PCM_SERVICE)
    resp = adapter.read_by_href(href)

    # Wrap it to our wrapper.  There is only one element in the feed.
    pref = pvm_mon.PcmPref.wrap(resp)[0]
    pref.compute_ltm_enabled = True
    pref.ltm_enabled = True
    if override_defaults:
        pref.stm_enabled = False
        pref.aggregation_enabled = True

    # This updates the backing entry.  This is part of the jankiness.  We have
    # to use the element from the preference, but then the etag from the feed.
    adapter.update(pref.entry.element, resp.etag,
                   pvm_ms.System.schema_type, root_id=host_uuid,
                   child_type=pvm_mon.PREFERENCES, service=pvm_mon.PCM_SERVICE)


def vm_metrics(adapter, phyp_ltm, vios_ltms):
    """Reduces the metrics to a per VM basis.

    The metrics returned by PCM are on a global level.  The anchor points are
    PHYP and the Virtual I/O Servers.

    Typical consumption models for metrics are on a 'per-VM' basis.  This class
    will break down the PHYP and VIOS statistics to be approached on a LPAR
    level.

    :param adapter: The pypowervm adapter.
    :param phyp_ltm: The LTMMetrics for the phyp component.
    :param vios_ltms: A list of the LTMMetrics for the Virtual I/O Server
                      components.
    :return vm_data: A dictionary where the UUID is the client LPAR UUID, but
                     the data is a LparMetric for that VM.

                     Note: Data can not be guaranteed.  It may exist in one
                     sample, but then not in another (ex. VM was powered off
                     between gathers).  Always validate that data as 'not
                     None' before use.
    """
    phyp = phyp_mon.PhypInfo(adapter.read_by_href(phyp_ltm.link))
    vioses = [vios_mon.ViosInfo(adapter.read_by_href(x.link))
              for x in vios_ltms]

    vm_data = {}
    for lpar_sample in phyp.sample.lpars:
        lpar_metric = lpar_mon.LparMetric(lpar_sample.uuid)

        # Fill in the Processor data.
        lpar_metric.processor = lpar_mon.LparProc(lpar_sample.processor)

        # Fill in the Memory data.
        lpar_metric.memory = lpar_mon.LparMemory(lpar_sample.memory)

        # All partitions require processor or memory.  They may not have
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
