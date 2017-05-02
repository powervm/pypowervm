# Copyright 2014, 2017 IBM Corp.
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

"""Wrappers for virtual storage elements and adapters."""

import abc
import base64
import binascii
from oslo_log import log as logging
import six

import pypowervm.const as c
import pypowervm.exceptions as ex
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

UDID = 'UniqueDeviceID'

# Virtual Disk Constants
DISK_ROOT = 'VirtualDisk'
_DISK_CAPACITY = 'DiskCapacity'
_DISK_LABEL = 'DiskLabel'
DISK_NAME = 'DiskName'
_DISK_MAX_LOGICAL_VOLS = 'MaxLogicalVolumes'
_DISK_PART_SIZE = 'PartitionSize'
_DISK_VG = 'VolumeGroup'
_DISK_BASE = 'BaseImage'
_DISK_UDID = UDID
_DISK_TYPE = 'VirtualDiskType'
_DISK_BACKSTORE_TYPE = 'BackStoreType'
_DISK_FILEFORMAT = 'FileFormat'
_DISK_OPTIONAL_PARMS = 'OptionalParameters'
_VDISK_EL_ORDER = [_DISK_CAPACITY, _DISK_LABEL, DISK_NAME,
                   _DISK_MAX_LOGICAL_VOLS, _DISK_PART_SIZE, _DISK_VG,
                   _DISK_BASE, _DISK_UDID, _DISK_TYPE, _DISK_BACKSTORE_TYPE,
                   _DISK_FILEFORMAT, _DISK_OPTIONAL_PARMS]


class VDiskType(object):
    """From VirtualDiskType.Enum."""
    FILE = 'File'
    LV = 'LogicalVolume'


class BackStoreType(object):
    """From BackStoreType.Enum."""
    # A kernel-space handler that supports raw files.
    FILE_IO = 'fileio'
    # A user-space handler that supports RAW, QCOW or QCOW2 files.
    USER_QCOW = 'user:qcow'


class FileFormatType(object):
    """From FileFormatType.Enum"""
    RAW = 'raw'
    QCOW2 = 'qcow2'

# Physical Volume Constants
PVS = 'PhysicalVolumes'
PHYS_VOL = 'PhysicalVolume'
_PV_AVAIL_PHYS_PART = 'AvailablePhysicalPartitions'
_PV_VOL_DESC = 'Description'
_PV_LOC_CODE = 'LocationCode'
_PV_PERSISTENT_RESERVE = 'PersistentReserveKeyValue'
_PV_RES_POLICY = 'ReservePolicy'
_PV_RES_POLICY_ALGO = 'ReservePolicyAlgorithm'
_PV_TOTAL_PHYS_PARTS = 'TotalPhysicalPartitions'
_PV_UDID = UDID
_PV_AVAIL_FOR_USE = 'AvailableForUsage'
_PV_VOL_SIZE = 'VolumeCapacity'
_PV_VOL_NAME = 'VolumeName'
_PV_VOL_STATE = 'VolumeState'
_PV_VOL_UNIQUE_ID = 'VolumeUniqueID'
_PV_FC_BACKED = 'IsFibreChannelBacked'
_PV_STG_LABEL = 'StorageLabel'
_PV_PG83 = 'DescriptorPage83'
_PV_EL_ORDER = [_PV_AVAIL_PHYS_PART, _PV_VOL_DESC, _PV_LOC_CODE,
                _PV_PERSISTENT_RESERVE, _PV_RES_POLICY, _PV_RES_POLICY_ALGO,
                _PV_TOTAL_PHYS_PARTS, _PV_UDID, _PV_AVAIL_FOR_USE,
                _PV_VOL_SIZE, _PV_VOL_NAME, _PV_VOL_STATE, _PV_VOL_UNIQUE_ID,
                _PV_FC_BACKED, _PV_STG_LABEL, _PV_PG83]

# Virtual Optical Media Constants
VOPT_ROOT = 'VirtualOpticalMedia'
VOPT_NAME = 'MediaName'
_VOPT_SIZE = 'Size'
_VOPT_UDID = 'MediaUDID'
_VOPT_MOUNT_TYPE = 'MountType'
_VOPT_EL_ORDER = [VOPT_NAME, _VOPT_UDID, _VOPT_MOUNT_TYPE, _VOPT_SIZE]

# Virtual Media Repository Constants
_VREPO_ROOT = 'VirtualMediaRepository'
_VREPO_OPTICAL_MEDIA_ROOT = 'OpticalMedia'
_VREPO_NAME = 'RepositoryName'
_VREPO_SIZE = 'RepositorySize'
_VREPO_EL_ORDER = [_VREPO_OPTICAL_MEDIA_ROOT, _VREPO_NAME, _VREPO_SIZE]

# Volume Group Constants
_VG_AVAILABLE_SIZE = 'AvailableSize'
_VG_BACKING_DEVICE_COUNT = 'BackingDeviceCount'
_VG_FREE_SPACE = 'FreeSpace'
_VG_CAPACITY = 'GroupCapacity'
_VG_NAME = 'GroupName'
_VG_SERIAL_ID = 'GroupSerialID'
_VG_STATE = 'GroupState'
_VG_MAX_LVS = 'MaximumLogicalVolumes'
_VG_MEDIA_REPOS = 'MediaRepositories'
_VG_MIN_ALLOC_SIZE = 'MinimumAllocationSize'
_VG_PHS_VOLS = PVS
_VG_UDID = UDID
_VG_VDISKS = 'VirtualDisks'
_VG_EL_ORDER = (_VG_AVAILABLE_SIZE, _VG_BACKING_DEVICE_COUNT, _VG_FREE_SPACE,
                _VG_CAPACITY, _VG_NAME, _VG_SERIAL_ID, _VG_STATE, _VG_MAX_LVS,
                _VG_MEDIA_REPOS, _VG_MIN_ALLOC_SIZE, _VG_PHS_VOLS, _VG_UDID,
                _VG_VDISKS)

# LogicalUnit Constants
_LU_THIN = 'ThinDevice'
_LU_UDID = UDID
_LU_CAPACITY = 'UnitCapacity'
_LU_TYPE = 'LogicalUnitType'
_LU_CLONED_FROM = 'ClonedFrom'
_LU_IN_USE = 'InUse'
_LU_NAME = 'UnitName'
_LU_EL_ORDER = (_LU_THIN, _LU_UDID, _LU_CAPACITY, _LU_TYPE, _LU_CLONED_FROM,
                _LU_IN_USE, _LU_NAME)


class LUType(object):
    DISK = "VirtualIO_Disk"
    HIBERNATION = "VirtualIO_Hibernation"
    IMAGE = "VirtualIO_Image"
    AMS = "VirtualIO_Active_Memory_Sharing"

_CAPACITY = 'Capacity'

# Tier Constants
_TIER_NAME = 'Name'
_TIER_UDID = UDID
_TIER_IS_DEFAULT = 'IsDefault'
_TIER_CAPACITY = _CAPACITY
_TIER_ASSOC_SSP = 'AssociatedSharedStoragePool'

# Shared Storage Pool Constants
_SSP_NAME = 'StoragePoolName'
_SSP_UDID = UDID
_SSP_CAPACITY = _CAPACITY
_SSP_FREE_SPACE = 'FreeSpace'
_SSP_TOTAL_LU_SIZE = 'TotalLogicalUnitSize'
_SSP_LUS = 'LogicalUnits'
_SSP_LU = 'LogicalUnit'
_SSP_OCS = 'OverCommitSpace'
_SSP_PVS = PVS
_SSP_PV = PHYS_VOL

# Virtual Adapter Constants
CLIENT_ADPT = 'ClientAdapter'
SERVER_ADPT = 'ServerAdapter'

# Common to all Virtual Adapters
_VADPT_TYPE = 'AdapterType'
_VADPT_DRC_NAME = 'DynamicReconfigurationConnectorName'
_VADPT_LOC_CODE = 'LocationCode'
_VADPT_LOCAL_ID = 'LocalPartitionID'
_VADPT_REQD = 'RequiredAdapter'
_VADPT_VARIED_ON = 'VariedOn'
_VADPT_NEXT_SLOT = 'UseNextAvailableSlotID'
_VADPT_NEXT_HI_SLOT = 'UseNextAvailableHighSlotID'
_VADPT_SLOT_NUM = 'VirtualSlotNumber'
_VADPT_ENABLED = 'Enabled'
_VADPT_NAME = 'AdapterName'
_VADPT_UDID = 'UniqueDeviceID'

# Common to VSCSI Adapters (Client & Server)
_VSCSI_ADPT_BACK_DEV_NAME = 'BackingDeviceName'
_VSCSI_ADPT_REM_BACK_DEV_NAME = 'RemoteBackingDeviceName'
_VSCSI_ADPT_REM_LPAR_ID = 'RemoteLogicalPartitionID'
_VSCSI_ADPT_REM_SLOT_NUM = 'RemoteSlotNumber'
_VSCSI_ADPT_SVR_LOC_CODE = 'ServerLocationCode'

# Common to Client Adapters
_VCLNT_ADPT_SVR_ADPT = SERVER_ADPT

# Common to VFC Adapters (Client & Server)
_VFC_ADPT_CONN_PARTITION = 'ConnectingPartition'
_VFC_ADPT_CONN_PARTITION_ID = 'ConnectingPartitionID'
_VFC_ADPT_CONN_SLOT_NUM = 'ConnectingVirtualSlotNumber'

# VFC Server Adapter-specific
_VFC_SVR_ADPT_MAP_PORT = 'MapPort'
_VFC_SVR_ADPT_PHYS_PORT = 'PhysicalPort'

# VFC Client Adapter-specific
_VFC_CLNT_ADPT_WWPNS = 'WWPNs'
_VFC_CLNT_ADPT_LOGGED_IN = 'NportLoggedInStatus'
_VFC_CLNT_ADPT_OS_DISKS = 'OperatingSystemDisks'

# Element Ordering:
#
# A <ServerAdapter/> might be a VSCSI server adapter or a VFC server adapter.
# Likewise <ClientAdapter/>.  The schema inheritance hierarchy informs the
# way we build up the element order constants:
#
#                            VirtualIOAdapter
#                   VFCAdapter             VSCSIAdapter == VSCSIServerAdapter
#      VFCClientAdapter  VFCServerAdapter        VSCSIClientAdapter
#
# However, this doesn't match up with the hierarchy of our wrapper classes:
#
#               VClientStorageAdapterElement
# VSCSIClientAdapterElement    VFCClientAdapterElement
#
#               VServerStorageAdapterElement
# VSCSIServerAdapterElement    VFCServerAdapterElement
#
# So we have to get creative with element ordering for the base classes, since
# they hold the @pvm_type decorator.  We interleave the VSCSI and VFC
# properties to create an element order that can be used commonly for both
# types.  This only works because all overlapping properties happen to be in
# the same order.
#
# Yes, this is funky.

# Converged ordering base for VFC and VSCSI adapters
_VADPT_BASE_EL_ORDER = (
    _VADPT_TYPE, _VADPT_DRC_NAME, _VADPT_LOC_CODE, _VADPT_LOCAL_ID,
    _VADPT_REQD, _VADPT_VARIED_ON, _VADPT_NEXT_SLOT, _VADPT_NEXT_HI_SLOT,
    _VADPT_SLOT_NUM, _VADPT_ENABLED, _VADPT_NAME, _VSCSI_ADPT_BACK_DEV_NAME,
    _VSCSI_ADPT_REM_BACK_DEV_NAME, _VSCSI_ADPT_REM_LPAR_ID,
    _VFC_ADPT_CONN_PARTITION, _VFC_ADPT_CONN_PARTITION_ID,
    _VSCSI_ADPT_REM_SLOT_NUM, _VFC_ADPT_CONN_SLOT_NUM,
    _VSCSI_ADPT_SVR_LOC_CODE, _VADPT_UDID)

# Converged (VSCSI & VFC) Server Adapter element order
_V_SVR_ADPT_EL_ORDER = _VADPT_BASE_EL_ORDER + (
    _VFC_SVR_ADPT_MAP_PORT, _VFC_SVR_ADPT_PHYS_PORT)

# Converged (VSCSI & VFC) Client Adapter element order
_V_CLNT_ADPT_EL_ORDER = _VADPT_BASE_EL_ORDER + (
    _VCLNT_ADPT_SVR_ADPT, _VFC_CLNT_ADPT_WWPNS, _VFC_CLNT_ADPT_LOGGED_IN,
    _VFC_CLNT_ADPT_OS_DISKS)

VFC_CLIENT_ADPT = 'VirtualFibreChannelClientAdapter'

# TargetDevice Constants
_TD_LU_TD = 'SharedStoragePoolLogicalUnitVirtualTargetDevice'
_TD_PV_TD = 'PhysicalVolumeVirtualTargetDevice'
_TD_VOPT_TD = 'VirtualOpticalTargetDevice'
_TD_VDISK_TD = 'LogicalVolumeVirtualTargetDevice'
_TD_LUA = 'LogicalUnitAddress'
_TD_NAME = 'TargetName'


@ewrap.EntryWrapper.pvm_type('VolumeGroup', child_order=_VG_EL_ORDER)
class VG(ewrap.EntryWrapper):
    """Represents a Volume Group that resides on the Virtual I/O Server."""

    @classmethod
    def bld(cls, adapter, name, pv_list):
        vg = super(VG, cls)._bld(adapter)
        vg.name = name
        vg.phys_vols = pv_list
        return vg

    @property
    def name(self):
        return self._get_val_str(_VG_NAME)

    @name.setter
    def name(self, val):
        self.set_parm_value(_VG_NAME, val)

    @property
    def capacity(self):
        """Overall capacity in GB (float)."""
        return self._get_val_float(_VG_CAPACITY)

    @property
    def available_size(self):
        """Available size for new volumes in GB (float)."""
        return self._get_val_float(_VG_AVAILABLE_SIZE)

    @property
    def free_space(self):
        """Current free space in GB (float)."""
        return self._get_val_float(_VG_FREE_SPACE)

    @property
    def serial_id(self):
        return self._get_val_str(_VG_SERIAL_ID)

    @property
    def vmedia_repos(self):
        """Returns a list of  wrappers."""
        es = ewrap.WrapperElemList(self._find_or_seed(_VG_MEDIA_REPOS),
                                   VMediaRepos)
        return es

    @vmedia_repos.setter
    def vmedia_repos(self, repos):
        """Replaces the VirtualMediaRepositories with the new value.

        :param repos: A list of VMediaRepos objects that will
                      replace the existing repositories.
        """
        self.replace_list(_VG_MEDIA_REPOS, repos)

    @property
    def phys_vols(self):
        """Returns a list of the Physical Volumes that back this repo."""
        # TODO(efried): parent_entry=self not needed once VIOS supports pg83
        # descriptor in Events
        es = ewrap.WrapperElemList(self._find_or_seed(_VG_PHS_VOLS), PV,
                                   parent_entry=self)
        return es

    @phys_vols.setter
    def phys_vols(self, phys_vols):
        """Replaces the physical volumes with the new value.

        :param phys_vols: A list of PV objects that will replace
                          the existing Physcial Volumes.
        """
        self.replace_list(_VG_PHS_VOLS, phys_vols)

    @property
    def virtual_disks(self):
        """Returns a list of the Virtual Disks that are in the repo."""
        es = ewrap.WrapperElemList(self._find_or_seed(_VG_VDISKS), VDisk)
        return es

    @virtual_disks.setter
    def virtual_disks(self, virt_disks):
        """Replaces the virtual disks with the new value.

        :param virt_disks: A list of VDisk objects that will replace
                           the existing Virtual Disks.
        """
        self.replace_list(_VG_VDISKS, virt_disks)


@ewrap.ElementWrapper.pvm_type(_VREPO_ROOT, has_metadata=True,
                               child_order=_VREPO_EL_ORDER)
class VMediaRepos(ewrap.ElementWrapper):
    """A Virtual Media Repository for a VIOS.

    Typically used to store an ISO file for image building.
    """

    @classmethod
    def bld(cls, adapter, name, size):
        """Creates a fresh VMediaRepos wrapper.

        This should be used when adding a new Virtual Media Repository to a
        Volume Group.  The name and size for the media repository is required.
        The other attributes are generated from the system.

        Additionally, once created, specific VirtualOpticalMedia can be added
        onto the object.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name of the Virtual Media Repository.
        :param size: The size of the repository in GB (float).
        :returns: A VMediaRepos wrapper that can be used for create.
        """
        vmr = super(VMediaRepos, cls)._bld(adapter)
        vmr._name(name)
        vmr._size(size)
        return vmr

    @property
    def optical_media(self):
        """Returns a list of the VirtualOpticalMedia devices in the repo."""
        seed = self._find_or_seed(_VREPO_OPTICAL_MEDIA_ROOT)
        return ewrap.WrapperElemList(seed, VOptMedia)

    @optical_media.setter
    def optical_media(self, new_media):
        """Sets the list of VirtualOpticalMedia devices in the repo.

        :param new_media: The list of new VOptMedia.
        """
        self.replace_list(_VREPO_OPTICAL_MEDIA_ROOT, new_media)

    @property
    def name(self):
        return self._get_val_str(_VREPO_NAME)

    def _name(self, new_name):
        self.set_parm_value(_VREPO_NAME, new_name)

    @property
    def size(self):
        """Returns the size in GB (float)."""
        return self._get_val_float(_VREPO_SIZE)

    def _size(self, new_size):
        self.set_float_gb_value(_VREPO_SIZE, new_size)


@six.add_metaclass(abc.ABCMeta)
@ewrap.Wrapper.base_pvm_type
class _VTargetDevMethods(ewrap.Wrapper):
    """Base class for {storage_type}TargetDevice of an active VSCSIMapping."""

    @classmethod
    def bld(cls, adapter, lua=None, name=None):
        """Build a new Virtual Target Device.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param lua: (Optional, Default None) Logical Unit Address string to
                    assign to the new VTD.
        :param name: (Optional, Default None) Name of the TargetDev. If None
                     name will be assigned by the server
        :return: A new {storage_type}TargetDev, where {storage_type} is
                 appropriate to the subclass.
        """
        vtd = super(_VTargetDevMethods, cls)._bld(adapter)
        if lua is not None:
            vtd._lua(lua)
        if name is not None:
            vtd._name(name)
        return vtd

    @property
    def lua(self):
        """Logical Unit Address of the target device."""
        return self._get_val_str(_TD_LUA)

    def _lua(self, val):
        """Set the Logical Unit Address of this target device."""
        self.set_parm_value(_TD_LUA, val)

    @property
    def name(self):
        """Target Name of the device"""
        return self._get_val_str(_TD_NAME)

    def _name(self, val):
        """Set the Target Name of the device"""
        self.set_parm_value(_TD_NAME, val)


@ewrap.ElementWrapper.pvm_type(_TD_LU_TD, has_metadata=True)
class LUTargetDev(_VTargetDevMethods, ewrap.ElementWrapper):
    """SSP Logical Unit Virtual Target Device for a VSCSIMapping."""
    pass


@ewrap.ElementWrapper.pvm_type(_TD_PV_TD, has_metadata=True)
class PVTargetDev(_VTargetDevMethods, ewrap.ElementWrapper):
    """Physical Volume Virtual Target Device for a VSCSIMapping."""
    pass


@ewrap.ElementWrapper.pvm_type(_TD_VDISK_TD, has_metadata=True)
class VDiskTargetDev(_VTargetDevMethods, ewrap.ElementWrapper):
    """Virtual Disk (Logical Volume) Target Device for a VSCSIMapping."""
    pass


@ewrap.ElementWrapper.pvm_type(_TD_VOPT_TD, has_metadata=True)
class VOptTargetDev(_VTargetDevMethods, ewrap.ElementWrapper):
    """Virtual Optical Media Target Device for a VSCSIMapping."""
    pass


@ewrap.ElementWrapper.pvm_type(VOPT_ROOT, has_metadata=True,
                               child_order=_VOPT_EL_ORDER)
class VOptMedia(ewrap.ElementWrapper):
    """A virtual optical piece of media."""
    target_dev_type = VOptTargetDev

    @classmethod
    def bld(cls, adapter, name, size=None, mount_type='rw'):
        """Creates a fresh VOptMedia wrapper.

        This should be used when adding a new VirtualOpticalMedia device to a
        VirtualMediaRepository.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The device name.
        :param size: The device size in GB, decimal precision.
        :param mount_type: The type of mount.  Defaults to RW.  Can be set to R
        :returns: A VOptMedia wrapper that can be used for create.
        """
        vom = super(VOptMedia, cls)._bld(adapter)
        vom._media_name(name)
        if size is not None:
            vom._size(size)
        vom._mount_type(mount_type)
        return vom

    @classmethod
    def bld_ref(cls, adapter, name):
        """Creates a VOptMedia wrapper for referencing an existing VOpt."""
        vom = super(VOptMedia, cls)._bld(adapter)
        vom._media_name(name)
        return vom

    @property
    def media_name(self):
        return self._get_val_str(VOPT_NAME)

    @property
    def name(self):
        """Same as media_name - for consistency with other storage types."""
        return self.media_name

    def _media_name(self, new_name):
        self.set_parm_value(VOPT_NAME, new_name)

    @property
    def size(self):
        """Size is a float represented in GB."""
        return self._get_val_float(_VOPT_SIZE)

    def _size(self, new_size):
        self.set_float_gb_value(_VOPT_SIZE, new_size)

    @property
    def udid(self):
        return self._get_val_str(_VOPT_UDID)

    @property
    def mount_type(self):
        return self._get_val_str(_VOPT_MOUNT_TYPE)

    def _mount_type(self, new_mount_type):
        self.set_parm_value(_VOPT_MOUNT_TYPE, new_mount_type)


@ewrap.ElementWrapper.pvm_type(PHYS_VOL, has_metadata=True,
                               child_order=_PV_EL_ORDER)
class PV(ewrap.ElementWrapper):
    """A physical volume that backs a Volume Group."""
    target_dev_type = PVTargetDev

    @classmethod
    def bld(cls, adapter, name, udid=None):
        """Creates the a fresh PV wrapper.

        This should be used when wishing to add physical volumes to a Volume
        Group.  Only the name is required.  The other attributes are generated
        from the system.

        The name matches the device name on the system.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name of the physical volume on the Virtual I/O Server
                     to add to the Volume Group.  Ex. 'hdisk1'.
        :param udid: Universal Disk Identifier.
        :returns: An Element that can be used for a PhysicalVolume create.
        """
        pv = super(PV, cls)._bld(adapter)
        # Assignment order is significant
        if udid:
            pv.udid = udid
        pv.name = name
        return pv

    @property
    def udid(self):
        """The unique device id."""
        return self._get_val_str(_PV_UDID)

    @udid.setter
    def udid(self, new_udid):
        self.set_parm_value(_PV_UDID, new_udid)

    @property
    def capacity(self):
        """Returns the capacity as an int in MB."""
        return self._get_val_int(_PV_VOL_SIZE)

    @property
    def name(self):
        return self._get_val_str(_PV_VOL_NAME)

    @name.setter
    def name(self, newname):
        self.set_parm_value(_PV_VOL_NAME, newname)

    @property
    def state(self):
        return self._get_val_str(_PV_VOL_STATE)

    @property
    def is_fc_backed(self):
        return self._get_val_bool(_PV_FC_BACKED)

    @property
    def description(self):
        return self._get_val_str(_PV_VOL_DESC)

    @property
    def loc_code(self):
        return self._get_val_str(_PV_LOC_CODE)

    @property
    def avail_for_use(self):
        return self._get_val_bool(_PV_AVAIL_FOR_USE)

    @property
    def pg83(self):
        encoded = self._get_val_str(_PV_PG83)
        # TODO(efried): Temporary workaround until VIOS supports pg83 in Events
        # >>>CUT HERE>>>
        if not encoded:
            # The PhysicalVolume XML doesn't contain the DescriptorPage83
            # property.  (This could be because the disk really doesn't have
            # this attribute; but if the caller is asking for pg83, they likely
            # expect that it should.)  More likely, it is because their VIOS is
            # running at a level which supplies this datum in a fresh inventory
            # query, but not in a PV ADD Event.  In that case, use the
            # LUARecovery Job to perform the fresh inventory query to retrieve
            # this value.  Since this is expensive, we cache the value.
            if not hasattr(self, '_pg83_encoded'):
                # Get the VIOS UUID from the parent_entry of this PV.  Raise if
                # it doesn't exist.
                if not hasattr(self, 'parent_entry') or not self.parent_entry:
                    raise ex.UnableToBuildPG83EncodingMissingParent(
                        dev_name=self.name)
                # The parent_entry is either a VG or a VIOS.  If a VG, it is a
                # child of the owning VIOS, so pull out the ROOT UUID of its
                # href. If a VIOS, we can't count on the href being a root URI,
                # so pull the target UUID regardless.
                use_root_uuid = isinstance(self.parent_entry, VG)
                vio_uuid = u.get_req_path_uuid(
                    self.parent_entry.href, preserve_case=True,
                    root=use_root_uuid)

                # Local import to prevent circular dependency
                from pypowervm.tasks import hdisk
                # Cache the encoded value for performance
                self._pg83_encoded = hdisk.get_pg83_via_job(
                    self.adapter, vio_uuid, self.udid)
            encoded = self._pg83_encoded
        # <<<CUT HERE<<<
        try:
            return base64.b64decode(encoded).decode(
                'utf-8') if encoded else None
        except (TypeError, binascii.Error) as te:
            LOG.warning(_('PV had encoded pg83 descriptor "%(pg83_raw)s", but '
                          'it failed to decode (%(type_error)s).'),
                        {'pg83_raw': encoded, 'type_error': te.args[0]})
        return None


@ewrap.Wrapper.base_pvm_type
class _VDisk(ewrap.ElementWrapper):
    """Methods common to VDisk and FileIO."""

    @property
    def name(self):
        return self._get_val_str(DISK_NAME)

    @name.setter
    def name(self, name):
        self.set_parm_value(DISK_NAME, name)

    @property
    def label(self):
        return self._get_val_str(_DISK_LABEL)

    def _label(self, new_label):
        self.set_parm_value(_DISK_LABEL, new_label)

    @property
    def capacity(self):
        """Returns the capacity in GB (float)."""
        return self._get_val_float(_DISK_CAPACITY)

    @capacity.setter
    def capacity(self, capacity):
        self.set_float_gb_value(_DISK_CAPACITY, capacity)

    @property
    def udid(self):
        return self._get_val_str(_DISK_UDID)

    @property
    def vdtype(self):
        return self._get_val_str(_DISK_TYPE)

    def _vdtype(self, val):
        self.set_parm_value(_DISK_TYPE, val, attrib=c.ATTR_KSV150)

    def _base_image(self, base_image):
        self.set_parm_value(_DISK_BASE, base_image)

    @property
    def backstore_type(self):
        """The backing store type, one of the BackStoreType enum values."""
        return self._get_val_str(_DISK_BACKSTORE_TYPE)

    def _backstore_type(self, val):
        """Set the backing store type.

        :param val: One of the BackStoreType enum values.
        """
        self.set_parm_value(_DISK_BACKSTORE_TYPE, val, attrib=c.ATTR_KSV150)

    @property
    def file_format(self):
        """File format to be used, one of the FileFormatType enum values."""
        return self._get_val_str(_DISK_FILEFORMAT)

    def _file_format(self, val):
        """Set the file format.

        :param val: One of the FileFormatType enum values.
        """
        self.set_parm_value(_DISK_FILEFORMAT, val, attrib=c.ATTR_KSV150)


@ewrap.ElementWrapper.pvm_type(DISK_ROOT, has_metadata=True,
                               child_order=_VDISK_EL_ORDER)
class FileIO(_VDisk):
    """A special case of VirtualDisk representing a File I/O object.

    Do not PUT (.create) this wrapper directly.  Attach it to a VSCSIMapping
    and PUT that instead.
    """
    target_dev_type = VDiskTargetDev

    @classmethod
    def bld_ref(cls, adapter, path, backstore_type=None):
        """Creates a FileIO reference for inclusion in a VSCSIMapping.

        :param adapter: A pypowervm.adapter.Adapter for the REST API.
        :param path: The file system path of the File I/O object.
        :return: An Element that can be attached to a VSCSIMapping to create a
                 File I/O mapping on the server.
        """
        fio = super(FileIO, cls)._bld(adapter)
        fio._label(path)
        fio.name = path
        fio._vdtype(VDiskType.FILE)
        if backstore_type is not None:
            fio._backstore_type(backstore_type)
        return fio

    # Maintained for backward compatibility.  FileIOs aren't created by REST.
    bld = bld_ref

    @property
    def path(self):
        """Alias for 'label'."""
        return self.label


@ewrap.ElementWrapper.pvm_type(DISK_ROOT, has_metadata=True,
                               child_order=_VDISK_EL_ORDER)
class VDisk(_VDisk):
    """A virtual disk that can be attached to a VM."""
    target_dev_type = VDiskTargetDev

    @classmethod
    def bld(cls, adapter, name, capacity, label=None, base_image=None,
            file_format=None):
        """Creates a VDisk Wrapper for creating a new VDisk.

        This should be used when the user wishes to add a new Virtual Disk to
        the Volume Group.  The flow is to use this method to lay out the
        attributes of the new Virtual Disk.  Then add it to the Volume Group's
        virtual disks. Then perform an update of the Volume Group.  The disk
        should be created by the update operation.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name of the virtual disk
        :param capacity: A float number that defines the GB of the disk.
        :param label: The generic label for the disk.  Not required.
        :param base_image: UDID of virtual disk that contains source data
                           Not required.
        :param file_format: (Optional) File format of VDisk.  See
                            FileFormatType enumeration for valid formats.
        :returns: An Element that can be used for a VirtualDisk create.
        """
        vd = super(VDisk, cls)._bld(adapter)
        vd.capacity = capacity
        # Label must be specified; str will make None 'None'.
        vd._label(str(label))
        vd.name = name
        if base_image:
            vd._base_image(base_image)
        if file_format:
            vd._file_format(file_format)
        return vd

    @classmethod
    def bld_ref(cls, adapter, name):
        """Creates a VDisk Wrapper for referring to an existing VDisk."""
        vd = super(VDisk, cls)._bld(adapter)
        vd.name = name
        return vd

    @property
    def vg_uri(self):
        return self.get_href(_DISK_VG, one_result=True)


@six.add_metaclass(abc.ABCMeta)
@ewrap.Wrapper.base_pvm_type
class _LUBase(ewrap.Wrapper):
    """Mixin for a Logical Unit EntryWrapper or ElementWrapper.

    A Logical Unit is either a DETAIL object (within a SharedStoragePool or
    SCSI mapping); or it is a first-class REST CHILD of Tier.  In either case,
    its properties/methods are the same, provided here.
    """
    target_dev_type = LUTargetDev

    @classmethod
    def bld(cls, adapter, name, capacity, thin=None, typ=None, clone=None):
        """Build a fresh wrapper for LU creation within an SSP.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name to assign to the new LogicalUnit
        :param capacity: Capacity in GB for the new LogicalUnit
        :param thin: Provision the new LU as thin (True) or thick (False).
        :param typ: Logical Unit type, one of the LUType values.
        :param clone: If the new LU is to be a linked clone, this param is a
                      LU(Ent) wrapper representing the backing image LU.
        :return: A new LU wrapper suitable for adding to SSP.logical_units
                 prior to update.
        """
        lu = super(_LUBase, cls)._bld(adapter)
        lu._name(name)
        lu._capacity(capacity)
        if thin is not None:
            lu._is_thin(thin)
        if typ is not None:
            lu._lu_type(typ)
        if clone is not None:
            lu._cloned_from_udid(clone.udid)
            # New LU must be at least as big as the backing LU.
            lu._capacity(max(capacity, clone.capacity))
        return lu

    @classmethod
    def bld_ref(cls, adapter, name, udid):
        """Creates the a fresh LU wrapper.

        The name matches the device name on the system.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name of the logical unit on the Virtual I/O Server.
        :param udid: Universal Disk Identifier.
        :returns: An Element that can be used for a PhysicalVolume create.
        """
        lu = super(_LUBase, cls)._bld(adapter)
        lu._name(name)
        lu._udid(udid)
        return lu

    def __eq__(self, other):
        """Name and UDID are sufficient for equality.

        For example, if we change an LU's capacity, it's still the same LU.
        We're counting on UDIDs not being repeated in any reasonable scenario.
        """
        return self.name == other.name and self.udid == other.udid

    def __hash__(self):
        """For comparing sets of LUs."""
        # The contract of hash is that two equal thingies must have the same
        # hash, but two thingies with the same hash are not necessarily equal.
        # The hash is used for assigning keys to hash buckets in a dictionary:
        # if two keys hash the same, their items go into the same bucket, but
        # they're still different items.
        if six.PY3:
            conv = int
        else:
            import __builtin__
            conv = __builtin__.long
        return conv(self.udid[2:], base=16)

    @property
    def name(self):
        return self._get_val_str(_LU_NAME)

    def _name(self, value):
        return self.set_parm_value(_LU_NAME, value)

    @property
    def udid(self):
        return self._get_val_str(_LU_UDID)

    def _udid(self, value):
        self.set_parm_value(_LU_UDID, value)

    @property
    def capacity(self):
        """Float capacity in GB."""
        return self._get_val_float(_LU_CAPACITY)

    def _capacity(self, val):
        """val is float."""
        self.set_float_gb_value(_LU_CAPACITY, val)

    @property
    def lu_type(self):
        """String enum value e.g. "VirtualIO_Disk."""
        return self._get_val_str(_LU_TYPE)

    def _lu_type(self, val):
        self.set_parm_value(_LU_TYPE, val)

    @property
    def is_thin(self):
        return self._get_val_bool(_LU_THIN, default=None)

    def _is_thin(self, val):
        """val is boolean."""
        self.set_parm_value(_LU_THIN, u.sanitize_bool_for_api(val))

    @property
    def cloned_from_udid(self):
        return self._get_val_str(_LU_CLONED_FROM)

    def _cloned_from_udid(self, val):
        self.set_parm_value(_LU_CLONED_FROM, val)

    @property
    def in_use(self):
        return self._get_val_bool(_LU_IN_USE, default=None)


@ewrap.ElementWrapper.pvm_type('LogicalUnit', has_metadata=True,
                               child_order=_LU_EL_ORDER)
class LU(_LUBase, ewrap.ElementWrapper):
    """ElementWrapper representing a LogicalUnit DETAIL object.

    LogicalUnit exists as a DETAIL object e.g. within a SharedStoragePool
    (accessed via SSP.logical_units[n]) or a SCSI mapping (accessed via
    VIOS.scsi_mappings[n].backing_storage).
    """
    pass


@ewrap.EntryWrapper.pvm_type('LogicalUnit', child_order=_LU_EL_ORDER)
class LUEnt(_LUBase, ewrap.EntryWrapper):
    """EntryWrapper representing a LogicalUnit as a first-class REST object.

    LogicalUnit exists as a CHILD REST object under Tier.  This class provides
    the ability to perform e.g.

        LUEnt.get(adapter, parent=tier)
    """
    pass


@ewrap.EntryWrapper.pvm_type('Tier')
class Tier(ewrap.EntryWrapper):
    """A storage grouping within a SharedStoragePool."""

    @property
    def name(self):
        return self._get_val_str(_TIER_NAME)

    @property
    def udid(self):
        return self._get_val_str(_TIER_UDID)

    @property
    def is_default(self):
        return self._get_val_bool(_TIER_IS_DEFAULT)

    @property
    def capacity(self):
        return self._get_val_float(_TIER_CAPACITY)

    @property
    def ssp_uuid(self):
        """The UUID of this Tier's parent SharedStoragePool."""
        return u.get_req_path_uuid(self.get_href(_TIER_ASSOC_SSP,
                                                 one_result=True))


@ewrap.EntryWrapper.pvm_type('SharedStoragePool')
class SSP(ewrap.EntryWrapper):
    """A Shared Storage Pool containing PVs and LUs."""

    search_keys = dict(name='StoragePoolName')

    @classmethod
    def bld(cls, adapter, name, data_pv_list):
        """Create a fresh SSP EntryWrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: String name for the SharedStoragePool.
        :param data_pv_list: Iterable of storage.PV instances
                             representing the data volumes for the
                             SharedStoragePool.
        """
        ssp = super(SSP, cls)._bld(adapter)
        # Assignment order matters.
        ssp.physical_volumes = data_pv_list
        ssp.name = name
        return ssp

    @property
    def name(self):
        return self._get_val_str(_SSP_NAME)

    @name.setter
    def name(self, newname):
        self.set_parm_value(_SSP_NAME, newname)

    @property
    def udid(self):
        return self._get_val_str(_SSP_UDID)

    @property
    def capacity(self):
        """Capacity in GB as a float."""
        return self._get_val_float(_SSP_CAPACITY)

    @property
    def free_space(self):
        """Free space in GB as a float."""
        return self._get_val_float(_SSP_FREE_SPACE)

    @property
    def over_commit_space(self):
        """Over commit space in GB as a float."""
        return self._get_val_float(_SSP_OCS)

    @property
    def total_lu_size(self):
        """Total LU size in GB as a float."""
        return self._get_val_float(_SSP_TOTAL_LU_SIZE)

    @property
    def logical_units(self):
        """WrapperElemList of LU wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(_SSP_LUS), LU)

    @logical_units.setter
    def logical_units(self, lus):
        self.replace_list(_SSP_LUS, lus)

    @property
    def physical_volumes(self):
        """WrapperElemList of PV wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(_SSP_PVS), PV)

    @physical_volumes.setter
    def physical_volumes(self, pvs):
        self.replace_list(_SSP_PVS, pvs)


@ewrap.Wrapper.base_pvm_type
class _VStorageAdapterMethods(ewrap.Wrapper):
    """Mixin to be used with _VStorageAdapter{Element|Entry}."""

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

    def _use_next_slot(self, use):
        """Use next available (not high) slot."""
        self.set_parm_value(_VADPT_NEXT_SLOT, u.sanitize_bool_for_api(use))

    @property
    def loc_code(self):
        """The device's location code."""
        return self._get_val_str(_VADPT_LOC_CODE)


# base_pvm_type by _VStorageAdapterMethods
@six.add_metaclass(abc.ABCMeta)
class _VStorageAdapterElement(ewrap.ElementWrapper, _VStorageAdapterMethods):
    """Parent class for the virtual storage adapters (FC or SCSI)."""
    has_metadata = True

    @classmethod
    def _bld_new(cls, adapter, side):
        """Build a {Client|Server}Adapter requesting a new virtual adapter.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param side: Either 'Client' or 'Server'.
        :returns: A fresh ClientAdapter or ServerAdapter wrapper with
                  UseNextAvailableSlotID=true
        """
        adp = super(_VStorageAdapterElement, cls)._bld(adapter)
        adp._use_next_slot(True)
        adp._side(side)
        return adp


# base_pvm_type by _VStorageAdapterMethods
@six.add_metaclass(abc.ABCMeta)
class _VStorageAdapterEntry(ewrap.EntryWrapper, _VStorageAdapterMethods):
    """Parent class for the virtual storage adapters (FC or SCSI)."""
    has_metadata = True

    @classmethod
    def _bld_new(cls, adapter, side):
        """Build a {Client|Server}Adapter requesting a new virtual adapter.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param side: Either 'Client' or 'Server'.
        :returns: A fresh ClientAdapter or ServerAdapter wrapper with
                  UseNextAvailableSlotID=true
        """
        adp = super(_VStorageAdapterEntry, cls)._bld(adapter)
        adp._side(side)
        adp._use_next_slot(True)
        return adp


@ewrap.Wrapper.base_pvm_type
class _VClientAdapterMethods(ewrap.Wrapper):
    """Mixin to be used with _VClientStorageAdapter{Element|Entry}."""
    @classmethod
    def bld(cls, adapter, slot_num=None):
        """Builds a new Client Adapter.

        If the slot number is None then we'll specify the
        'UseNextAvailableSlot' tag to REST and the REST layer will assign the
        slot. The slot number that it chose will be in the response.

        :param adapter: A pypowervm.adapter.Adapter
        :param slot_num: (Optional, Default: None) The client slot number to
                         be used.
        :returns: A new Client Adapter.
        """
        clad = super(_VClientAdapterMethods, cls)._bld_new(adapter, 'Client')
        if slot_num is not None:
            clad._lpar_slot_num(slot_num)
            clad._use_next_slot(False)
        return clad

    @property
    def lpar_id(self):
        """The short ID (not UUID) of the LPAR side of this adapter.

        Note that the LPAR ID is LocalPartitionID on the client side, and
        RemoteLogicalPartitionID on the server side.
        """
        return self._get_val_int(_VADPT_LOCAL_ID)

    @property
    def lpar_slot_num(self):
        """The (int) slot number that the adapter is in."""
        return self._get_val_int(_VADPT_SLOT_NUM)

    def _lpar_slot_num(self, slot_num):
        """Set the slot number that the adapter is in."""
        self.set_parm_value(_VADPT_SLOT_NUM, slot_num)


@six.add_metaclass(abc.ABCMeta)
@ewrap.ElementWrapper.pvm_type(CLIENT_ADPT, has_metadata=True,
                               child_order=_V_CLNT_ADPT_EL_ORDER)
class VClientStorageAdapterElement(_VClientAdapterMethods,
                                   _VStorageAdapterElement):
    """Parent class for Client Virtual Storage Adapter Elements."""
    pass


@six.add_metaclass(abc.ABCMeta)
@ewrap.ElementWrapper.pvm_type(SERVER_ADPT, has_metadata=True,
                               child_order=_V_SVR_ADPT_EL_ORDER)
class VServerStorageAdapterElement(_VStorageAdapterElement):
    """Parent class for Server Virtual Storage Adapters."""

    @classmethod
    def bld(cls, adapter):
        return super(VServerStorageAdapterElement, cls)._bld_new(adapter,
                                                                 'Server')

    @property
    def name(self):
        """The adapter's name on the Virtual I/O Server."""
        return self._get_val_str(_VADPT_NAME)

    @property
    def udid(self):
        """The device's Unique Device Identifier."""
        return self._get_val_str(_VADPT_UDID)


# pvm_type decorator by superclass (it is not unique)
class VSCSIClientAdapterElement(VClientStorageAdapterElement):
    """The Virtual SCSI Client Adapter within a VSCSI mapping.

    Paired with a VSCSIServerAdapterElement.
    """
    @property
    def vios_id(self):
        """The short ID (not UUID) of the VIOS side of this adapter.

        Note that the VIOS ID is RemoteLogicalPartitionID on the client side,
        and LocalPartitionID on the server side.
        """
        return self._get_val_int(_VSCSI_ADPT_REM_LPAR_ID)

    @property
    def vios_slot_num(self):
        """The (int) remote slot number of the paired adapter."""
        return self._get_val_int(_VSCSI_ADPT_REM_SLOT_NUM)


# pvm_type decorator by superclass (it is not unique)
class VSCSIServerAdapterElement(VServerStorageAdapterElement):
    """The Virtual SCSI Server Adapter within a VSCSI mapping.

    Paired with a VSCSIClientAdapterElement.
    """

    @property
    def backing_dev_name(self):
        """The backing device name that this virtual adapter is hooked into."""
        return self._get_val_str(_VSCSI_ADPT_BACK_DEV_NAME)

    @property
    def lpar_id(self):
        """The short ID (not UUID) of the LPAR side of this adapter.

        Note that the LPAR ID is LocalPartitionID on the client side, and
        RemoteLogicalPartitionID on the server side.
        """
        return self._get_val_int(_VSCSI_ADPT_REM_LPAR_ID)

    @property
    def vios_id(self):
        """The short ID (not UUID) of the VIOS side of this adapter.

        Note that the VIOS ID is RemoteLogicalPartitionID on the client side,
        and LocalPartitionID on the server side.
        """
        return self._get_val_int(_VADPT_LOCAL_ID)

    @property
    def lpar_slot_num(self):
        """The (int) slot number that the LPAR side of the adapter."""
        return self._get_val_int(_VSCSI_ADPT_REM_SLOT_NUM)

    @property
    def vios_slot_num(self):
        """The (int) slot number of the VIOS side of the adapter."""
        return self._get_val_int(_VADPT_SLOT_NUM)


@ewrap.Wrapper.base_pvm_type
class _VFCClientAdapterMethods(ewrap.Wrapper):
    """Mixin to be used with VFCClientAdapter(Element)."""
    def _wwpns(self, value):
        """Sets the WWPN string.

        :param value: The list of WWPNs.  Should only contain two.
        """
        if value is not None:
            self.set_parm_value(_VFC_CLNT_ADPT_WWPNS, " ".join(value).lower())

    @property
    def wwpns(self):
        """Returns a list that contains the WWPNs.  If no WWPNs, empty list."""
        val = self._get_val_str(_VFC_CLNT_ADPT_WWPNS)
        if val is None:
            return []
        else:
            return val.upper().split(' ')

    @property
    def vios_id(self):
        """The short ID (not UUID) of the VIOS side of this adapter."""
        return self._get_val_int(_VFC_ADPT_CONN_PARTITION_ID)

    @property
    def vios_slot_num(self):
        """The (int) remote slot number of the paired adapter."""
        return self._get_val_int(_VFC_ADPT_CONN_SLOT_NUM)


# pvm_type decorator by superclass (it is not unique)
class VFCClientAdapterElement(VClientStorageAdapterElement,
                              _VFCClientAdapterMethods):
    """The Virtual Fibre Channel Client Adapter within a VFC mapping.

    Paired with a VFCServerAdapterElement.
    """

    @classmethod
    def bld(cls, adapter, wwpns=None, slot_num=None):
        """Create a fresh Virtual Fibre Channel Client Adapter.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param wwpns: An optional set of two client WWPNs to set on the
                      adapter.
        :param slot_num: An optional integer to be set as the Virtual
                         slot number.
        """
        adpt = super(VFCClientAdapterElement, cls).bld(adapter,
                                                       slot_num=slot_num)

        if wwpns is not None:
            adpt._wwpns(wwpns)

        return adpt


@six.add_metaclass(abc.ABCMeta)
@ewrap.EntryWrapper.pvm_type(VFC_CLIENT_ADPT, has_metadata=True)
class VFCClientAdapter(_VStorageAdapterEntry, _VClientAdapterMethods,
                       _VFCClientAdapterMethods):
    """EntryWrapper for VirtualFibreChannelClientAdapter CHILD.

    Use this to wrap LogicalPartition/{uuid}/VirtualFibreChannelClientAdapter.
    """
    pass


# pvm_type decorator by superclass (it is not unique)
class VFCServerAdapterElement(VServerStorageAdapterElement):
    """The Virtual Fibre Channel Server Adapter within a VFC mapping.

    Paired with a VFCClientAdapterElement.
    """

    @property
    def map_port(self):
        """The physical FC port name that this virtual port is connect to."""
        return self._get_val_str(_VFC_SVR_ADPT_MAP_PORT)

    @property
    def lpar_id(self):
        """The short ID (not UUID) of the LPAR side of this adapter."""
        return self._get_val_int(_VFC_ADPT_CONN_PARTITION_ID)

    @property
    def vios_id(self):
        """The short ID (not UUID) of the VIOS side of this adapter."""
        return self._get_val_int(_VADPT_LOCAL_ID)

    @property
    def lpar_slot_num(self):
        """The (int) slot number that the LPAR side of the adapter."""
        return self._get_val_int(_VFC_ADPT_CONN_SLOT_NUM)

    @property
    def vios_slot_num(self):
        """The (int) slot number of the VIOS side of the adapter."""
        return self._get_val_int(_VADPT_SLOT_NUM)
