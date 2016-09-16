# Copyright 2014, 2016 IBM Corp.
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

"""Wrappers for VirtualIOServer and virtual storage mapping elements."""

import abc
import copy
import functools
import re
import six

from oslo_log import log as logging

import pypowervm.const as c
import pypowervm.entities as ent
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as ms
import pypowervm.wrappers.network as net
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)

# VIO Constants
_VIO_API_CAP = 'APICapable'
_VIO_VNIC_CAP = 'IsVNICCapable'
_VIO_VNIC_FAILOVER_CAP = 'VNICFailOverCapable'
_VIO_SVR_INST_CFG = 'ServerInstallConfiguration'
_VIO_LNAGGS = 'LinkAggregations'
_VIO_MGR_PASSTHRU_CAP = 'ManagerPassthroughCapable'
_VIO_MEDIA_REPOS = 'MediaRepositories'
_VIO_MVR_SVC_PARTITION = 'MoverServicePartition'
_VIO_NET_BOOT_DEVS = 'NetworkBootDevices'
_VIO_PAGING_SVC_PARTITION = 'PagingServicePartition'
_VIO_PVS = stor.PVS
_VIO_SEAS = net.NB_SEAS
_VIO_SSP_CAP = 'SharedStoragePoolCapable'
_VIO_SSP_VER = 'SharedStoragePoolVersion'
_VIO_STOR_POOLS = 'StoragePools'
_VIO_TRUNK_ADPTS = net.SEA_TRUNKS
_VIO_LICENSE = 'VirtualIOServerLicense'
_VIO_LICENSE_ACCEPTED = 'VirtualIOServerLicenseAccepted'
_VIO_VFC_MAPPINGS = 'VirtualFibreChannelMappings'
_VIO_VSCSI_MAPPINGS = 'VirtualSCSIMappings'
_VIO_FREE_IO_ADPTS_FOR_LNAGG = 'FreeIOAdaptersForLinkAggregation'
# "FreeEthernetBackingDevicesForSEA" is really misspelled in the schema.
_VIO_FREE_ETH_BACKDEVS_FOR_SEA = 'FreeEthenetBackingDevicesForSEA'
_VIO_VNIC_BACKDEVS = 'VirtualNICBackingDevices'
_VIO_CAPS = 'VirtualIOServerCapabilities'
_VIO_VSCSI_BUS = 'VirtualSCSIBus'

_VOL_UID = 'VolumeUniqueID'
_VOL_NAME = 'VolumeName'
_RESERVE_POLICY = 'ReservePolicy'

_IO_ADPT_CHOICE = 'IOAdapterChoice'
_IO_ADPT = 'IOAdapter'
_IO_LINK_AGG_ADPT_ID = 'AdapterID'
_IO_LINK_AGG_DESC = 'Description'
_IO_LINK_AGG_DEV_NAME = 'DeviceName'
_IO_LINK_AGG_DEV_TYPE = 'DeviceType'
_IO_LINK_AGG_DRC_NAME = 'DynamicReconfigurationConnectorName'
_IO_LINK_AGG_PHYS_LOC = 'PhysicalLocation'
_IO_LINK_AGG_UDID = 'UniqueDeviceID'

_VIRT_MEDIA_REPOSITORY_PATH = u.xpath(_VIO_MEDIA_REPOS,
                                      'VirtualMediaRepository')
_IF_ADDR = u.xpath('IPInterface', 'IPAddress')
_ETHERNET_BACKING_DEVICE = u.xpath(_VIO_FREE_ETH_BACKDEVS_FOR_SEA,
                                   'IOAdapterChoice', net.ETH_BACK_DEV)
_SEA_PATH = u.xpath(_VIO_SEAS, net.SHARED_ETH_ADPT)

# Mapping Constants
_MAP_STORAGE = 'Storage'
_MAP_TARGET_DEV = 'TargetDevice'
_MAP_CLIENT_LPAR = 'AssociatedLogicalPartition'
_MAP_PORT = 'Port'
_MAP_ORDER = (_MAP_CLIENT_LPAR, stor.CLIENT_ADPT, stor.SERVER_ADPT,
              _MAP_STORAGE)
_VFC_MAP_ORDER = (_MAP_CLIENT_LPAR, stor.CLIENT_ADPT, _MAP_PORT,
                  stor.SERVER_ADPT, _MAP_STORAGE)

# VSCSI Bus Constants
_BUS_ASSOC_MAPS = 'AssociatedMappings'

_BUS_EL_ORDER = (_MAP_CLIENT_LPAR, stor.CLIENT_ADPT, stor.SERVER_ADPT,
                 _BUS_ASSOC_MAPS)

# VSCSI Storage/Target Device Constants
_STDEV_EL_ORDER = (_MAP_STORAGE, _MAP_TARGET_DEV)

_WWPNS_PATH = u.xpath(_VIO_VFC_MAPPINGS, 'VirtualFibreChannelMapping',
                      stor.CLIENT_ADPT, 'WWPNs')
_PVS_PATH = u.xpath(stor.PVS, stor.PHYS_VOL)

_VIOS_EL_ORDER = bp.BP_EL_ORDER + (
    _VIO_API_CAP, _VIO_VNIC_CAP, _VIO_VNIC_FAILOVER_CAP, _VIO_SVR_INST_CFG,
    _VIO_LNAGGS, _VIO_MGR_PASSTHRU_CAP, _VIO_MEDIA_REPOS,
    _VIO_MVR_SVC_PARTITION, _VIO_NET_BOOT_DEVS, _VIO_PAGING_SVC_PARTITION,
    _VIO_PVS, _VIO_SEAS, _VIO_SSP_CAP, _VIO_SSP_VER, _VIO_STOR_POOLS,
    _VIO_TRUNK_ADPTS, _VIO_LICENSE, _VIO_LICENSE_ACCEPTED, _VIO_VFC_MAPPINGS,
    _VIO_VSCSI_MAPPINGS, _VIO_FREE_IO_ADPTS_FOR_LNAGG,
    _VIO_FREE_ETH_BACKDEVS_FOR_SEA, _VIO_VNIC_BACKDEVS, _VIO_CAPS,
    _VIO_VSCSI_BUS)

LinkAggrIOAdapterChoice = card.LinkAggrIOAdapterChoice


class _VIOSXAGs(object):
    """Extended attribute groups relevant to Virtual I/O Server.

    DEPRECATED.  Use pypowervm.const.XAG and pypowervm.util.xag_attrs().
    """

    @functools.total_ordering
    class _Handler(object):
        def __init__(self, name):
            self.name = name
            self.attrs = u.xag_attrs(name)

        def __str__(self):
            return self.name

        def __eq__(self, other):
            if type(other) is str:
                return self.name == other
            return self.name == other.name

        def __lt__(self, other):
            if type(other) is str:
                return self.name < other
            return self.name < other.name

        def __hash__(self):
            return hash(self.name)

    _vals = dict(
        NETWORK=_Handler(c.XAG.VIO_NET),
        STORAGE=_Handler(c.XAG.VIO_STOR),
        SCSI_MAPPING=_Handler(c.XAG.VIO_SMAP),
        FC_MAPPING=_Handler(c.XAG.VIO_FMAP))

    def __getattr__(self, item):
        if item in self._vals:
            import warnings
            warnings.warn(_("The 'xags' property of the VIOS EntryWrapper "
                            "class is deprecated!  Please use values from "
                            "pypowervm.const.XAG instead."),
                          DeprecationWarning)
            return self._vals[item]


@ewrap.EntryWrapper.pvm_type('VirtualIOServer', child_order=_VIOS_EL_ORDER)
class VIOS(bp.BasePartition):

    # DEPRECATED.  Use pypowervm.const.XAG and pypowervm.util.xag_attrs().
    xags = _VIOSXAGs()

    @classmethod
    def bld(cls, adapter, name, mem_cfg, proc_cfg, io_cfg=None):
        """Creates a new VIOS wrapper."""
        return super(VIOS, cls)._bld_base(adapter, name, mem_cfg, proc_cfg,
                                          env=bp.LPARType.VIOS, io_cfg=io_cfg)

    @ewrap.Wrapper.xag_property(c.XAG.VIO_STOR)
    def media_repository(self):
        return self.element.find(_VIRT_MEDIA_REPOSITORY_PATH)

    def get_vfc_wwpns(self):
        """Returns a list of the virtual FC WWPN pairs for the vios.

        The response is a List of Lists.
        Ex. (('c05076065a8b005a', 'c05076065a8b005b'),
             ('c05076065a8b0060', 'c05076065a8b0061'))

        Note: ViosFCMapping extended attribute is required.
        """
        return set([frozenset(x.split()) for x in
                    self._get_vals(_WWPNS_PATH)])

    def get_pfc_wwpns(self):
        """Returns a set of the Physical FC Adapter WWPNs on this VIOS."""
        path = u.xpath(bp.IO_CFG_ROOT, bp.IO_SLOTS_ROOT,
                       bp.IO_SLOT_ROOT, bp.ASSOC_IO_SLOT_ROOT,
                       bp.RELATED_IO_ADPT_ROOT, bp.IO_PFC_ADPT_ROOT,
                       bp.PFC_PORTS_ROOT, bp.PFC_PORT_ROOT,
                       bp.PFC_PORT_WWPN)
        return set(self._get_vals(path))

    def get_active_pfc_wwpns(self):
        """Returns a set of Physical FC Adapter WWPNs of 'active' ports."""
        # The logic to check for active ports is poor.  Right now it only
        # checks if the port has NPIV connections available.  If there is a
        # FC, non-NPIV card...then this logic fails.
        #
        # This will suffice until the backing API adds more granular logic.
        return [pfc.wwpn for pfc in self.pfc_ports if pfc.npiv_total_ports > 0]

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
        return self._get_val_bool(_VIO_LICENSE_ACCEPTED, default=True)

    def hdisk_reserve_policy(self, disk_uuid):
        """Get the reserve policy for an hdisk.

        :param disk_uuid: The uuid of the hdisk.
        :returns: The reserve policy or None if the disk isn't found.
        """
        policy = None

        # Get all the physical volume elements and look for a diskname match
        volumes = self.element.findall(_PVS_PATH)
        for volume in volumes:
            vol_uuid = volume.findtext(_VOL_UID)
            match = re.search(r'^[0-9]{5}([0-9A-F]{32}).+$', vol_uuid)

            if match and match.group(1) == disk_uuid:
                policy = volume.findtext(_RESERVE_POLICY)
                break

        return policy

    def hdisk_from_uuid(self, disk_uuid):
        """Get the hdisk name from the volume uuid.

        :param disk_uuid: The uuid of the hdisk.
        :returns: The associated hdisk name.
        """
        name = None

        # Get all the physical volume elements and look for a diskname match
        volumes = self.element.findall(_PVS_PATH)
        for volume in volumes:
            vol_uuid = volume.findtext(stor.UDID)
            if vol_uuid:
                LOG.debug('get_hdisk_from_uuid match: %s' % vol_uuid)
                LOG.debug('get_hdisk_from_uuid disk_uuid: %s' % disk_uuid)
                if vol_uuid == disk_uuid:
                    name = volume.findtext(_VOL_NAME)
                    break

        return name

    @property
    def is_mover_service_partition(self):
        return self._get_val_bool(_VIO_MVR_SVC_PARTITION, False)

    @is_mover_service_partition.setter
    def is_mover_service_partition(self, value):
        """Set the Mover Service Partition designation.

        :param value: Boolean indicating whether the VIOS should be designated
                      as a Mover Service Partition.
        """
        self.set_parm_value(_VIO_MVR_SVC_PARTITION,
                            u.sanitize_bool_for_api(value))

    @ewrap.Wrapper.xag_property(c.XAG.VIO_NET)
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
        seas = self.element.findall(_SEA_PATH)
        free_eths = self.element.findall(_ETHERNET_BACKING_DEVICE)
        for eth in seas + free_eths:
            ip = eth.findtext(_IF_ADDR)
            if ip and ip not in ip_list:
                ip_list.append(ip)

        return tuple(ip_list)

    @ewrap.Wrapper.xag_property(c.XAG.VIO_FMAP)
    def vfc_mappings(self):
        """Returns a WrapperElemList of the VFCMapping objects."""
        es = ewrap.WrapperElemList(self._find_or_seed(
            _VIO_VFC_MAPPINGS, attrib=u.xag_attrs(c.XAG.VIO_FMAP)), VFCMapping)
        return es

    @vfc_mappings.setter
    def vfc_mappings(self, new_mappings):
        self.replace_list(_VIO_VFC_MAPPINGS, new_mappings,
                          attrib=u.xag_attrs(c.XAG.VIO_FMAP))

    @ewrap.Wrapper.xag_property(c.XAG.VIO_SMAP)
    def scsi_mappings(self):
        """Returns a WrapperElemList of the VSCSIMapping objects."""
        # TODO(efried): remove parent_entry once VIOS has pg83 in Events
        es = ewrap.WrapperElemList(
            self._find_or_seed(_VIO_VSCSI_MAPPINGS,
                               attrib=u.xag_attrs(c.XAG.VIO_SMAP)),
            VSCSIMapping, parent_entry=self)
        return es

    @scsi_mappings.setter
    def scsi_mappings(self, new_mappings):
        self.replace_list(_VIO_VSCSI_MAPPINGS, new_mappings,
                          attrib=u.xag_attrs(c.XAG.VIO_SMAP))

    @ewrap.Wrapper.xag_property(c.XAG.VIO_NET)
    def seas(self):
        es = ewrap.WrapperElemList(self._find_or_seed(
            _VIO_SEAS, attrib=u.xag_attrs(c.XAG.VIO_NET)), net.SEA)
        return es

    @ewrap.Wrapper.xag_property(c.XAG.VIO_NET)
    def trunk_adapters(self):
        es = ewrap.WrapperElemList(
            self._find_or_seed(_VIO_TRUNK_ADPTS,
                               attrib=u.xag_attrs(c.XAG.VIO_NET)),
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

    @ewrap.Wrapper.xag_property(c.XAG.VIO_STOR)
    def phys_vols(self):
        """Will return a list of physical volumes attached to this VIOS.

        This list is READ-ONLY.
        """
        # TODO(efried): remove parent_entry once VIOS has pg83 in Events
        es = ewrap.WrapperElemList(
            self._find_or_seed(stor.PVS, attrib=u.xag_attrs(c.XAG.VIO_STOR)),
            stor.PV, parent_entry=self)
        es_list = [es_val for es_val in es]
        return tuple(es_list)

    @ewrap.Wrapper.xag_property(c.XAG.VIO_NET)
    def io_adpts_for_link_agg(self):
        es = ewrap.WrapperElemList(
            self._find_or_seed(_VIO_FREE_IO_ADPTS_FOR_LNAGG,
                               attrib=u.xag_attrs(c.XAG.VIO_NET)),
            LinkAggrIOAdapterChoice)
        return es

    def can_lpm(self, host_w, migr_data=None):
        """Determines if a partition is ready for Live Partition Migration.

        :return capable: False, VIOS types are not LPM capable
        :return reason: A message that will indicate why it was not
                        capable of LPM.
        """
        return False, _('Partition of VIOS type is not LPM capable')

    @property
    def vnic_capable(self):
        return self._get_val_bool(_VIO_VNIC_CAP)

    @property
    def vnic_failover_capable(self):
        return self._get_val_bool(_VIO_VNIC_FAILOVER_CAP)


@six.add_metaclass(abc.ABCMeta)
@ewrap.Wrapper.base_pvm_type
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
        """Returns the Client side V*ClientAdapterElement.

        If None - then no client is connected.
        """
        elem = self.element.find(stor.CLIENT_ADPT)
        if elem is not None:
            return self._client_adapter_cls.wrap(elem)
        return None

    def _client_adapter(self, ca):
        elem = self._find_or_seed(stor.CLIENT_ADPT)
        self.element.replace(elem, ca.element)

    @property
    def server_adapter(self):
        """Returns the Virtual I/O Server side V*ServerAdapterElement."""
        return self._server_adapter_cls.wrap(
            self.element.find(stor.SERVER_ADPT))

    def _server_adapter(self, sa):
        elem = self._find_or_seed(stor.SERVER_ADPT)
        self.element.replace(elem, sa.element)


@ewrap.Wrapper.base_pvm_type
class _STDevMethods(ewrap.ElementWrapper):
    """Methods for storage and target common to STDev and VSCSIMapping."""
    def _set_stg_and_tgt(self, adapter, stg_ref, lua=None, target_name=None):
        self._backing_storage(stg_ref)
        if lua is not None or target_name is not None:
            # Build a *TargetDev of the appropriate type for this stg_ref
            self._target_dev(stg_ref.target_dev_type.bld(adapter, lua,
                                                         target_name))

    @property
    def backing_storage(self):
        """The backing storage element (if applicable).

        This element may be a PV, LU, VirtualDisk, or VirtualOpticalMedia.
        May return None.
        """
        elem = self.element.find(_MAP_STORAGE)
        if elem is None:
            return None
        # If backing storage exists, it comprises a single child of elem.  But
        # type is unknown immediately, so call all children and then wrap.
        stor_elems = list(elem)
        if len(stor_elems) != 1:
            return None
        # TODO(efried): parent_entry not needed once VIOS has pg83 in Events
        parent_entry = getattr(self, 'parent_entry', None)
        # The storage element may be any one of VDisk, VOptMedia, PV, or LU.
        # Allow ElementWrapper to detect (from the registry) and wrap correctly
        return ewrap.ElementWrapper.wrap(stor_elems[0],
                                         parent_entry=parent_entry)

    def _backing_storage(self, stg):
        """Sets the backing storage of this mapping to a VDisk, VOpt, LU or PV.

        :param stg: Either a VDisk, VOpt, LU or PV wrapper representing the
                    backing storage to assign.
        """
        # Always replace.  Because while the storage has one element, it can't
        # inject properly if the backing type changes (ex. cloning from vOpt to
        # vDisk).
        stor_elem = ent.Element(_MAP_STORAGE, self.adapter, attrib={},
                                children=[])
        stor_elem.inject(stg.element)
        self.inject(stor_elem)

    @property
    def target_dev(self):
        """The target device associated with the backing storage.

        May be any of {storage_type}TargetDev for {storage_type} in VDisk,
        VOpt, LU or PV.
        """
        elem = self.element.find(_MAP_TARGET_DEV)
        if elem is None:
            return None
        # If the virtual target device exists, it comprises a single child of
        # elem.  But the exact type is unknown.
        vtd_elems = list(elem)
        if len(vtd_elems) != 1:
            return None
        # Let ElementWrapper.wrap figure out (from the registry) the
        # appropriate return type.
        return ewrap.ElementWrapper.wrap(vtd_elems[0])

    def _target_dev(self, vtd):
        """Sets the target device of this mapping.

        :param vtd: A {storage_type}TargetDev ElementWrapper representing the
                    virtual target device to assign.
        """
        vtd_elem = ent.Element(_MAP_TARGET_DEV, self.adapter, attrib={},
                               children=[])
        vtd_elem.inject(vtd.element)
        self.inject(vtd_elem)


@ewrap.ElementWrapper.pvm_type('VirtualSCSIStorageAndTargetDevice',
                               has_metadata=True, child_order=_STDEV_EL_ORDER)
class STDev(_STDevMethods):
    """Mapping backing storage and target device.

    Used as a mixin for VSCSIMapping, and first-class internal Element for
    VSCSIBus.
    """
    @classmethod
    def bld(cls, adapter, stg_ref, lua=None):
        """Build a new STDev - only to be used with VSCSIBus.

        :param adapter: The pypowervm Adapter that will be used to create the
                        mapping.
        :param stg_ref: The backing storage element (PV, LU, VDisk, or
                        VOptMedia) to use in the new mapping.
        :param lua: (Optional.  Default: None) Logical Unit Address to set on
                    the TargetDevice.  If None, the LUA will be assigned by the
                    server.  Should be specified for all of the VSCSIMappings
                    for a particular bus, or none of them.
        :return: The newly-created STDev.
        """
        stdev = super(STDev, cls)._bld(adapter)
        stdev._set_stg_and_tgt(adapter, stg_ref, lua=lua)
        return stdev


@ewrap.ElementWrapper.pvm_type('VirtualSCSIMapping', has_metadata=True,
                               child_order=_MAP_ORDER)
class VSCSIMapping(VStorageMapping, _STDevMethods):
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
    _client_adapter_cls = stor.VSCSIClientAdapterElement
    _server_adapter_cls = stor.VSCSIServerAdapterElement

    @classmethod
    def bld(cls, adapter, host_uuid, client_lpar_uuid, stg_ref,
            lpar_slot_num=None, lua=None, target_name=None):
        """Creates a new VSCSIMapping

        :param adapter: The pypowervm Adapter that will be used to create the
                        mapping.
        :param host_uuid: The host system's UUID.
        :param client_lpar_uuid: The client LPAR's UUID.
        :param stg_ref: The backing storage element (PV, LU, VDisk, or
                        VOptMedia) to use in the new mapping.
        :param lpar_slot_num: (Optional, Default: None) The client slot number
                              to use in the new mapping. If None then we let
                              REST choose the slot number.
        :param lua: (Optional.  Default: None) Logical Unit Address to set on
                    the TargetDevice.  If None, the LUA will be assigned by the
                    server.  Should be specified for all of the VSCSIMappings
                    for a particular bus, or none of them.
        :param target_name: (Optional, Default: None) Name of the TargetDevice
                            If None, the target_name will be assigned by the
                            server.
        :return: The newly-created VSCSIMapping.
        """
        s_map = super(VSCSIMapping, cls)._bld(adapter)
        # Create the 'Associated Logical Partition' element of the mapping.
        s_map._client_lpar_href(
            cls.crt_related_href(adapter, host_uuid, client_lpar_uuid))
        s_map._client_adapter(stor.VClientStorageAdapterElement.bld(
            adapter, slot_num=lpar_slot_num))
        s_map._server_adapter(stor.VServerStorageAdapterElement.bld(adapter))
        s_map._set_stg_and_tgt(adapter, stg_ref, lua=lua,
                               target_name=target_name)
        return s_map

    @classmethod
    def bld_from_existing(cls, existing_map, stg_ref, lpar_slot_num=None,
                          lua=None, target_name=None):
        """Clones the existing mapping, but swaps in the new storage elem.

        :param existing_map: The existing VSCSIMapping to clone.
        :param stg_ref: The backing storage element (PV, LU, VDisk, or
                        VOptMedia) to use in the new mapping.  If explicitly
                        None, the new mapping is created with no storage.
        :param lpar_slot_num: (Optional, Default: None) The client slot number
                              to use in the mapping. If None then the
                              existing slot number is used.
        :param lua: (Optional.  Default: None) Logical Unit Address to set on
                    the TargetDevice.  If None, the LUA will be assigned by the
                    server.  Should be specified for all of the VSCSIMappings
                    for a particular bus, or none of them.
        :param target_name: (Optional, Default: None) Name of the TargetDevice
                            If None, the target_name will be assigned by the
                            server.
        :return: The newly-created VSCSIMapping.
        """
        # We do NOT want the source's TargetDevice element, so we explicitly
        # copy the pieces we want from the original mapping.
        new_map = super(VSCSIMapping, cls)._bld(existing_map.adapter)
        if existing_map.client_lpar_href is not None:
            new_map._client_lpar_href(existing_map.client_lpar_href)
        if existing_map.client_adapter is not None:
            new_map._client_adapter(copy.deepcopy(existing_map.client_adapter))
        if existing_map.server_adapter is not None:
            new_map._server_adapter(copy.deepcopy(existing_map.server_adapter))
        if stg_ref is not None:
            new_map._backing_storage(copy.deepcopy(stg_ref))
        if lpar_slot_num is not None:
            # Set the slot number and remove the 'UseNextAvailableSlot' tag.
            new_map.client_adapter._lpar_slot_num(lpar_slot_num)
            new_map.client_adapter._use_next_slot(False)
        if any((lua, target_name)):
            if stg_ref is None:
                raise ValueError(_("Can't specify target device LUA without a "
                                   "backing storage device!"))
            # Build a *TargetDev of the appropriate type for this stg_ref
            new_map._target_dev(stg_ref.target_dev_type.bld(
                existing_map.adapter, lua, target_name))
        return new_map


@ewrap.EntryWrapper.pvm_type('VirtualSCSIBus', child_order=_BUS_EL_ORDER)
class VSCSIBus(ewrap.EntryWrapper, VStorageMapping):
    """Virtual SCSI Bus, first-class CHILD of VirtualIOServer.

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
    _client_adapter_cls = stor.VSCSIClientAdapterElement
    _server_adapter_cls = stor.VSCSIServerAdapterElement

    @classmethod
    def bld(cls, adapter, client_lpar_uuid, lpar_slot_num=None):
        """Creates a new VSCSIBus with no storage.

        Storage should be added afterwards by modifying stg_targets.

        :param adapter: The pypowervm Adapter that will be used to create the
                        bus.
        :param client_lpar_uuid: The client LPAR's UUID.
        :param lpar_slot_num: (Optional, Default: None) The client slot number
                              to use in the new mapping. If None then we let
                              REST choose the slot number.
        :return: The newly-created VSCSIBus.
        """
        s_bus = super(VSCSIBus, cls)._bld(adapter)
        # Create the 'Associated Logical Partition' element of the mapping.
        s_bus._client_lpar_href(adapter.build_href(lpar.LPAR.schema_type,
                                                   client_lpar_uuid, xag=[]))
        s_bus._client_adapter(stor.VClientStorageAdapterElement.bld(
            adapter, slot_num=lpar_slot_num))
        s_bus._server_adapter(stor.VServerStorageAdapterElement.bld(adapter))
        return s_bus

    @classmethod
    def bld_from_existing(cls, existing_bus):
        """Clones a bus's LPAR and client/server adapters, but not storage.

        :param existing_bus: The existing VSCSIBus to clone.
        :return: The newly-created VSCSIBus.
        """
        # We do NOT want the source's storage, so we explicitly copy the pieces
        # we want from the original bus.
        new_bus = super(VSCSIBus, cls)._bld(existing_bus.adapter)
        if existing_bus.client_lpar_href is not None:
            new_bus._client_lpar_href(existing_bus.client_lpar_href)
        if existing_bus.client_adapter is not None:
            new_bus._client_adapter(copy.deepcopy(existing_bus.client_adapter))
        if existing_bus.server_adapter is not None:
            new_bus._server_adapter(copy.deepcopy(existing_bus.server_adapter))
        return new_bus

    @property
    def mappings(self):
        return ewrap.WrapperElemList(self._find_or_seed(
            _BUS_ASSOC_MAPS), STDev)

    @mappings.setter
    def mappings(self, stdevs):
        self.replace_list(_BUS_ASSOC_MAPS, stdevs)


@ewrap.ElementWrapper.pvm_type('VirtualFibreChannelMapping', has_metadata=True,
                               child_order=_VFC_MAP_ORDER)
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

    _client_adapter_cls = stor.VFCClientAdapterElement
    _server_adapter_cls = stor.VFCServerAdapterElement

    @classmethod
    def bld(cls, adapter, host_uuid, client_lpar_uuid, backing_phy_port,
            client_wwpns=None, lpar_slot_num=None):
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
        :param lpar_slot_num: An optional integer to be used as the Virtual
                              slot number on the client adapter
        :returns: The new VFCMapping Wrapper.
        """
        s_map = super(VFCMapping, cls)._bld(adapter)
        # Create the 'Associated Logical Partition' element of the mapping.
        s_map._client_lpar_href(
            cls.crt_related_href(adapter, host_uuid, client_lpar_uuid))
        s_map._client_adapter(stor.VFCClientAdapterElement.bld(
            adapter, wwpns=client_wwpns, slot_num=lpar_slot_num))

        # Create the backing port with required 'Port' tag.
        s_map.backing_port = bp.PhysFCPort.bld_ref(adapter, backing_phy_port,
                                                   ref_tag='Port')

        s_map._server_adapter(stor.VFCServerAdapterElement.bld(adapter))
        return s_map

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

    @backing_port.setter
    def backing_port(self, value):
        """Sets the backing port."""
        elem = self._find_or_seed(_MAP_PORT)
        self.element.replace(elem, value.element)
