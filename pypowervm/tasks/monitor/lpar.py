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

"""Objects that contain the per LPAR monitor data."""

import abc

import six


class LparMetric(object):
    """Represents a set of metrics for a given LPAR.

    This is a reduction and consolidation of the raw PCM statistics.
    """

    def __init__(self, uuid):
        """Creates a LPAR Metric.  Data will be set by invoker.

         - uuid - The LPAR's UUID.
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


@six.add_metaclass(abc.ABCMeta)
class PropertyWrapper(object):
    """Provides a thin wrapper around the raw metrics class.

    Sub class should have the _supported_metrics element defined.
    """

    def __init__(self, elem):
        self.elem = elem

    def __getattr__(self, attr):
        if attr not in self._supported_metrics:
            raise AttributeError()
        return getattr(self.elem, attr)


class LparMemory(PropertyWrapper):
    """Represents the memory for a given LPAR.

    Requires the PhypLparMemory raw metric as input.

    The supported metrics are as follows:
      - logical_mem: The amount of memory on the LPAR.
      - backed_physical_mem: The amount of backing physical memory used by
                             the LPAR.
    """

    _supported_metrics = ('logical_mem', 'backed_physical_mem')


class LparProc(PropertyWrapper):
    """Represents the CPU statistics for a given LPAR.

    Requires the PhypLparProc raw metric as input.

    The supported metrics are as follows:
      - pool_id: The CPU pool for this LPAR.
      - mode: The CPU mode.  Typically cap or uncap.
      - virt_procs: The number of virtual processors assigned to the LPAR.
      - proc_units: The number of proc units assigned to the LPAR.

          Ex. if virt_procs is 4 and proc_units is .4, then each virtual
          processor has .1 CPUs.
      - weight: The CPU weight for uncapped processors.

          This defines how aggressive this CPU should be when using unused
          cycles from other LPARs (as compared to other VMs that may also
          request those unused cycles).
      - entitled_proc_cycles: The entitled number of processor cycles.
      - util_cap_proc_cycles: The number of used processor cycles from its
                              capped capacity.
      - util_uncap_proc_cycles: The number of utilized processor cycles pulled
                                from uncap spare.
      - idle_proc_cycles: The CPU cycles spent idling.
      - donated_proc_cycles: The number of CPU cycles donated to other VMs due
                             to no need.
      - time_wait_dispatch: Time spent waiting for CPU dispatch.
      - total_instructions: The total instructions executed.
      - total_inst_exec_time: The time for the instructions to execute.
    """

    _supported_metrics = ('pool_id', 'mode', 'virt_procs', 'proc_units',
                          'weight', 'entitled_proc_cycles',
                          'util_cap_proc_cycles', 'util_uncap_proc_cycles',
                          'idle_proc_cycles', 'donated_proc_cycles',
                          'time_wait_dispatch', 'total_instructions',
                          'total_inst_exec_time')


class LparStorage(object):
    """Represents the Storage statistics for a given LPAR.

    Requires the PhypLparStorage and list of ViosInfo raw metrics as input.

    Contains the various LPAR storage statistic elements.
     - virt_adapters - List of LparVirtStorageAdpt on the LPAR
     - vfc_adpts - List of LparVFCAdpt on the LPAR
    """

    def __init__(self, lpar_phyp_storage, vios_metrics):
        """Fills the VM storage metrics from the raw PHYP/VIOS metrics.

        :param lpar_phyp_storage: The raw Phyp Storage object.
        :param vios_metrics: The list of Virtual I/O Server raw metrics that
                             are paired to the sample from the lpar_phyp
                             metrics.
        """
        # Add the various adapters.
        self.virt_adpts = []
        for vadpt in lpar_phyp_storage.v_stor_adpts:
            vio_adpt = self._find_vio_vstor_adpt(vadpt, vios_metrics)
            if vio_adpt is not None:
                self.virt_adpts.append(LparVirtStorageAdpt(vio_adpt))

        self.vfc_adpts = []
        for phyp_vfc_adpt in lpar_phyp_storage.v_fc_adpts:
            vfc_adpt = self._find_vio_vfc_adpt(phyp_vfc_adpt, vios_metrics)
            if vfc_adpt is not None:
                self.vfc_adpts.append(LparVFCAdpt(vfc_adpt))

    @staticmethod
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
                break

            # See if this virtual adapters has the right data.
            slot_str = "-C%d" % phyp_vadpt.vios_slot
            for vadpt in raw_stor.virt_adpts:
                # We have to match on the location code.  We can only match
                # on the tail end of the slot (we've already validated that
                # we have the right VIOS, so slot is sufficient).
                if vadpt.physical_location.endswith(slot_str):
                    return vadpt

            # If we reached this point, we found the right VIOS, but couldn't
            # find proper data.  Therefore we can just exit the loop.
            break

        return None

    @staticmethod
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
                vfc_adpt = LparStorage._find_vfc(phyp_vfc_adpt, pfc_adpt)
                if vfc_adpt is not None:
                    return vfc_adpt

        return None

    @staticmethod
    def _find_vfc(phyp_vfc_adpt, vio_pfc_adpt):
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


@six.add_metaclass(abc.ABCMeta)
class LparStorageAdpt(PropertyWrapper):
    """Base class for storage adapters on a given LPAR.

    Requires the vios storage adapter raw metric as input.  Specific classes
    are defined by the subclasses.

    The supported metrics are as follows:
      - name: The identifier of the adapter.  Ex: vhost2.
      - physical_location: The physical location code of the adapter.
      - num_reads: The number of read operations done against the adapter.
      - num_writes: The number of write operations done against the adapter.
      - read_bytes: The number of bytes read from the adapter.
      - write_bytes: The number of bytes written to the adapter.
      - type: The type of the adapter.
    """

    _supported_metrics = ('name', 'physical_location', 'num_reads', 'type',
                          'num_writes', 'read_bytes', 'write_bytes')


class LparVFCAdpt(LparStorageAdpt):
    """A Virtual Fibre Channel Adapter attached to the LPAR.

    Requires the ViosFCVirtAdpt raw metric as input.

    The supported metrics are as follows:
      - name: The identifier of the adapter.  Ex: vhost2.
      - physical_location: The physical location code of the adapter.
      - num_reads: The number of read operations done against the adapter.
      - num_writes: The number of write operations done against the adapter.
      - read_bytes: The number of bytes read from the adapter.
      - write_bytes: The number of bytes written to the adapter.
      - type: The type of the adapter.  Will be set to VFC.
    """

    @property
    def type(self):
        """Overrides the type property as the raw metric.

        The VFC Adapter does not natively have a type in the raw metric.  This
        property overrides and circumvents the standard property lookup
        mechanism.
        """
        return "VFC"


class LparPhysAdpt(LparStorageAdpt):
    """A physical adapter (ex SAS drive) on the LPAR.

    Requires the ViosStoragePAdpt raw metric as input.

    The supported metrics are as follows:
      - name: The identifier of the adapter.  Ex: vhost2.
      - physical_location: The physical location code of the adapter.
      - num_reads: The number of read operations done against the adapter.
      - num_writes: The number of write operations done against the adapter.
      - read_bytes: The number of bytes read from the adapter.
      - write_bytes: The number of bytes written to the adapter.
      - type: The type of the adapter.
    """
    pass


class LparVirtStorageAdpt(LparStorageAdpt):
    """A Virutal Storage Adapter (ex. vscsi) attached to the LPAR.

    Requires the ViosStorageVAdpt raw metric as input.

    The supported metrics are as follows:
      - name: The identifier of the adapter.  Ex: vhost2.
      - physical_location: The physical location code of the adapter.
      - num_reads: The number of read operations done against the adapter.
      - num_writes: The number of write operations done against the adapter.
      - read_bytes: The number of bytes read from the adapter.
      - write_bytes: The number of bytes written to the adapter.
      - type: The type of the adapter.
    """
    pass


class LparNetwork(object):
    """Represents the Network statistics for a given LPAR.

    Requires the PhypNetwork raw metric as input.

    Aggregates the various types of network statistics for a given LPAR.
     - cnas - List of the Client Network Adapter stats.
    """

    def __init__(self, lpar_sample_net):
        """Creates the Network Statistics aggregation element.

        Puts the network information into the lpar_metric.network variable.

        :param lpar_sample_net: The PHYP raw data sample.
        """
        # Fill in the Client Network Adapter data sources
        self.cnas = ([] if lpar_sample_net.veas is None else
                     [LparCNA(x) for x in lpar_sample_net.veas])

        # TODO(thorst) Additional network metrics.  Ex. SR-IOV ports


class LparCNA(PropertyWrapper):
    """Represents a Client Network Adapter on a LPAR.

    Requires the PhypVEA raw metric as input.

    The supported metrics are as follows:
      - vlan_id: The PVID of the Client Network Adapter.
      - vswitch_id: The virtual switch ID (not UUID).
      - physical_location: The physical location for the Client Network
                           Adapter.
      - received_packets: The count of packets received to the Client Network
                          Adapter.
      - sent_packets: The count of packets sent by the Client Network Adapter.
      - dropped_packets: The count of the packets dropped by the Client Network
                         Adapter.
      - sent_bytes: The count of the bytes sent by the Client Network Adapter.
      - received_bytes: The count of the bytes received by the Client Network
                        Adapter.
    """

    _supported_metrics = ('vlan_id', 'vswitch_id', 'physical_location',
                          'received_packets', 'sent_packets',
                          'dropped_packets', 'sent_bytes', 'received_bytes')
