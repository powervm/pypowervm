# Copyright 2014, 2015 IBM Corp.
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

import abc
import copy
import logging
import re

import six

from pypowervm import adapter as adpt
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap
from pypowervm.wrappers import logical_partition as lpar
from pypowervm.wrappers import network
from pypowervm.wrappers import storage

LOG = logging.getLogger(__name__)


LOCATION_CODE = 'LocationCode'

# Extended Attribute Groups
XAG_VIOS_NETWORK = 'ViosNetwork'
XAG_VIOS_STORAGE = 'ViosStorage'
XAG_VIOS_SCSI_MAPPING = 'ViosSCSIMapping'
XAG_VIOS_FC_MAPPING = 'ViosFCMapping'

# VIO Constants
VIO_ROOT = 'VirtualIOServer'
VIO_VFC_MAPPINGS = 'VirtualFibreChannelMappings'
VIO_VFC_MAP = 'VirtualFibreChannelMapping'
VIO_SCSI_MAPPINGS = 'VirtualSCSIMappings'
VIO_SCSI_MAP = 'VirtualSCSIMapping'
VIO_LICENSE = 'VirtualIOServerLicenseAccepted'
VIO_PARTITION_ID = 'PartitionID'

# Mapping Constants
MAP_CLIENT_ADAPTER = 'ClientAdapter'
MAP_SERVER_ADAPTER = 'ServerAdapter'
MAP_STORAGE = 'Storage'
MAP_CLIENT_LPAR = 'AssociatedLogicalPartition'
MAP_PORT = 'Port'

# Virtual Adapter Constants
VADPT_LPAR_ID = 'LocalPartitionID'
VADPT_UDID = 'UniqueDeviceID'
VADPT_MAP_PORT = 'MapPort'
VADPT_WWPNS = 'WWPNs'
VADPT_BACK_DEV_NAME = 'BackingDeviceName'
VADPT_SLOT_NUM = 'VirtualSlotNumber'
VADPT_VARIED_ON = 'VariedOn'
VADPT_NAME = 'AdapterName'
VADPT_TYPE = 'AdapterType'

# Adapter Creation Private Constants
_NEW_SERVER_ADAPTER = (
    adpt.Element(MAP_SERVER_ADAPTER,
                 attrib=c.DEFAULT_SCHEMA_ATTR,
                 children=[adpt.Element(VADPT_TYPE, text='Server'),
                           adpt.Element(c.NEXT_SLOT, text='true')]))

_NEW_CLIENT_ADAPTER = (
    adpt.Element(MAP_CLIENT_ADAPTER,
                 attrib=c.DEFAULT_SCHEMA_ATTR,
                 children=[adpt.Element(VADPT_TYPE, text='Client'),
                           adpt.Element(c.NEXT_SLOT, text='true')]))


def crt_scsi_map_to_vdisk(adapter, host_uuid, client_lpar_uuid, disk_name):
    """Creates the VirtualSCSIMapping object for a VirtualDisk.

    This is used when creating a new mapping between a Client LPAR and the
    VirtualIOServer.  This creates a SCSI connection between a VirtualDisk
    and the corresponding client LPAR.

    The response object should be used for creating the mapping via an update
    call in the Adapter.  The response object will not have UDIDs (as those
    are not assigned until the update is done).  This holds true for other
    elements as well.

    :param adapter: The pypowervm Adapter that will be used to create the
                    mapping.
    :param host_uuid: (TEMPORARY) The host system's UUID.
    :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                             connected to.
    :param disk_name: The name of the VirtualDisk that should be used.  Can
                      be determined by referencing the VolumeGroup.
    :returns: The Element that represents the new VirtualSCSIMapping (it is
              not the Wrapper, but the element that serves as input into the
              VirtualSCSIMapping wrapper).
    """
    # Create the 'Storage' element of the mapping.
    vdisk = adpt.Element(storage.DISK_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                         children=[adpt.Element(storage.DISK_NAME,
                                                text=str(disk_name))])
    stor = adpt.Element(MAP_STORAGE, children=[vdisk])

    # Create the 'Associated Logical Partition' element of the mapping.
    lpar = _crt_related_href(adapter, host_uuid, client_lpar_uuid)

    # Now bundle the components together.  Order is important.
    opts = [lpar, _NEW_CLIENT_ADAPTER, _NEW_SERVER_ADAPTER, stor]
    return adpt.Element(VIO_SCSI_MAP, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=opts)


def crt_fc_map_to_fc_port(adapter, host_uuid, client_lpar_uuid):
    """Creates the VirtualFCMapping object to connect to a Physical FC Port.

    This is used when creating a new mapping between a Client LPAR and the
    VirtualIOServer.  This creates a Fibre Channel connection between an LPAR
    and a physical Fibre Port.

    The response object should be used for creating the mapping via an
    adapter.update() to the Virtual I/O Server.  The response object
    will not have the UUIDs (as those are not assigned until the update is
    done).  This holds true for certain other elements as well.

    :param adapter: The pypowervm Adapter that will be used to create the
                    mapping.
    :param host_uuid: (TEMPORARY) The host system's UUID.
    :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                             connected to.
    :returns: The Element that represents the new VirtualFCMapping (it is
              not the Wrapper, but the element that serves as input into the
              VirtualFCMapping wrapper).
    """
    # TODO(IBM) Implement
    pass


def crt_scsi_map_to_vopt(adapter, host_uuid, client_lpar_uuid, media_name):
    """Creates the VirtualSCSIMapping object for Virtual Optical Media.

    This is used when creating a new mapping between a Client LPAR and Virtual
    Optical Media that the Virtual I/O Server is hosting.  This creates a SCSI
    connection between a virtual media and the corresponding client LPAR.

    The response object should be used for creating the mapping via an update
    call in the Adapter.  The response object will not have UDIDs (as those
    are not assigned until the update is done).  This holds true for other
    elements as well.

    :param adapter: The pypowervm Adapter that will be used to create the
                    mapping.
    :param host_uuid: (TEMPORARY) The host system's UUID.
    :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                             connected to.
    :param media_name: The name of the Virtual Optical Media device to add.
                       Maps to the volume_group's VirtualOpticalMedia
                       media_name.
    :returns: The Element that represents the new VirtualSCSIMapping (it is
              not the Wrapper, but the element that serves as input into the
              VirtualSCSIMapping wrapper).
    """
    # Create the 'Storage' element of the mapping
    vopt = adpt.Element(storage.VOPT_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=[adpt.Element(storage.VOPT_NAME,
                                               text=str(media_name))])
    stor = adpt.Element(MAP_STORAGE, children=[vopt])

    # Create the 'Associated Logical Partition' element of the mapping.
    lpar = _crt_related_href(adapter, host_uuid, client_lpar_uuid)

    # Now bundle the components together.  Order is important.
    opts = [lpar, _NEW_CLIENT_ADAPTER, _NEW_SERVER_ADAPTER, stor]
    return adpt.Element(VIO_SCSI_MAP, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=opts)


def _crt_related_href(adapter, host_uuid, client_lpar_uuid):
    """Creates the Element for the 'AssociatedLogicalPartition'."""
    client_href = adapter.build_href(c.SYS, host_uuid, c.LPAR,
                                     client_lpar_uuid)
    return adpt.Element(MAP_CLIENT_LPAR, attrib={'href': client_href,
                                                 'rel': 'related'})


def _crt_attrs(group):
    schema = copy.copy(c.DEFAULT_SCHEMA_ATTR)
    schema['group'] = group
    return schema


class VirtualIOServer(ewrap.EntryWrapper):
    schema_type = c.VIOS

    @property
    def name(self):
        return self._get_val_str(c.PARTITION_NAME)

    @property
    def partition_id(self):
        return int(self._get_val_str(c.ROOT + VIO_PARTITION_ID, c.ZERO))

    @property
    def state(self):
        return self._get_val_str(c.PARTITION_STATE)

    @property
    def is_running(self):
        return self.state == 'running'

    @property
    def rmc_state(self):
        return self._get_val_str(c.RMC_STATE)

    @property
    def is_rmc_active(self):
        return self.rmc_state == 'active'

    @property
    def virtual_scsi_mappings(self):
        return self._entry.element.find(c.VIRT_SCSI_MAPPINGS)

    @property
    def media_repository(self):
        return self._entry.element.find(c.VIRT_MEDIA_REPOSITORY_PATH)

    def get_vfc_wwpns(self):
        """Returns a list of the virtual FC WWPN pairs for the vios.

        The response is a List of Lists.
        Ex. (('c05076065a8b005a', 'c05076065a8b005b'),
             ('c05076065a8b0060', 'c05076065a8b0061'))
        """
        return set([frozenset(x.split()) for x in
                    self._get_vals(c.WWPNS_PATH)])

    def get_pfc_wwpns(self):
        """Returns a set of the Physical FC Adapter WWPNs on this VIOS."""
        path = c.DELIM.join(['.', lpar.IO_CFG_ROOT, lpar.IO_SLOTS_ROOT,
                             lpar.IO_SLOT_ROOT, lpar.ASSOC_IO_SLOT_ROOT,
                             lpar.RELATED_IO_ADPT_ROOT, lpar.IO_PFC_ADPT_ROOT,
                             lpar.PFC_PORTS_ROOT, lpar.PFC_PORT_ROOT,
                             lpar.PFC_PORT_WWPN])
        return set(self._get_vals(path))

    @property
    def is_license_accepted(self):
        return self._get_val_bool(c.ROOT + VIO_LICENSE, default=True)

    def hdisk_reserve_policy(self, disk_uuid):
        """Get the reserve policy for an hdisk.

        :param disk_uuid: The uuid of the hdisk.
        :returns: The reserve policy or None if the disk isn't found.
        """
        policy = None

        # Get all the physical volume elements and look for a diskname match
        volumes = self._entry.element.findall(c.PVS_PATH)
        for volume in volumes:
            vol_uuid = volume.findtext(c.VOL_UID)
            match = re.search(r'^[0-9]{5}([0-9A-F]{32}).+$', vol_uuid)

            if match and match.group(1) == disk_uuid:
                policy = volume.findtext(c.RESERVE_POLICY)
                break

        return policy

    def hdisk_from_uuid(self, disk_uuid):
        """Get the hdisk name from the volume uuid.

        :param disk_uuid: The uuid of the hdisk.
        :returns: The associated hdisk name.
        """
        name = None

        # Get all the physical volume elements and look for a diskname match
        volumes = self._entry.element.findall(c.PVS_PATH)
        for volume in volumes:
            vol_uuid = volume.findtext(c.UDID)
            if vol_uuid:
                LOG.debug('get_hdisk_from_uuid match: %s' % vol_uuid)
                LOG.debug('get_hdisk_from_uuid disk_uuid: %s' % disk_uuid)
                if vol_uuid == disk_uuid:
                    name = volume.findtext(c.VOL_NAME)
                    break

        return name

    @property
    def current_mem(self):
        return self._get_val_str(c.CURR_MEM, c.ZERO)

    @property
    def current_proc_mode(self):
        # Returns true if dedicated or false if shared
        return self._get_val_str(c.CURR_USE_DED_PROCS, c.FALSE).lower()

    @property
    def current_procs(self):
        return self._get_val_str(c.CURR_PROCS, c.ZERO)

    @property
    def current_proc_units(self):
        return self._get_val_str(c.CURR_PROC_UNITS, c.ZERO)

    @property
    def is_mover_service_partition(self):
        return self._get_val_bool(c.MOVER_SERVICE_PARTITION, False)

    @property
    def ip_addresses(self):
        """Returns a list of IP addresses assigned to the VIOS.

        Will only return the IP Addresses that can be made known to the system.
        This only includes online Shared Ethernet Adapters and Ethernet Backing
        Devices.  It will not include, for example, a VLAN adapter.

        This is a READ-ONLY list.
        """
        ip_list = []

        # Get all the shared ethernet adapters and free
        # ethernet devices and pull the IPs
        seas = self._entry.element.findall(c.SHARED_ETHERNET_ADAPTER)
        free_eths = self._entry.element.findall(c.ETHERNET_BACKING_DEVICE)
        for eth in seas + free_eths:
            ip = eth.findtext(c.IF_ADDR)
            if ip and ip not in ip_list:
                ip_list.append(ip)

        return tuple(ip_list)

    @property
    def vfc_mappings(self):
        """Returns a WrapperElemList of the VirtualFCMapping objects."""
        def_attrib = _crt_attrs('ViosFCMapping')
        es = ewrap.WrapperElemList(self._find_or_seed(VIO_VFC_MAPPINGS,
                                                      attrib=def_attrib),
                                   VIO_VFC_MAP, VirtualFCMapping)
        return es

    @vfc_mappings.setter
    def vfc_mappings(self, new_mappings):
        self.replace_list(VIO_VFC_MAPPINGS, new_mappings,
                          attrib=_crt_attrs('ViosSCSIMapping'))

    @property
    def scsi_mappings(self):
        """Returns a WrapperElemList of the VirtualSCSIMapping objects."""
        def_attrib = _crt_attrs('ViosSCSIMapping')
        es = ewrap.WrapperElemList(self._find_or_seed(VIO_SCSI_MAPPINGS,
                                                      attrib=def_attrib),
                                   VIO_SCSI_MAP, VirtualSCSIMapping)
        return es

    @scsi_mappings.setter
    def scsi_mappings(self, new_mappings):
        self.replace_list(VIO_SCSI_MAPPINGS, new_mappings,
                          attrib=_crt_attrs('ViosSCSIMapping'))

    @property
    def seas(self):
        def_attrib = _crt_attrs('ViosNetwork')
        es = ewrap.WrapperElemList(self._find_or_seed(network.NB_SEAS,
                                                      attrib=def_attrib),
                                   network.NB_SEA,
                                   network.SharedEthernetAdapter)
        return es

    @property
    def trunk_adapters(self):
        def_attrib = _crt_attrs('ViosNetwork')
        es = ewrap.WrapperElemList(self._find_or_seed(network.SEA_TRUNKS,
                                                      attrib=def_attrib),
                                   network.TA_ROOT, network.TrunkAdapter)
        return es

    @property
    def io_config(self):
        """The Partition I/O Configuration for the VIOS."""
        elem = self._element.find(lpar.IO_CFG_ROOT)
        return lpar.PartitionIOConfiguration.wrap(elem)

    def derive_orphan_trunk_adapters(self):
        """Builds a list of trunk adapters not attached to a SEA."""
        sea_trunks = []
        for sea in self.seas:
            sea_trunks.append(sea.primary_adpt)
            sea_trunks.extend(sea.addl_adpts)

        # Subtract the list of our adapters from there.
        orig_trunks = copy.copy(self.trunk_adapters)
        orphan_trunks = copy.copy(self.trunk_adapters)
        for sea_trunk in sea_trunks:
            # We can't just remove because the trunk adapters from the SEA
            # have the vswitch ref instead of id...  So we have to compare
            # based off anchors.
            for ta in orig_trunks:
                if ta.dev_name == sea_trunk.dev_name:
                    orphan_trunks.remove(ta)
                    break
        return orphan_trunks


class VirtualSCSIMapping(ewrap.ElementWrapper):
    """The mapping of a VIOS SCSI adapter to the Client LPAR SCSI adapter.

    PowerVM provides a mechanism for Server/Client adapters to provide storage
    connectivity (for LPARs that do not have dedicated hardware).  This mapping
    describes the Virtual I/O Server's Server SCSI Adapter and the Client
    LPAR's Client SCSI Adapter.

    To create a new Client SCSI Adapter, create a new mapping and update the
    Virtual I/O Server.  This will be an atomic operation that creates the
    adapters on the Virtual I/O Server and Client LPAR, and then maps them
    properly.  There is no need to pre-create the adapters before creating a
    new mapping.
    """
    schema_type = c.VSCSI_MAP
    has_metadata = True

    @property
    def client_lpar_href(self):
        """Returns the Client LPAR (if any) URI.

        If None - then no client is connected.
        """
        return self.get_href(MAP_CLIENT_LPAR, one_result=True)

    @property
    def client_adapter(self):
        """Returns the Client side VirtualSCSIClientAdapter.

        If None - then no client is connected.
        """
        elem = self._element.find(MAP_CLIENT_ADAPTER)
        if elem is not None:
            return VirtualSCSIClientAdapter.wrap(elem)
        return None

    @property
    def server_adapter(self):
        """Returns the Virtual I/O Server side VirtualSCSIServerAdapter."""
        return VirtualSCSIServerAdapter.wrap(
            self._element.find(MAP_SERVER_ADAPTER))

    @property
    def backing_storage(self):
        """The backing storage element (if applicable).

        Refer to the 'volume_group' wrapper.  This element may be a
        VirtualDisk or VirtualOpticalMedia.  May return None.
        """
        elem = self._element.find(MAP_STORAGE)
        if elem is not None:
            # Check if virtual disk
            e = elem.find(storage.DISK_ROOT)
            if e is not None:
                return storage.VirtualDisk.wrap(e)

            # Check if virtual optical media
            e = elem.find(storage.VOPT_ROOT)
            if e is not None:
                return storage.VirtualOpticalMedia.wrap(e)

            # Some unknown type, throw error
            raise Exception('Found unknown type %s' % e.toxmlstring())
        return None


class VirtualFCMapping(ewrap.ElementWrapper):
    """The mapping of a VIOS FC adapter to the Client LPAR FC adapter.

    PowerVM provides a mechanism for Server/Client adapters to provide storage
    connectivity (for LPARs that do not have dedicated hardware).  This mapping
    describes the Virtual I/O Server's Server Fibre Channel (FC) Adapter and
    the Client LPAR's Client FC Adapter.

    To create a new Client FC Adapter, create a new mapping and update the
    Virtual I/O Server.  This will be an atomic operation that creates the
    adapters on the Virtual I/O Server and Client LPAR, and then maps them
    properly.  There is no need to pre-create the adapters before creating a
    new mapping.
    """
    schema_type = c.VFC_MAP
    has_metadata = True

    @property
    def client_lpar_href(self):
        """Returns the Client LPAR (if any) URI.

        If None - then no client is connected.
        """
        return self.get_href(MAP_CLIENT_LPAR, one_result=True)

    @property
    def client_adapter(self):
        """Returns the Client Virtual FC Adapter.

        If None - then no client is connected.
        """
        elem = self._element.find(MAP_CLIENT_ADAPTER)
        if elem is not None:
            return VirtualFCClientAdapter.wrap(elem)
        return None

    @property
    def backing_port(self):
        """The Virtual I/O Server backing PhysicalFCPort.

        If None - then the vfcmap isn't done and no physical port is backing
        it.
        """
        elem = self._element.find(MAP_PORT)
        if elem is not None:
            return lpar.PhysFCPort.wrap(elem)
        return None

    @property
    def server_adapter(self):
        """Returns the Virtual I/O Server Virtual FC Adapter."""
        return VirtualFCServerAdapter.wrap(
            self._element.find(MAP_SERVER_ADAPTER))


@six.add_metaclass(abc.ABCMeta)
class VirtualStorageAdapter(ewrap.ElementWrapper):
    """Parent class for the virtual storage adapters (FC or SCSI)."""
    has_metadata = True

    @property
    def side(self):
        """Will return either Server or Client.

        A Server indicates that this is a virtual adapter that resides on the
        Virtual I/O Server.

        A Client indicates that this is an adapter residing on a Client LPAR.
        """
        return self._get_val_str(VADPT_TYPE)

    @property
    def is_varied_on(self):
        """True if the adapter is varied on."""
        return self._get_val_str(VADPT_VARIED_ON)

    @property
    def slot_number(self):
        """The (int) slot number that the adapter is in."""
        return self._get_val_int(VADPT_SLOT_NUM)

    @property
    def loc_code(self):
        """The device's location code."""
        return self._get_val_str(LOCATION_CODE)


class VirtualSCSIClientAdapter(VirtualStorageAdapter):
    """The Virtual SCSI Adapter that hosts storage traffic.

    Paired with a VirtualSCSIServerAdapter.
    """
    schema_type = c.CLIENT_ADAPTER

    @property
    def lpar_id(self):
        """The LPAR ID the contains this client adapter."""
        return self._get_val_str(VADPT_LPAR_ID)


class VirtualSCSIServerAdapter(VirtualStorageAdapter):
    """The Virtual SCSI Adapter that hosts storage traffic.

    Paired with a VirtualSCSIClientAdapter.
    """
    schema_type = c.SERVER_ADAPTER

    @property
    def name(self):
        """The adapter's name on the Virtual I/O Server."""
        return self._get_val_str(VADPT_NAME)

    @property
    def backing_dev_name(self):
        """The backing device name that this virtual adapter is hooked into."""
        return self._get_val_str(VADPT_BACK_DEV_NAME)

    @property
    def udid(self):
        """The device's Unique Device Identifier."""
        return self._get_val_str(VADPT_UDID)


class VirtualFCClientAdapter(VirtualStorageAdapter):
    """The Virtual Fibre Channel Adapter on the client LPAR.

    Paired with a VirtualFCServerAdapter.
    """
    schema_type = c.CLIENT_ADAPTER

    @property
    def wwpns(self):
        """Returns a String (delimited by spaces) that contains the WWPNs."""
        return self._get_val_str(VADPT_WWPNS)

    @property
    def lpar_id(self):
        """The ID of the LPAR that contains this client adapter."""
        return self._get_val_str(VADPT_LPAR_ID)


class VirtualFCServerAdapter(VirtualStorageAdapter):
    """The Virtual Fibre Channel Adapter on the VIOS.

    Paired with a VirtualFCClientAdapter.
    """
    schema_type = c.SERVER_ADAPTER

    @property
    def name(self):
        """The adapter's name on the Virtual I/O Server."""
        return self._get_val_str(VADPT_NAME)

    @property
    def udid(self):
        """The device's Unique Device Identifier."""
        return self._get_val_str(VADPT_UDID)

    @property
    def map_port(self):
        """The physical FC port name that this virtual port is connect to."""
        return self._get_val_str(VADPT_MAP_PORT)
