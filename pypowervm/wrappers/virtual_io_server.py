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

import pypowervm.entities as ent
import pypowervm.util as u
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.constants as wc
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
_MOVER_SERVICE_PARTITION = 'MoverServicePartition'

# Mapping Constants
_MAP_CLIENT_ADAPTER = 'ClientAdapter'
_MAP_SERVER_ADAPTER = 'ServerAdapter'
_MAP_STORAGE = 'Storage'
_MAP_CLIENT_LPAR = 'AssociatedLogicalPartition'
_MAP_PORT = 'Port'
_MAP_ORDER = (_MAP_CLIENT_LPAR, _MAP_CLIENT_ADAPTER, _MAP_SERVER_ADAPTER,
              _MAP_STORAGE)


@ewrap.EntryWrapper.pvm_type('VirtualIOServer')
class VIOS(bp.BasePartition):

    # Extended Attribute Groups
    xags = ent.XAGEnum(NETWORK='ViosNetwork',
                       STORAGE='ViosStorage',
                       SCSI_MAPPING='ViosSCSIMapping',
                       FC_MAPPING='ViosFCMapping')

    @property
    def media_repository(self):
        return self.element.find(wc.VIRT_MEDIA_REPOSITORY_PATH)

    def get_vfc_wwpns(self):
        """Returns a list of the virtual FC WWPN pairs for the vios.

        The response is a List of Lists.
        Ex. (('c05076065a8b005a', 'c05076065a8b005b'),
             ('c05076065a8b0060', 'c05076065a8b0061'))
        """
        return set([frozenset(x.split()) for x in
                    self._get_vals(wc.WWPNS_PATH)])

    def get_pfc_wwpns(self):
        """Returns a set of the Physical FC Adapter WWPNs on this VIOS."""
        path = u.xpath(bp.IO_CFG_ROOT, bp.IO_SLOTS_ROOT,
                       bp.IO_SLOT_ROOT, bp.ASSOC_IO_SLOT_ROOT,
                       bp.RELATED_IO_ADPT_ROOT, bp.IO_PFC_ADPT_ROOT,
                       bp.PFC_PORTS_ROOT, bp.PFC_PORT_ROOT,
                       bp.PFC_PORT_WWPN)
        return set(self._get_vals(path))

    @property
    def pfc_ports(self):
        """The physical Fibre Channel ports assigned to the VIOS."""
        path = u.xpath(bp.IO_CFG_ROOT, bp.IO_SLOTS_ROOT,
                       bp.IO_SLOT_ROOT, bp.ASSOC_IO_SLOT_ROOT,
                       bp.RELATED_IO_ADPT_ROOT, bp.IO_PFC_ADPT_ROOT,
                       bp.PFC_PORTS_ROOT, bp.PFC_PORT_ROOT)
        elems = self._find(path, use_find_all=True)
        resp = []
        for elem in elems:
            resp.append(bp.PhysFCPort.wrap(elem))
        return resp

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
        volumes = self.element.findall(wc.PVS_PATH)
        for volume in volumes:
            vol_uuid = volume.findtext(wc.VOL_UID)
            match = re.search(r'^[0-9]{5}([0-9A-F]{32}).+$', vol_uuid)

            if match and match.group(1) == disk_uuid:
                policy = volume.findtext(wc.RESERVE_POLICY)
                break

        return policy

    def hdisk_from_uuid(self, disk_uuid):
        """Get the hdisk name from the volume uuid.

        :param disk_uuid: The uuid of the hdisk.
        :returns: The associated hdisk name.
        """
        name = None

        # Get all the physical volume elements and look for a diskname match
        volumes = self.element.findall(wc.PVS_PATH)
        for volume in volumes:
            vol_uuid = volume.findtext(wc.UDID)
            if vol_uuid:
                LOG.debug('get_hdisk_from_uuid match: %s' % vol_uuid)
                LOG.debug('get_hdisk_from_uuid disk_uuid: %s' % disk_uuid)
                if vol_uuid == disk_uuid:
                    name = volume.findtext(wc.VOL_NAME)
                    break

        return name

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
        seas = self.element.findall(wc.SHARED_ETHERNET_ADAPTER)
        free_eths = self.element.findall(wc.ETHERNET_BACKING_DEVICE)
        for eth in seas + free_eths:
            ip = eth.findtext(wc.IF_ADDR)
            if ip and ip not in ip_list:
                ip_list.append(ip)

        return tuple(ip_list)

    @property
    def vfc_mappings(self):
        """Returns a WrapperElemList of the VFCMapping objects."""
        def_attrib = self.xags.FC_MAPPING.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(_VIO_VFC_MAPPINGS, attrib=def_attrib),
            VFCMapping)
        return es

    @vfc_mappings.setter
    def vfc_mappings(self, new_mappings):
        self.replace_list(_VIO_VFC_MAPPINGS, new_mappings,
                          attrib=self.xags.SCSI_MAPPING.attrs)

    @property
    def scsi_mappings(self):
        """Returns a WrapperElemList of the VSCSIMapping objects."""
        def_attrib = self.xags.SCSI_MAPPING.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(_VIO_SCSI_MAPPINGS, attrib=def_attrib),
            VSCSIMapping)
        return es

    @scsi_mappings.setter
    def scsi_mappings(self, new_mappings):
        self.replace_list(_VIO_SCSI_MAPPINGS, new_mappings,
                          attrib=self.xags.SCSI_MAPPING.attrs)

    @property
    def seas(self):
        def_attrib = self.xags.NETWORK.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(net.NB_SEAS, attrib=def_attrib), net.SEA)
        return es

    @property
    def trunk_adapters(self):
        def_attrib = self.xags.NETWORK.attrs
        es = ewrap.WrapperElemList(
            self._find_or_seed(net.SEA_TRUNKS, attrib=def_attrib),
            net.TrunkAdapter)
        return es

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
    def crt_related_href(adapter, host_uuid, client_lpar_uuid):
        """Creates the Element for the 'AssociatedLogicalPartition'."""
        return adapter.build_href(ms.System.schema_type, host_uuid,
                                  lpar.LPAR.schema_type, client_lpar_uuid,
                                  xag=[])

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


@ewrap.ElementWrapper.pvm_type('VirtualSCSIMapping', has_metadata=True,
                               child_order=_MAP_ORDER)
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

    _client_adapter_cls = stor.VSCSIClientAdapter
    _server_adapter_cls = stor.VSCSIServerAdapter

    @classmethod
    def bld(cls, adapter, host_uuid, client_lpar_uuid, stg_ref):
        s_map = super(VSCSIMapping, cls)._bld()
        # Create the 'Associated Logical Partition' element of the mapping.
        s_map._client_lpar_href(
            cls.crt_related_href(adapter, host_uuid, client_lpar_uuid))
        s_map._client_adapter(stor.VClientStorageAdapter.bld())
        s_map._server_adapter(stor.VServerStorageAdapter.bld())
        s_map._backing_storage(stg_ref)
        return s_map

    @classmethod
    def bld_from_existing(cls, existing_map, stg_ref):
        """Clones the existing mapping, but swaps in the new storage elem."""
        new_map = copy.deepcopy(existing_map)
        new_map._backing_storage(stg_ref)
        return new_map

    @property
    def backing_storage(self):
        """The backing storage element (if applicable).

        Refer to the 'volume_group' wrapper.  This element may be a
        VirtualDisk or VirtualOpticalMedia.  May return None.
        """
        elem = self.element.find(_MAP_STORAGE)
        if elem is None:
            return None
        # If backing storage exists, it comprises a single child of elem.  But
        # type is unknown immediately, so call all children and then wrap.
        stor_elems = elem.getchildren()
        if len(stor_elems) != 1:
            return None
        # The storage element may be any one of VDisk, VOptMedia, PV, or LU.
        # Allow ElementWrapper to detect (from the registry) and wrap correctly
        return ewrap.ElementWrapper.wrap(stor_elems[0])

    def _backing_storage(self, stg):
        """Sets the backing storage of this mapping to a VDisk, VOpt, LU or PV.

        :param stg: Either a VDisk, VOpt, LU or PV wrapper representing the
                    backing storage to assign.
        """
        # Always replace.  Because while the storage has one element, it can't
        # inject properly if the backing type changes (ex. cloning from vOpt to
        # vDisk).
        stor_elem = ent.Element(_MAP_STORAGE, attrib={}, children=[])
        stor_elem.inject(stg.element)
        self.inject(stor_elem)


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

    _client_adapter_cls = stor.VFCClientAdapter
    _server_adapter_cls = stor.VFCServerAdapter

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
            cls.crt_related_href(adapter, host_uuid, client_lpar_uuid))
        s_map._client_adapter(stor.VFCClientAdapter.bld(wwpns=client_wwpns))

        # Create the backing port and change label.  API requires it be
        # Port, even though it is a Physical FC Port
        backing_port = bp.PhysFCPort.bld_ref(backing_phy_port)
        backing_port.element.tag = 'Port'
        s_map._backing_port(backing_port)

        s_map._server_adapter(stor.VFCServerAdapter.bld())
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
            return bp.PhysFCPort.wrap(elem)
        return None
