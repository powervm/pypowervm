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
            lpar_metric.network = lpar_mon.LparNetwork()
            _saturate_network(lpar_metric, lpar_sample.network)

        # Fill in the Storage metrics
        if lpar_sample.storage is None:
            lpar_metric.storage = None
        else:
            lpar_metric.storage = lpar_mon.LparStorage()
            _saturate_storage(lpar_metric, lpar_sample.storage, vioses)

        vm_data[lpar_metric.uuid] = lpar_metric
    return vm_data


def _saturate_network(lpar_metric, net_phyp_sample):
    """Fills the VM network metrics from the raw metrics.

    Puts the network information into the lpar_metric.network variable.

    :param lpar_metric: The 'per VM' metric to fill the data into.
    :param net_phyp_sample: The PHYP raw data sample.
    """
    # Fill in the Client Network Adapter data sources
    lpar_metric.network.cnas = (None if net_phyp_sample.veas is None else
                                [lpar_mon.LparCNA(x)
                                 for x in net_phyp_sample.veas])

    # TODO(thorst) Additional network metrics.  Ex. SR-IOV ports


def _saturate_storage(lpar_metric, lpar_phyp_storage, vios_metrics):
    """Fills the VM storage metrics from the raw PHYP/VIOS metrics.

    Puts the storage information into the lpar_metric.storage variable.

    :param lpar_metric: The 'per VM' metric to fill the data into.
    :param lpar_phyp_storage: The raw Phyp Storage object.
    :param vios_metrics: The list of Virtual I/O Server raw metrics that are
                         paired to the sample from the lpar_phyp metrics.
    """
    # Add the various adapters.
    virt_adpts = []
    for vadpt in lpar_phyp_storage.v_stor_adpts:
        vio_adpt = _find_vio_vstor_adpt(vadpt, vios_metrics)
        if vio_adpt is not None:
            virt_adpts.append(lpar_mon.LparVirtStorageAdpt(vio_adpt))

    vfc_adpts = []
    for phyp_vfc_adpt in lpar_phyp_storage.v_fc_adpts:
        vfc_adpt = _find_vio_vfc_adpt(phyp_vfc_adpt, vios_metrics)
        if vfc_adpt is not None:
            vfc_adpts.append(lpar_mon.LparVFCAdpt(vfc_adpt))

    # Set the storage elements
    lpar_metric.storage.virt_adpts = virt_adpts
    lpar_metric.storage.vfc_adpts = vfc_adpts


def _find_vio_vstor_adpt(phyp_vadpt, vios_metrics):
    """Finds the appropriate VIOS virtual storage adapter.

    For a given PHYP virtual adapter, PHYP only has a little bit of
    information about it.  Which VIOS is hosting it, and the slot.

    The VIOS metrics actually contain the information for that
    device.

    This method will look through all the VIOS samples to find the
    matching ViosStorageVAdpt for the given PhypStorageVAdpt.  If one
    can not be found, None is returned.

    :param phyp_vadpt: The PhypStorageVAdpt raw metric.
    :param vios_metrics: The list of ViosInfos.
    :return: The corresponding ViosStorageVAdpt from the ViosInfos
             if one can be found.  None otherwise.
    """
    for vios_ltm in vios_metrics:
        # We need to find the VIOS sample that matches this storage
        # element.  Loop until we find one (if one doesn't exist, then
        # this will just return None).
        if vios_ltm.sample.id != phyp_vadpt.vios_id:
            continue

        # If we reach here, we found the VIOS.  From that sample, see
        # if we have the appropriate storage.
        raw_stor = vios_ltm.sample.storage
        if raw_stor is None or raw_stor.virt_adpts is None:
            return None

        # See if this virtual adapters has the right data.
        slot_str = "-C%d" % phyp_vadpt.vios_slot
        for vadpt in raw_stor.virt_adpts:
            # We have to match on the location code.  We can only match
            # on the tail end of the slot (we've already validated that
            # we have the right VIOS, so slot is sufficient).
            if vadpt.physical_location.endswith(slot_str):
                return vadpt

        # If we reached this point, we found the right VIOS, but couldn't find
        # proper data.  Therefore we can just exit the loop.
        break

    return None


def _find_vio_vfc_adpt(phyp_vfc_adpt, vios_metrics):
    """Finds the appropriate VIOS virtual FC adapter.

    For a given PHYP virtual FC adapter, PHYP only has a little bit of
    information about it.  Which VIOS is hosting it, and the WWPNs.

    The VIOS metrics actually contain the information for that
    device.

    This method will look through all the VIOS samples to find the
    matching ViosFCVirtAdpt for the given PhypVirtualFCAdpt.  If one
    can not be found, None is returned.

    :param phyp_vadpt: The PhypVirtualFCAdpt raw metric.
    :param vios_metrics: The list of ViosInfos.
    :return: The corresponding ViosFCVirtAdpt from the ViosInfos
             if one can be found.  None otherwise.
    """
    for vios_ltm in vios_metrics:
        # We need to find the VIOS sample that matches this VFC
        # element.  Loop until we find one (if one doesn't exist, then
        # this will just return None).
        if vios_ltm.sample.id != phyp_vfc_adpt.vios_id:
            continue

        # If we reach here, we found the VIOS.  From that sample, see
        # if we have the appropriate storage.
        raw_stor = vios_ltm.sample.storage
        if raw_stor is None or raw_stor.fc_adpts is None:
            return None

        # Check the WWPNs.
        for pfc_adpt in raw_stor.fc_adpts:
            vfc_adpt = __find_vfc(phyp_vfc_adpt, pfc_adpt)
            if vfc_adpt is not None:
                return vfc_adpt

    return None


def __find_vfc(phyp_vfc_adpt, vio_pfc_adpt):
    """Finds the matching VIOS vfc adpt for a given PHYP adapter

    :param phyp_vfc_adpt: The raw PhypVirtualFCAdpt object.
    :param vio_pfc_adpt: The raw ViosFCPhysAdpt.
    :return: The matching ViosFCVirtAdpt contained within the physical VIOS
             adapter.  If one can't be found, None will be returned.
    """
    if vio_pfc_adpt.ports is None:
        return None
    for vfc_adpt in vio_pfc_adpt.ports:
        for wwpn in phyp_vfc_adpt.wwpn_pair:
            if wwpn == vfc_adpt.wwpn:
                return vfc_adpt
    return None
