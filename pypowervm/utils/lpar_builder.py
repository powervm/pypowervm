# Copyright 2015 IBM Corp.
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

import six

from pypowervm.wrappers import logical_partition as lpar

# Dict keys used for input to the builder
NAME = 'name'
ENV = 'env'

MEM = 'memory'
MAX_MEM = 'max_mem'
MIN_MEM = 'min_mem'

DED_PROCS = 'dedicated_proc'
VCPU = 'vcpu'
MAX_VCPU = 'max_vcpu'
MIN_VCPU = 'min_vcpu'

PROC_UNITS = 'proc_units'
MAX_PROC_U = 'max_proc_units'
MIN_PROC_U = 'min_proc_units'

SHARING_MODE = 'sharing_mode'
UNCAPPED_WEIGHT = 'uncapped_weight'
SPP = 'proc_pool'
MAX_IO_SLOTS = 'max_io_slots'

MINIMUM_ATTRS = (NAME, ENV, MEM, VCPU)


class LPARBuilderException(Exception):
    pass


@six.add_metaclass(abc.ABCMeta)
class Standardize(object):
    def __init__(self, attr):
        self.attr = attr

    def general(self):
        pass

    def memory(self):
        pass

    def dedicated_proc(self):
        pass

    def shr_proc(self):
        pass


class DefaultStandardize(Standardize):
    def __init__(self, attr, proc_units_factor=0.5, max_slots=64,
                 uncapped_weight=128, spp=0):
        super(DefaultStandardize, self).__init__(attr)
        self.proc_units_factor = proc_units_factor
        self.max_slots = max_slots
        self.uncapped_weight = uncapped_weight
        self.spp = spp

    def _set_prop(self, attr, prop, base_prop):
        attr[prop] = self.attr.get(prop, self.attr[base_prop])

    def _set_val(self, attr, prop, value):
        attr[prop] = self.attr.get(prop, value)

    def general(self):
        attr = {NAME: self.attr[NAME]}
        self._set_val(attr, ENV, lpar.LPARTypeEnum.AIXLINUX)
        self._set_val(attr, MAX_IO_SLOTS, self.max_slots)
        return attr

    def memory(self):
        attr = {MEM: self.attr[MEM]}
        self._set_prop(attr, MAX_MEM, MEM)
        self._set_prop(attr, MIN_MEM, MEM)
        return attr

    def shr_proc(self):
        attr = {VCPU: self.attr[VCPU]}
        self._set_prop(attr, MAX_VCPU, VCPU)
        self._set_prop(attr, MIN_VCPU, VCPU)

        proc_units = int(attr[VCPU]) * self.proc_units_factor
        self._set_val(attr, PROC_UNITS, proc_units)
        self._set_val(attr, MIN_PROC_U, proc_units)
        self._set_val(attr, MAX_PROC_U, proc_units)
        self._set_val(attr, SHARING_MODE, lpar.SharingModesEnum.UNCAPPED)

        if attr.get(SHARING_MODE) == lpar.SharingModesEnum.UNCAPPED:
            self._set_val(attr, UNCAPPED_WEIGHT, self.uncapped_weight)
        self._set_val(attr, SPP, self.spp)
        return attr

    def ded_proc(self):
        # Set the proc based on vcpu field
        attr = {VCPU: self.attr[VCPU]}
        self._set_prop(attr, MAX_VCPU, VCPU)
        self._set_prop(attr, MIN_VCPU, VCPU)
        self._set_val(attr, SHARING_MODE,
                      lpar.DedicatedSharingModesEnum.SHARE_IDLE_PROCS)
        return attr


class LPARBuilder(object):
    def __init__(self, attr, stdz):
        self.attr = attr
        self.stdz = stdz
        for attr in MINIMUM_ATTRS:
            if self.attr.get(attr) is None:
                raise LPARBuilderException('Missing required attribute: %s'
                                           % attr)

    def build_ded_proc(self):
        std = self.stdz.ded_proc()
        dproc = lpar.PartitionProcessorConfiguration.bld_dedicated(
            std[VCPU], min_proc=std[MIN_VCPU], max_proc=std[MAX_VCPU],
            sharing_mode=std[SHARING_MODE])
        return dproc

    def build_shr_proc(self):
        std = self.stdz.shr_proc()
        shr_proc = lpar.PartitionProcessorConfiguration.bld_shared(
            std[PROC_UNITS], std[VCPU], sharing_mode=std[SHARING_MODE],
            uncapped_weight=std[UNCAPPED_WEIGHT],
            min_proc_unit=std[MIN_PROC_U], max_proc_unit=std[MAX_PROC_U],
            min_proc=std[MIN_VCPU], max_proc=std[MAX_VCPU], proc_pool=std[SPP])
        return shr_proc

    def build_mem(self):
        std = self.stdz.memory()
        mem_wrap = lpar.PartitionMemoryConfiguration.bld(
            std[MEM], min_mem=std[MIN_MEM], max_mem=std[MAX_MEM])
        return mem_wrap

    def build(self):
        # Build a minimimal LPAR, the real work will be done in _rebuild
        std = self.stdz.general()

        lpar_w = lpar.LPAR.bld(
            std[NAME], lpar.PartitionMemoryConfiguration.bld(0),
            lpar.PartitionProcessorConfiguration.bld_dedicated(0),
            io_cfg=lpar.PartitionIOConfiguration.bld(0),
            env=std[ENV])
        return self._rebuild(lpar_w)

    def rebuild(self, existing):
        return self._rebuild(existing)

    def _rebuild(self, lpar_w):
        # Build the memory section
        mem_cfg = self.build_mem()

        # Build proc section
        if self.attr.get(DED_PROCS, False):
            proc_cfg = self.build_ded_proc()
        else:
            proc_cfg = self.build_shr_proc()

        std = self.stdz.general()
        io_cfg = lpar.PartitionIOConfiguration.bld(std[MAX_IO_SLOTS])

        # Now start replacing the sections
        lpar_w.mem_config = mem_cfg
        lpar_w.proc_config = proc_cfg
        lpar_w.io_config = io_cfg
        return lpar_w
