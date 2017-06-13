# Copyright 2017 IBM Corp.
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

"""Helper classes for PowerOn/PowerOff options (additional Job parameters)."""

import abc
from oslo_log import log as logging
import six

import pypowervm.exceptions as exc
import pypowervm.wrappers.base_partition as bp
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as lpar


LOG = logging.getLogger(__name__)

IPLSrc = lpar.IPLSrc


class BootMode(object):
    """Valid values for the 'bootmode' parameter in power_on.

    Not to be confused with pypowervm.wrappers.base_partition.BootMode.

    Example usage:
        power_on(..., add_parms={BootMode.KEY: BootMode.SMS, ...})
    """
    KEY = 'bootmode'
    NORM = 'norm'
    SMS = 'sms'
    DD = 'dd'
    DS = 'ds'
    OF = 'of'
    ALL_VALUES = (NORM, SMS, DD, DS, OF)


class KeylockPos(object):
    """Valid values for the 'keylock' parameter in power_on.

    Not to be confused with pypowervm.wrappers.base_partition.KeylockPos.

    Example usage:
        power_on(..., add_parms={KeylockPos.KEY: KeylockPos.MANUAL, ...})
    """
    KEY = 'keylock'
    MANUAL = 'manual'
    NORMAL = 'norm'
    UNKNOWN = 'unknown'
    ALL_VALUES = (MANUAL, NORMAL, UNKNOWN)


class RemoveOptical(object):
    """Valid values for the 'remove_optical_*' parameters in power_on.

    This is primarily used to remove the config drive after install. KEY_NAME
    is required and maps to a VirtualOpticalMedia name to remove. KEY_TIME is
    optional and maps to the time, in minutes, to wait before deleting the
    media.

    Example usage:
        power_on(..., add_parms={RemoveOptical.KEY_TIME: <Integer>,
                                 RemoveOptical.KEY_NAME: <String>}, ...)
    """
    KEY_NAME = 'remove_optical_name'
    KEY_TIME = 'remove_optical_time'

    @classmethod
    def bld_map(cls, name, time=0):
        return {cls.KEY_NAME: name, cls.KEY_TIME: time}


class IBMiOperationType(object):
    """Valid values for the IBMi operation type in power_on."""
    KEY = 'OperationType'
    ACTIVATE = 'activate'
    NETBOOT = 'netboot'
    CHANGE_KEYLOCK = 'changeKeylock'
    ALL_VALUES = (ACTIVATE, NETBOOT, CHANGE_KEYLOCK)


class PowerOffOperation(object):
    """Valid values for the operation in power_off."""
    KEY = 'operation'
    VSP = 'shutdown'
    OS = 'osshutdown'
    DUMPRESTART = 'dumprestart'
    ALL_VALUES = (VSP, OS, DUMPRESTART)


class Force(object):
    """Enumeration indicating the strategy for forcing power-off."""
    # The force-immediate option is included on the first pass.
    TRUE = True
    # The force-immediate option is not included on the first pass; but if the
    # power-off fails, it is retried with the force-immediate option included.
    # This value is False for backward compatibility.
    ON_FAILURE = False
    # The force-immediate option is not included.  If the power-off fails, it
    # is not retried.
    NO_RETRY = 'no retry'


@six.add_metaclass(abc.ABCMeta)
class _PowerOpts(object):
    # Specify a set of string keys that are legal Job parameters for the
    # operation.  Illegal keys found in legacy_add_parms will be dropped with a
    # warning.
    # Leaving as None will skip validation and send all legacy_add_parms to the
    # Job.
    valid_param_keys = None

    def __init__(self, legacy_add_parms=None):
        """Initialize a PowerOpts instance.

        :param legacy_add_parms: For legacy use only, initialize the internal
                                 parameter map from the specified dictionary of
                                 Job parameter name/value pairs.
        """
        self._parm_map = {}
        if self.valid_param_keys is None:
            self._parm_map.update(legacy_add_parms or {})
        else:
            for key in legacy_add_parms or {}:
                if key in self.valid_param_keys:
                    self._parm_map[key] = legacy_add_parms[key]
                else:
                    LOG.warning("Ignoring unknown Job parameter %s specified "
                                "via legacy add_parms.", key)

    def __str__(self):
        """String representation of this instance, for log/test purposes."""
        parms = ', '.join(["%s=%s" % (key, self._parm_map[key])
                           for key in sorted(self._parm_map)])
        return "%s(%s)" % (self.JOB_SUFFIX, parms)

    def _process_enum(self, enum, value):
        if value not in enum.ALL_VALUES:
            raise exc.InvalidEnumValue(enum=enum.__name__, value=value,
                                       valid_values=str(enum.ALL_VALUES))
        self._parm_map[enum.KEY] = value
        return self

    def _process_bool(self, key, value):
        """Process a boolean option.

        All boolean options are false by default.  Thus, if value is 'true'/i
        or True, the key is added with the value 'true'; otherwise it is
        *removed* from the _PowerOpt.

        :param key: The JobParameterName.
        :param value: A bool (True/False) or string ('true', 'false',
                      case-insensitive).  Default: True.
        """
        if key in self._parm_map:
            del self._parm_map[key]
        if str(value).lower() == 'true':
            self._parm_map[key] = 'true'
        return self

    def is_param_set(self, key):
        """Detect whether a parameter is set.

        For some parameters, the absence of the key assumes a default behavior.
        For example, is_immediate == False could mean the 'immediate' key is
        entirely absent; or that it is present with a value of 'false'.  This
        method allows the consumer to distinguish between these two scenarios,
        typically for the purpose of deciding whether to enact some default
        behavior.

        :param key: The key of the parameter in question.
        :return: True if any value is set for the supplied key; False if that
                 key is absent from the parameter list.
        """
        return key in self._parm_map

    def bld_jparms(self):
        return [job.Job.create_job_parameter(key, str(val)) for key, val in
                six.iteritems(self._parm_map)]


class PowerOnOpts(_PowerOpts):
    """Job parameters for pypowervm.tasks.power.power_on/PowerOp.start."""

    JOB_SUFFIX = 'PowerOn'

    def bootmode(self, value):
        """Set the boot mode.

        :param value: One of the BootMode enum values.
        :return self: For chaining.
        """
        return self._process_enum(BootMode, value)

    def keylock_pos(self, value):
        """Set the Keylock Position.

        :param value: One of the KeylockPos enum values.
        :return self: For chaining.
        """
        return self._process_enum(KeylockPos, value)

    def bootstring(self, value):
        """Set the boot string.

        :param value: The boot string to use.
        :return self: For chaining.
        """
        self._parm_map['bootstring'] = value
        return self

    def force(self, value=True):
        """Add the force option.

        :param value: A bool (True/False) or string ('true', 'false',
                      case-insensitive).  Default: True.
        :return self: For chaining.
        """
        return self._process_bool('force', value)

    def remove_optical(self, name, time=0):
        """Add options to remove an optical drive after boot.

        :param name: The name of a VirtualOpticalMedia name to remove.
        :param time: The time, in minutes, to wait before deleting the media.
        :return self: For chaining.
        """
        self._parm_map.update(RemoveOptical.bld_map(name, time=time))
        return self

    def ibmi_ipl_source(self, value):
        """Set the IBMi IPL Source.

        :param value: One of the IPLSrc enum values.
        :return self: For chaining.
        """
        return self._process_enum(IPLSrc, value)

    def ibmi_op_type(self, value):
        """Set the IBMi Operation Type.

        :param value: One of the IBMiOperationType enum values.
        :return self: For chaining.
        """
        return self._process_enum(IBMiOperationType, value)

    def ibmi_netboot_params(self, ipaddr, serverip, gateway, serverdir,
                            subnet=None, connspeed=None, duplex=None, mtu=None,
                            vlanid=None):
        """Set parameters for IBMi netboot.

        Use with  ibmi_op_type(IBMiOperationType.NETBOOT).

        :param ipaddr: IP (v4 or v6) address of the client VM.
        :param serverip: IP (v4 or v6) address of the netboot server.
        :param gateway: IP (v4 or v6) address of the gateway.
        :param serverdir: Location of the netboot image on the server.
        :param subnet: Subnet mask.  IPv4 only.
        :param connspeed: Connection speed.
        :param duplex: Duplex mode.
        :param mtu: Maximum Transmission Unit.
        :param vlanid: VLAN ID.
        :return self: For chaining.
        """
        self._parm_map['IPAddress'] = ipaddr
        self._parm_map['ServerIPAddress'] = serverip
        self._parm_map['Gateway'] = gateway
        self._parm_map['IBMiImageServerDirectory'] = serverdir
        # Optional args
        for key, val in (('SubnetMask', subnet),
                         ('ConnectionSpeed', connspeed),
                         ('DuplexMode', duplex),
                         ('VLANID', vlanid),
                         ('MaximumTransmissionUnit', mtu)):
            if val is not None:
                # connspeed/vlanid/mtu may arrive as ints
                self._parm_map[key] = str(val)
        return self


class PowerOffOpts(_PowerOpts):
    """Job parameters for pypowervm.tasks.power.power_off/PowerOp.stop.

    Use *one* of os_normal, os_immediate, vsp_normal, vsp_hard, or soft_detect.

    Optionally specify restart.
    """
    JOB_SUFFIX = 'PowerOff'
    valid_param_keys = {'operation', 'immediate', 'restart'}

    def immediate(self, value=True):
        """Whether to include immediate=true.

        This corresponds to "hard" for VSP, "immediate" for OS.

        This should only be used with operation(DUMPRESTART).  Otherwise, one
        of the os_normal, os_immediate, vsp_normal, vsp_hard, or soft_detect
        methods should be used.

        :param value: A bool (True/False) or string ('true', 'false',
                      case-insensitive).
        :return self: For chaining.
        """
        return self._process_bool('immediate', value)

    @property
    def is_immediate(self):
        return self._parm_map.get('immediate') == 'true'

    def operation(self, value):
        """The PowerOff operation to perform.

        This should only be used for DUMPRESTART.  Otherwise, one of the
        os_normal, os_immediate, vsp_normal, vsp_hard, or soft_detect methods
        should be used.

        :param value: One of the PowerOffOperation enum values.
        :return self: For chaining.
        """
        return self._process_enum(PowerOffOperation, value)

    @staticmethod
    def can_os_shutdown(part):
        """Can the specified partition perform an OS shutdown?

        :param part: LPAR/VIOS wrapper indicating the partition to inspect.
        :return: True if the specified partition is capable of OS shutdown;
                 False otherwise.
        """
        # OS shutdown is always available on IBMi partitions.
        # OS shutdown is available if RMC is up.
        return (part.env == bp.LPARType.OS400) or (part.rmc_state ==
                                                   bp.RMCState.ACTIVE)

    @property
    def is_os(self):
        return self._parm_map.get('operation') == PowerOffOperation.OS

    def restart(self, value=True):
        """Whether to restart the partition after power-off.

        :param value: A bool (True/False) or string ('true', 'false',
                      case-insensitive).  Default: True.
        :return self: For chaining.
        """
        return self._process_bool('restart', value)

    @property
    def is_restart(self):
        return self._parm_map.get('restart') == 'true'

    def os_normal(self):
        """Set up normal OS shutdown.

        Sends the 'shutdown' command to the operating system.

        :return self: For chaining.
        """
        return self.operation(PowerOffOperation.OS).immediate(value=False)

    def os_immediate(self):
        """Set up immediate OS shutdown.

        Sends the 'shutdown -t now' command to the operating system.

        :return self: For chaining.
        """
        return self.operation(PowerOffOperation.OS).immediate()

    def vsp_normal(self):
        """Set up normal VSP shutdown.

        The Virtual Service Processor sends the equivalent of an EPOW event to
        the operating system.  The result is OS-dependent.

        :return self: For chaining.
        """
        return self.operation(PowerOffOperation.VSP).immediate(value=False)

    def vsp_hard(self):
        """Set up hard VSP shutdown.

        Akin to pulling the plug from the partition.  Processors are stopped
        immediately, and any pending I/O is lost.  May result in data
        corruption.

        :return self: For chaining.
        """
        return self.operation(PowerOffOperation.VSP).immediate()

    def soft_detect(self, part, immed_if_os=None):
        """Determine the appropriate soft shutdown operation for a partition.

        For IBMi partitions, this will always set up an OS shutdown.

        For non-IBMi partitions with active RMC, this will set up an OS
        shutdown.

        For non-IBMi partitions without RMC, this will set up a *normal* VSP
        shutdown.

        :param part: LPAR or VIOS wrapper indicating the partition being shut
                     down.
        :param immed_if_os: If this method determines that an OS shutdown is to
                            be performed, this parameter indicates whether that
                            shutdown should be immediate (True) or not (False).
                            The default is False for IBMi partitions, and True
                            for non-IBMi partitions.  This parameter is ignored
                            if a VSP shutdown is detected.
        :return self: For chaining.
        """
        if self.can_os_shutdown(part):
            self.operation(PowerOffOperation.OS)
            # Specific 'immediate' behavior requested for OS shutdown?
            if immed_if_os is not None:
                self.immediate(value=immed_if_os)
            else:
                # Default is normal for IBMi, immediate for non-IBMi.
                self.immediate(value=part.env != bp.LPARType.OS400)
        else:
            # OS shutdown not available; perform *normal* VSP shutdown.
            self.vsp_normal()
        return self
