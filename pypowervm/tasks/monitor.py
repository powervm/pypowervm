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

import abc

import six

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
        lpar_metric = LparMetric(lpar_sample.uuid)
        vm_data[lpar_metric.uuid] = lpar_metric

        # Fill in the Processor data.
        lpar_metric.processor = LparProc(lpar_sample.processor)

        # Fill in the Memory data.
        lpar_metric.memory = LparMemory(lpar_sample.memory)

        # Fill in the Network data.
        if lpar_sample.network is None:
            lpar_metric.network = None
        else:
            lpar_metric.network = LparNetwork()
            _saturate_network(lpar_metric, lpar_sample.network)

        # Fill in the Storage metrics
        if lpar_sample.storage is None:
            lpar_metric.storage = None
        else:
            lpar_metric.storage = LparStorage()
            _saturate_storage(lpar_metric, lpar_sample.storage, vioses)
    return vm_data


def _saturate_network(lpar_metric, net_phyp_sample):
    """Fills the VM network metrics from the raw metrics.

    Puts the network information into the lpar_metric.network variable.

    :param lpar_metric: The 'per VM' metric to fill the data into.
    :param net_phyp_sample: The PHYP raw data sample.
    """
    # Fill in the Client Network Adapter data sources
    lpar_metric.network.cnas = (None if net_phyp_sample.veas is None else
                                [LparCNA(x) for x in net_phyp_sample.veas])

    # TODO(thorst) Additional network metrics.  Ex. SR-IOV ports


def _saturate_storage(lpar_metric, lpar_phyp_storage, vios_metrics):
    """Fills the VM storage metrics from the raw PHYP/VIOS metrics.

    Puts the storage information into the lpar_metric.storage variable.

    :param lpar_metric: The 'per VM' metric to fill the data into.
    :param lpar_phyp_storage: The raw Phyp Storage object.
    """
    # Add the various adapters.
    virt_adpts = []
    for vadpt in lpar_phyp_storage.v_stor_adpts:
        vio_adpt = _find_vio_vstor_adpt(vadpt, vios_metrics)
        if vio_adpt is not None:
            virt_adpts.append(LparVirtStorageAdpt(vio_adpt))
            continue

    vfc_adpts = []
    for phyp_vfc_adpt in lpar_phyp_storage.v_fc_adpts:
        vfc_adpt = _find_vio_vfc_adpt(phyp_vfc_adpt, vios_metrics)
        if vfc_adpt is not None:
            vfc_adpts.append(LparVFCAdpt(vfc_adpt))
            continue

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
        for wwpn in phyp_vfc_adpt.wwpn_pair:
            for pfc_adpt in raw_stor.fc_adpts:
                if pfc_adpt.ports is None:
                    continue
                for vfc_adpt in pfc_adpt.ports:
                    if wwpn == vfc_adpt.wwpn:
                        return vfc_adpt

    return None


class LparMetric(object):
    """Represents a set of metrics for a given LPAR.

    This is a reduction and consolidation of the raw PCM statistics.
    """

    def __init__(self, uuid):
        """Creates a LPAR Metric.  Data will be set by invoker.

         - memory - The LPAR's memory statistics.
         - processor - The LPAR's processor statistics.
         - network - The LparNetwork aggregation of network statistics.
         - storage - the LparStorage aggregation of storage statistics.

        If certain attributes are None, that means the statistics could not
        be pulled.

        :param uuid: The LPAR UUID
        """
        self.uuid = uuid
        self.memory = None
        self.processor = None
        self.network = None
        self.storage = None


class LparMemory(object):
    """Represents memory statistics for a LPAR."""

    def __init__(self, lpar_mem):
        """Initializes based off Raw Metrics.

        :param lpar_mem: The PHYP VMMemory.
        """
        self.mem = lpar_mem

    @property
    def logical_mem(self):
        """The amount of memory on the LPAR."""
        return self.mem.logical_mem

    @property
    def backed_physical_mem(self):
        """The amount of backing physical memory used by the LPAR."""
        return self.mem.backed_physical_mem


class LparProc(object):
    """Represents the CPU statistics for a given LPAR."""

    def __init__(self, lpar_processor):
        """Initializes based off Raw Metrics.

        :param lpar_processor: The phyp LPARProcessor.
        """
        self.proc = lpar_processor

    @property
    def pool_id(self):
        """The CPU pool for this LPAR."""
        return self.proc.pool_id

    @property
    def mode(self):
        """The CPU mode.  Typically cap or uncap."""
        return self.proc.mode

    @property
    def virt_procs(self):
        """The number of virtual processors assigned to the LPAR."""
        return self.proc.max_virt_procs

    @property
    def proc_units(self):
        """The number of proc units assigned to the LPAR.

        Ex. if virt_procs is 4 and proc_units is .4, then each virtual
        processor has .1 CPUs.
        """
        return self.proc.max_proc_units

    @property
    def weight(self):
        """The CPU weight for uncapped processors.

        This defines how aggressive this CPU should be when using unused cycles
        from other LPARs (as compared to other VMs that may also request
        those unused cycles).
        """
        return self.proc.weight

    @property
    def entitled_proc_cycles(self):
        """The entitled number of processor cycles."""
        return self.proc.entitled_proc_cycles

    @property
    def util_cap_proc_cycles(self):
        """The number of used processor cycles from its capped capacity."""
        return self.proc.util_cap_proc_cycles

    @property
    def util_uncap_proc_cycles(self):
        """The number of utilized processor cycles pulled from uncap spare."""
        return self.proc.util_uncap_proc_cycles

    @property
    def idle_proc_cycles(self):
        """The CPU cycles spent idling."""
        return self.proc.idle_proc_cycles

    @property
    def donated_proc_cycles(self):
        """The number of CPU cycles donated to other VMs due to no need."""
        return self.proc.donated_proc_cycles

    @property
    def time_wait_dispatch(self):
        """Time spent waiting for CPU dispatch."""
        return self.proc.time_wait_dispatch

    @property
    def total_instructions(self):
        """The total instructions executed."""
        return self.proc.total_instructions

    @property
    def total_inst_exec_time(self):
        """The time for the instructions to execute."""
        return self.proc.total_inst_exec_time


class LparStorage(object):
    """Represents the Storage statistics for a given LPAR.

    Contains the various LPAR storage statistic elements.
     - virt_adapters - List of LparVirtStorageAdpt on the LPAR
     - vfc_adpts - List of LparVFCAdpt on the LPAR
    """

    def __init__(self):
        """Creates a blank LparStorage element."""
        self.virt_adpts = []
        self.vfc_adpts = []


@six.add_metaclass(abc.ABCMeta)
class LparStorageAdpt(object):
    """Base class for storage adapters on a given LPAR."""

    def __init__(self, adpt):
        self.adpt = adpt

    @property
    def id(self):
        """The identifier of the adapter.  Ex: vhost2."""
        return self.adpt.id

    @property
    def physical_location(self):
        """The physical location of the adapter."""
        return self.adpt.physical_location

    @property
    def num_reads(self):
        """The number of read operations done against the adapter."""
        return self.adpt.num_reads

    @property
    def num_writes(self):
        """The number of write operations done against the adapter."""
        return self.adpt.num_writes

    @property
    def read_bytes(self):
        """The number of bytes read from the adapter."""
        return self.adpt.read_bytes

    @property
    def write_bytes(self):
        """The number of bytes written to the adapter."""
        return self.adpt.write_bytes


class LparVFCAdpt(LparStorageAdpt):
    """A Virtual Fibre Channel Adapter attached to the LPAR."""

    def __init__(self, adpt):
        super(LparVFCAdpt, self).__init__(adpt)


class LparPhysAdpt(LparStorageAdpt):
    """A physical adapter (ex SAS drive) on the LPAR."""

    def __init__(self, adpt):
        super(LparPhysAdpt, self).__init__(adpt)

    @property
    def type(self):
        """The type of adapter."""
        return self.adpt.type


class LparVirtStorageAdpt(LparStorageAdpt):
    """A Virutal Storage Adapter (ex. vscsi) attached to the LPAR."""

    def __init__(self, adpt):
        super(LparVirtStorageAdpt, self).__init__(adpt)

    @property
    def type(self):
        """The type of adapter."""
        return self.adpt.type


class LparNetwork(object):
    """Represents the Network statistics for a given LPAR.

    Aggregates the various types of network statistics for a given LPAR.
     - cnas - List of the Client Network Adapter stats.
    """

    def __init__(self):
        """Creates the Network Statistics aggregation element."""
        self.cnas = []

        # TODO(thorst) Add SR-IOV ports


class LparCNA(object):
    """Represents a Client Network Adapter on a LPAR."""

    def __init__(self, vea):
        """Creates the Lpar Client Network Adapter metric source.

        :param vea: The Raw Metric VEA.
        """
        self.vea = vea

    @property
    def vlan_id(self):
        """The PVID of the Client Network Adapter."""
        return self.vea.vlan_id

    @property
    def vswitch_id(self):
        """The virtual switch ID (not UUID)."""
        return self.vea.vswitch_id

    @property
    def physical_location(self):
        """The physical location for the Client Network Adapter."""
        return self.vea.physical_location

    @property
    def received_packets(self):
        """The count of packets received to the Client Network Adapter."""
        return self.vea.received_packets

    @property
    def sent_packets(self):
        """The count of packets sent by the Client Network Adapter."""
        return self.vea.sent_packets

    @property
    def dropped_packets(self):
        """The count of the packets dropped by the Client Network Adapter."""
        return self.vea.dropped_packets

    @property
    def sent_bytes(self):
        """The count of the bytes sent by the Client Network Adapter."""
        return self.vea.sent_bytes

    @property
    def received_bytes(self):
        """The count of the bytes received by the Client Network Adapter."""
        return self.vea.received_bytes
