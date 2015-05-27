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

"""Wrappers to parse the output of the PCM JSON data from VIOS."""

import abc
import json

import six

from pypowervm.wrappers import pcm


class ViosInfo(object):
    """Represents a monitor sample from the Virtual I/O Server monitor.

    The VIOS PCM monitor JSON data can be parsed by this.  The base structure
    is:
    - ViosInfo
      - Info
      - ViosSample
        - Memory
        - Network
          - NetworkAdpt (List)
          - NetworkBridge (List)
        - Storage
          - FCAdapter (List)
          - PhysStorageAdpt (List)
          - VirtStorageAdpt (List)
    """

    def __init__(self, raw_json):
        data = json.loads(raw_json)
        systemUtil = data.get('systemUtil')
        self.info = pcm.Info(systemUtil.get('utilInfo'))
        self.sample = ViosSample(systemUtil.get('utilSample'))


class ViosSample(object):

    def __init__(self, utilSample):
        self.time_stamp = utilSample.get('timeStamp')

        # TODO(thorst) Evaluate with multi VIOS.
        vios = utilSample.get('viosUtil')[0]
        self.id = vios.get('id')
        self.name = vios.get('name')

        # Complex types
        mem = vios.get('memory')
        self.mem = Memory(mem) if mem else None

        net = vios.get('network')
        self.network = Network(net) if net else None

        storage = vios.get('storage')
        self.storage = Storage(storage) if storage else None


class Memory(object):

    def __init__(self, mem):
        self.utilized_mem = mem.get('utilizedMem')


class Network(object):
    """The Network elements within the VIOS."""

    def __init__(self, net):
        self.adpts = [NetworkAdpt(x) for x in net.get('genericAdapters')]
        self.seas = [NetworkBridge(x) for x in net.get('sharedAdapters')]


class NetworkAdpt(object):
    """Represents a Network Adapter on the system."""

    def __init__(self, adpt):
        self.id = adpt.get('id')
        # Type: 'virtual' or 'physical' or 'sea' (if NetworkBridge)
        self.type = adpt.get('type')
        self.physical_location = adpt.get('physicalLocation')
        self.received_packets = adpt.get('receivedPackets')
        self.sent_packets = adpt.get('sentPackets')
        self.dropped_packets = adpt.get('droppedPackets')
        self.received_bytes = adpt.get('receivedBytes')
        self.sent_bytes = adpt.get('sentBytes')


class NetworkBridge(NetworkAdpt):
    """Represents a Shared Ethernet Adapter on the VIOS."""

    def __init__(self, bridge):
        super(NetworkBridge, self).__init__(bridge)
        self.bridged_adpts = bridge.get('bridgedAdapters')


class Storage(object):
    """Represents the storage elements on the VIOS."""

    def __init__(self, storage):
        fc_adpts = storage.get('fiberChannelAdapters')
        self.fc_adpts = [FCAdapter(x) for x in fc_adpts]

        phys_adpts = storage.get('genericPhysicalAdapters')
        self.phys_adpts = [PhysStorageAdpt(x) for x in phys_adpts]

        virt_adpts = storage.get('genericVirtualAdapters')
        self.virt_adpts = [VirtStorageAdpt(x) for x in virt_adpts]


@six.add_metaclass(abc.ABCMeta)
class StorageAdpt(object):
    """Base class for storage adapters."""

    def __init__(self, adpt):
        self.id = adpt.get('id')
        self.physical_location = adpt.get('physicalLocation')
        self.num_of_reads = adpt.get('numOfReads')
        self.num_of_writes = adpt.get('numOfWrites')
        self.read_bytes = adpt.get('readBytes')
        self.write_bytes = adpt.get('writeBytes')


class FCAdapter(StorageAdpt):
    """Represents a physical fiber channel adapter on the VIOS."""

    def __init__(self, adpt):
        super(FCAdapter, self).__init__(adpt)
        self.wwpn = adpt.get('wwpn')

        # Appears to be Gb/s interface speed
        self.running_speed = adpt.get('runningSpeed')

        # TODO(thorst) Add FC Ports (need vfc mappings)
        self.ports = []


class PhysStorageAdpt(StorageAdpt):
    """Represents a physical storage adapter (typically a SAS drive)."""

    def __init__(self, adpt):
        super(PhysStorageAdpt, self).__init__(adpt)
        self.type = adpt.get('type')


class VirtStorageAdpt(StorageAdpt):
    """Represents a virtual storage adapter (vscsi)."""

    def __init__(self, adpt):
        super(VirtStorageAdpt, self).__init__(adpt)
        self.type = adpt.get('type')
