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

"""Wrappers to parse the output of the PCM JSON data from PHYP."""

import abc
import json

import six

from pypowervm.wrappers import pcm


class PhypInfo(object):
    """Represents a monitor sample from the PHYP monitor.

    The PHYP PCM monitor JSON data can be parsed by this.  The base structure
    is:
    - PhypInfo
      - Info
      - PhypSample
        - PhypSystemFirmware
        - PhypSystemProcessor
        - PhypSystemMemory
        - PhypSharedProcPool
        - PhypVMSample (list - client virtual machines)
          - PhypLparProc
          - PhypLparMemory
          - PhypNetwork
           - PhypVEA
           - PhypSriovLparPort
          - PhypStorage
           - PhypStorageVAdpt
           - PhypVirtualFCAdpt
        - PhypViosSample (list - Virtual I/O Servers)
          - PhypLparProc
    """

    def __init__(self, raw_json):
        data = json.loads(raw_json)
        systemUtil = data.get('systemUtil')
        self.info = pcm.Info(systemUtil.get('utilInfo'))
        self.sample = PhypSample(systemUtil.get('utilSample'))


class PhypSample(object):
    """A Power Hypervisor Sample."""

    def __init__(self, util_sample):
        self.time_stamp = util_sample.get('timeStamp')
        self.status = util_sample.get('status')
        self.time_based_cycles = util_sample.get('timeBasedCycles')

        # Complex objects
        sys_f = util_sample.get('systemFirmware')
        self.system_firmware = (None if sys_f is None
                                else PhypSystemFirmware(sys_f))

        proc = util_sample.get('processor')
        self.processor = None if proc is None else PhypSystemProcessor(proc)

        mem = util_sample.get('memory')
        self.memory = None if mem is None else PhypSystemMemory(mem)

        spp_list = util_sample.get('sharedProcessorPool')
        self.shared_proc_pools = [PhypSharedProcPool(x) for x in spp_list]

        # List of LPARs
        lpars = util_sample.get('lparsUtil')
        self.lpars = [PhypVMSample(x) for x in lpars]

        # List of Virtual I/O Servers
        vioses = util_sample.get('viosUtil')
        self.vioses = [PhypViosSample(x) for x in vioses]


class PhypSystemFirmware(object):
    """Firmware information from PHYP."""

    def __init__(self, system_firmware):
        self.utilized_proc_cycles = system_firmware.get('utilizedProcCycles')
        self.assigned_mem = system_firmware.get('assignedMem')


class PhypSharedProcPool(object):
    """Information of the Shared Processor Pool."""

    def __init__(self, spp):
        self.id = spp.get('id')
        self.name = spp.get('name')
        self.assigned_proc_cycles = spp.get('assignedProcCycles')
        self.utilized_pool_cycles = spp.get('utilizedPoolCycles')
        self.max_proc_units = spp.get('maxProcUnits')
        self.borrowed_pool_proc_units = spp.get('borrowedPoolProcUnits')


class PhypSystemProcessor(object):
    """Processor information about the entire system from PHYP."""

    def __init__(self, processor):
        self.total_proc_units = processor.get('totalProcUnits')
        self.configurable_proc_units = processor.get('configurableProcUnits')
        self.available_proc_units = processor.get('availableProcUnits')
        self.proc_cycles_per_sec = processor.get('procCyclesPerSecond')


class PhypSystemMemory(object):
    """System wide Memory information from PHYP."""

    def __init__(self, mem):
        self.total_mem = mem.get('totalMem')
        self.available_mem = mem.get('availableMem')
        self.configurable_mem = mem.get('configurableMem')


@six.add_metaclass(abc.ABCMeta)
class PhypLparSample(object):
    """A LPAR sample presented by PHYP.  Generic for VIOS & VM."""

    def __init__(self, lpar):
        self.id = lpar.get('id')
        self.uuid = lpar.get('uuid')
        self.name = lpar.get('name')
        self.state = lpar.get('state')
        self.affinity_score = lpar.get('affinityScore')

        # Complex types
        proc = lpar.get('processor')
        self.processor = None if proc is None else PhypLparProc(proc)


class PhypViosSample(PhypLparSample):
    """A VIOS sample presented by the PHYP metrics."""

    def __init__(self, lpar):
        super(PhypViosSample, self).__init__(lpar)


class PhypVMSample(PhypLparSample):
    """A Virtual Machine (non VIOS) presented by the PHYP metrics."""

    def __init__(self, lpar):
        super(PhypVMSample, self).__init__(lpar)
        self.type = lpar.get('type')

        # Complex Types
        mem = lpar.get('memory')
        self.memory = None if mem is None else PhypLparMemory(mem)

        net = lpar.get('network')
        self.network = None if net is None else PhypNetwork(net)

        storage = lpar.get('storage')
        self.storage = None if storage is None else PhypStorage(storage)


class PhypLparMemory(object):
    """A sample of a Client Virtual Machines's memory presented by PHYP.

    Part of the PhypLparSample.
    """

    def __init__(self, mem):
        self.logical_mem = mem.get('logicalMem')
        self.backed_physical_mem = mem.get('backedPhysicalMem')


class PhypLparProc(object):
    """A sample of the LPARs processor presented by PHYP.

    Part of the PhypLparSample
    """

    def __init__(self, proc):
        self.pool_id = proc.get('poolId')
        self.mode = proc.get('mode')
        self.virt_procs = proc.get('maxVirtualProcessors')
        self.proc_units = proc.get('maxProcUnits')
        self.weight = proc.get('weight')
        self.entitled_proc_cycles = proc.get('entitledProcCycles')
        self.util_cap_proc_cycles = proc.get('utilizedCappedProcCycles')
        self.util_uncap_proc_cycles = proc.get('utilizedUnCappedProcCycles')
        self.idle_proc_cycles = proc.get('idleProcCycles')
        self.donated_proc_cycles = proc.get('donatedProcCycles')
        self.time_wait_dispatch = proc.get('timeSpentWaitingForDispatch')
        self.total_instructions = proc.get('totalInstructions')
        self.total_inst_exec_time = proc.get('totalInstructionsExecutionTime')


class PhypNetwork(object):
    """A sample of the LPARs network information.

    Part of the PhypLparSample
    """

    def __init__(self, network):
        veas = network.get('virtualEthernetAdapters')
        self.veas = [] if veas is None else [PhypVEA(x) for x in veas]

        sriov_ports = network.get('sriovLogicalPorts')
        self.sriov_ports = ([] if sriov_ports is None
                            else [PhypSriovLparPort(x) for x in sriov_ports])


class PhypVEA(object):
    """The Virtual Ethernet Adapters (aka. CNA's) data."""

    def __init__(self, vea):
        self.vlan_id = vea.get('vlanId')
        self.vswitch_id = vea.get('vswitchId')
        self.physical_location = vea.get('physicalLocation')
        self.is_pvid = vea.get('isPortVLANID')
        self.received_packets = vea.get('receivedPackets')
        self.sent_packets = vea.get('sentPackets')
        self.dropped_packets = vea.get('droppedPackets')
        self.sent_bytes = vea.get('sentBytes')
        self.received_bytes = vea.get('receivedBytes')
        self.received_physical_packets = vea.get('receivedPhysicalPackets')
        self.sent_physical_packets = vea.get('sentPhysicalPackets')
        self.dropped_physical_packets = vea.get('droppedPhysicalPackets')
        self.sent_physical_bytes = vea.get('sentPhysicalBytes')
        self.received_physical_bytes = vea.get('receivedPhysicalBytes')


class PhypSriovLparPort(object):
    """A metric for the SR-IOV Logical Ports."""

    def __init__(self, sriov_p):
        self.drc_index = sriov_p.get('drcIndex')
        self.phys_drc_index = sriov_p.get('physicalDrcIndex')
        self.phys_port_id = sriov_p.get('physicalPortId')
        self.physical_location = sriov_p.get('physicalLocation')
        self.received_packets = sriov_p.get('receivedPackets')
        self.sent_packets = sriov_p.get('sentPackets')
        self.dropped_sent_packets = sriov_p.get('droppedSentPackets')
        self.dropped_received_packets = sriov_p.get('droppedReceivedPackets')
        self.sent_bytes = sriov_p.get('sentBytes')
        self.recevied_bytes = sriov_p.get('receivedBytes')
        self.error_in = sriov_p.get('errorIn')
        self.error_out = sriov_p.get('errorOut')


class PhypStorage(object):
    """A sample of the LPARs storage information.

    Part of the PhypLparSample
    """

    def __init__(self, stor):
        v_adpts = stor.get('genericVirtualAdapters')
        self.v_stor_adpts = ([] if v_adpts is None
                             else [PhypStorageVAdpt(x) for x in v_adpts])

        v_fcs = stor.get('virtualFiberChannelAdapters')
        self.v_fc_adpts = ([] if v_fcs is None
                           else [PhypVirtualFCAdpt(x) for x in v_fcs])


class PhypStorageVAdpt(object):
    """An indicator to the Client VM Storage to the VIOS storage elem."""

    def __init__(self, stor):
        self.physical_location = stor.get('physicalLocation')
        self.vios_id = stor.get('viosId')
        self.vios_slot = stor.get('viosAdapterSlotId')


class PhypVirtualFCAdpt(object):
    """An indicator to identify the Client VFC Adpt with the VIOS storage."""

    def __init__(self, vfc):
        self.vios_id = vfc.get('viosId')
        # The PCM metrics will have wwpnPair as key name in older versions
        # and wwpnpair as key name in newer versions.
        self.wwpn_pair = vfc.get('wwpnpair', vfc.get('wwpnPair', []))
        self.physical_location = vfc.get('physicalLocation')
