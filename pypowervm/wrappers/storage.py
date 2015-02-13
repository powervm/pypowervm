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

from pypowervm import adapter as adpt
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

# Virtual Disk Constants
DISK_CAPACITY = 'DiskCapacity'
DISK_LABEL = 'DiskLabel'
DISK_NAME = 'DiskName'
DISK_UDID = c.UDID
DISK_ROOT = 'VirtualDisk'

# Physical Volume Constants
PV_UDID = c.UDID
PV_VOL_SIZE = 'VolumeCapacity'
PV_VOL_NAME = 'VolumeName'
PV_VOL_STATE = 'VolumeState'
PV_FC_BACKED = 'IsFibreChannelBacked'
PV_VOL_DESC = 'Description'
PV_LOC_CODE = 'LocationCode'
PV_ROOT = 'PhysicalVolume'

# Virtual Optical Media Constants
VOPT_NAME = 'MediaName'
VOPT_SIZE = 'Size'
VOPT_UDID = 'MediaUDID'
VOPT_MOUNT_TYPE = 'MountType'
VOPT_ROOT = 'VirtualOpticalMedia'

# Virtual Media Repository Constants
VREPO_OPTICAL_MEDIA_ROOT = c.OPTICAL_MEDIA
VREPO_NAME = 'RepositoryName'
VREPO_SIZE = 'RepositorySize'
VREPO_ROOT = 'VirtualMediaRepository'

# Volume Group Constants
VG_ROOT = 'VolumeGroup'
VG_NAME = 'GroupName'
VG_CAPACITY = 'GroupCapacity'
VG_SERIAL_ID = 'GroupSerialID'
VG_FREE_SPACE = 'FreeSpace'
VG_AVAILABLE_SIZE = 'AvailableSize'
VG_MEDIA_REPOS = 'MediaRepositories'
VG_PHS_VOLS = 'PhysicalVolumes'
VG_VDISKS = 'VirtualDisks'

# LogicalUnit Constants
LU_THIN = 'ThinDevice'
LU_UDID = c.UDID
LU_CAPACITY = 'UnitCapacity'
LU_NAME = 'UnitName'
LU_TYPE = 'LogicalUnitType'

# Shared Storage Pool Constants
SSP_NAME = 'StoragePoolName'
SSP_UDID = c.UDID
SSP_CAPACITY = 'Capacity'
SSP_FREE_SPACE = 'FreeSpace'
SSP_TOTAL_LU_SIZE = 'TotalLogicalUnitSize'
SSP_LUS = 'LogicalUnits'
SSP_LU = 'LogicalUnit'
SSP_PVS = c.PVS
SSP_PV = c.PV


def crt_virtual_disk_obj(name, capacity, label=None):
    """Creates the Element structure needed for a VirtualDisk.

    The response Element can be wrapped into a VirtualDisk object.

    This should be used when the user wishes to add a new Virtual Disk to
    the Volume Group.  The flow is to use this method to lay out the attributes
    of the new Virtual Disk.  Then add it to the Volume Group's virtual disks.
    Then perform an update of the Volume Group.  The disk should be created
    by the update operation.

    :param name: The name of the virtual disk
    :param capacity: A float number that defines the GB of the disk.
    :param label: The generic label for the disk.  Not required.
    :returns: An Element that can be used for a VirtualDisk create.
    """
    # Label has to always be specified...even if None.
    if not label:
        label = 'None'

    attrs = [adpt.Element(DISK_CAPACITY, text=str(capacity)),
             adpt.Element(DISK_LABEL, text=str(label)),
             adpt.Element(DISK_NAME, text=str(name))]

    return adpt.Element(DISK_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=attrs)


def crt_phys_vol(name):
    """Creates the Element structure needed for a PhysicalVolume.

    The response Element can be wrapped into a PhysicalVolume object.

    This should be used when wishing to add physical volumes to a Volume
    Group.  Only the name is required.  The other attributes are generated
    from the system.

    The name matches the device name on the system.

    :param name: The name of the physical volume on the Virtual I/O Server
                 to add to the Volume Group.  Ex. 'hdisk1'.
    :returns: An Element that can be used for a PhysicalVolume create.
    """
    attrs = [adpt.Element(PV_VOL_NAME, text=str(name))]

    return adpt.Element(PV_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=attrs)


def crt_vmedia_repo(name, size):
    """Creates the Element structure needed for a VirtualMediaRepository.

    The response Element can be wrapped into a VirtualMediaRepository object.

    This should be used when adding a new Virtual Media Repository to a
    Volume Group.  The name and size for the media repository is required.
    The other attributes are generated from the system.

    Additionally, once created, specific VirtualOpticalMedia can be added
    onto the object.

    :param name: The name of the Virtual Media Repository.
    :param size: The size of the repository in GB.
    :returns: An Element that can be used for a VirtualMediaRepository create.
    """
    attrs = [adpt.Element(VREPO_NAME, text=str(name)),
             adpt.Element(VREPO_SIZE, text=str(size))]

    return adpt.Element(VREPO_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=attrs)


def crt_voptical_media(name, size, mount_type='rw'):
    """Creates the Element structure needed for a VirtualOpticalMedia.

    The response Element can be wrapped into a VirtualOpticalMedia object.

    This should be used when adding a new VirtualOpticalMedia device to a
    VirtualMediaRepository .

    :param name: The device name.
    :param size: The device size in GB.  However, it has decimal precision.
    :param mount_type: The type of mount.  Defaults to RW.  Can be set to R.
    :returns: An Element that can be used for a VirtualOpticalMedia create.
    """
    attrs = [adpt.Element(VOPT_NAME, text=str(name)),
             adpt.Element(VOPT_SIZE, text=str(size)),
             adpt.Element(VOPT_MOUNT_TYPE, text=str(mount_type))]

    return adpt.Element(VOPT_ROOT, attrib=c.DEFAULT_SCHEMA_ATTR,
                        children=attrs)


class VolumeGroup(ewrap.EntryWrapper):
    """Represents a Volume Group that resides on the Virtual I/O Server."""

    @property
    def name(self):
        return self.get_parm_value(VG_NAME)

    @property
    def capacity(self):
        """Overall capacity in MB (int)."""
        return self.get_parm_value_int(VG_CAPACITY)

    @property
    def available_size(self):
        """Available size for new volumes in MB (int)."""
        return self.get_parm_value_int(VG_AVAILABLE_SIZE)

    @property
    def free_space(self):
        """Current free space in MB (int)."""
        return self.get_parm_value_int(VG_FREE_SPACE)

    @property
    def serial_id(self):
        return self.get_parm_value(VG_SERIAL_ID)

    @property
    def vmedia_repos(self):
        """Returns a list of VirtualMediaRepository wrappers."""
        es = ewrap.WrapperElemList(self._find_or_seed(VG_MEDIA_REPOS),
                                   VREPO_ROOT, VirtualMediaRepository)
        return es

    @vmedia_repos.setter
    def vmedia_repos(self, repos):
        """Replaces the VirtualMediaRepositories with the new value.

        :param repos: A list of VirtualMediaRepository objects that will
                      replace the existing repositories.
        """
        self.replace_list(VG_MEDIA_REPOS, repos)

    @property
    def phys_vols(self):
        """Returns a list of the Physical Volumes that back this repo."""
        es = ewrap.WrapperElemList(self._find_or_seed(VG_PHS_VOLS),
                                   PV_ROOT, PhysicalVolume)
        return es

    @phys_vols.setter
    def phys_vols(self, phys_vols):
        """Replaces the physical volumes with the new value.

        :param phys_vols: A list of PhysicalVolume objects that will replace
                          the existing Physcial Volumes.
        """
        self.replace_list(VG_PHS_VOLS, phys_vols)

    @property
    def virtual_disks(self):
        """Returns a list of the Virtual Disks that are in the repo."""
        es = ewrap.WrapperElemList(self._find_or_seed(VG_VDISKS),
                                   DISK_ROOT, VirtualDisk)
        return es

    @virtual_disks.setter
    def virtual_disks(self, virt_disks):
        """Replaces the virtual disks with the new value.

        :param virt_disks: A list of VirtualDisk objects that will replace
                           the existing Virtual Disks.
        """
        self.replace_list(VG_VDISKS, virt_disks)


class VirtualMediaRepository(ewrap.ElementWrapper):
    """A Virtual Media Repository for a VIOS.

    Typically used to store an ISO file for image building.
    """

    @property
    def optical_media(self):
        """Returns a list of the VirtualOpticalMedia devices in the repo."""
        seed = self._find_or_seed(VREPO_OPTICAL_MEDIA_ROOT)
        return ewrap.WrapperElemList(seed, VOPT_ROOT, VirtualOpticalMedia)

    @optical_media.setter
    def optical_media(self, new_media):
        """Sets the list of VirtualOpticalMedia devices in the repo.

        :param new_media: The list of new VirtualOpticalMedia.
        """
        self.replace_list(VREPO_OPTICAL_MEDIA_ROOT, new_media)

    @property
    def name(self):
        return self.get_parm_value(VREPO_NAME)

    @property
    def size(self):
        """Returns the size in GB (int)."""
        return self.get_parm_value_int(VREPO_SIZE)


class VirtualOpticalMedia(ewrap.ElementWrapper):
    """A virtual optical piece of media."""

    @property
    def media_name(self):
        return self.get_parm_value(VOPT_NAME)

    @property
    def size(self):
        """Size is a str.  Represented in GB - has decimal precision."""
        return self.get_parm_value(VOPT_SIZE)

    @property
    def udid(self):
        return self.get_parm_value(VOPT_UDID)

    @property
    def mount_type(self):
        return self.get_parm_value(VOPT_MOUNT_TYPE)


class PhysicalVolume(ewrap.ElementWrapper):
    """A physical volume that backs a Volume Group."""

    schema_type = 'PhysicalVolume'
    has_metadata = True

    @property
    def udid(self):
        """The unique device id."""
        return self.get_parm_value(PV_UDID)

    @property
    def capacity(self):
        """Returns the capacity as an int in MB."""
        return self.get_parm_value_int(PV_VOL_SIZE)

    @property
    def name(self):
        return self.get_parm_value(PV_VOL_NAME)

    @name.setter
    def name(self, newname):
        self.set_parm_value(PV_VOL_NAME, newname)

    @property
    def state(self):
        return self.get_parm_value(PV_VOL_STATE)

    @property
    def is_fc_backed(self):
        return self.get_parm_value_bool(PV_FC_BACKED)

    @property
    def description(self):
        return self.get_parm_value(PV_VOL_DESC)

    @property
    def loc_code(self):
        return self.get_parm_value(PV_LOC_CODE)


class VirtualDisk(ewrap.ElementWrapper):
    """A virtual disk that can be attached to a VM."""

    @property
    def name(self):
        return self.get_parm_value(DISK_NAME)

    @name.setter
    def name(self, name):
        self.set_parm_value(DISK_NAME, name)

    @property
    def label(self):
        return self.get_parm_value(DISK_LABEL)

    @property
    def capacity(self):
        """Returns the capacity in GB (float)."""
        return float(self.get_parm_value(DISK_CAPACITY))

    @capacity.setter
    def capacity(self, capacity):
        self.set_parm_value(DISK_CAPACITY, str(capacity))

    @property
    def udid(self):
        return self.get_parm_value(DISK_UDID)


class LogicalUnit(ewrap.ElementWrapper):
    """A Logical Unit (usually part of a SharedStoragePool."""

    @property
    def name(self):
        return self.get_parm_value(LU_NAME)

    @property
    def udid(self):
        return self.get_parm_value(LU_UDID)

    @property
    def capacity(self):
        """Float capacity in GB."""
        return float(self.get_parm_value(LU_CAPACITY))

    @property
    def lu_type(self):
        """String enum value e.g. "VirtualIO_Disk."""
        return self.get_parm_value(LU_TYPE)

    @property
    def is_thin(self):
        return self.get_parm_value_bool(LU_THIN)


class SharedStoragePool(ewrap.EntryWrapper):
    """A Shared Storage Pool containing PVs and LUs."""

    @property
    def name(self):
        return self.get_parm_value(SSP_NAME)

    @property
    def udid(self):
        return self.get_parm_value(SSP_UDID)

    @property
    def capacity(self):
        """Capacity in GB as a float."""
        return float(self.get_parm_value(SSP_CAPACITY))

    @property
    def free_space(self):
        """Free space in GB as a float."""
        return float(self.get_parm_value(SSP_FREE_SPACE))

    @property
    def total_lu_size(self):
        """Total LU size in GB as a float."""
        return float(self.get_parm_value(SSP_TOTAL_LU_SIZE))

    @property
    def logical_units(self):
        """WrapperElemList of LogicalUnit wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(SSP_LUS),
                                     SSP_LU, LogicalUnit)

    @logical_units.setter
    def logical_units(self, lus):
        self.replace_list(SSP_LUS, lus)

    @property
    def physical_volumes(self):
        """WrapperElemList of PhysicalVolume wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(SSP_PVS),
                                     SSP_PV, PhysicalVolume)

    @physical_volumes.setter
    def physical_volumes(self, pvs):
        self.replace_list(SSP_PVS, pvs)
