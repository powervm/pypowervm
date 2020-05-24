# Copyright 2020 IBM Corp.
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

"""Base classes, enums, and constants for Persistent Memory EntryWrappers."""

from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

# SystemPersistentMemoryConfiguration
_SYS_PMEM_MAX_PMEM_VOLUMES = "MaximumPersistentMemoryVolumes"
_SYS_PMEM_CUR_PMEM_VOLUMES = "CurrentPersistentMemoryVolumes"
_SYS_PMEM_MAX_AIX_PMEM_VOLUMES = "MaximumAixLinuxPersistentMemoryVolumes"
_SYS_PMEM_MAX_OS400_PMEM_VOLUMES = "MaximumOS400PersistentMemoryVolumes"
_SYS_PMEM_MAX_VIOS_PMEM_VOLUMES = "MaximumVIOSPersistentMemoryVolumes"
_SYS_PMEM_DRAM_VOL_BSIZE = "DramPersistentMemoryVolumeBlockSize"
_SYS_PMEM_DRAM_VOL_SIZE = "DramPersistentMemoryVolumesSize"
_SYS_PMEM_DRAM_CUR_SIZE = "DramPersistentMemoryVolumesCurrentSize"
_SYS_PMEM_SUP_DEV_TYPES = "SupportedPersistentMemoryDeviceTypes"

_SYS_PMEM_EL_ORDER = (_SYS_PMEM_MAX_PMEM_VOLUMES, _SYS_PMEM_CUR_PMEM_VOLUMES,
                      _SYS_PMEM_MAX_AIX_PMEM_VOLUMES,
                      _SYS_PMEM_MAX_OS400_PMEM_VOLUMES,
                      _SYS_PMEM_MAX_VIOS_PMEM_VOLUMES,
                      _SYS_PMEM_DRAM_VOL_BSIZE, _SYS_PMEM_DRAM_VOL_SIZE,
                      _SYS_PMEM_DRAM_CUR_SIZE, _SYS_PMEM_SUP_DEV_TYPES)

# PersistentMemoryDevice
_PDEV_DYNAMIC_RECONF_CONNECT_INDEX = "DynamicReconfigurationConnectorIndex"
_PDEV_TYPE = "Type"
_PDEV_STATUS = "Status"
_PDEV_BSIZE = "BlockSize"
_PDEV_TSIZE = "TotalSize"
_PDEV_FSIZE = "FreeSize"
_PDEV_MAX_NUM_VOL = "MaximumNumberOfVolumes"
_PDEV_CUR_NUM_VOL = "CurrentNumberOfVolumes"
_PDEV_PHY_LOC_CODE = "PhysicalLocationCode"
_PDEV_PHY_SERIAL_NUM = "SerialNumber"

_PDEV_EL_ORDER = (_PDEV_DYNAMIC_RECONF_CONNECT_INDEX, _PDEV_TYPE, _PDEV_STATUS,
                  _PDEV_BSIZE, _PDEV_TSIZE, _PDEV_FSIZE, _PDEV_MAX_NUM_VOL,
                  _PDEV_CUR_NUM_VOL, _PDEV_PHY_LOC_CODE, _PDEV_PHY_SERIAL_NUM)


@ewrap.EntryWrapper.pvm_type('PersistentMemoryDevice',
                             child_order=_PDEV_EL_ORDER)
class PersistentMemoryDevice(ewrap.EntryWrapper):
    """Class PersistentMemoryDevice.

    This corresponds to the abstract PersistentMemoryDevice
    object in the PowerVM schema.
    """

    @classmethod
    def bld(cls, adapter, type, drc_index):
        """Creates a PersistentMemoryVolume.
        """
        pmemdev = super(PersistentMemoryDevice, cls)._bld(adapter, type)
        # Create the 'Associated Logical Partition' element of the mapping.
        pmemdev._drc_index(drc_index)

        return pmemdev

    @property
    def drc_index(self):
        return self._get_val_int(_PDEV_DYNAMIC_RECONF_CONNECT_INDEX)

    def _drc_index(self, val):
        self.set_parm_value(_PDEV_DYNAMIC_RECONF_CONNECT_INDEX, val)

    @property
    def type(self):
        return self._get_val_str(_PDEV_TYPE)

    @property
    def status(self):
        return self._get_val_str(_PDEV_STATUS)

    @property
    def blocksize(self):
        return self._get_val_int(_PDEV_BSIZE)

    @property
    def totalsize(self):
        return self._get_val_int(_PDEV_TSIZE)

    @property
    def freesize(self):
        return self._get_val_int(_PDEV_FSIZE)

    @property
    def max_num_volumes(self):
        return self._get_val_int(_PDEV_MAX_NUM_VOL)

    @property
    def cur_num_volumes(self):
        return self._get_val_int(_PDEV_CUR_NUM_VOL)

    @property
    def pys_loc(self):
        return self._get_val_str(_PDEV_PHY_LOC_CODE)

    @property
    def serial_number(self):
        return self._get_val_str(_PDEV_PHY_SERIAL_NUM)

# PersistentMemoryVolume
_PMEM_VOL_DYN_RECONF_INDEX = "DeviceDynamicReconfigurationConnectorIndex"
_PMEM_VOL_NAME = "Name"
_PMEM_VOL_SIZE = "Size"
_PMEM_VOL_ID = "VolumeId"
_PMEM_VOL_ASC_PART_NAME = "AssociatedPartitionName"
_PMEM_VOL_ASC_PART_ID = "AssociatedPartitionId"
_PMEM_VOL_ASC_PARTITION = "AssociatedPartition"
_PMEM_VOL_UUID = "Uuid"

_PMEM_EL_ORDER = (_PMEM_VOL_DYN_RECONF_INDEX, _PMEM_VOL_NAME, _PMEM_VOL_SIZE,
                  _PMEM_VOL_ID, _PMEM_VOL_ASC_PART_NAME, _PMEM_VOL_ASC_PART_ID,
                  _PMEM_VOL_ASC_PARTITION, _PMEM_VOL_UUID)


@ewrap.EntryWrapper.pvm_type('PersistentMemoryVolume',
                             child_order=_PMEM_EL_ORDER)
class PersistentMemoryVolume(PersistentMemoryDevice):
    """Class VirtualPersistentMemoryVolume.

    This corresponds to the abstract PersistentMemoryVolume
    object in the PowerVM schema.
    """

    @classmethod
    def bld(cls, adapter, host_uuid, client_lpar_uuid,
            name, size, volid, drc_index):
        """Creates a PersistentMemoryVolume.
        """
        pmemvol = super(PersistentMemoryVolume, cls)._bld(adapter, name,
                                                          size, volid)
        # Create the 'Associated Logical Partition' element of the mapping.
        pmemvol._client_lpar_href(
            cls.crt_related_href(adapter, None, client_lpar_uuid))
        pmemvol._drc_index(drc_index)

        return pmemvol

        @property
        def drc_index(self):
            return self._get_val_int(_PMEM_VOL_DYN_RECONF_INDEX)

        def _drc_index(self, val):
            self.set_parm_value(_PMEM_VOL_DYN_RECONF_INDEX, val)

        @property
        def uuid(self):
            return self._get_val_str(_PMEM_VOL_UUID)

        @property
        def name(self):
            return self._get_val_str(_PMEM_VOL_NAME)

        @property
        def size(self):
            return self._get_val_int(_PMEM_VOL_SIZE)

        @property
        def volume_id(self):
            return self._get_val_int(_PMEM_VOL_ID)


# PartitionPersistentMemoryConfiguration
_PMCONF_MAX_PMEM_CONF = "MaximumPersistentMemoryVolumes"
_PMCONF_CUR_PMEM_CONF = "CurrentPersistentMemoryVolumes"

_PMCONF_EL_ORDER = (_PMCONF_MAX_PMEM_CONF, _PMCONF_CUR_PMEM_CONF)

# VirtualPersistentMemoryVolume
_VIRT_PMEM_VOL_UUID = "Uuid"
_VIRT_PMEM_VOL_NAME = "Name"
_VIRT_PMEM_VOL_SIZE = "Size"
_VIRT_PMEM_VOL_CURSIZE = "CurrentSize"
_VIRT_PMEM_VOL_ID = "VolumeId"
_VIRT_PMEM_VOL_AFFINITY = "Affinity"
_VIRT_PMEM_VOL_ASC_PARTNAME = "AssociatedPartitionName"
_VIRT_PMEM_VOL_ASC_PARTID = "AssociatedPartitionId"
_VIRT_PMEM_VOL_ASC_PART = "AssociatedPartition"

_VIRT_PMEM_EL_ORDER = (_VIRT_PMEM_VOL_UUID, _VIRT_PMEM_VOL_NAME,
                       _VIRT_PMEM_VOL_SIZE, _VIRT_PMEM_VOL_CURSIZE,
                       _VIRT_PMEM_VOL_ID, _VIRT_PMEM_VOL_AFFINITY,
                       _VIRT_PMEM_VOL_ASC_PARTNAME, _VIRT_PMEM_VOL_ASC_PARTID,
                       _VIRT_PMEM_VOL_ASC_PART)


@ewrap.EntryWrapper.pvm_type('VirtualPersistentMemoryVolume',
                             child_order=_VIRT_PMEM_EL_ORDER)
class VirtualPMEMVolume(ewrap.EntryWrapper):
    """Class VirtualPersistentMemoryVolume.

    This corresponds to the abstract VirtualPersistentMemoryVolume
    object in the PowerVM schema.
    """

    @classmethod
    def bld(cls, adapter, host_uuid, client_lpar_uuid,
            name, size, volid):
        """Creates a VirtualPersistentMemoryVolume.
        """
        vpmemvol = super(VirtualPMEMVolume, cls)._bld(adapter, name,
                                                      size, volid)
        # Create the 'Associated Logical Partition' element of the mapping.
        vpmemvol._client_lpar_href(
            cls.crt_related_href(adapter, None, client_lpar_uuid))
        return vpmemvol

    @property
    def uuid(self):
        return self._get_val_str(_VIRT_PMEM_VOL_UUID)

    @property
    def name(self):
        return self._get_val_str(_VIRT_PMEM_VOL_NAME)

    @property
    def size(self):
        return self._get_val_int(_VIRT_PMEM_VOL_SIZE)

    @property
    def cur_size(self):
        return self._get_val_int(_VIRT_PMEM_VOL_CURSIZE)

    @property
    def volume_id(self):
        return self._get_val_int(_VIRT_PMEM_VOL_ID)

    @property
    def affinity(self):
        return self._get_val_bool(_VIRT_PMEM_VOL_AFFINITY, default=True)

    @property
    def assoc_partition_name(self):
        return self._get_val_str(_VIRT_PMEM_VOL_ASC_PARTNAME)

    @property
    def assoc_partition_id(self):
        return self._get_val_int(_VIRT_PMEM_VOL_ASC_PARTID)

    @property
    def assoc_partition(self):
        return self.get_href(_VIRT_PMEM_VOL_ASC_PART)
