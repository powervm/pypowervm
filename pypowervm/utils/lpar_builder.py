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
import logging
import types

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
DED_PROC_KEYS = ()

PROC_UNITS = 'proc_units'
MAX_PROC_U = 'max_proc_units'
MIN_PROC_U = 'min_proc_units'
PROC_UNITS_KEYS = (PROC_UNITS, MAX_PROC_U, MIN_PROC_U)

SHARING_MODE = 'sharing_mode'
UNCAPPED_WEIGHT = 'uncapped_weight'
SPP = 'proc_pool'
MAX_IO_SLOTS = 'max_io_slots'

# The minimum attributes that must be supplied to create an LPAR
MINIMUM_ATTRS = (NAME, MEM, VCPU)
# Keys that indicate that shared processors are being configured
SHARED_PROC_KEYS = PROC_UNITS_KEYS + (UNCAPPED_WEIGHT,)

MEM_LOW_BOUND = 128
VCPU_LOW_BOUND = 1
PROC_UNITS_LOW_BOUND = 0.05
MAX_LPAR_NAME_LEN = 40  # TODO(IBM): validate this value.

LOG = logging.getLogger(__name__)

# TODO(IBM) translation
_LE = lambda x: x


class LPARBuilderException(Exception):
    """Exceptions thrown from the lpar builder."""
    pass


@six.add_metaclass(abc.ABCMeta)
class Standardize(object):
    """Interface class to standardize the LPAR definition

    A standardizer is responsible for validating the LPAR attributes
    that are presented and augmenting those which are required to create
    the LPAR.
    """
    def __init__(self, attr):
        self.attr = attr

    def general(self):
        """Validates and standardizes the general LPAR attributes.

        :returns: dict of attributes.
            Expected: NAME, ENV, MAX_IO_SLOTS
        """
        pass

    def memory(self):
        """Validates and standardizes the memory LPAR attributes.

        :returns: dict of attributes.
            Expected: MEM, MIN_MEM, MAX_MEM
        """
        pass

    def ded_proc(self):
        """Validates and standardizes the dedicated processor LPAR attributes.

        :returns: dict of attributes.
            Expected: VCPU, MIN_VCPU, MAX_VCPU, SHARING_MODE
        """
        pass

    def shr_proc(self):
        """Validates and standardizes the shared processor LPAR attributes.

        :returns: dict of attributes.
            Expected: VCPU, MIN_VCPU, MAX_VCPU, PROC_UNITS, MAX_PROC_U,
                      MIN_PROC_U, SHARING_MODE,
                      UNCAPPED_WEIGHT(if UNCAPPED)
        """
        pass


class DefaultStandardize(Standardize):
    """Default standardizer.

    This class implements the Standardizer interface.  It takes a
    simple approach for augmenting missing LPAR settings.  It does
    reasonable validation of the LPAR attributes.

    """
    def __init__(self, attr, mngd_sys,
                 proc_units_factor=0.5, max_slots=64,
                 uncapped_weight=128, spp=0):
        """Initialize the standardizer

        :param attr: dict of lpar attributes provided by the user
        :param mngd_sys: managed_system wrapper of the host to deploy to.
            This is used to validate the fields and standardize against the
            host.
        :param proc_units_factor: amount of proc units to assign to each vcpu
            if proc units are not specified
        :param max_slots: number of max io slots to assign, if not specified
        :param uncapped_weight: the uncapped weight to use if the processors
            are shared and a weight is not specified
        :param spp: shared processor pool to assign if the processors are
            shared and the pool is not specified
        """

        super(DefaultStandardize, self).__init__(attr)
        self.mngd_sys = mngd_sys
        self.proc_units_factor = proc_units_factor
        self.max_slots = max_slots
        self.uncapped_weight = uncapped_weight
        self.spp = spp

    def _set_prop(self, attr, prop, base_prop):
        """Copies a property if present or copies the base property."""
        attr[prop] = self.attr.get(prop, self.attr[base_prop])

    def _set_val(self, attr, prop, value):
        """Copies a property if present or uses the supplied value."""
        attr[prop] = self.attr.get(prop, value)

    def validate_general(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr
        name_len = len(attrs[NAME])
        if name_len < 1 or name_len > MAX_LPAR_NAME_LEN:

            msg = _LE("Logical partition name has invalid length."
                      " Name: %s") % attrs[NAME]
            raise LPARBuilderException(msg)
        LPARType(attrs.get(ENV), allow_none=partial).validate()
        IOSlots(attrs.get(MAX_IO_SLOTS), allow_none=partial).validate()

    def validate_memory(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr
        mem = Memory(attrs.get(MIN_MEM), attrs.get(MEM), attrs.get(MAX_MEM),
                     self.mngd_sys.memory_region_size, allow_none=partial)
        mem.validate()

    def validate_shared_proc(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr

        # Validate the vcpu first
        VCpu(attrs.get(MIN_VCPU), attrs.get(VCPU), attrs.get(MAX_VCPU),
             partial).validate()
        # Validate the proc units
        ProcUnits(attrs.get(MIN_PROC_U), attrs.get(PROC_UNITS),
                  attrs.get(MAX_PROC_U), allow_none=partial).validate()
        # TODO(IBM): Validate any shared CPU associated parameters

    def validate_lpar_ded_cpu(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr

        VCpu(attrs.get(MIN_VCPU), attrs.get(VCPU), attrs.get(MAX_VCPU),
             allow_none=partial).validate()

        # If specified, ensure the dedicated procs value is valid
        DedicatedProc(attrs.get(DED_PROCS), allow_none=True).validate()

    def general(self):
        # Validate the settings sent in
        self.validate_general(partial=True)

        attr = {NAME: self.attr[NAME]}
        self._set_val(attr, ENV, lpar.LPARTypeEnum.AIXLINUX)
        self._set_val(attr, MAX_IO_SLOTS, self.max_slots)

        # Validate the attributes
        self.validate_general(attrs=attr)
        return attr

    def memory(self):
        # Validate the partial settings
        self.validate_memory(partial=True)

        attr = {MEM: self.attr[MEM]}
        self._set_prop(attr, MAX_MEM, MEM)
        self._set_prop(attr, MIN_MEM, MEM)

        # Validate the full memory settings
        self.validate_memory(attrs=attr)
        return attr

    def shr_proc(self):
        # Validate the partial settings
        self.validate_shared_proc(partial=True)

        attr = {VCPU: self.attr[VCPU]}
        self._set_prop(attr, MAX_VCPU, VCPU)
        self._set_prop(attr, MIN_VCPU, VCPU)

        proc_units = int(attr[VCPU]) * self.proc_units_factor
        self._set_val(attr, PROC_UNITS, proc_units)
        self._set_val(attr, MIN_PROC_U, proc_units)
        self._set_val(attr, MAX_PROC_U, proc_units)
        self._set_val(attr, SHARING_MODE, lpar.SharingModesEnum.UNCAPPED)

        # If uncapped sharing mode then set the weight
        if attr.get(SHARING_MODE) == lpar.SharingModesEnum.UNCAPPED:
            self._set_val(attr, UNCAPPED_WEIGHT, self.uncapped_weight)
        self._set_val(attr, SPP, self.spp)

        # Validate all the values
        self.validate_shared_proc(attrs=attr)
        return attr

    def ded_proc(self):
        self.validate_lpar_ded_cpu(partial=True)
        # Set the proc based on vcpu field
        attr = {VCPU: self.attr[VCPU]}
        self._set_prop(attr, MAX_VCPU, VCPU)
        self._set_prop(attr, MIN_VCPU, VCPU)
        self._set_val(attr, SHARING_MODE,
                      lpar.DedicatedSharingModesEnum.SHARE_IDLE_PROCS)
        self.validate_lpar_ded_cpu(attrs=attr)
        return attr


@six.add_metaclass(abc.ABCMeta)
class Field(object):
    """Represents a field to validate."""
    type_ = str

    def __init__(self, name, value, allow_none=True):
        self.name = name
        self.value = value
        self.typed_value = None
        self.allow_none = allow_none

    def _type_error(self, value, exc=TypeError):
        values = dict(field=self.name, value=value)
        msg = _LE('Field %(field)s has invalid value: %(value)s') % values
        LOG.error(msg)
        raise exc(msg)

    def convert_value(self, value):
        """Does the actual conversion of the value and returns it."""
        try:
            return self.type_(value)
        except (TypeError, ValueError) as e:
            self._type_error(value, exc=e.__class__)

    def convert(self):
        """Converts the value and saves it away for future use."""
        self.typed_value = self.convert_value(self.value)

    def validate(self):
        # Check if the value is none and we allow that
        if self.value is None:
            if not self.allow_none:
                self._type_error(None)
        else:
            # The base value is not none, so see if we should convert it
            if self.typed_value is None:
                self.convert()


@six.add_metaclass(abc.ABCMeta)
class BoolField(Field):
    """Facilitates validating boolean fields."""
    type_ = bool

    def __init__(self, name, value, allow_none=True):
        super(BoolField, self).__init__(name, value, allow_none=allow_none)

    def convert_value(self, value):
        # Special case string values, so random strings don't map to True
        if isinstance(value, types.StringTypes):
            return value.lower() in ['true', 'yes']
        try:
            return self.type_(value)
        except TypeError:
            self._type_error(value)


@six.add_metaclass(abc.ABCMeta)
class ChoiceField(Field):
    _choices = None

    def convert_value(self, value):
        if value is None:
            self._type_error(value)
        value = value.lower()
        for choice in self._choices:
            if value == choice.lower():
                return choice

        # If we didn't find it, that's a problem...
        self._type_error(value)


@six.add_metaclass(abc.ABCMeta)
class BoundField(Field):
    min_bound = None
    max_bound = None

    def __init__(self, name, value, allow_none=False):
        super(BoundField, self).__init__(name, value, allow_none=allow_none)

    def validate(self):
        super(BoundField, self).validate()
        # If value was not converted to the type, then don't validate bounds
        if self.typed_value is None:
            return
        if (self.min_bound is not None and
                self.typed_value < self.convert_value(self.min_bound)):
            values = dict(field=self.name, value=self.typed_value,
                          minimum=self.min_bound)
            msg = _LE("Field '%(field)s' has a value below the minimum. "
                      "Value: %(value)s Minimum: %(minimum)s") % values
            LOG.error(msg)
            raise ValueError(msg)

        if (self.max_bound is not None and
                self.typed_value > self.convert_value(self.max_bound)):
            values = dict(field=self.name, value=self.typed_value,
                          maximum=self.max_bound)
            msg = _LE("Field '%(field)s' has a value above the maximum. "
                      "Value: %(value)s Maximum: %(maximum)s") % values

            LOG.error(msg)
            raise ValueError(msg)


@six.add_metaclass(abc.ABCMeta)
class IntBoundField(BoundField):
    type_ = int


@six.add_metaclass(abc.ABCMeta)
class FloatBoundField(BoundField):
    type_ = float


@six.add_metaclass(abc.ABCMeta)
class MinDesiredMaxField(object):

    def __init__(self, name, field_type, min_name, des_name, max_name,
                 min_value, desired_value, max_value,
                 min_min=None, max_max=None,
                 allow_none=True):
        self.name = name

        self.min_field = field_type(min_name, min_value, allow_none=allow_none)
        self.min_field.max_bound = desired_value
        self.min_field.min_bound = min_min

        self.des_field = field_type(
            des_name, desired_value, allow_none=allow_none)
        self.des_field.min_bound = min_value
        self.des_field.max_bound = max_value

        self.max_field = field_type(max_name, max_value, allow_none=allow_none)
        self.max_field.min_bound = desired_value
        self.max_field.max_bound = max_max

    def validate(self):
        # Do specific validations before the general ones
        for fld in [self.min_field, self.des_field, self.max_field]:
            if fld.value is not None or not fld.allow_none:
                fld.convert()

        # Ensure the desired value is between the min and max
        if all([self.des_field.typed_value, self.max_field.typed_value,
               self.des_field.typed_value > self.max_field.typed_value]):
            values = dict(desired_field=self.des_field.name,
                          max_field=self.max_field.name,
                          desired=self.des_field.typed_value,
                          maximum=self.max_field.typed_value)
            msg = _LE("The '%(desired_field)s' has a value above the "
                      "'%(max_field)s' value. "
                      "Desired: %(desired)s Maximum: %(maximum)s") % values

            LOG.error(msg)
            raise ValueError(msg)
        # Now the minimum
        if all([self.des_field.typed_value, self.min_field.typed_value,
               self.des_field.typed_value < self.min_field.typed_value]):
            values = dict(desired_field=self.des_field.name,
                          min_field=self.min_field.name,
                          desired=self.des_field.typed_value,
                          minimum=self.min_field.typed_value)
            msg = _LE("The '%(desired_field)s' has a value below the "
                      "'%(min_field)s' value. "
                      "Desired: %(desired)s Minimum: %(minimum)s") % values

            LOG.error(msg)
            raise ValueError(msg)

        # Now the fields individually
        self.min_field.validate()
        self.des_field.validate()
        self.max_field.validate()


class Memory(MinDesiredMaxField):
    def __init__(self, min_value, desired_value, max_value, lmb_size,
                 allow_none=True):
        super(Memory, self).__init__(
            'Memory', IntBoundField, 'Minimum Memory', 'Desired Memory',
            'Maximum Memory', min_value, desired_value, max_value,
            allow_none=allow_none)
        self.lmb_size = lmb_size
        # Set the lowest memory we'll honor
        self.min_field.min_bound = MEM_LOW_BOUND
        # Don't allow the desired memory to not be specified.
        self.des_field.allow_none = False

    def validate(self):
        super(Memory, self).validate()
        # Validate against the LMB size
        if self.lmb_size is not None:
            # For each value, make sure it's a multiple
            for x in [self.min_field.typed_value,
                      self.des_field.typed_value,
                      self.max_field.typed_value]:
                if x is not None and (x % self.lmb_size) != 0:
                    values = dict(lmb_size=self.lmb_size, value=x)
                    msg = _LE("Memory value is not a multiple of the "
                              "logical memory block size (%(lmb_size)s) of "
                              " the host.  Value: %(value)s") % values
                    LOG.error(msg)
                    raise ValueError(msg)


class VCpu(MinDesiredMaxField):
    def __init__(self, min_value, desired_value, max_value, allow_none=True):
        super(VCpu, self).__init__(
            'VCPU', IntBoundField, 'Minimum VCPU', 'Desired VCPU',
            'Maximum VCPU', min_value, desired_value, max_value,
            allow_none=allow_none)
        # Set the lowest VCPU we'll honor
        self.min_field.min_bound = VCPU_LOW_BOUND


class ProcUnits(MinDesiredMaxField):
    def __init__(self, min_value, desired_value, max_value, allow_none=True):
        super(ProcUnits, self).__init__(
            'ProcUnits', FloatBoundField, 'Minimum Proc Units',
            'Desired Proc Units', 'Maximum Proc Units', min_value,
            desired_value, max_value,
            allow_none=allow_none)
        # Set the lowest ProcUnits we'll honor
        self.min_field.min_bound = PROC_UNITS_LOW_BOUND


class DedicatedProc(BoolField):
    def __init__(self, value, allow_none=True):
        super(DedicatedProc, self).__init__(
            'Dedicated Processors', value, allow_none=allow_none)


class LPARType(ChoiceField):
    _choices = (lpar.LPARTypeEnum.AIXLINUX, lpar.LPARTypeEnum.OS400)

    def __init__(self, value, allow_none=False):
        super(LPARType, self).__init__('Logical Partition Type', value,
                                       allow_none=allow_none)


class IOSlots(IntBoundField):
    min_bound = 2  # slot 0 & 1 are always in use
    max_bound = 65534

    def __init__(self, value, allow_none=False):
        super(IOSlots, self).__init__('I/O Slots', value,
                                      allow_none=allow_none)


class LPARBuilder(object):
    def __init__(self, attr, stdz):
        self.attr = attr
        self.stdz = stdz
        for attr in MINIMUM_ATTRS:
            if self.attr.get(attr) is None:
                raise LPARBuilderException('Missing required attribute: %s'
                                           % attr)

    def build_ded_proc(self):
        # Ensure no shared proc keys are present
        # TODO(IBM):

        std = self.stdz.ded_proc()
        dproc = lpar.PartitionProcessorConfiguration.bld_dedicated(
            std[VCPU], min_proc=std[MIN_VCPU], max_proc=std[MAX_VCPU],
            sharing_mode=std[SHARING_MODE])
        return dproc

    def build_shr_proc(self):
        # Ensure no dedicated proc keys are present
        # TODO(IBM):

        std = self.stdz.shr_proc()
        # The weight may not be set if it's not uncapped
        uncapped_weight = std.get(UNCAPPED_WEIGHT)
        # Build the shared procs
        shr_proc = lpar.PartitionProcessorConfiguration.bld_shared(
            std[PROC_UNITS], std[VCPU], sharing_mode=std[SHARING_MODE],
            uncapped_weight=uncapped_weight,
            min_proc_unit=std[MIN_PROC_U], max_proc_unit=std[MAX_PROC_U],
            min_proc=std[MIN_VCPU], max_proc=std[MAX_VCPU], proc_pool=std[SPP])
        return shr_proc

    def build_mem(self):
        std = self.stdz.memory()
        mem_wrap = lpar.PartitionMemoryConfiguration.bld(
            std[MEM], min_mem=std[MIN_MEM], max_mem=std[MAX_MEM])
        return mem_wrap

    def _shared_proc_keys_specified(self):
        # Check for any shared proc keys
        for key in SHARED_PROC_KEYS:
            if self.attr.get(key, None) is not None:
                return True

        # Check the sharing mode values if any
        smode = self.attr.get(SHARING_MODE, None)
        if (smode is not None and
                smode in lpar.SharingModesEnum.ALL_MODES):
            return True

        return False

    def _dedicated_proc_keys_specified(self):
        # Check for dedicated proc keys
        # TODO(IBM):

        # Check for dedicated sharing mode
        smode = self.attr.get(SHARING_MODE, None)
        if (smode is not None and
                smode in lpar.DedicatedSharingModesEnum.ALL_MODES):
                return True

    def _shared_procs_specified(self):
        """Determine if shared procs should be configured.

        General methodology is to try to check everything that would
        indicate shared processors first, then dedicated, and finally
        just default to shared if we can't determine either way.
        """
        if self.attr.get(DED_PROCS, None) is not None:
            return not self.attr[DED_PROCS]

        # Check each key that would indicate sharing procs
        if self._shared_proc_keys_specified():
            return True

        # Check for dedicated sharing mode
        if self._dedicated_proc_keys_specified():
            return False

        # Default is to use shared if not proven otherwise
        return True

    def build(self):
        # Build a minimimal LPAR, the real work will be done in _rebuild
        std = self.stdz.general()

        lpar_w = lpar.LPAR.bld(
            std[NAME], lpar.PartitionMemoryConfiguration.bld(0),
            lpar.PartitionProcessorConfiguration.bld_dedicated(0),
            io_cfg=lpar.PartitionIOConfiguration.bld(0),
            env=std[ENV])
        return self.rebuild(lpar_w)

    def rebuild(self, lpar_w):
        # Build the memory section
        mem_cfg = self.build_mem()

        # Build proc section
        # Determine if using shared or dedicated processors
        if self._shared_procs_specified():
            proc_cfg = self.build_shr_proc()
        else:
            proc_cfg = self.build_ded_proc()

        std = self.stdz.general()
        io_cfg = lpar.PartitionIOConfiguration.bld(std[MAX_IO_SLOTS])

        # Now start replacing the sections
        lpar_w.mem_config = mem_cfg
        lpar_w.proc_config = proc_cfg
        lpar_w.io_config = io_cfg
        return lpar_w
