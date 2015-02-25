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

import pypowervm.adapter as adr
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

import logging

LOG = logging.getLogger(__name__)

T = 'true'
F = 'false'

DED_PROCS = 'DesiredProcessors'
DED_MAX_PROCS = 'MaximumProcessors'
DED_MIN_PROCS = 'MinimumProcessors'

DED_PROC_CFG = 'DedicatedProcessorConfiguration'
HAS_DED_PROCS = 'HasDedicatedProcessors'
SHARING_MODE = 'SharingMode'

SHR_PROC_CFG = 'SharedProcessorConfiguration'
PROC_UNIT = 'DesiredProcessingUnits'
MIN_PU = 'MinimumProcessingUnits'
MAX_PU = 'MaximumProcessingUnits'
DES_VIRT_PROC = 'DesiredVirtualProcessors'
MIN_VIRT_PROC = 'MinimumVirtualProcessors'
MAX_VIRT_PROC = 'MaximumVirtualProcessors'

MEM = 'DesiredMemory'
MAX_MEM = 'MaximumMemory'
MIN_MEM = 'MinimumMemory'

NAME = 'PartitionName'
TYPE = 'PartitionType'
LPAR_TYPE_OS400 = 'OS400'
LPAR_TYPE_AIXLINUX = 'AIX/Linux'

MAX_IO_SLOT = 'MaximumVirtualIOSlots'

LPAR_ROOT = 'LogicalPartition'
LPAR = LPAR_ROOT
LPAR_PROC_CFG = 'PartitionProcessorConfiguration'
LPAR_MEM_CFG = 'PartitionMemoryConfiguration'
LPAR_IO_CFG = 'PartitionIOConfiguration'

# Dedicated sharing modes
DED_SHARING_MODES = ('sre idle proces', 'keep idle procs',
                     'sre idle procs active', 'sre idle procs always')
SHARING_MODES = ('capped', 'uncapped')
UNCAPPED_WEIGHT = 'UncappedWeight'

# Constants for the Partition I/O Configuration
IO_CFG_ROOT = LPAR_IO_CFG
IO_CFG_MAX_SLOTS = 'MaximumVirtualIOSlots'

# Constants for the I/O Slot Configuration
IO_SLOTS_ROOT = 'ProfileIOSlots'
IO_SLOT_ROOT = 'ProfileIOSlot'

# Constants for the Associated I/O Slot
ASSOC_IO_SLOT_ROOT = 'AssociatedIOSlot'
ASSOC_IO_SLOT_DESC = 'Description'
ASSOC_IO_SLOT_PHYS_LOC = 'IOUnitPhysicalLocation'
ASSOC_IO_SLOT_ADPT_ID = 'PCAdapterID'
ASSOC_IO_SLOT_PCI_CLASS = 'PCIClass'
ASSOC_IO_SLOT_PCI_DEV_ID = 'PCIDeviceID'
ASSOC_IO_SLOT_PCI_SUB_DEV_ID = 'PCISubsystemDeviceID'
ASSOC_IO_SLOT_PCI_MFG_ID = 'PCIManufacturerID'
ASSOC_IO_SLOT_PCI_REV_ID = 'PCIRevisionID'
ASSOC_IO_SLOT_PCI_VENDOR_ID = 'PCIVendorID'
ASSOC_IO_SLOT_SUBSYS_VENDOR_ID = 'PCISubsystemVendorID'

# Constants for generic I/O Adapter
RELATED_IO_ADPT_ROOT = 'RelatedIOAdapter'
IO_ADPT_ROOT = 'IOAdapter'
IO_PFC_ADPT_ROOT = 'PhysicalFibreChannelAdapter'
IO_ADPT_ID = 'AdapterID'
IO_ADPT_DESC = 'Description'
IO_ADPT_NAME = 'DeviceName'
IO_ADPT_DYN_NAME = 'DynamicReconfigurationConnectorName'
IO_ADPT_PHYS_LOC = 'PhysicalLocation'

# Physical Fibre Channel Port Constants
PFC_PORT_LOC_CODE = 'LocationCode'
PFC_PORT_NAME = 'PortName'
PFC_PORT_UDID = 'UniqueDeviceID'
PFC_PORT_WWPN = 'WWPN'
PFC_PORT_AVAILABLE_PORTS = 'AvailablePorts'
PFC_PORT_TOTAL_PORTS = 'TotalPorts'
PFC_PORTS_ROOT = 'PhysicalFibreChannelPorts'
PFC_PORT_ROOT = 'PhysicalFibreChannelPort'


def crt_ded_procs(proc, sharing_mode=DED_SHARING_MODES[0],
                  min_proc=None, max_proc=None):
    """Create the dedicated processor structure

    :param proc: The number of dedicated processors
    :param sharing_mode: The processor sharing mode of the lpar
    :param min_proc: The minimum number of processors. Defaults to the same as
                     the proc param
    :param max_proc: The maximum number of processors. Defaults to the same as
                     the proc param
    """

    if min_proc is None:
        min_proc = proc
    if max_proc is None:
        max_proc = proc

    proc_details = [adr.Element(DED_PROCS, text=proc),
                    adr.Element(DED_MAX_PROCS, text=max_proc),
                    adr.Element(DED_MIN_PROCS, text=min_proc)]

    proc_cfg = [adr.Element(DED_PROC_CFG,
                            attrib=c.DEFAULT_SCHEMA_ATTR,
                            children=proc_details),
                adr.Element(HAS_DED_PROCS, text=T),
                adr.Element(SHARING_MODE, text=sharing_mode)]

    proc_ele = adr.Element(LPAR_PROC_CFG,
                           attrib=c.DEFAULT_SCHEMA_ATTR,
                           children=proc_cfg)

    return proc_ele


def crt_shared_procs(proc_unit, proc, sharing_mode=SHARING_MODES[1],
                     uncapped_weight='128',
                     min_proc_unit=None, max_proc_unit=None,
                     min_proc=None, max_proc=None):
    """Create the shared processor structure

    :param proc_unit: The number of processing units
    :param proc: The number of virtual processors
    :param min_proc_unit: The minimum number of processors units.
                          Defaults to the same as the proc_unit param
    :param max_proc_unit: The maximum number of processors units.
                          Defaults to the same as the proc_unit param
    :param min_proc: The minimum number of processors. Defaults to the same as
                     the proc param
    :param max_proc: The maximum number of processors. Defaults to the same as
                     the proc param
    """

    if min_proc_unit is None:
        min_proc_unit = proc_unit
    if max_proc_unit is None:
        max_proc_unit = proc_unit
    if min_proc is None:
        min_proc = proc
    if max_proc is None:
        max_proc = proc

    proc_details = [adr.Element(PROC_UNIT, text=proc_unit),
                    adr.Element(DES_VIRT_PROC, text=proc),
                    adr.Element(MAX_PU, text=max_proc_unit),
                    adr.Element(MAX_VIRT_PROC, text=max_proc),
                    adr.Element(MIN_PU, text=min_proc_unit),
                    adr.Element(MIN_VIRT_PROC, text=min_proc)]

    if sharing_mode == 'uncapped':
        proc_details.append(adr.Element(UNCAPPED_WEIGHT,
                            text=str(uncapped_weight)))
    proc_cfg = [adr.Element(HAS_DED_PROCS, text=F),
                adr.Element(SHR_PROC_CFG,
                            attrib=c.DEFAULT_SCHEMA_ATTR,
                            children=proc_details),
                adr.Element(SHARING_MODE, text=sharing_mode)]

    proc_ele = adr.Element(LPAR_PROC_CFG,
                           attrib=c.DEFAULT_SCHEMA_ATTR,
                           children=proc_cfg)

    return proc_ele


def crt_lpar(name, type_, proc_cfg, mem, min_mem=None, max_mem=None,
             max_io_slots='64'):
    """Create the LPAR element structure

    :param name: The name of the lpar
    :param type_: The type of lpar
    :param proc_cfg: The processor configuration section
    :param mem: The amount of memory for the partition in MB (str)
    :param min_mem: The minimum amount of memory in MB (str). Defaults to the
                    mem param
    :param max_mem: The maximum amount of memory in MB (str). Defaults to the
                    mem param
    :param max_io_slots: The number of IO slots to configure for the
    partition (str)

    """
    if min_mem is None:
        min_mem = mem
    if max_mem is None:
        max_mem = mem

    io_cfg = [adr.Element(MAX_IO_SLOT, text=max_io_slots)]
    memory = [adr.Element(MEM, text=mem),
              adr.Element(MAX_MEM, text=max_mem),
              adr.Element(MIN_MEM, text=min_mem)]

    attrs = [adr.Element(LPAR_IO_CFG, attrib=c.DEFAULT_SCHEMA_ATTR,
                         children=io_cfg),
             adr.Element(LPAR_MEM_CFG, attrib=c.DEFAULT_SCHEMA_ATTR,
                         children=memory),
             adr.Element(NAME, text=name),
             proc_cfg,
             adr.Element(TYPE, text=type_)
             ]
    lpar = adr.Element(LPAR, attrib=c.DEFAULT_SCHEMA_ATTR, children=attrs)

    return lpar


class LogicalPartition(ewrap.EntryWrapper):
    schema_type = c.LPAR

    @property
    def state(self):
        """See LogicalPartitionStateEnum.

        e.g. 'not activated', 'running', 'migrating running', etc.
        """
        partition_state = self._get_val_str(c.PARTITION_STATE)
        return partition_state

    @property
    def name(self):
        """Short name (not ID, MTMS, or hostname)."""
        return self._get_val_str(c.PARTITION_NAME)

    @property
    def id(self):
        """Short ID (not UUID)."""
        return int(self._get_val_str(c.PARTITION_ID, c.ZERO))

    @property
    def env(self):
        """See LogicalPartitionEnvironmentEnum.

        Should always be 'AIX/Linux' for LPAREntry.  'Virtual IO Server'
        should only happen for VIOSEntry.
        """
        return self._get_val_str(c.PARTITION_TYPE)

    @property
    def current_mem(self):
        return self._get_val_str(c.CURR_MEM, c.ZERO)

    @property
    def current_max_mem(self):
        return self._get_val_str(c.CURR_MAX_MEM, c.ZERO)

    @property
    def current_min_mem(self):
        return self._get_val_str(c.CURR_MIN_MEM, c.ZERO)

    @property
    def desired_mem(self):
        return self._get_val_str(c.DES_MEM, c.ZERO)

    @property
    def max_mem(self):
        return self._get_val_str(c.DES_MAX_MEM, c.ZERO)

    @property
    def min_mem(self):
        return self._get_val_str(c.DES_MIN_MEM, c.ZERO)

    @property
    def run_mem(self):
        return self._get_val_str(c.RUN_MEM, c.ZERO)

    @property
    def current_mem_share_enabled(self):
        # The default is None instead of False so that the caller
        # can know if the value is not set
        return self._get_val_bool(c.SHARED_MEM_ENABLED, None)

    @property
    def current_proc_mode_is_dedicated(self):
        """Returns boolean True if dedicated, False if shared or not found."""
        return self._get_val_bool(c.CURR_USE_DED_PROCS, False)

    @property
    def proc_mode_is_dedicated(self):
        """Returns boolean True if dedicated, False if shared or not found."""
        return self._get_val_bool(c.USE_DED_PROCS, False)

    @property
    def current_procs(self):
        return self._get_val_str(c.CURR_PROCS, c.ZERO)

    @property
    def current_max_procs(self):
        return self._get_val_str(c.CURR_MAX_PROCS, c.ZERO)

    @property
    def current_min_procs(self):
        return self._get_val_str(c.CURR_MIN_PROCS, c.ZERO)

    @property
    def desired_procs(self):
        return self._get_val_str(c.DES_PROCS, c.ZERO)

    @property
    def max_procs(self):
        return self._get_val_str(c.DES_MAX_PROCS, c.ZERO)

    @property
    def min_procs(self):
        return self._get_val_str(c.DES_MIN_PROCS, c.ZERO)

    @property
    def current_vcpus(self):
        return self._get_val_str(c.CURR_VCPU, c.ZERO)

    @property
    def current_max_vcpus(self):
        return self._get_val_str(c.CURR_MAX_VCPU, c.ZERO)

    @property
    def current_min_vcpus(self):
        return self._get_val_str(c.CURR_MIN_VCPU, c.ZERO)

    @property
    def desired_vcpus(self):
        return self._get_val_str(c.DES_VCPU, c.ZERO)

    @property
    def max_vcpus(self):
        return self._get_val_str(c.DES_MAX_VCPU, c.ZERO)

    @property
    def min_vcpus(self):
        return self._get_val_str(c.DES_MIN_VCPU, c.ZERO)

    @property
    def current_proc_units(self):
        return self._get_val_str(c.CURR_PROC_UNITS, c.ZERO)

    @property
    def current_max_proc_units(self):
        return self._get_val_str(c.CURR_MAX_PROC_UNITS, c.ZERO)

    @property
    def current_min_proc_units(self):
        return self._get_val_str(c.CURR_MIN_PROC_UNITS, c.ZERO)

    @property
    def desired_proc_units(self):
        return self._get_val_str(c.DES_PROC_UNITS, c.ZERO)

    @property
    def max_proc_units(self):
        return self._get_val_str(c.MAX_PROC_UNITS, c.ZERO)

    @property
    def min_proc_units(self):
        return self._get_val_str(c.MIN_PROC_UNITS, c.ZERO)

    @property
    def run_procs(self):
        return self._get_val_str(c.RUN_PROCS, c.ZERO)

    @property
    def run_vcpus(self):
        return self._get_val_str(c.RUN_VCPU, c.ZERO)

    @property
    def current_uncapped_weight(self):
        return self._get_val_str(c.CURR_UNCAPPED_WEIGHT, c.ZERO)

    @property
    def uncapped_weight(self):
        return self._get_val_str(c.UNCAPPED_WEIGHT, c.ZERO)

    @property
    def shared_proc_pool_id(self):
        return int(self._get_val_str(c.SHARED_PROC_POOL_ID, c.ZERO))

    @property
    def avail_priority(self):
        return self._get_val_str(c.AVAIL_PRIORITY, c.ZERO)

    @property
    def sharing_mode(self):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        return self._get_val_str(c.CURR_SHARING_MODE)

    @property
    def migration_state(self):
        """See PartitionMigrationStateEnum.

        e.g. 'Not_Migrating', 'Migration_Starting', 'Migration_Failed', etc.
        Defaults to 'Not_Migrating'
        """
        return self._get_val_str(c.MIGRATION_STATE, 'Not_Migrating')

    @property
    def proc_compat_mode(self):
        """*Current* processor compatibility mode.

        See LogicalPartitionProcessorCompatibilityModeEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self._get_val_str(c.CURRENT_PROC_MODE)

    @property
    def pending_proc_compat_mode(self):
        """Pending processor compatibility mode.

        See LogicalPartitionProcessorCompatibilityModeEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self._get_val_str(c.PENDING_PROC_MODE)

    @property
    def operating_system(self):
        """String representing the OS and version, or 'Unknown'."""
        return self._get_val_str(c.OPERATING_SYSTEM_VER, 'Unknown')

    @property
    def cna_uris(self):
        """Return a list of URI strings to the LPAR's ClientNetworkAdapters.

        This is a READ ONLY list.
        """
        return self.get_href(c.CNA_LINKS)

    @property
    def rmc_state(self):
        """See ResourceMonitoringControlStateEnum.

        e.g. 'active', 'inactive', 'busy', etc.
        """
        return self._get_val_str(c.RMC_STATE)

    @property
    def ref_code(self):
        return self._get_val_str(c.REF_CODE)

    @property
    def restrictedio(self):
        return self._get_val_bool(c.RESTRICTED_IO, False)

    def check_dlpar_connectivity(self):
        """Check the partition for DLPAR capability and rmc state.

        :returns: Returns true or false if DLPAR capable
        :returns: Returns RMC state as string
        """

        # Pull the dlpar and rmc values from PowerVM
        mem_dlpar = self._get_val_bool(c.DLPAR_MEM_CAPABLE)
        proc_dlpar = self._get_val_bool(c.DLPAR_PROC_CAPABLE)

        dlpar = mem_dlpar and proc_dlpar

        return dlpar, self.rmc_state

    @desired_mem.setter
    def desired_mem(self, value):
        self.set_parm_value(c.DES_MEM, value)

    @max_mem.setter
    def max_mem(self, value):
        self.set_parm_value(c.DES_MAX_MEM, value)

    @min_mem.setter
    def min_mem(self, value):
        self.set_parm_value(c.DES_MIN_MEM, value)

    @proc_compat_mode.setter
    def proc_compat_mode(self, value):
        """Sets *PENDING* proc compat mode.

        Note that corresponding getter retrieves the *CURRENT* proc compat
        mode.
        """
        self.set_parm_value(c.PENDING_PROC_MODE, value)

    @avail_priority.setter
    def avail_priority(self, value):
        self.set_parm_value(c.AVAIL_PRIORITY, value)

    @sharing_mode.setter
    def sharing_mode(self, value):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        self.set_parm_value(c.SHARING_MODE, value)

    @desired_procs.setter
    def desired_procs(self, value):
        self.set_parm_value(c.DES_PROCS, value)

    @max_procs.setter
    def max_procs(self, value):
        self.set_parm_value(c.DES_MAX_PROCS, value)

    @min_procs.setter
    def min_procs(self, value):
        self.set_parm_value(c.DES_MIN_PROCS, value)

    @desired_vcpus.setter
    def desired_vcpus(self, value):
        self.set_parm_value(c.DES_VCPU, value)

    @max_vcpus.setter
    def max_vcpus(self, value):
        self.set_parm_value(c.DES_MAX_VCPU, value)

    @min_vcpus.setter
    def min_vcpus(self, value):
        self.set_parm_value(c.DES_MIN_VCPU, value)

    @desired_proc_units.setter
    def desired_proc_units(self, value):
        self.set_parm_value(c.DES_PROC_UNITS, value)

    @max_proc_units.setter
    def max_proc_units(self, value):
        self.set_parm_value(c.MAX_PROC_UNITS, value)

    @min_proc_units.setter
    def min_proc_units(self, value):
        self.set_parm_value(c.MIN_PROC_UNITS, value)

    @uncapped_weight.setter
    def uncapped_weight(self, value):
        self.set_parm_value(c.UNCAPPED_WEIGHT, value)

    @proc_mode_is_dedicated.setter
    def proc_mode_is_dedicated(self, value):
        """Expects 'true' (string) for dedicated or 'false' for shared."""
        self.set_parm_value(c.USE_DED_PROCS, value)

    @property
    def io_config(self):
        """The Partition I/O Configuration for the LPAR."""
        elem = self.element.find(IO_CFG_ROOT)
        return PartitionIOConfiguration.wrap(elem)


class PartitionIOConfiguration(ewrap.ElementWrapper):
    """Represents the partitions Dedicated IO Configuration.

    Comprised of I/O Slots.  There are two types of IO slots.  Those dedicated
    to physical hardware (io_slots) and those that get used by virtual
    hardware.
    """
    schema_type = 'PartitionIOConfiguration'

    @property
    def max_virtual_slots(self):
        """The maximum number of virtual slots.

        A slot is used for every VirtuScsiServerAdapter, TrunkAdapter, etc...
        """
        return self._get_val_int(IO_CFG_MAX_SLOTS)

    @max_virtual_slots.setter
    def max_virtual_slots(self, value):
        self.set_parm_value(IO_CFG_MAX_SLOTS, str(value))

    @property
    def io_slots(self):
        """The physical I/O Slots.

        Each slot will have hardware associated with it.
        """
        es = ewrap.WrapperElemList(self._find_or_seed(IO_SLOTS_ROOT),
                                   IO_SLOT_ROOT, IOSlot)
        return es


class IOSlot(ewrap.ElementWrapper):
    """An I/O Slot represents a device bus on the system.

    It may contain a piece of hardware within it.
    """
    schema_type = 'ProfileIOSlot'

    class AssociatedIOSlot(ewrap.ElementWrapper):
        """Internal class.  Hides the nested AssociatedIOSlot from parent.

        Every ProfileIOSlot contains one AssociatedIOSlot.  If both are
        exposed at the API level, the user would have to go from:
         - lpar -> partition i/o config -> i/o slot -> associated i/o slot ->
           i/o data

        Since every i/o slot has a single Associated I/O Slot (unless said
        I/O slot has no associated I/O), then we can just hide this from
        the user.

        We still keep the structure internally, but makes the API easier to
        consume.
        """
        schema_type = 'AssociatedIOSlot'

        @property
        def description(self):
            return self._get_val_str(ASSOC_IO_SLOT_DESC)

        @property
        def phys_loc(self):
            return self._get_val_str(ASSOC_IO_SLOT_PHYS_LOC)

        @property
        def pc_adpt_id(self):
            return self._get_val_str(ASSOC_IO_SLOT_ADPT_ID)

        @property
        def pci_class(self):
            return self._get_val_str(ASSOC_IO_SLOT_PCI_CLASS)

        @property
        def pci_dev_id(self):
            return self._get_val_str(ASSOC_IO_SLOT_PCI_DEV_ID)

        @property
        def pci_subsys_dev_id(self):
            return self._get_val_str(ASSOC_IO_SLOT_PCI_DEV_ID)

        @property
        def pci_mfg_id(self):
            return self._get_val_str(ASSOC_IO_SLOT_PCI_MFG_ID)

        @property
        def pci_rev_id(self):
            return self._get_val_str(ASSOC_IO_SLOT_PCI_REV_ID)

        @property
        def pci_vendor_id(self):
            return self._get_val_str(ASSOC_IO_SLOT_PCI_VENDOR_ID)

        @property
        def pci_subsys_vendor_id(self):
            return self._get_val_str(ASSOC_IO_SLOT_SUBSYS_VENDOR_ID)

        @property
        def io_adapter(self):
            """Jumps over the 'Related IO Adapter' element direct to the I/O.

            This is another area where the schema has a two step jump that the
            API can avoid.  This method skips over the RelatedIOAdapter
            and jumps right to the IO Adapter.

            Return values are either the generic IOAdapter or the
            PhysFCAdapter.
            """
            # The child can be either an IO Adapter or a PhysFCAdapter.
            # Need to check for both...
            io_adpt_root = self._find(RELATED_IO_ADPT_ROOT + c.DELIM +
                                      IO_ADPT_ROOT)
            if io_adpt_root is not None:
                return IOAdapter.wrap(io_adpt_root)

            # Didn't have the generic...check for non-generic.
            io_adpt_root = self._find(RELATED_IO_ADPT_ROOT + c.DELIM +
                                      IO_PFC_ADPT_ROOT)
            if io_adpt_root is not None:
                return PhysFCAdapter.wrap(io_adpt_root)

            return None

    def __get_prop(self, func):
        """Thin wrapper to get the Associated I/O Slot and get a property."""
        elem = self._find(ASSOC_IO_SLOT_ROOT)
        if elem is None:
            return None

        # Build the Associated IO Slot, find the function and execute it.
        assoc_io_slot = self.AssociatedIOSlot.wrap(elem)
        return getattr(assoc_io_slot, func)

    @property
    def description(self):
        return self.__get_prop('description')

    @property
    def phys_loc(self):
        return self.__get_prop('phys_loc')

    @property
    def pc_adpt_id(self):
        return self.__get_prop('pc_adpt_id')

    @property
    def pci_class(self):
        return self.__get_prop('pci_class')

    @property
    def pci_dev_id(self):
        return self.__get_prop('pci_dev_id')

    @property
    def pci_subsys_dev_id(self):
        return self.__get_prop('pci_subsys_dev_id')

    @property
    def pci_mfg_id(self):
        return self.__get_prop('pci_mfg_id')

    @property
    def pci_rev_id(self):
        return self.__get_prop('pci_rev_id')

    @property
    def pci_vendor_id(self):
        return self.__get_prop('pci_vendor_id')

    @property
    def pci_subsys_vendor_id(self):
        return self.__get_prop('pci_subsys_vendor_id')

    @property
    def adapter(self):
        """Returns the physical I/O Adapter for this slot.

        This will be one of two types.  Either a generic I/O Adapter or
        a Physical Fibre Channel Adapter (PhysFCAdapter).
        """
        return self.__get_prop('io_adapter')


class IOAdapter(ewrap.ElementWrapper):
    """A generic IO Adapter,

    This is a device plugged in to the system.  The location code indicates
    where it is plugged into the system.
    """
    schema_type = 'IOAdapter'

    @property
    def id(self):
        """The adapter system id."""
        return self._get_val_str(IO_ADPT_ID)

    @property
    def description(self):
        return self._get_val_str(IO_ADPT_DESC)

    @property
    def dev_name(self):
        return self._get_val_str(IO_ADPT_DESC)

    @property
    def dyn_reconfig_conn_name(self):
        return self._get_val_str(IO_ADPT_DYN_NAME)

    @property
    def phys_loc_code(self):
        return self._get_val_str(IO_ADPT_PHYS_LOC)


class PhysFCAdapter(IOAdapter):
    """A Physical Fibre Channel I/O Adapter.

    Extends the generic I/O Adapter, but provides port detail as well.

    The adapter has a set of Physical Fibre Channel Ports (PhysFCPort).
    """
    schema_type = 'PhysicalFibreChannelAdapter'

    @property
    def fc_ports(self):
        """The set of PhysFCPort's that are attached to this adapter.

        The data on this should be considered read only.
        """
        es = ewrap.WrapperElemList(self._find_or_seed(PFC_PORTS_ROOT),
                                   PFC_PORT_ROOT, PhysFCPort)
        return es


class PhysFCPort(ewrap.ElementWrapper):
    """A Physical Fibre Channel Port."""
    schema_type = 'PhysicalFibreChannelPort'

    @property
    def loc_code(self):
        return self._get_val_str(PFC_PORT_LOC_CODE)

    @property
    def name(self):
        return self._get_val_str(PFC_PORT_NAME)

    @property
    def udid(self):
        return self._get_val_str(PFC_PORT_UDID)

    @property
    def wwpn(self):
        return self._get_val_str(PFC_PORT_WWPN)

    @property
    def npiv_available_ports(self):
        return self._get_val_int(PFC_PORT_AVAILABLE_PORTS, 0)

    @property
    def npiv_total_ports(self):
        return self._get_val_int(PFC_PORT_TOTAL_PORTS, 0)
