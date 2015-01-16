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

import copy
import logging
import re

from pypowervm import adapter as adpt
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap
from pypowervm.wrappers import volume_group

LOG = logging.getLogger(__name__)


LOCATION_CODE = 'LocationCode'

# VIO Constants
VIO_VFC_MAPPINGS = 'VirtualFibreChannelMappings'
VIO_VFC_MAP = 'VirtualFibreChannelMapping'
VIO_SCSI_MAPPINGS = 'VirtualSCSIMappings'
VIO_SCSI_MAP = 'VirtualSCSIMapping'

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

# Physical FC Port Constants
PFC_NAME = 'PortName'
PFC_UDID = 'UniqueDeviceID'
PFC_WWPN = 'WWPN'
PFC_AVAILABLE_PORTS = 'AvailablePorts'
PFC_TOTAL_PORTS = 'TotalPorts'

# Adapter Creation Private Constants
_NEW_SERVER_ADAPTER = (
    adpt.Element(MAP_SERVER_ADAPTER,
                 attrib=c.DEFAULT_SCHEMA_ATTR,
                 children=[adpt.Element(VADPT_TYPE, text='Server'),
                           adpt.Element('UseNextAvailableSlotID',
                                        text='true')]))

_NEW_CLIENT_ADAPTER = (
    adpt.Element(MAP_CLIENT_ADAPTER,
                 attrib=c.DEFAULT_SCHEMA_ATTR,
                 children=[adpt.Element(VADPT_TYPE, text='Client'),
                           adpt.Element('UseNextAvailableSlotID',
                                        text='true')]))


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
    vdisk = adpt.Element(volume_group.DISK_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                         children=[adpt.Element(volume_group.DISK_NAME,
                                                text=str(disk_name))])
    stor = adpt.Element(MAP_STORAGE, children=[vdisk])

    # Create the 'Associated Logical Partition' element of the mapping.
    lpar = _crt_related_href(adapter, host_uuid, client_lpar_uuid)

    # Now bundle the components together.  Order is important.
    opts = [lpar, _NEW_CLIENT_ADAPTER, _NEW_SERVER_ADAPTER, stor]
    return adpt.Element(VIO_SCSI_MAP, attrib=_crt_attrs('ViosSCSIMapping'),
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
    vopt = adpt.Element(volume_group.VOPT_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=[adpt.Element(volume_group.VOPT_NAME,
                                               text=str(media_name))])
    stor = adpt.Element(MAP_STORAGE, children=[vopt])

    # Create the 'Associated Logical Partition' element of the mapping.
    lpar = _crt_related_href(adapter, host_uuid, client_lpar_uuid)

    # Now bundle the components together.  Order is important.
    opts = [lpar, _NEW_CLIENT_ADAPTER, _NEW_SERVER_ADAPTER, stor]
    return adpt.Element(VIO_SCSI_MAP, attrib=_crt_attrs('ViosSCSIMapping'),
                        children=opts)


def _crt_related_href(adapter, host_uuid, client_lpar_uuid):
    """Creates the Element for the 'AssociatedLogicalPartition'."""
    client_href = adapter.build_href(c.MGT_SYS, host_uuid, c.LPAR,
                                     client_lpar_uuid)
    return adpt.Element(MAP_CLIENT_LPAR, attrib={'href': client_href,
                                                 'rel': 'related'})


def _crt_attrs(group):
    schema = copy.copy(c.DEFAULT_SCHEMA_ATTR)
    schema['group'] = group
    return schema


class VirtualIOServer(ewrap.EntryWrapper):

    def get_name(self):
        return self.get_parm_value(c.PARTITION_NAME)

    def get_partition_id(self):
        return int(self.get_parm_value(c.VIOS_ID, c.ZERO))

    def get_state(self):
        return self.get_parm_value(c.PARTITION_STATE)

    def is_running(self):
        return self.get_state() == 'running'

    def get_rmc_state(self):
        return self.get_parm_value(c.RMC_STATE)

    def is_rmc_active(self):
        return self.get_rmc_state() == 'active'

    def get_virtual_scsi_mappings(self):
        return self._entry.element.find(c.VIRT_SCSI_MAPPINGS)

    def get_media_repository(self):
        return self._entry.element.find(c.VIRT_MEDIA_REPOSITORY_PATH)

    def get_wwpns(self):
        """Returns a list of the wwpn pairs for the vios."""
        return self.get_parm_values(c.WWPNS_PATH)

    def license_accepted(self):
        return self.get_parm_value_bool(c.VIOS_LICENSE, default=True)

    def get_hdisk_reserve_policy(self, disk_uuid):
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

    def get_hdisk_from_uuid(self, disk_uuid):
        """Get the hdisk name from the volume uuid.

        :param disk_uuid: The uuid of the hdisk.
        :returns: The associated hdisk name.
        """
        name = None

        # Get all the physical volume elements and look for a diskname match
        volumes = self._entry.element.findall(c.PVS_PATH)
        for volume in volumes:
            # TODO(IBM): c.UDID_PATH is './'.  This isn't right.  Fix it.
            vol_uuid = volume.findtext(c.UDID_PATH)
            if vol_uuid:
                LOG.debug('get_hdisk_from_uuid match: %s' % vol_uuid)
                LOG.debug('get_hdisk_from_uuid disk_uuid: %s' % disk_uuid)
                if vol_uuid == disk_uuid:
                    name = volume.findtext(c.VOL_NAME)
                    break

        return name

    def get_current_mem(self):
        return self.get_parm_value(c.CURR_MEM, c.ZERO)

    def get_current_proc_mode(self):
        # Returns true if dedicated or false if shared
        return self.get_parm_value(c.CURR_USE_DED_PROCS, c.FALSE).lower()

    def get_current_procs(self):
        return self.get_parm_value(c.CURR_PROCS, c.ZERO)

    def get_current_proc_units(self):
        return self.get_parm_value(c.CURR_PROC_UNITS, c.ZERO)

    def is_mover_service_partition(self):
        return self.get_parm_value_bool(c.MOVER_SERVICE_PARTITION, False)

    def get_ip_addresses(self):
        """Returns a list of IP addresses assigned to the VIOS.

        Will only return the IP Addresses that can be made known to the system.
        This only includes online Shared Ethernet Adapters and Ethernet Backing
        Devices.  It will not include, for example, a VLAN adapter.
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

        return ip_list

    def get_vfc_mappings(self):
        """Returns a list of the VirtualFCMapping objects."""
        mappings = []

        # Get all of the mapping elements
        q = c.ROOT + VIO_VFC_MAPPINGS + c.DELIM + VIO_VFC_MAP
        maps = self._entry.element.findall(q)
        for mapping in maps:
            mappings.append(VirtualFCMapping(mapping))
        return mappings

    def set_vfc_mappings(self, new_mappings):
        """Replaces the current VirtualFCMapping objects with the new list."""
        self.replace_list(VIO_VFC_MAPPINGS, new_mappings)

    def get_scsi_mappings(self):
        """Returns a list of the VirtualSCSIMapping objects."""
        mappings = []

        # Get all of the mapping elements
        q = c.ROOT + VIO_SCSI_MAPPINGS + c.DELIM + VIO_SCSI_MAP
        maps = self._entry.element.findall(q)
        for mapping in maps:
            mappings.append(VirtualSCSIMapping(mapping))
        return mappings

    def set_scsi_mappings(self, new_mappings):
        """Replaces the current SCSI mappings with the new mappings."""
        self.replace_list(VIO_SCSI_MAPPINGS, new_mappings)


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

    def get_client_lpar_href(self):
        """Returns the Client LPAR (if any) URI.

        If None - then no client is connected.
        """
        elem = self._element.find(MAP_CLIENT_LPAR)
        if elem is not None:
            return elem.get('href')
        return None

    def get_client_adapter(self):
        """Returns the Client side VirtualSCSIClientAdapter.

        If None - then no client is connected.
        """
        elem = self._element.find(MAP_CLIENT_ADAPTER)
        if elem is not None:
            return VirtualSCSIClientAdapter(elem)
        return None

    def get_server_adapter(self):
        """Returns the Virtual I/O Server side VirtualSCSIServerAdapter."""
        return VirtualSCSIServerAdapter(self._element.find(MAP_SERVER_ADAPTER))

    def get_backing_storage(self):
        """The backing storage element (if applicable).

        Refer to the 'volume_group' wrapper.  This element may be a
        VirtualDisk or VirtualOpticalMedia.  May return None.
        """
        elem = self._element.find(MAP_STORAGE)
        if elem is not None:
            # Check if virtual disk
            e = elem.find(volume_group.DISK_ROOT)
            if e is not None:
                return volume_group.VirtualDisk(e)

            # Check if virtual optical media
            e = elem.find(volume_group.VOPT_ROOT)
            if e is not None:
                return volume_group.VOPT_ROOT

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

    def get_client_lpar_href(self):
        """Returns the Client LPAR (if any) URI.

        If None - then no client is connected.
        """
        elem = self._element.find(MAP_CLIENT_LPAR)
        if elem is not None:
            return elem.get('href')
        return None

    def get_client_adapter(self):
        """Returns the Client Virtual FC Adapter.

        If None - then no client is connected.
        """
        elem = self._element.find(MAP_CLIENT_ADAPTER)
        if elem is not None:
            return VirtualFCClientAdapter(elem)
        return None

    def get_backing_port(self):
        """The Virtual I/O Server backing PhysicalFCPort.

        If None - then the vfcmap isn't done and no physical port is backing
        it.
        """
        elem = self._element.find(MAP_PORT)
        if elem is not None:
            return PhysicalFCPort(elem)
        return None

    def get_server_adapter(self):
        """Returns the Virtual I/O Server Virtual FC Adapter."""
        return VirtualFCServerAdapter(self._element.find(MAP_SERVER_ADAPTER))


class VirtualStorageAdapter(ewrap.ElementWrapper):
    """Parent class for the virtual storage adapters (FC or SCSI)."""

    def get_type(self):
        """Will return either Server or Client.

        A Server indicates that this is a virtual adapter that resides on the
        Virtual I/O Server.

        A Client indicates that this is an adapter residing on a Client LPAR.
        """
        return self.get_parm_value(VADPT_TYPE)

    def is_varied_on(self):
        """True if the adapter is varied on."""
        return self.get_parm_value(VADPT_VARIED_ON)

    def get_slot_number(self):
        """The (int) slot number that the adapter is in."""
        return self.get_parm_value_int(VADPT_SLOT_NUM)

    def get_loc_code(self):
        """The device's location code."""
        return self.get_parm_value(LOCATION_CODE)


class VirtualSCSIClientAdapter(VirtualStorageAdapter):
    """The Virtual SCSI Adapter that hosts storage traffic.

    Paired with a VirtualSCSIServerAdapter.
    """

    def get_lpar_id(self):
        """The LPAR ID the contains this client adapter."""
        return self.get_parm_value(VADPT_LPAR_ID)


class VirtualSCSIServerAdapter(VirtualStorageAdapter):
    """The Virtual SCSI Adapter that hosts storage traffic.

    Paired with a VirtualSCSIClientAdapter.
    """

    def get_name(self):
        """The adapter's name on the Virtual I/O Server."""
        return self.get_parm_value(VADPT_NAME)

    def get_backing_dev_name(self):
        """The backing device name that this virtual adapter is hooked into."""
        return self.get_parm_value(VADPT_BACK_DEV_NAME)

    def get_udid(self):
        """The device's Unique Device Identifier."""
        return self.get_parm_value(VADPT_UDID)


class VirtualFCClientAdapter(VirtualStorageAdapter):
    """The Virtual Fibre Channel Adapter on the client LPAR.

    Paired with a VirtualFCServerAdapter.
    """

    def get_wwpns(self):
        """Returns a String (delimited by spaces) that contains the WWPNs."""
        return self.get_parm_value(VADPT_WWPNS)

    def get_lpar_id(self):
        """The ID of the LPAR that contains this client adapter."""
        return self.get_parm_value(VADPT_LPAR_ID)


class VirtualFCServerAdapter(VirtualStorageAdapter):
    """The Virtual Fibre Channel Adapter on the VIOS.

    Paired with a VirtualFCClientAdapter.
    """

    def get_name(self):
        """The adapter's name on the Virtual I/O Server."""
        return self.get_parm_value(VADPT_NAME)

    def get_udid(self):
        """The device's Unique Device Identifier."""
        return self.get_parm_value(VADPT_UDID)

    def get_map_port(self):
        """The physical FC port name that this virtual port is connect to."""
        return self.get_parm_value(VADPT_MAP_PORT)


class PhysicalFCPort(ewrap.ElementWrapper):
    """A physical FibreChannel port on the Virtual I/O Server."""

    def get_loc_code(self):
        """Returns the location code."""
        return self.get_parm_value(LOCATION_CODE)

    def get_name(self):
        """The name of the port."""
        return self.get_parm_value(PFC_NAME)

    def get_udid(self):
        """The Unique Device ID."""
        return self.get_parm_value(PFC_UDID)

    def get_wwpn(self):
        """The port's world wide port name."""
        return self.get_parm_value(PFC_WWPN)

    def get_available_ports(self):
        """The number of available NPIV ports.  Int value."""
        return self.get_parm_value_int(PFC_AVAILABLE_PORTS)

    def get_total_ports(self):
        """The total number of NPIV ports.  Int value."""
        return self.get_parm_value_int(PFC_TOTAL_PORTS)
