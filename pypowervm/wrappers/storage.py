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

import logging

import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

# Virtual Disk Constants
DISK_ROOT = 'VirtualDisk'
_DISK_CAPACITY = 'DiskCapacity'
_DISK_LABEL = 'DiskLabel'
DISK_NAME = 'DiskName'
_DISK_UDID = c.UDID

# Physical Volume Constants
_PV_UDID = c.UDID
_PV_VOL_SIZE = 'VolumeCapacity'
_PV_VOL_NAME = 'VolumeName'
_PV_VOL_STATE = 'VolumeState'
_PV_FC_BACKED = 'IsFibreChannelBacked'
_PV_VOL_DESC = 'Description'
_PV_LOC_CODE = 'LocationCode'

# Virtual Optical Media Constants
VOPT_ROOT = 'VirtualOpticalMedia'
VOPT_NAME = 'MediaName'
_VOPT_SIZE = 'Size'
_VOPT_UDID = 'MediaUDID'
_VOPT_MOUNT_TYPE = 'MountType'

# Virtual Media Repository Constants
_VREPO_ROOT = 'VirtualMediaRepository'
_VREPO_OPTICAL_MEDIA_ROOT = c.OPTICAL_MEDIA
_VREPO_NAME = 'RepositoryName'
_VREPO_SIZE = 'RepositorySize'

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
_VG_PHS_VOLS = 'PhysicalVolumes'
_VG_UDID = c.UDID
_VG_VDISKS = 'VirtualDisks'
_VG_EL_ORDER = (_VG_AVAILABLE_SIZE, _VG_BACKING_DEVICE_COUNT, _VG_FREE_SPACE,
                _VG_CAPACITY, _VG_NAME, _VG_SERIAL_ID, _VG_STATE, _VG_MAX_LVS,
                _VG_MEDIA_REPOS, _VG_MIN_ALLOC_SIZE, _VG_PHS_VOLS, _VG_UDID,
                _VG_VDISKS)

# LogicalUnit Constants
_LU_THIN = 'ThinDevice'
_LU_UDID = c.UDID
_LU_CAPACITY = 'UnitCapacity'
_LU_TYPE = 'LogicalUnitType'
_LU_CLONED_FROM = 'ClonedFrom'
_LU_IN_USE = 'InUse'
_LU_NAME = 'UnitName'
_LU_EL_ORDER = (_LU_THIN, _LU_UDID, _LU_CAPACITY, _LU_TYPE, _LU_CLONED_FROM,
                _LU_IN_USE, _LU_NAME)

# Shared Storage Pool Constants
_SSP_NAME = 'StoragePoolName'
_SSP_UDID = c.UDID
_SSP_CAPACITY = 'Capacity'
_SSP_FREE_SPACE = 'FreeSpace'
_SSP_TOTAL_LU_SIZE = 'TotalLogicalUnitSize'
_SSP_LUS = 'LogicalUnits'
_SSP_LU = 'LogicalUnit'
_SSP_PVS = c.PVS
_SSP_PV = c.PV


@ewrap.EntryWrapper.pvm_type('VolumeGroup', child_order=_VG_EL_ORDER)
class VG(ewrap.EntryWrapper):
    """Represents a Volume Group that resides on the Virtual I/O Server."""

    @classmethod
    def bld(cls, name, pv_list):
        vg = super(VG, cls)._bld()
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

    def _capacity(self, val):
        self.set_parm_value(_VG_CAPACITY, val)

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


@ewrap.ElementWrapper.pvm_type('VirtualMediaRepository', has_metadata=True)
class VMediaRepos(ewrap.ElementWrapper):
    """A Virtual Media Repository for a VIOS.

    Typically used to store an ISO file for image building.
    """

    @classmethod
    def bld(cls, name, size):
        """Creates a fresh VMediaRepos wrapper.

        This should be used when adding a new Virtual Media Repository to a
        Volume Group.  The name and size for the media repository is required.
        The other attributes are generated from the system.

        Additionally, once created, specific VirtualOpticalMedia can be added
        onto the object.

        :param name: The name of the Virtual Media Repository.
        :param size: The size of the repository in GB.
        :returns: A VMediaRepos wrapper that can be used for create.
        """
        vmr = super(VMediaRepos, cls)._bld()
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
        """Returns the size in GB (int)."""
        return self._get_val_int(_VREPO_SIZE)

    def _size(self, new_size):
        self.set_parm_value(_VREPO_SIZE, new_size)


@ewrap.ElementWrapper.pvm_type('VirtualOpticalMedia', has_metadata=True)
class VOptMedia(ewrap.ElementWrapper):
    """A virtual optical piece of media."""

    @classmethod
    def bld(cls, name, size=None, mount_type='rw'):
        """Creates a fresh VOptMedia wrapper.

        This should be used when adding a new VirtualOpticalMedia device to a
        VirtualMediaRepository.

        :param name: The device name.
        :param size: The device size in GB.  However, it has decimal precision.
        :param mount_type: The type of mount.  Defaults to RW.  Can be set to R
        :returns: A VOptMedia wrapper that can be used for create.
        """
        vom = super(VOptMedia, cls)._bld()
        vom._media_name(name)
        if size is not None:
            vom._size(size)
        vom._mount_type(mount_type)
        return vom

    @classmethod
    def bld_ref(cls, name):
        """Creates a VOptMedia wrapper for referencing an existing VOpt."""
        vom = super(VOptMedia, cls)._bld()
        vom._media_name(name)
        return vom

    @property
    def media_name(self):
        return self._get_val_str(VOPT_NAME)

    def _media_name(self, new_name):
        self.set_parm_value(VOPT_NAME, new_name)

    @property
    def size(self):
        """Size is a str.  Represented in GB - has decimal precision."""
        return self._get_val_str(_VOPT_SIZE)

    def _size(self, new_size):
        self.set_parm_value(_VOPT_SIZE, new_size)

    @property
    def udid(self):
        return self._get_val_str(_VOPT_UDID)

    @property
    def mount_type(self):
        return self._get_val_str(_VOPT_MOUNT_TYPE)

    def _mount_type(self, new_mount_type):
        self.set_parm_value(_VOPT_MOUNT_TYPE, new_mount_type)


@ewrap.ElementWrapper.pvm_type('PhysicalVolume', has_metadata=True)
class PV(ewrap.ElementWrapper):
    """A physical volume that backs a Volume Group."""

    @classmethod
    def bld(cls, name, udid=None):
        """Creates the a fresh PV wrapper.

        This should be used when wishing to add physical volumes to a Volume
        Group.  Only the name is required.  The other attributes are generated
        from the system.

        The name matches the device name on the system.

        :param name: The name of the physical volume on the Virtual I/O Server
                     to add to the Volume Group.  Ex. 'hdisk1'.
        :param udid: Universal Disk Identifier.
        :returns: An Element that can be used for a PhysicalVolume create.
        """
        pv = super(PV, cls)._bld()
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


@ewrap.ElementWrapper.pvm_type('VirtualDisk', has_metadata=True)
class VDisk(ewrap.ElementWrapper):
    """A virtual disk that can be attached to a VM."""

    @classmethod
    def bld(cls, name, capacity, label=None):
        """Creates a VDisk Wrapper for creating a new VDisk.

        This should be used when the user wishes to add a new Virtual Disk to
        the Volume Group.  The flow is to use this method to lay out the
        attributes of the new Virtual Disk.  Then add it to the Volume Group's
        virtual disks. Then perform an update of the Volume Group.  The disk
        should be created by the update operation.

        :param name: The name of the virtual disk
        :param capacity: A float number that defines the GB of the disk.
        :param label: The generic label for the disk.  Not required.
        :returns: An Element that can be used for a VirtualDisk create.
        """
        vd = super(VDisk, cls)._bld()
        vd.capacity = capacity
        # Label must be specified; str will make None 'None'.
        vd._label(str(label))
        vd.name = name
        return vd

    @classmethod
    def bld_ref(cls, name):
        """Creates a VDisk Wrapper for referring to an existing VDisk."""
        vd = super(VDisk, cls)._bld()
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
        self.set_parm_value(_DISK_CAPACITY, capacity)

    @property
    def udid(self):
        return self._get_val_str(_DISK_UDID)


@ewrap.ElementWrapper.pvm_type('LogicalUnit', has_metadata=True,
                               child_order=_LU_EL_ORDER)
class LU(ewrap.ElementWrapper):
    """A Logical Unit (usually part of a SharedStoragePool)."""

    @classmethod
    def bld_ref(cls, name, udid):
        """Creates the a fresh LU wrapper.

        The name matches the device name on the system.

        :param name: The name of the logical unit on the Virtual I/O Server.
        :param udid: Universal Disk Identifier.
        :returns: An Element that can be used for a PhysicalVolume create.
        """
        pv = super(LU, cls)._bld()
        # Assignment order is significant
        pv._name(name)
        pv._udid(udid)
        return pv

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

    @property
    def lu_type(self):
        """String enum value e.g. "VirtualIO_Disk."""
        return self._get_val_str(_LU_TYPE)

    @property
    def is_thin(self):
        return self._get_val_bool(_LU_THIN)


@ewrap.EntryWrapper.pvm_type('SharedStoragePool')
class SSP(ewrap.EntryWrapper):
    """A Shared Storage Pool containing PVs and LUs."""

    search_keys = dict(name='StoragePoolName')

    @classmethod
    def bld(cls, name, data_pv_list):
        """Create a fresh SSP EntryWrapper.

        :param name: String name for the SharedStoragePool.
        :param data_pv_list: Iterable of storage.PV instances
                             representing the data volumes for the
                             SharedStoragePool.
        """
        ssp = super(SSP, cls)._bld()
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
