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
import functools
import logging
import re

import six

import pypowervm.util as u
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as ms
import pypowervm.wrappers.network as net
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)


_LOCATION_CODE = 'LocationCode'


# VIO Constants
_VIO_VFC_MAPPINGS = 'VirtualFibreChannelMappings'
_VIO_SCSI_MAPPINGS = 'VirtualSCSIMappings'
_VIO_LICENSE = 'VirtualIOServerLicenseAccepted'
_VIO_PARTITION_NAME = 'PartitionName'
_VIO_PARTITION_ID = 'PartitionID'
_VIO_PARTITION_STATE = 'PartitionState'
_MOVER_SERVICE_PARTITION = 'MoverServicePartition'

# Mapping Constants
_MAP_CLIENT_ADAPTER = 'ClientAdapter'
_MAP_SERVER_ADAPTER = 'ServerAdapter'
_MAP_STORAGE = 'Storage'
_MAP_CLIENT_LPAR = 'AssociatedLogicalPartition'
_MAP_PORT = 'Port'

# Virtual Adapter Constants
_VADPT_LPAR_ID = 'LocalPartitionID'
_VADPT_UDID = 'UniqueDeviceID'
_VADPT_MAP_PORT = 'MapPort'
_VADPT_WWPNS = 'WWPNs'
_VADPT_BACK_DEV_NAME = 'BackingDeviceName'
_VADPT_SLOT_NUM = 'VirtualSlotNumber'
_VADPT_VARIED_ON = 'VariedOn'
_VADPT_NAME = 'AdapterName'
_VADPT_TYPE = 'AdapterType'
_NEXT_SLOT = 'UseNextAvailableSlotID'


class XAGEnum(object):
    """Extended Attribute Groups for VirtualIOServer GET."""
    @functools.total_ordering
    class _Handler(object):
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return self.name

        def __eq__(self, other):
            return self.name == other.name

        def __lt__(self, other):
            return self.name < other.name

        @property
        def attrs(self):
            schema = copy.copy(c.DEFAULT_SCHEMA_ATTR)
            schema['group'] = self.name
            return schema

    VIOS_NETWORK = _Handler('ViosNetwork')
    VIOS_STORAGE = _Handler('ViosStorage')
    VIOS_SCSI_MAPPING = _Handler('ViosSCSIMapping')
    VIOS_FC_MAPPING = _Handler('ViosFCMapping')


@ewrap.EntryWrapper.pvm_type('VirtualIOServer')
class VIOS(ewrap.EntryWrapper):

    search_keys = dict(name='PartitionName', id='PartitionID')

    @property
    def name(self):
        return self._get_val_str(_VIO_PARTITION_NAME)

    @property
    def partition_id(self):
        return int(self._get_val_str(_VIO_PARTITION_ID, c.ZERO))

    @property
    def state(self):
        return self._get_val_str(_VIO_PARTITION_STATE)

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
    def media_repository(self):
        return self.element.find(c.VIRT_MEDIA_REPOSITORY_PATH)

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
        path = u.xpath(lpar.IO_CFG_ROOT, lpar.IO_SLOTS_ROOT,
                       lpar.IO_SLOT_ROOT, lpar.ASSOC_IO_SLOT_ROOT,
                       lpar.RELATED_IO_ADPT_ROOT, lpar.IO_PFC_ADPT_ROOT,
                       lpar.PFC_PORTS_ROOT, lpar.PFC_PORT_ROOT,
                       lpar.PFC_PORT_WWPN)
        return set(self._get_vals(path))

    @property
    def is_license_accepted(self):
        return self._get_val_bool(_VIO_LICENSE, default=True)

    def hdisk_reserve_policy(self, disk_uuid):
        """Get the reserve policy for an hdisk.

        :param disk_uuid: The uuid of the hdisk.
        :returns: The reserve policy or None if the disk isn't found.
        """
        policy = None

        # Get all the physical volume elements and look for a diskname match
        volumes = self.element.findall(c.PVS_PATH)
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
        volumes = self.element.findall(c.PVS_PATH)
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
        return self._get_val_bool(c.CURR_USE_DED_PROCS)

    @property
    def current_procs(self):
        return self._get_val_str(c.CURR_PROCS, c.ZERO)

    @property
    def current_proc_units(self):
        return self._get_val_str(c.CURR_PROC_UNITS, c.ZERO)

    @property
    def is_mover_service_partition(self):
        return self._get_val_bool(_MOVER_SERVICE_PARTITION, False)

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
        seas = self.element.findall(c.SHARED_ETHERNET_ADAPTER)
        free_eths = self.element.findall(c.ETHERNET_BACKING_DEVICE)
        for eth in seas + free_eths:
            ip = eth.findtext(c.IF_ADDR)
            if ip and ip not in ip_list:
                ip_list.append(ip)

        return tuple(ip_list)

    @property
    def vfc_mappings(self):
        """Returns a WrapperElemList of the VFCMapping objects."""
        def_attrib = XAGEnum.VIOS_FC_MAPPING.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(_VIO_VFC_MAPPINGS, attrib=def_attrib),
            VFCMapping)
        return es

    @vfc_mappings.setter
    def vfc_mappings(self, new_mappings):
        self.replace_list(_VIO_VFC_MAPPINGS, new_mappings,
                          attrib=XAGEnum.VIOS_SCSI_MAPPING.attrs)

    @property
    def scsi_mappings(self):
        """Returns a WrapperElemList of the VSCSIMapping objects."""
        def_attrib = XAGEnum.VIOS_SCSI_MAPPING.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(_VIO_SCSI_MAPPINGS, attrib=def_attrib),
            VSCSIMapping)
        return es

    @scsi_mappings.setter
    def scsi_mappings(self, new_mappings):
        self.replace_list(_VIO_SCSI_MAPPINGS, new_mappings,
                          attrib=XAGEnum.VIOS_SCSI_MAPPING.attrs)

    @property
    def seas(self):
        def_attrib = XAGEnum.VIOS_NETWORK.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(net.NB_SEAS, attrib=def_attrib), net.SEA)
        return es

    @property
    def trunk_adapters(self):
        def_attrib = XAGEnum.VIOS_NETWORK.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(net.SEA_TRUNKS, attrib=def_attrib),
            net.TrunkAdapter)
        return es

    @property
    def io_config(self):
        """The Partition I/O Configuration for the VIOS."""
        elem = self.element.find(lpar.IO_CFG_ROOT)
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


@six.add_metaclass(abc.ABCMeta)
class VStorageMapping(ewrap.ElementWrapper):
    """Base class for VSCSIMapping and VFCMapping."""

    @staticmethod
    def _crt_related_href(adapter, host_uuid, client_lpar_uuid):
        """Creates the Element for the 'AssociatedLogicalPartition'."""
        return adapter.build_href(ms.System.schema_type, host_uuid,
                                  lpar.LPAR.schema_type, client_lpar_uuid)

    @property
    def client_lpar_href(self):
        """Returns the Client LPAR (if any) URI.

        If None - then no client is connected.
        """
        return self.get_href(_MAP_CLIENT_LPAR, one_result=True)

    def _client_lpar_href(self, href):
        self.set_href(_MAP_CLIENT_LPAR, href)

    @property
    def client_adapter(self):
        """Returns the Client side VSCSIClientAdapter.

        If None - then no client is connected.
        """
        elem = self.element.find(_MAP_CLIENT_ADAPTER)
        if elem is not None:
            return self._client_adapter_cls.wrap(elem)
        return None

    def _client_adapter(self, ca):
        elem = self._find_or_seed(_MAP_CLIENT_ADAPTER)
        self.element.replace(elem, ca.element)

    @property
    def server_adapter(self):
        """Returns the Virtual I/O Server side VSCSIServerAdapter."""
        return self._server_adapter_cls.wrap(
            self.element.find(_MAP_SERVER_ADAPTER))

    def _server_adapter(self, sa):
        elem = self._find_or_seed(_MAP_SERVER_ADAPTER)
        self.element.replace(elem, sa.element)


@six.add_metaclass(abc.ABCMeta)
class VStorageAdapter(ewrap.ElementWrapper):
    """Parent class for the virtual storage adapters (FC or SCSI)."""
    has_metadata = True

    @classmethod
    def _bld_new(cls, side):
        """Build a {Client|Server}Adapter requesting a new virtual adapter.

        :param side: Either 'Client' or 'Server'.
        :returns: A fresh ClientAdapter or ServerAdapter wrapper with
                  UseNextAvailableSlotID=true
        """
        adp = super(VStorageAdapter, cls)._bld()
        adp._side(side)
        adp._use_next_slot(True)
        return adp

    @property
    def side(self):
        """Will return either Server or Client.

        A Server indicates that this is a virtual adapter that resides on the
        Virtual I/O Server.

        A Client indicates that this is an adapter residing on a Client LPAR.
        """
        return self._get_val_str(_VADPT_TYPE)

    def _side(self, t):
        self.set_parm_value(_VADPT_TYPE, t)

    @property
    def is_varied_on(self):
        """True if the adapter is varied on."""
        return self._get_val_str(_VADPT_VARIED_ON)

    @property
    def slot_number(self):
        """The (int) slot number that the adapter is in."""
        return self._get_val_int(_VADPT_SLOT_NUM)

    def _use_next_slot(self, use):
        self.set_parm_value(_NEXT_SLOT, u.sanitize_bool_for_api(use))

    @property
    def loc_code(self):
        """The device's location code."""
        return self._get_val_str(_LOCATION_CODE)


@six.add_metaclass(abc.ABCMeta)
@ewrap.ElementWrapper.pvm_type('ClientAdapter', has_metadata=True)
class VClientStorageAdapter(VStorageAdapter):
    """Parent class for Client Virtual Storage Adapters."""

    @classmethod
    def bld(cls):
        return super(VClientStorageAdapter, cls)._bld_new('Client')

    @property
    def lpar_id(self):
        """The LPAR ID the contains this client adapter."""
        return self._get_val_str(_VADPT_LPAR_ID)


@six.add_metaclass(abc.ABCMeta)
@ewrap.ElementWrapper.pvm_type('ServerAdapter', has_metadata=True)
class VServerStorageAdapter(VStorageAdapter):
    """Parent class for Server Virtual Storage Adapters."""

    @classmethod
    def bld(cls):
        return super(VServerStorageAdapter, cls)._bld_new('Server')

    @property
    def name(self):
        """The adapter's name on the Virtual I/O Server."""
        return self._get_val_str(_VADPT_NAME)

    @property
    def udid(self):
        """The device's Unique Device Identifier."""
        return self._get_val_str(_VADPT_UDID)


# pvm_type decorator by superclass (it is not unique)
class VSCSIClientAdapter(VClientStorageAdapter):
    """The Virtual SCSI Adapter that hosts storage traffic.

    Paired with a VSCSIServerAdapter.
    """
    pass  # Implemented by superclasses


# pvm_type decorator by superclass (it is not unique)
class VSCSIServerAdapter(VServerStorageAdapter):
    """The Virtual SCSI Adapter that hosts storage traffic.

    Paired with a VSCSIClientAdapter.
    """

    @property
    def backing_dev_name(self):
        """The backing device name that this virtual adapter is hooked into."""
        return self._get_val_str(_VADPT_BACK_DEV_NAME)


@ewrap.ElementWrapper.pvm_type('VirtualSCSIMapping', has_metadata=True)
class VSCSIMapping(VStorageMapping):
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

    _client_adapter_cls = VSCSIClientAdapter
    _server_adapter_cls = VSCSIServerAdapter

    @classmethod
    def bld(cls, adapter, host_uuid, client_lpar_uuid, stg_ref):
        s_map = super(VSCSIMapping, cls)._bld()
        # Create the 'Associated Logical Partition' element of the mapping.
        s_map._client_lpar_href(
            cls._crt_related_href(adapter, host_uuid, client_lpar_uuid))
        s_map._client_adapter(VClientStorageAdapter.bld())
        s_map._server_adapter(VServerStorageAdapter.bld())
        s_map._backing_storage(stg_ref)
        return s_map

    @classmethod
    def bld_to_vdisk(cls, adapter, host_uuid, client_lpar_uuid, disk_name):
        """Creates the VSCSIMapping Wrapper for a VirtualDisk.

        This is used when creating a new mapping between a Client LPAR and the
        VirtualIOServer.  This creates a SCSI connection between a VirtualDisk
        and the corresponding client LPAR.

        The response object should be used for creating the mapping via an
        update call in the Adapter.  The response object will not have UDIDs
        (as those are not assigned until the update is done).  This holds true
        for other elements as well.

        :param adapter: The pypowervm Adapter that will be used to create the
                        mapping.
        :param host_uuid: (TEMPORARY) The host system's UUID.
        :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                                 connected to.
        :param disk_name: The name of the VirtualDisk that should be used.  Can
                          be determined by referencing the VolumeGroup.
        :returns: The Element that represents the new VSCSIMapping (it is
                  not the Wrapper, but the element that serves as input into
                  the VSCSIMapping wrapper).
        """
        return cls.bld(adapter, host_uuid, client_lpar_uuid,
                       stor.VDisk.bld_ref(disk_name))

    @classmethod
    def bld_to_vopt(cls, adapter, host_uuid, client_lpar_uuid, media_name):
        """Creates the VSCSIMapping object for Virtual Optical Media.

        This is used when creating a new mapping between a Client LPAR and
        Virtual Optical Media that the Virtual I/O Server is hosting.  This
        creates a SCSI connection between a virtual media and the corresponding
        client LPAR.

        The response object should be used for creating the mapping via an
        update call in the Adapter.  The response object will not have UDIDs
        (as those are not assigned until the update is done).  This holds true
        for other elements as well.

        :param adapter: The pypowervm Adapter that will be used to create the
                        mapping.
        :param host_uuid: (TEMPORARY) The host system's UUID.
        :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                                 connected to.
        :param media_name: The name of the Virtual Optical Media device to add.
                           Maps to the volume_group's VirtualOpticalMedia
                           media_name.
        :returns: The new VSCSIMapping Wrapper.
        """
        return cls.bld(adapter, host_uuid, client_lpar_uuid,
                       stor.VOptMedia.bld_ref(media_name))

    @classmethod
    def bld_to_lu(cls, adapter, host_uuid, client_lpar_uuid, udid,
                  disk_name):
        """Creates the VSCSIMapping object for a LU.

        This is used when creating a new mapping between a Client LPAR and
        a LU (typically Shared Storage Pool based) that the Virtual I/O Server
        is hosting.  This creates a SCSI connection between a LUN and the
        corresponding client LPAR.

        The response object should be used for creating the mapping via an
        update call in the Adapter.  The response object will not have UDIDs
        (as those are not assigned until the update is done).  This holds true
        for other elements as well.

        :param adapter: The pypowervm Adapter that will be used to create the
                        mapping.
        :param host_uuid: (TEMPORARY) The host system's UUID.
        :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                                 connected to.
        :param udid: The UDID of the LU.
        :param disk_name: The name of the LU.
        :returns: The new VSCSIMapping Wrapper.
        """
        return cls.bld(adapter, host_uuid, client_lpar_uuid,
                       stor.LU.bld_ref(disk_name, udid))

    @classmethod
    def bld_to_pv(cls, adapter, host_uuid, client_lpar_uuid, disk_name):
        """Creates the VSCSIMapping object for a Physical Volume.

        This is used when creating a new mapping between a Client LPAR and
        a physical volume (typically for classic vSCSI connections) that the
        Virtual I/O Server is hosting.  This creates a SCSI connection between
        a physical volume (ex. hdisk) and the corresponding client LPAR.

        The response object should be used for creating the mapping via an
        update call in the Adapter.  The response object will not have UDIDs
        (as those are not assigned until the update is done).  This holds true
        for other elements as well.

        :param adapter: The pypowervm Adapter that will be used to create the
                        mapping.
        :param host_uuid: (TEMPORARY) The host system's UUID.
        :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                                 connected to.
        :param disk_name: The name of the hdisk to map the client LPAR to.
        :returns: The new VSCSIMapping Wrapper.
        """
        return cls.bld(adapter, host_uuid, client_lpar_uuid,
                       stor.PV.bld(disk_name))

    @property
    def backing_storage(self):
        """The backing storage element (if applicable).

        Refer to the 'volume_group' wrapper.  This element may be a
        VirtualDisk or VirtualOpticalMedia.  May return None.
        """
        elem = self.element.find(_MAP_STORAGE)
        if elem is None:
            return None
        # If backing storage exists, it comprises a single child of elem.
        media = elem.getchildren()
        if len(media) != 1:
            return None
        # The storage element may be any one of VDisk, VOptMedia, PV, or LU.
        # Allow ElementWrapper to detect (from the registry) and wrap correctly
        return ewrap.ElementWrapper.wrap(media[0])

    def _backing_storage(self, stg):
        """Sets the backing storage of this mapping to a VDisk or VOpt.

        Currently assumes this mapping does not already have storage assigned.

        :param stg: Either a VDisk or VOptMedia wrapper representing the
                    backing storage to assign.
        """
        elem = self._find_or_seed(_MAP_STORAGE, attrib={})
        elem.append(stg.element)


# pvm_type decorator by superclass (it is not unique)
class VFCClientAdapter(VClientStorageAdapter):
    """The Virtual Fibre Channel Adapter on the client LPAR.

    Paired with a VFCServerAdapter.
    """

    @classmethod
    def bld(cls, wwpns=None):
        """Create a fresh Virtual Fibre Channel Client Adapter.

        :param wwpns: An optional set of two client WWPNs to set on the
                      adapter.
        """
        adpt = super(VFCClientAdapter, cls).bld()

        if wwpns is not None:
            adpt._wwpns(wwpns)

        return adpt

    def _wwpns(self, value):
        """Sets the WWPN string.

        :param value: The set (or list) of WWPNs.  Should only contain two.
        """
        if value is not None:
            self.set_parm_value(_VADPT_WWPNS, " ".join(value))

    @property
    def wwpns(self):
        """Returns a set that contains the WWPNs.  If no WWPNs, empty set."""
        val = self._get_val_str(_VADPT_WWPNS)
        if val is None:
            return set()
        else:
            return set(val.split(' '))


# pvm_type decorator by superclass (it is not unique)
class VFCServerAdapter(VServerStorageAdapter):
    """The Virtual Fibre Channel Adapter on the VIOS.

    Paired with a VFCClientAdapter.
    """

    @property
    def map_port(self):
        """The physical FC port name that this virtual port is connect to."""
        return self._get_val_str(_VADPT_MAP_PORT)


@ewrap.ElementWrapper.pvm_type('VirtualFibreChannelMapping', has_metadata=True)
class VFCMapping(VStorageMapping):
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

    _client_adapter_cls = VFCClientAdapter
    _server_adapter_cls = VFCServerAdapter

    @classmethod
    def bld(cls, adapter, host_uuid, client_lpar_uuid, backing_phy_port,
            client_wwpns=None):
        """Creates the VFCMapping object to connect to a Physical FC Port.

        This is used when creating a new mapping between a Client LPAR and the
        VirtualIOServer.  This creates a Fibre Channel connection between an
        LPAR and a physical Fibre Port.

        The response object should be used for creating the mapping via an
        adapter.update() to the Virtual I/O Server.  The response object
        will not have the UUIDs (as those are not assigned until the update is
        done).  This holds true for certain other elements as well.

        :param adapter: The pypowervm Adapter that will be used to create the
                        mapping.
        :param host_uuid: The host system's UUID.
        :param client_lpar_uuid: The client LPAR's UUID that the disk should be
                                 connected to.
        :param backing_phy_port: The name of the physical FC port that backs
                                 the virtual adapter.
        :param client_wwpns: An optional set of two WWPNs that can be set upon
                             the mapping.  These represent the client VM's
                             WWPNs on the client FC adapter.  If not set, the
                             system will dynamically generate them.
        :returns: The new VFCMapping Wrapper.
        """
        s_map = super(VFCMapping, cls)._bld()
        # Create the 'Associated Logical Partition' element of the mapping.
        s_map._client_lpar_href(
            cls._crt_related_href(adapter, host_uuid, client_lpar_uuid))
        s_map._client_adapter(VFCClientAdapter.bld(wwpns=client_wwpns))

        # Create the backing port and change label.  API requires it be
        # Port, even though it is a Physical FC Port
        backing_port = lpar.PhysFCPort.bld_ref(backing_phy_port)
        backing_port.element.tag = 'Port'
        s_map._backing_port(backing_port)

        s_map._server_adapter(VFCServerAdapter.bld())
        return s_map

    def _backing_port(self, value):
        """Sets the backing port."""
        elem = self._find_or_seed(_MAP_PORT)
        self.element.replace(elem, value.element)

    @property
    def backing_port(self):
        """The Virtual I/O Server backing PhysicalFCPort.

        If None - then the vfcmap isn't done and no physical port is backing
        it.
        """
        elem = self.element.find(_MAP_PORT)
        if elem is not None:
            return lpar.PhysFCPort.wrap(elem)
        return None
