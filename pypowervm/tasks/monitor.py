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

"""Tasks to query the metrics data."""

from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import monitor as pvm_mon

RAW_METRICS = 'RawMetrics'


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
                              child_id=pvm_mon.LTMMetrics.schema_type,
                              service='pcm')
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
                              child_type='preferences', service='pcm')
    resp = adapter.read_by_href(href)

    # Wrap it to out wrapper.  There is only one element in the feed.
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
                   child_type='preferences', service='pcm')
