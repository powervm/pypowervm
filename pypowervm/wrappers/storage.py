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

"""Wrappers for virtual storage elements and adapters."""

import abc
import logging

import six

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
_DISK_UDID = UDID
_VDISK_EL_ORDER = [_DISK_CAPACITY, _DISK_LABEL, DISK_NAME,
                   _DISK_MAX_LOGICAL_VOLS, _DISK_PART_SIZE, _DISK_VG,
                   _DISK_UDID]

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
_PV_EL_ORDER = [_PV_AVAIL_PHYS_PART, _PV_VOL_DESC, _PV_LOC_CODE,
                _PV_PERSISTENT_RESERVE, _PV_RES_POLICY, _PV_RES_POLICY_ALGO,
                _PV_TOTAL_PHYS_PARTS, _PV_UDID, _PV_AVAIL_FOR_USE,
                _PV_VOL_SIZE, _PV_VOL_NAME, _PV_VOL_STATE, _PV_VOL_UNIQUE_ID,
                _PV_FC_BACKED]

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

# Shared Storage Pool Constants
_SSP_NAME = 'StoragePoolName'
_SSP_UDID = UDID
_SSP_CAPACITY = 'Capacity'
_SSP_FREE_SPACE = 'FreeSpace'
_SSP_TOTAL_LU_SIZE = 'TotalLogicalUnitSize'
_SSP_LUS = 'LogicalUnits'
_SSP_LU = 'LogicalUnit'
_SSP_PVS = PVS
_SSP_PV = PHYS_VOL

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
_LOCATION_CODE = 'LocationCode'

CLIENT_ADPT = 'ClientAdapter'
SERVER_ADPT = 'ServerAdapter'


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
        es = ewrap.WrapperElemList(self._find_or_seed(_VG_PHS_VOLS), PV)
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


@ewrap.ElementWrapper.pvm_type(VOPT_ROOT, has_metadata=True,
                               child_order=_VOPT_EL_ORDER)
class VOptMedia(ewrap.ElementWrapper):
    """A virtual optical piece of media."""

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


@ewrap.ElementWrapper.pvm_type(DISK_ROOT, has_metadata=True,
                               child_order=_VDISK_EL_ORDER)
class VDisk(ewrap.ElementWrapper):
    """A virtual disk that can be attached to a VM."""

    @classmethod
    def bld(cls, adapter, name, capacity, label=None):
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
        :returns: An Element that can be used for a VirtualDisk create.
        """
        vd = super(VDisk, cls)._bld(adapter)
        vd.capacity = capacity
        # Label must be specified; str will make None 'None'.
        vd._label(str(label))
        vd.name = name
        return vd

    @classmethod
    def bld_ref(cls, adapter, name):
        """Creates a VDisk Wrapper for referring to an existing VDisk."""
        vd = super(VDisk, cls)._bld(adapter)
        vd.name = name
        return vd

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


@ewrap.ElementWrapper.pvm_type('LogicalUnit', has_metadata=True,
                               child_order=_LU_EL_ORDER)
class LU(ewrap.ElementWrapper):
    """A Logical Unit (usually part of a SharedStoragePool)."""

    @classmethod
    def bld(cls, adapter, name, capacity, thin=None, typ=None):
        """Build a fresh wrapper for LU creation within an SSP.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name to assign to the new LogicalUnit
        :param capacity: Capacity in GB for the new LogicalUnit
        :param thin: Provision the new LU as thin (True) or thick (False).
        :param typ: Logical Unit type, one of the LUType values.
        :return: A new LU wrapper suitable for adding to SSP.logical_units
                 prior to update.
        """
        lu = super(LU, cls)._bld(adapter)
        lu._name(name)
        lu._capacity(capacity)
        if thin is not None:
            lu._is_thin(thin)
        if typ is not None:
            lu._lu_type(typ)
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
        lu = super(LU, cls)._bld(adapter)
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
        conv = int if six.PY3 else long
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
        return self.set_parm_value(_LU_UDID, value)

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


@six.add_metaclass(abc.ABCMeta)
class VStorageAdapter(ewrap.ElementWrapper):
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
        adp = super(VStorageAdapter, cls)._bld(adapter)
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
@ewrap.ElementWrapper.pvm_type(CLIENT_ADPT, has_metadata=True)
class VClientStorageAdapter(VStorageAdapter):
    """Parent class for Client Virtual Storage Adapters."""

    @classmethod
    def bld(cls, adapter):
        return super(VClientStorageAdapter, cls)._bld_new(adapter, 'Client')

    @property
    def lpar_id(self):
        """The LPAR ID the contains this client adapter."""
        return self._get_val_int(_VADPT_LPAR_ID)


@six.add_metaclass(abc.ABCMeta)
@ewrap.ElementWrapper.pvm_type(SERVER_ADPT, has_metadata=True)
class VServerStorageAdapter(VStorageAdapter):
    """Parent class for Server Virtual Storage Adapters."""

    @classmethod
    def bld(cls, adapter):
        return super(VServerStorageAdapter, cls)._bld_new(adapter, 'Server')

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


# pvm_type decorator by superclass (it is not unique)
class VFCClientAdapter(VClientStorageAdapter):
    """The Virtual Fibre Channel Adapter on the client LPAR.

    Paired with a VFCServerAdapter.
    """

    @classmethod
    def bld(cls, adapter, wwpns=None):
        """Create a fresh Virtual Fibre Channel Client Adapter.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param wwpns: An optional set of two client WWPNs to set on the
                      adapter.
        """
        adpt = super(VFCClientAdapter, cls).bld(adapter)

        if wwpns is not None:
            adpt._wwpns(wwpns)

        return adpt

    def _wwpns(self, value):
        """Sets the WWPN string.

        :param value: The set (or list) of WWPNs.  Should only contain two.
        """
        if value is not None:
            self.set_parm_value(_VADPT_WWPNS, " ".join(value).lower())

    @property
    def wwpns(self):
        """Returns a set that contains the WWPNs.  If no WWPNs, empty set."""
        val = self._get_val_str(_VADPT_WWPNS)
        if val is None:
            return set()
        else:
            return set(val.upper().split(' '))


# pvm_type decorator by superclass (it is not unique)
class VFCServerAdapter(VServerStorageAdapter):
    """The Virtual Fibre Channel Adapter on the VIOS.

    Paired with a VFCClientAdapter.
    """

    @property
    def map_port(self):
        """The physical FC port name that this virtual port is connect to."""
        return self._get_val_str(_VADPT_MAP_PORT)
