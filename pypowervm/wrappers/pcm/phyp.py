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
        - SystemFirmware
        - SystemProcessor
        - SystemMemory
        - VMSample (list - client virtual machines)
          - LPARProcessor
          - VMMemory
          - VEA
          - Storage
        - VIOSSample (list - Virtual I/O Servers)
         - LPARProcessor
    """

    def __init__(self, raw_json):
        data = json.loads(raw_json)
        systemUtil = data.get('systemUtil')
        self.info = pcm.Info(systemUtil.get('utilInfo'))
        self.sample = PhypSample(systemUtil.get('utilSample'))


class PhypSample(object):
    """A Power Hypervisor Sample."""

    def __init__(self, utilSample):
        self.time_stamp = utilSample.get('timeStamp')
        self.status = utilSample.get('status')
        self.time_based_cycles = utilSample.get('timeBasedCycles')

        # Complex objects
        sys_f = utilSample.get('systemFirmware')
        self.system_firmware = None if sys_f is None else SystemFirmware(sys_f)

        proc = utilSample.get('processor')
        self.processor = None if proc is None else SystemProcessor(proc)

        mem = utilSample.get('memory')
        self.memory = None if mem is None else SystemMemory(mem)

        # List of LPARs
        lpars = utilSample.get('lparsUtil')
        self.lpars = [VMSample(x) for x in lpars]

        # List of Virtual I/O Servers
        vioses = utilSample.get('viosUtil')
        self.vioses = [VIOSSample(x) for x in vioses]


class SystemFirmware(object):
    """Firmware information from PHYP."""

    def __init__(self, systemFirmware):
        self.utilized_proc_cycles = systemFirmware.get('utilizedProcCycles')
        self.assigned_mem = systemFirmware.get('assignedMem')


class SystemProcessor(object):
    """Processor information about the entire system from PHYP."""

    def __init__(self, processor):
        self.total_proc_units = processor.get('totalProcUnits')
        self.configurable_proc_units = processor.get('configurableProcUnits')
        self.available_proc_units = processor.get('availableProcUnits')
        self.proc_cycles_per_sec = processor.get('procCyclesPerSecond')


class SystemMemory(object):
    """System Memory information from PHYP."""

    def __init__(self, mem):
        self.total_mem = mem.get('totalMem')
        self.available_mem = mem.get('availableMem')
        self.configurable_mem = mem.get('configurableMem')


@six.add_metaclass(abc.ABCMeta)
class LPARSample(object):
    """A LPAR sample presented by PHYP.  Generic for VIOS & VM."""

    def __init__(self, lpar):
        self.id = lpar.get('id')
        self.uuid = lpar.get('uuid')
        self.name = lpar.get('name')
        self.state = lpar.get('state')
        self.affinity_score = lpar.get('affinityScore')

        # Complex types
        proc = lpar.get('processor')
        self.processor = None if proc is None else LPARProcessor(proc)


class VIOSSample(LPARSample):
    """A VIOS sample presented by the PHYP metrics."""

    def __init__(self, lpar):
        super(VIOSSample, self).__init__(lpar)


class VMSample(LPARSample):
    """A Virtual Machine (non VIOS) presented by the PHYP metrics."""

    def __init__(self, lpar):
        super(VMSample, self).__init__(lpar)
        self.type = lpar.get('type')

        # Complex Types
        mem = lpar.get('memory')
        self.memory = None if mem is None else VMMemory(mem)

        net = lpar.get('network')
        veas = net.get('virtualEthernetAdapters') if net else []
        self.veas = [VEA(vea) for vea in veas]

        storage = lpar.get('storage')
        stor_adpts = storage.get('genericVirtualAdapters') if storage else []
        self.storage_adpts = [Storage(sadpt) for sadpt in stor_adpts]


class VMMemory(object):
    """A sample of a Client Virtual Machines's memory presented by PHYP.

    Part of the LPARSample.
    """

    def __init__(self, mem):
        self.logical_mem = mem.get('logicalMem')
        self.backed_physical_mem = mem.get('backedPhysicalMem')


class LPARProcessor(object):
    """A sample of the LPARs processor presented by PHYP.

    Part of the LPARSample
    """

    def __init__(self, proc):
        self.pool_id = proc.get('poolId')
        self.mode = proc.get('mode')
        self.max_virt_procs = proc.get('maxVirtualProcessors')
        self.max_proc_units = proc.get('maxProcUnits')
        self.weight = proc.get('weight')
        self.entitled_proc_cycles = proc.get('entitledProcCycles')
        self.util_cap_proc_cycles = proc.get('utilizedCappedProcCycles')
        self.util_uncap_proc_cycles = proc.get('utilizedUnCappedProcCycles')
        self.idle_proc_cycles = proc.get('idleProcCycles')
        self.donated_proc_cycles = proc.get('donatedProcCycles')
        self.time_wait_dispatch = proc.get('timeSpentWaitingForDispatch')
        self.total_instructions = proc.get('totalInstructions')
        self.total_inst_exec_time = proc.get('totalInstructionsExecutionTime')


class VEA(object):
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


class Storage(object):
    """An indicator to line the Client VM Storage to the VIOS storage elem."""

    def __init__(self, stor):
        self.physical_location = stor.get('physicalLocation')
        self.vios_id = stor.get('viosId')
        self.vios_slot = stor.get('viosAdapterSlotId')
