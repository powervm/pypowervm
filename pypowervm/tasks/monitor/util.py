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


from pypowervm.tasks.monitor import lpar as lpar_mon
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import monitor as pvm_mon
from pypowervm.wrappers.pcm import phyp as phyp_mon
from pypowervm.wrappers.pcm import vios as vios_mon

RAW_METRICS = 'RawMetrics'


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

    Typical consumption models for metrics are on a 'per-VM' basis.  The
    dictionary returned contains the LPAR UUID and a LparMetric object.  That
    object breaks down the PHYP and VIOS statistics to be approached on a LPAR
    level.

    :param adapter: The pypowervm adapter.
    :param phyp_ltm: The LTMMetrics for the phyp component.
    :param vios_ltms: A list of the LTMMetrics for the Virtual I/O Server
                      components.
    :return vm_data: A dictionary where the UUID is the client LPAR UUID, but
                     the data is a LparMetric for that VM.

                     Note: Data can not be guaranteed.  It may exist in one
                     sample, but then not in another (ex. VM was powered off
                     between gathers).  Always validate that data is 'not
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
