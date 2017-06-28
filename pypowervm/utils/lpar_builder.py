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

"""Construction and basic validation of an LPAR or VIOS EntryWrapper."""

import abc
import six

from oslo_log import log as logging

from pypowervm import i18n
from pypowervm.wrappers import base_partition as bp
from pypowervm.wrappers import logical_partition as lpar
from pypowervm.wrappers import virtual_io_server as vios

# Dict keys used for input to the builder
NAME = 'name'
ENV = 'env'
UUID = 'uuid'
ID = 'id'

MEM = 'memory'
MAX_MEM = 'max_mem'
MIN_MEM = 'min_mem'
AME_FACTOR = 'ame_factor'

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
AVAIL_PRIORITY = 'avail_priority'
SRR_CAPABLE = 'srr_capability'
PROC_COMPAT = 'processor_compatibility'

# IBMi specific keys
ALT_LOAD_SRC = 'alt_load_src'
CONSOLE = 'console'
LOAD_SRC = 'load_src'
RESTRICTED_IO = 'restricted_io'

# The minimum attributes that must be supplied to create an LPAR
MINIMUM_ATTRS = (NAME, MEM, VCPU)
# Keys that indicate that shared processors are being configured
SHARED_PROC_KEYS = (PROC_UNITS_KEYS + (UNCAPPED_WEIGHT,))

MEM_LOW_BOUND = 128
VCPU_LOW_BOUND = 1
PROC_UNITS_LOW_BOUND = 0.05
MAX_LPAR_NAME_LEN = 31

# Defaults
DEF_PROC_UNIT_FACT = 0.5
DEF_MAX_SLOT = 64
DEF_UNCAPPED_WT = 64
DEF_SPP = 0
DEF_AVAIL_PRI = 127
DEF_SRR = 'false'

LOG = logging.getLogger(__name__)

# TODO(IBM) translation
_LE = i18n._


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
    def __init__(self):
        self.attr = None

    def set_attr(self, attr):
        """Set the attributes to be validated and standardized.

        :param attr: dict of lpar attributes provided by the user
        """
        self.attr = attr

    def general(self):
        """Validates and standardizes the general LPAR attributes.

        :returns: dict of attributes.
            Expected: NAME, ENV, MAX_IO_SLOTS, AVAIL_PRIORITY,
                      PROC_COMPAT
            Optional: SRR_CAPABLE, UUID, ID
                      IBMi value: CONSOLE, LOAD_SRC, ALT_LOAD_SRC,
                                  RESTRICTED_IO
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

    It first validates the user input as-is, then fills in any missing
    attributes that are required and supported by the host.  Finally,
    it validates what it's sending back to the caller.  If any validation
    rules are missed, the PowerVM management interface will catch them
    and surface an error at that time.

    """
    def __init__(self, mngd_sys,
                 proc_units_factor=DEF_PROC_UNIT_FACT, max_slots=DEF_MAX_SLOT,
                 uncapped_weight=DEF_UNCAPPED_WT, spp=DEF_SPP,
                 avail_priority=DEF_AVAIL_PRI, srr=DEF_SRR,
                 proc_compat=bp.LPARCompat.DEFAULT):
        """Initialize the standardizer

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
        :param avail_priority: availability priority of the LPAR
        :param srr: simplified remote restart capable
        :param proc_compat: processor compatibility mode value
        """

        super(DefaultStandardize, self).__init__()
        self.mngd_sys = mngd_sys
        self.proc_units_factor = proc_units_factor
        if proc_units_factor > 1 or proc_units_factor < 0.05:
            msg = _LE('Processor units factor must be between 0.05 and 1.0. '
                      'Value: %s') % proc_units_factor
            raise LPARBuilderException(msg)
        self.max_slots = max_slots
        self.uncapped_weight = uncapped_weight
        self.spp = spp
        self.avail_priority = avail_priority
        self.srr = srr
        self.proc_compat = proc_compat

    def _set_prop(self, attr, prop, base_prop, convert_func=str):
        """Copies a property if present or copies the base property."""
        attr[prop] = convert_func(self.attr.get(prop, self.attr[base_prop]))

    def _set_val(self, attr, prop, value=None, convert_func=str):
        """Copies a property if present or uses the supplied value."""
        val = self.attr.get(prop, value)
        if val is not None:
            attr[prop] = convert_func(val)

    def _validate_general(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr
        name_len = len(attrs[NAME])
        if name_len < 1 or name_len > MAX_LPAR_NAME_LEN:

            msg = _LE("Logical partition name has invalid length."
                      " Name: %s") % attrs[NAME]
            raise LPARBuilderException(msg)
        LPARType(attrs.get(ENV), allow_none=partial).validate()
        IOSlots(attrs.get(MAX_IO_SLOTS), allow_none=partial).validate()
        AvailPriority(attrs.get(AVAIL_PRIORITY), allow_none=partial).validate()
        IDBoundField(attrs.get(ID), allow_none=True).validate()
        # SRR is always optional since the host may not be capable of it.
        SimplifiedRemoteRestart(attrs.get(SRR_CAPABLE),
                                allow_none=True).validate()
        ProcCompatMode(attrs.get(PROC_COMPAT),
                       host_modes=self.mngd_sys.proc_compat_modes,
                       allow_none=partial).validate()

        # Validate fields specific to IBMi
        if attrs.get(ENV, '') == bp.LPARType.OS400:
            RestrictedIO(attrs.get(RESTRICTED_IO), allow_none=True).validate()

    def _validate_memory(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr
        host_ame_cap = self.mngd_sys.get_capability(
            'active_memory_expansion_capable')
        mem = Memory(attrs.get(MIN_MEM), attrs.get(MEM), attrs.get(MAX_MEM),
                     attrs.get(AME_FACTOR), host_ame_cap,
                     self.mngd_sys.memory_region_size, allow_none=partial)
        mem.validate()

    def _validate_shared_proc(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr

        # Validate the vcpu first
        VCpu(attrs.get(MIN_VCPU), attrs.get(VCPU), attrs.get(MAX_VCPU),
             partial).validate()
        # Validate the proc units
        ProcUnits(attrs.get(MIN_PROC_U), attrs.get(PROC_UNITS),
                  attrs.get(MAX_PROC_U), allow_none=partial).validate()
        # TODO(IBM): Validate any shared CPU associated parameters

    def _validate_lpar_ded_cpu(self, attrs=None, partial=False):
        if attrs is None:
            attrs = self.attr

        VCpu(attrs.get(MIN_VCPU), attrs.get(VCPU), attrs.get(MAX_VCPU),
             allow_none=partial).validate()

        # If specified, ensure the dedicated procs value is valid
        DedicatedProc(attrs.get(DED_PROCS), allow_none=True).validate()
        DedProcShareMode(attrs.get(SHARING_MODE), allow_none=True).validate()

    def general(self):
        # Validate the settings sent in
        self._validate_general(partial=True)

        bld_attr = {NAME: self.attr[NAME]}
        self._set_val(bld_attr, ID, convert_func=int)
        self._set_val(bld_attr, UUID)
        self._set_val(bld_attr, ENV, bp.LPARType.AIXLINUX,
                      convert_func=LPARType.convert_value)
        self._set_val(bld_attr, MAX_IO_SLOTS, self.max_slots)
        self._set_val(bld_attr, AVAIL_PRIORITY, self.avail_priority)
        # See if the host is capable of SRR before setting it.
        srr_cap = self.mngd_sys.get_capability(
            'simplified_remote_restart_capable')
        if srr_cap:
            self._set_val(bld_attr, SRR_CAPABLE, self.srr,
                          convert_func=SimplifiedRemoteRestart.convert_value)
        self._set_val(bld_attr, PROC_COMPAT, bp.LPARCompat.DEFAULT,
                      convert_func=ProcCompatMode.convert_value)

        # Build IBMi attributes
        if bld_attr[ENV] == bp.LPARType.OS400:
            self._set_val(bld_attr, CONSOLE, value='HMC')
            self._set_val(bld_attr, LOAD_SRC, value='0')
            self._set_val(bld_attr, ALT_LOAD_SRC, value='NONE')
            if self.mngd_sys.get_capability('ibmi_restrictedio_capable'):
                self._set_val(bld_attr, RESTRICTED_IO, value=True,
                              convert_func=RestrictedIO.convert_value)

        # Validate the attributes
        self._validate_general(attrs=bld_attr)
        return bld_attr

    def memory(self):
        # Validate the partial settings
        self._validate_memory(partial=True)

        bld_attr = {MEM: self.attr[MEM]}
        self._set_prop(bld_attr, MAX_MEM, MEM)
        self._set_prop(bld_attr, MIN_MEM, MEM)

        # Validate the full memory settings
        self._validate_memory(attrs=bld_attr)
        return bld_attr

    def shr_proc(self):
        def _compare(prop, value, compare_func, typ):
            v1 = self.attr.get(prop)
            # Ensure the property is specified
            if v1 is None:
                return value

            # Compare
            return compare_func(typ(v1), value)

        # Validate the partial settings
        self._validate_shared_proc(partial=True)

        bld_attr = {VCPU: self.attr[VCPU]}
        self._set_prop(bld_attr, MAX_VCPU, VCPU)
        self._set_prop(bld_attr, MIN_VCPU, VCPU)

        # See if we need to calculate a default proc_units value and min/max
        # Before setting the proc units ensure it's between min/max
        spec_proc_units = self.attr.get(PROC_UNITS)
        if spec_proc_units is None:
            proc_units = int(bld_attr[VCPU]) * self.proc_units_factor

            # Ensure it's at least as large as a specified min value
            proc_units = _compare(MIN_PROC_U, proc_units, max, float)

            # Ensure it's smaller than a specified max value
            proc_units = _compare(MAX_PROC_U, proc_units, min, float)
        else:
            proc_units = float(spec_proc_units)

        self._set_val(bld_attr, PROC_UNITS, proc_units)
        self._set_val(bld_attr, MIN_PROC_U, proc_units)
        self._set_val(bld_attr, MAX_PROC_U, proc_units)
        self._set_val(bld_attr, SHARING_MODE, bp.SharingMode.UNCAPPED)

        # If uncapped sharing mode then set the weight
        if bld_attr.get(SHARING_MODE) == bp.SharingMode.UNCAPPED:
            self._set_val(bld_attr, UNCAPPED_WEIGHT, self.uncapped_weight)
        self._set_val(bld_attr, SPP, self.spp)

        # Validate all the values
        self._validate_shared_proc(attrs=bld_attr)
        return bld_attr

    def ded_proc(self):
        self._validate_lpar_ded_cpu(partial=True)
        # Set the proc based on vcpu field
        bld_attr = {VCPU: self.attr[VCPU]}
        self._set_prop(bld_attr, MAX_VCPU, VCPU)
        self._set_prop(bld_attr, MIN_VCPU, VCPU)
        self._set_val(bld_attr, SHARING_MODE,
                      bp.DedicatedSharingMode.SHARE_IDLE_PROCS,
                      convert_func=DedProcShareMode.convert_value)
        self._validate_lpar_ded_cpu(attrs=bld_attr)
        return bld_attr


@six.add_metaclass(abc.ABCMeta)
class Field(object):
    """Represents a field to validate."""
    _type = str

    def __init__(self, value, name=None, allow_none=True):
        self.name = name if name is not None else self.__class__._name
        self.value = value
        self.typed_value = None
        self.allow_none = allow_none

    @classmethod
    def convert_value(cls, value):
        """Static converter for the Field type."""
        return cls._type(value)

    def _type_error(self, value, exc=TypeError):
        values = dict(field=self.name, value=value)
        msg = _LE("Field '%(field)s' has invalid value: '%(value)s'") % values
        LOG.error(msg)
        raise exc(msg)

    def _convert_value(self, value):
        """Does the actual conversion of the value and returns it."""
        try:
            return self.convert_value(value)
        except (TypeError, ValueError) as e:
            self._type_error(value, exc=e.__class__)

    def _convert(self):
        """Converts the value and saves it away for future use."""
        self.typed_value = self._convert_value(self.value)

    def validate(self):
        # Check if the value is none and we allow that
        if self.value is None:
            if not self.allow_none:
                self._type_error(None)
        else:
            # The base value is not none, so see if we should convert it
            if self.typed_value is None:
                self._convert()


@six.add_metaclass(abc.ABCMeta)
class BoolField(Field):
    """Facilitates validating boolean fields."""
    _type = bool

    @classmethod
    def convert_value(cls, value):
        # Special case string values, so random strings don't map to True
        if isinstance(value, six.string_types):
            if value.lower() in ['true', 'yes']:
                return True
            if value.lower() in ['false', 'no']:
                return False
        elif isinstance(value, bool):
                return value
        raise ValueError('Could not convert %s.' % value)


@six.add_metaclass(abc.ABCMeta)
class ChoiceField(Field):
    _choices = None

    @classmethod
    def convert_value(cls, value):
        return cls._validate_choices(value, cls._choices)

    @classmethod
    def _validate_choices(cls, value, choices):
        if value is None:
            raise ValueError(_LE('None value is not valid.'))
        for choice in choices:
            if value.lower() == choice.lower():
                return choice
        # If we didn't find it, that's a problem...
        values = dict(value=value, field=cls._name,
                      choices=choices)
        msg = _LE("Value '%(value)s' is not valid "
                  "for field '%(field)s' with acceptable "
                  "choices: %(choices)s") % values
        raise ValueError(msg)

    def validate(self):
        if self.value is None and self.allow_none:
            return
        super(ChoiceField, self).validate()
        self._validate_choices(self.value, self._choices)


@six.add_metaclass(abc.ABCMeta)
class BoundField(Field):
    _min_bound = None
    _max_bound = None

    def validate(self):
        super(BoundField, self).validate()
        # If value was not converted to the type, then don't validate bounds
        if self.typed_value is None:
            return
        if (self._min_bound is not None and
                self.typed_value < self._convert_value(self._min_bound)):
            values = dict(field=self.name, value=self.typed_value,
                          minimum=self._min_bound)
            msg = _LE("Field '%(field)s' has a value below the minimum. "
                      "Value: %(value)s; Minimum: %(minimum)s") % values
            LOG.error(msg)
            raise ValueError(msg)

        if (self._max_bound is not None and
                self.typed_value > self._convert_value(self._max_bound)):
            values = dict(field=self.name, value=self.typed_value,
                          maximum=self._max_bound)
            msg = _LE("Field '%(field)s' has a value above the maximum. "
                      "Value: %(value)s; Maximum: %(maximum)s") % values

            LOG.error(msg)
            raise ValueError(msg)


@six.add_metaclass(abc.ABCMeta)
class IntBoundField(BoundField):
    _type = int


@six.add_metaclass(abc.ABCMeta)
class FloatBoundField(BoundField):
    _type = float


@six.add_metaclass(abc.ABCMeta)
class MinDesiredMaxField(object):

    def __init__(self, field_type, min_name, des_name, max_name,
                 min_value, desired_value, max_value,
                 min_min=None, max_max=None, name=None,
                 allow_none=True):
        self.name = name if name is not None else self.__class__._name

        self.min_field = field_type(
            min_value, name=min_name, allow_none=allow_none)
        self.min_field._max_bound = desired_value
        self.min_field._min_bound = min_min

        self.des_field = field_type(
            desired_value, name=des_name, allow_none=allow_none)
        self.des_field._min_bound = min_value
        self.des_field._max_bound = max_value

        self.max_field = field_type(
            max_value, name=max_name, allow_none=allow_none)
        self.max_field._min_bound = desired_value
        self.max_field._max_bound = max_max

    def validate(self):
        # Do specific validations before the general ones
        for fld in [self.min_field, self.des_field, self.max_field]:
            if fld.value is not None or not fld.allow_none:
                fld._convert()

        # Ensure the desired value is between the min and max
        if (self.des_field.typed_value and self.max_field.typed_value and
                self.des_field.typed_value > self.max_field.typed_value):
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
        if (self.des_field.typed_value and self.min_field.typed_value and
                self.des_field.typed_value < self.min_field.typed_value):
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
    _name = 'Memory'

    def __init__(self, min_value, desired_value, max_value,
                 ame_ef, host_ame_cap, lmb_size, allow_none=True):
        super(Memory, self).__init__(
            IntBoundField, 'Minimum Memory', 'Desired Memory',
            'Maximum Memory', min_value, desired_value, max_value,
            allow_none=allow_none)
        self.lmb_size = lmb_size
        # Set the lowest memory we'll honor
        self.min_field._min_bound = MEM_LOW_BOUND
        # Don't allow the desired memory to not be specified.
        self.des_field.allow_none = False
        self.ame_ef = ame_ef
        self.host_ame_cap = host_ame_cap

    def validate(self):
        super(Memory, self).validate()
        self._validate_lmb_size()
        self._validate_ame()

    def _validate_lmb_size(self):
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
                    raise ValueError(msg)

    def _validate_ame(self):
        # Validate the expansion factor value
        if self.ame_ef is not None:
            exp_fact_float = round(float(self.ame_ef), 2)
            values = dict(value=self.ame_ef)
            if not self.host_ame_cap and exp_fact_float != 0:
                msg = _LE("The managed system does not support active memory "
                          "expansion. The expansion factor value '%(value)s' "
                          "is not valid.") % values
                raise ValueError(msg)
            if (exp_fact_float != 0 and exp_fact_float < 1 or
                    exp_fact_float > 10):
                msg = _LE("Active memory expansion value must be greater "
                          "than or equal to 1.0 and less than or equal to "
                          "10.0. A value of 0 is also valid and indicates "
                          "that AME is off. '%(value)s' is not "
                          "valid.") % values
                raise ValueError(msg)


class VCpu(MinDesiredMaxField):
    _name = 'VCPU'

    def __init__(self, min_value, desired_value, max_value, allow_none=True):
        super(VCpu, self).__init__(
            IntBoundField, 'Minimum VCPU', 'Desired VCPU',
            'Maximum VCPU', min_value, desired_value, max_value,
            allow_none=allow_none)
        # Set the lowest VCPU we'll honor
        self.min_field._min_bound = VCPU_LOW_BOUND


class ProcUnits(MinDesiredMaxField):
    _name = 'ProcUnits'

    def __init__(self, min_value, desired_value, max_value, allow_none=True):
        super(ProcUnits, self).__init__(
            FloatBoundField, 'Minimum Proc Units',
            'Desired Proc Units', 'Maximum Proc Units', min_value,
            desired_value, max_value,
            allow_none=allow_none)
        # Set the lowest ProcUnits we'll honor
        self.min_field._min_bound = PROC_UNITS_LOW_BOUND


class DedicatedProc(BoolField):
    _name = 'Dedicated Processors'


class LPARType(ChoiceField):
    _choices = (bp.LPARType.AIXLINUX, bp.LPARType.OS400, bp.LPARType.VIOS)
    _name = 'Logical Partition Type'

    def __init__(self, value, allow_none=False):
        super(LPARType, self).__init__(value, allow_none=allow_none)


class ProcCompatMode(ChoiceField):
    _choices = bp.LPARCompat.ALL_VALUES
    _name = 'Processor Compatability Mode'

    def __init__(self, value, host_modes=None, allow_none=True):
        super(ProcCompatMode, self).__init__(value, allow_none=allow_none)
        if host_modes:
            self._choices = host_modes


class DedProcShareMode(ChoiceField):
    _choices = bp.DedicatedSharingMode.ALL_VALUES
    _name = 'Dedicated Processor Sharing Mode'

    def __init__(self, value, allow_none=False):
        super(DedProcShareMode, self).__init__(value, allow_none=allow_none)


class IOSlots(IntBoundField):
    _min_bound = 2  # slot 0 & 1 are always in use
    _max_bound = 65534
    _name = 'I/O Slots'

    def __init__(self, value, allow_none=False):
        super(IOSlots, self).__init__(value, allow_none=allow_none)


class AvailPriority(IntBoundField):
    _min_bound = 0
    _max_bound = 255
    _name = 'Availability Priority'


class IDBoundField(IntBoundField):
    _min_bound = 1
    _name = 'ID'


class SimplifiedRemoteRestart(BoolField):
    _name = 'Simplified Remote Restart'


class RestrictedIO(BoolField):
    _name = 'Restricted IO'


class LPARBuilder(object):
    def __init__(self, adapter, attr, stdz):
        self.adapter = adapter
        self.attr = attr
        self.stdz = stdz
        for val in MINIMUM_ATTRS:
            if self.attr.get(val) is None:
                raise LPARBuilderException('Missing required attribute: %s'
                                           % val)
        stdz.set_attr(attr)

    def build_ded_proc(self):
        # Ensure no shared proc keys are present
        # TODO(IBM):

        std = self.stdz.ded_proc()
        dproc = bp.PartitionProcessorConfiguration.bld_dedicated(
            self.adapter, std[VCPU], min_proc=std[MIN_VCPU],
            max_proc=std[MAX_VCPU], sharing_mode=std[SHARING_MODE])
        return dproc

    def build_shr_proc(self):
        # Ensure no dedicated proc keys are present
        # TODO(IBM):

        std = self.stdz.shr_proc()
        # The weight may not be set if it's not uncapped
        uncapped_weight = std.get(UNCAPPED_WEIGHT)
        # Build the shared procs
        shr_proc = bp.PartitionProcessorConfiguration.bld_shared(
            self.adapter, std[PROC_UNITS], std[VCPU],
            sharing_mode=std[SHARING_MODE], uncapped_weight=uncapped_weight,
            min_proc_unit=std[MIN_PROC_U], max_proc_unit=std[MAX_PROC_U],
            min_proc=std[MIN_VCPU], max_proc=std[MAX_VCPU], proc_pool=std[SPP])
        return shr_proc

    def build_mem(self):
        std = self.stdz.memory()
        mem_wrap = bp.PartitionMemoryConfiguration.bld(
            self.adapter, std[MEM], min_mem=std[MIN_MEM], max_mem=std[MAX_MEM])
        # Determine AME enabled boolean value from expansion factor value
        if self.attr.get(AME_FACTOR) is not None:
            exp_fact_float = round(float(self.attr.get(AME_FACTOR)), 2)
            mem_wrap.exp_factor = exp_fact_float
        return mem_wrap

    def _shared_proc_keys_specified(self):
        # Check for any shared proc keys
        for key in SHARED_PROC_KEYS:
            if self.attr.get(key, None) is not None:
                return True

        # Check the sharing mode values if any
        smode = self.attr.get(SHARING_MODE, None)
        if (smode is not None and
                smode in bp.SharingMode.ALL_VALUES):
            return True

        return False

    def _dedicated_proc_keys_specified(self):
        # Check for dedicated proc keys
        # TODO(IBM):

        # Check for dedicated sharing mode
        smode = self.attr.get(SHARING_MODE, None)
        if (smode is not None and
                smode in bp.DedicatedSharingMode.ALL_VALUES):
                return True

    def _shared_procs_specified(self):
        """Determine if shared procs should be configured.

        General methodology is to try to check everything that would
        indicate shared processors first, then dedicated, and finally
        just default to shared if we can't determine either way.
        """
        if self.attr.get(DED_PROCS, None) is not None:
            return not DedicatedProc.convert_value(self.attr[DED_PROCS])

        # Check each key that would indicate sharing procs
        if self._shared_proc_keys_specified():
            return True

        # Check for dedicated sharing mode
        if self._dedicated_proc_keys_specified():
            return False

        # Default is to use shared if not proven otherwise
        return True

    def build(self):
        # Build a minimimal LPAR, the real work will be done in rebuild
        std = self.stdz.general()

        if std[ENV] == bp.LPARType.VIOS:
            lpar_w = vios.VIOS.bld(
                self.adapter, std[NAME],
                bp.PartitionMemoryConfiguration.bld(self.adapter, 0),
                bp.PartitionProcessorConfiguration.bld_dedicated(
                    self.adapter, 0),
                io_cfg=bp.PartitionIOConfiguration.bld(self.adapter, 0))
        else:
            lpar_w = lpar.LPAR.bld(
                self.adapter, std[NAME],
                bp.PartitionMemoryConfiguration.bld(self.adapter, 0),
                bp.PartitionProcessorConfiguration.bld_dedicated(
                    self.adapter, 0),
                io_cfg=bp.PartitionIOConfiguration.bld(self.adapter, 0),
                env=std[ENV])

        # Only set the uuid if one is sent in, otherwise it will be set
        # by PowerVM
        if std.get(UUID) is not None:
            lpar_w.uuid = std[UUID]

        if std.get(ID) is not None:
            lpar_w._id(std[ID])

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

        # Update any general attributes
        std = self.stdz.general()
        lpar_w.name = std[NAME]
        lpar_w.avail_priority = std[AVAIL_PRIORITY]
        lpar_w.proc_compat_mode = std[PROC_COMPAT]
        # Host may not be capable of SRR, so only add it if it's in the
        # standardized attributes
        if std.get(SRR_CAPABLE) is not None:
            lpar_w.srr_enabled = std[SRR_CAPABLE]
        io_cfg = bp.PartitionIOConfiguration.bld(self.adapter,
                                                 std[MAX_IO_SLOTS])

        # Now start replacing the sections
        lpar_w.mem_config = mem_cfg
        lpar_w.proc_config = proc_cfg
        lpar_w.io_config = io_cfg

        # Add IBMi values if needed
        if lpar_w.env == bp.LPARType.OS400:
            lpar_w.io_config.tagged_io = bp.TaggedIO.bld(
                self.adapter, load_src=std[LOAD_SRC], console=std[CONSOLE],
                alt_load_src=std[ALT_LOAD_SRC])
            if std.get(RESTRICTED_IO) is not None:
                lpar_w.restrictedio = std[RESTRICTED_IO]

        return lpar_w
