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
import pypowervm.util as u
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

    @property
    def state(self):
        """See LogicalPartitionStateEnum.

        e.g. 'not activated', 'running', 'migrating running', etc.
        """
        partition_state = self.get_parm_value(c.PARTITION_STATE)
        return partition_state

    @property
    def name(self):
        """Short name (not ID, MTMS, or hostname)."""
        return self.get_parm_value(c.PARTITION_NAME)

    @property
    def id(self):
        """Short ID (not UUID)."""
        return int(self.get_parm_value(c.PARTITION_ID, c.ZERO))

    @property
    def env(self):
        """See LogicalPartitionEnvironmentEnum.

        Should always be 'AIX/Linux' for LPAREntry.  'Virtual IO Server'
        should only happen for VIOSEntry.
        """
        return self.get_parm_value(c.PARTITION_TYPE)

    @property
    def current_mem(self):
        return self.get_parm_value(c.CURR_MEM, c.ZERO)

    @property
    def current_max_mem(self):
        return self.get_parm_value(c.CURR_MAX_MEM, c.ZERO)

    @property
    def current_min_mem(self):
        return self.get_parm_value(c.CURR_MIN_MEM, c.ZERO)

    @property
    def desired_mem(self):
        return self.get_parm_value(c.DES_MEM, c.ZERO)

    @property
    def max_mem(self):
        return self.get_parm_value(c.DES_MAX_MEM, c.ZERO)

    @property
    def min_mem(self):
        return self.get_parm_value(c.DES_MIN_MEM, c.ZERO)

    @property
    def run_mem(self):
        return self.get_parm_value(c.RUN_MEM, c.ZERO)

    @property
    def current_mem_share_enabled(self):
        # The default is None instead of False so that the caller
        # can know if the value is not set
        return self.get_parm_value(c.SHARED_MEM_ENABLED, converter=u.str2bool)

    @property
    def current_proc_mode_is_dedicated(self):
        """Returns True (bool) if dedicated or False if shared."""
        return self.get_parm_value(c.CURR_USE_DED_PROCS, converter=u.str2bool)

    @property
    def proc_mode_is_dedicated(self):
        """Returns True (bool) if dedicated or False if shared."""
        # TODO(efried): change to boolean
        return self.get_parm_value(c.USE_DED_PROCS, converter=u.str2bool)

    @property
    def current_procs(self):
        return self.get_parm_value(c.CURR_PROCS, c.ZERO)

    @property
    def current_max_procs(self):
        return self.get_parm_value(c.CURR_MAX_PROCS, c.ZERO)

    @property
    def current_min_procs(self):
        return self.get_parm_value(c.CURR_MIN_PROCS, c.ZERO)

    @property
    def desired_procs(self):
        return self.get_parm_value(c.DES_PROCS, c.ZERO)

    @property
    def max_procs(self):
        return self.get_parm_value(c.DES_MAX_PROCS, c.ZERO)

    @property
    def min_procs(self):
        return self.get_parm_value(c.DES_MIN_PROCS, c.ZERO)

    @property
    def current_vcpus(self):
        return self.get_parm_value(c.CURR_VCPU, c.ZERO)

    @property
    def current_max_vcpus(self):
        return self.get_parm_value(c.CURR_MAX_VCPU, c.ZERO)

    @property
    def current_min_vcpus(self):
        return self.get_parm_value(c.CURR_MIN_VCPU, c.ZERO)

    @property
    def desired_vcpus(self):
        return self.get_parm_value(c.DES_VCPU, c.ZERO)

    @property
    def max_vcpus(self):
        return self.get_parm_value(c.DES_MAX_VCPU, c.ZERO)

    @property
    def min_vcpus(self):
        return self.get_parm_value(c.DES_MIN_VCPU, c.ZERO)

    @property
    def current_proc_units(self):
        return self.get_parm_value(c.CURR_PROC_UNITS, c.ZERO)

    @property
    def current_max_proc_units(self):
        return self.get_parm_value(c.CURR_MAX_PROC_UNITS, c.ZERO)

    @property
    def current_min_proc_units(self):
        return self.get_parm_value(c.CURR_MIN_PROC_UNITS, c.ZERO)

    @property
    def desired_proc_units(self):
        return self.get_parm_value(c.DES_PROC_UNITS, c.ZERO)

    @property
    def max_proc_units(self):
        return self.get_parm_value(c.MAX_PROC_UNITS, c.ZERO)

    @property
    def min_proc_units(self):
        return self.get_parm_value(c.MIN_PROC_UNITS, c.ZERO)

    @property
    def run_procs(self):
        return self.get_parm_value(c.RUN_PROCS, c.ZERO)

    @property
    def run_vcpus(self):
        return self.get_parm_value(c.RUN_VCPU, c.ZERO)

    @property
    def current_uncapped_weight(self):
        return self.get_parm_value(c.CURR_UNCAPPED_WEIGHT, c.ZERO)

    @property
    def uncapped_weight(self):
        return self.get_parm_value(c.UNCAPPED_WEIGHT, c.ZERO)

    @property
    def shared_proc_pool_id(self):
        return int(self.get_parm_value(c.SHARED_PROC_POOL_ID, c.ZERO))

    @property
    def avail_priority(self):
        return self.get_parm_value(c.AVAIL_PRIORITY, c.ZERO)

    @property
    def sharing_mode(self):
        """Sharing mode.

        Note that the getter retrieves the CURRENT sharing mode; and the
        setter sets the (PENDING) sharing mode.
        """
        return self.get_parm_value(c.CURR_SHARING_MODE)

    @property
    def migration_state(self):
        """See PartitionMigrationStateEnum.

        e.g. 'Not_Migrating', 'Migration_Starting', 'Migration_Failed', etc.
        Defaults to 'Not_Migrating'
        """
        return self.get_parm_value(c.MIGRATION_STATE, 'Not_Migrating')

    @property
    def proc_compat_mode(self):
        """*Current* processor compatibility mode.

        See LogicalPartitionProcessorCompatibilityModeEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self.get_parm_value(c.CURRENT_PROC_MODE)

    @property
    def pending_proc_compat_mode(self):
        """Pending processor compatibility mode.

        See LogicalPartitionProcessorCompatibilityModeEnum.  E.g. 'POWER7',
        'POWER7_Plus', 'POWER8', etc.
        """
        return self.get_parm_value(c.PENDING_PROC_MODE)

    @property
    def operating_system(self):
        """String representing the OS and version, or 'Unknown'."""
        return self.get_parm_value(c.OPERATING_SYSTEM_VER, 'Unknown')

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
        return self.get_parm_value(c.RMC_STATE)

    @property
    def ref_code(self):
        return self.get_parm_value(c.REF_CODE)

    @property
    def restrictedio(self):
        return self.get_parm_value(c.RESTRICTED_IO, default=False,
                                   converter=u.str2bool)

    def check_dlpar_connectivity(self):
        """Check the partition for DLPAR capability and rmc state.

        :returns: Returns true or false if DLPAR capable
        :returns: Returns RMC state as string
        """

        # Pull the dlpar and rmc values from PowerVM
        mem_dlpar = self.get_parm_value(c.DLPAR_MEM_CAPABLE,
                                        converter=u.str2bool)
        proc_dlpar = self.get_parm_value(c.DLPAR_PROC_CAPABLE,
                                         converter=u.str2bool)

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
        return self.set_parm_value(c.UNCAPPED_WEIGHT, value)

    @proc_mode_is_dedicated.setter
    def proc_mode_is_dedicated(self, value):
        """Expects 'true' (string) for dedicated or 'false' for shared."""
        self.set_parm_value(c.USE_DED_PROCS, value)
