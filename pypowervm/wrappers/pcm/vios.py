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
        - ViosMemory
        - ViosNetwork
          - ViosNetworkAdpt (List)
          - ViosSharedEthernetAdapter (List)
        - ViosStorage
          - ViosPhysFCAdpt (List)
            - ViosVirtFCAdpt (List)
          - ViosPhysStorageAdpt (List)
          - ViosVirtStorageAdpt (List)
          - ViosSSP (List)
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
        self.mem = ViosMemory(mem) if mem else None

        net = vios.get('network')
        self.network = ViosNetwork(net) if net else None

        storage = vios.get('storage')
        self.storage = ViosStorage(storage) if storage else None


class ViosMemory(object):

    def __init__(self, mem):
        self.utilized_mem = mem.get('utilizedMem')


class ViosNetwork(object):
    """The Network elements within the VIOS."""

    def __init__(self, net):
        self.adpts = [ViosNetworkAdpt(x) for x in net.get('genericAdapters')]
        self.seas = [ViosSharedEthernetAdapter(x)
                     for x in net.get('sharedAdapters')]


class ViosNetworkAdpt(object):
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


class ViosSharedEthernetAdapter(ViosNetworkAdpt):
    """Represents a Shared Ethernet Adapter on the VIOS."""

    def __init__(self, bridge):
        super(ViosSharedEthernetAdapter, self).__init__(bridge)
        self.bridged_adpts = bridge.get('bridgedAdapters')


class ViosStorage(object):
    """Represents the storage elements on the VIOS."""

    def __init__(self, storage):
        fc_adpts = storage.get('fiberChannelAdapters')
        self.fc_adpts = [ViosPhysFCAdpt(x) for x in fc_adpts]

        phys_adpts = storage.get('genericPhysicalAdapters')
        self.phys_adpts = [ViosPhysStorageAdpt(x) for x in phys_adpts]

        virt_adpts = storage.get('genericVirtualAdapters')
        self.virt_adpts = [ViosVirtStorageAdpt(x) for x in virt_adpts]

        ssps = storage.get('sharedStoragePools')
        self.ssps = [ViosSSP(x) for x in ssps]


@six.add_metaclass(abc.ABCMeta)
class ViosStorageAdpt(object):
    """Base class for storage adapters."""

    def __init__(self, adpt):
        self.id = adpt.get('id')
        self.physical_location = adpt.get('physicalLocation')
        self.num_reads = adpt.get('numOfReads')
        self.num_writes = adpt.get('numOfWrites')
        self.read_bytes = adpt.get('readBytes')
        self.write_bytes = adpt.get('writeBytes')


class ViosPhysFCAdpt(ViosStorageAdpt):
    """Represents a physical fiber channel adapter on the VIOS."""

    def __init__(self, adpt):
        super(ViosPhysFCAdpt, self).__init__(adpt)
        self.wwpn = adpt.get('wwpn')

        # Appears to be Gb/s interface speed
        self.running_speed = adpt.get('runningSpeed')

        # TODO(thorst) Add FC Ports (need vfc mappings)
        vadpts = adpt.get('ports')
        self.ports = [ViosVirtFCAdpt(x) for x in vadpts]


class ViosVirtFCAdpt(ViosStorageAdpt):
    """Represents a Virtual FC Port (NPIV)."""

    def __init__(self, vadpt):
        super(ViosVirtFCAdpt, self).__init__(vadpt)
        self.wwpn = vadpt.get('wwpn')

        # Appears to be Gb/s interface speed
        self.running_speed = vadpt.get('runningSpeed')


class ViosPhysStorageAdpt(ViosStorageAdpt):
    """Represents a physical storage adapter (typically a SAS drive)."""

    def __init__(self, adpt):
        super(ViosPhysStorageAdpt, self).__init__(adpt)
        self.type = adpt.get('type')


class ViosVirtStorageAdpt(ViosStorageAdpt):
    """Represents a virtual storage adapter (vscsi)."""

    def __init__(self, adpt):
        super(ViosVirtStorageAdpt, self).__init__(adpt)
        self.type = adpt.get('type')


class ViosSSP(object):
    """Represents a Shared Storage Pool (entire element)."""

    def __init__(self, ssp):
        self.id = ssp.get('id')
        self.pool_disks = ssp.get('poolDisks')
        self.num_reads = ssp.get('numOfReads')
        self.num_writes = ssp.get('numOfWrites')
        self.total_space = ssp.get('totalSpace')
        self.used_space = ssp.get('usedSpace')
        self.read_bytes = ssp.get('readBytes')
        self.write_bytes = ssp.get('writeBytes')
