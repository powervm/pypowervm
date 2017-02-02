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

"""Tasks to start, stop, and reboot partitions."""

from oslo_config import cfg
from oslo_log import log as logging
import six

import pypowervm.const as c
import pypowervm.exceptions as pexc
from pypowervm.i18n import _
import pypowervm.log as lgc
import pypowervm.wrappers.base_partition as bp
from pypowervm.wrappers import job

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

# Error codes indicate osshutdown is not supported
_OSSHUTDOWN_RMC_ERRS = ['HSCL0DB4', 'PVME01050905', 'PVME01050402']
# Error codes indicate partition is already powered off
_ALREADY_POWERED_OFF_ERRS = ['HSCL1558', 'PVME04000005']
# Error codes indicate partition is already powered on
_ALREADY_POWERED_ON_ERRS = ['HSCL3681', 'PVME01042026']


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


class PowerOp(object):
    """Provides granular control over a partition PowerOn/Off Job.

    Use the start or stop @classmethod to invoke the appropriate Job.  Jobs
    invoked through these classmethods are never retried.  If they fail or
    time out, they raise relevant exceptions - see the methods' docstrings for
    details.
    """
    _SUFF_PWRON = 'PowerOn'
    _SUFF_PWROFF = 'PowerOff'

    OP_PWROFF_VSP = 'shutdown'
    OP_PWROFF_OS = 'osshutdown'

    def __init__(self, part, suff=_SUFF_PWROFF, oper=None, immed=False):
        """Create a PowerOp instance which can be invoked via the run method.

        Do not call this directly; use the start or stop @classmethod.

        :param part: Partition (LPAR or VIOS) wrapper indicating the partition
                     on which the operation is to be run.
        :param suff: Job suffix, one of the _SUFF_* constants.
        :param oper: Operation, one of the OP_* constants.
        :param immed: Include the immediate=true Job parameter?  True or False.
        """
        self.part = part
        self.job_suffix = suff

        self.job_parms = {}
        if oper:
            self.job_parms['operation'] = oper

        self.immediate = immed
        if immed:
            self.job_parms['immediate'] = 'true'

    @classmethod
    def start(cls, part, add_parms, timeout=CONF.pypowervm_job_request_timeout,
              synchronous=True):
        """Power on a partition.

        :param part: Partition (LPAR or VIOS) wrapper indicating the partition
                     to power on.
        :param add_parms: A dict of parameters to the Job.
        :param timeout: value in seconds for specifying how long to wait for
                        the Job to complete.
        :param synchronous: If True, this method will not return until the Job
                            completes (whether success or failure) or times
                            out.  If False, this method will return as soon as
                            the Job has started on the server (that is,
                            achieved any state beyond NOT_ACTIVE).  Note that
                            timeout is still possible in this case.
        :raise VMPowerOnTimeout: If the Job timed out.
        :raise VMPowerOnFailure: If the Job failed for some reason other than
                                 that the partition was already powered on.
        """
        pwrop = cls(part, cls._SUFF_PWRON)
        try:
            pwrop._run(add_parms or {}, timeout, synchronous=synchronous)
        except pexc.JobRequestTimedOut as error:
            LOG.exception(error)
            raise pexc.VMPowerOnTimeout(lpar_nm=part.name, timeout=timeout)
        except pexc.JobRequestFailed as error:
            emsg = six.text_type(error)
            # If already powered on, don't send exception
            if (any(err_prefix in emsg
                    for err_prefix in _ALREADY_POWERED_ON_ERRS)):
                LOG.warning(_("Partition %s already powered on."), part.name)
                return
            LOG.exception(error)
            raise pexc.VMPowerOnFailure(lpar_nm=part.name, reason=emsg)

    @classmethod
    def stop(cls, part, oper=None, hard=False, restart=False, add_parms=None,
             timeout=CONF.pypowervm_job_request_timeout, synchronous=True):
        """Power off a partition.

        oper           hard   Behavior
        OP_PWROFF_OS   False  Normal OS shutdown.
                              Send the 'shutdown' command to the operating
                              system.  For non-IBMi partitions, RMC must be
                              active; otherwise OSShutdownNoRMC is raised.
        OP_PWROFF_OS   True   Immediate OS shutdown.
                              Send the 'shutdown -t now' command to the
                              operating system.  For non-IBMi partitions, RMC
                              must be active; otherwise OSShutdownNoRMC is
                              raised.
        OP_PWROFF_VSP  False  Normal VSP shutdown.
                              The Virtual Service Processor sends the
                              equivalent of an EPOW event to the operating
                              system.  The result is OS-dependent.
        OP_PWROFF_VSP  True   Hard VSP shutdown.
                              Akin to pulling the plug from the partition.
                              Processors are stopped immediately, and any
                              pending I/O is lost.  May result in data
                              corruption.
        None           False  For IBMi partitions, normal OS shutdown.
                              For non-IBMi partitions: if RMC is up, normal
                              OS shutdown; if RMC is down, normal VSP shutdown.
        None           True   For IBMi partitions, immediate OS shutdown.
                              For non-IBMi partitions: if RMC is up, immediate
                              OS shutdown; if RMC is down, *normal* VSP
                              shutdown.

        :param part: Partition (LPAR or VIOS) wrapper indicating the partition
                     to power off.
        :param oper: Whether to perform OS or VSP shutdown.  May be
                     OP_PWROFF_VSP or OP_PWROFF_OS.  If None, this method will
                     decide which to use based on the partition type and RMC
                     state.
        :param hard: Whether to perform a hard (VSP) / immediate (OS) shutdown.
        :param restart: Boolean.  Perform a restart after the power off.
        :param add_parms: A dict of parameters to the Job.
        :param timeout: value in seconds for specifying how long to wait for
                        the Job to complete.
        :param synchronous: If True, this method will not return until the Job
                            completes (whether success or failure) or times
                            out.  If False, this method will return as soon as
                            the Job has started on the server (that is,
                            achieved any state beyond NOT_ACTIVE).  Note that
                            timeout is still possible in this case.
        :raise VMPowerOffTimeout: If the Job timed out.
        :raise VMPowerOffFailure: If the Job failed for some reason other than
                                  that the partition was already powered off,
                                  and restart was not requested.
        :return: A PowerOp instance which can be invoked via the _run method.
        :raise OSShutdownNoRMC: OP_PWROFF_OS was requested on a non-IBMi
                                partition with no RMC connection.
        """
        ibmi = part.env == bp.LPARType.OS400
        rmc_up = part.rmc_state == bp.RMCState.ACTIVE
        mgmt = part.is_mgmt_partition

        # OS shutdown is always available on IBMi partitions.
        # OS shutdown is available if RMC is up.
        # The management partition doesn't need RMC.
        can_os = ibmi or rmc_up or mgmt

        if oper == PowerOp.OP_PWROFF_OS and not can_os:
            raise pexc.OSShutdownNoRMC(lpar_nm=part.name)

        if oper is None:
            if can_os:
                oper = PowerOp.OP_PWROFF_OS
            else:
                # OS shutdown not available; perform *normal* VSP shutdown.
                oper = PowerOp.OP_PWROFF_VSP
                if 'immediate' in add_parms:
                    del add_parms['immediate']
                hard = False

        add_parms = add_parms or {}
        if restart:
            add_parms['restart'] = 'true'

        pwrop = cls(part, oper=oper, immed=hard)
        try:
            pwrop._run(add_parms, timeout, synchronous=synchronous)
        except pexc.JobRequestTimedOut as error:
            LOG.exception(error)
            raise pexc.VMPowerOffTimeout(lpar_nm=part.name, timeout=timeout)
        except pexc.JobRequestFailed as error:
            emsg = six.text_type(error)
            # If already powered off and not a reboot, don't send exception
            if (any(err_prefix in emsg
                    for err_prefix in _ALREADY_POWERED_OFF_ERRS) and
                    not restart):
                LOG.warning(_("Partition %s already powered off."), part.name)
                return
            LOG.exception(error)
            raise pexc.VMPowerOffFailure(lpar_nm=part.name, reason=emsg)

    def _run(self, add_parms, timeout, synchronous=True):
        """Fetch, fill out, and run a Power* Job for this PowerOp.

        :param add_parms: A dict of parameters to the Job.  Must not be None.
        :param timeout: value in seconds for specifying how long to wait for
                        the Job to complete.
        :param synchronous: If True, this method will not return until the Job
                            completes (whether success or failure) or times
                            out.  If False, this method will return as soon as
                            the Job has started on the server (that is,
                            achieved any state beyond NOT_ACTIVE).  Note that
                            timeout is still possible in this case.
        :raise VMPowerOffTimeout: If the Job timed out.
        :raise VMPowerOffFailure: If the Job failed.
        """
        # Fetch the Job template wrapper
        jwrap = job.Job.wrap(self.part.adapter.read(
            self.part.schema_type, self.part.uuid,
            suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=self.job_suffix))

        # Consolidate additional parameters with operation/immediate/restart.
        add_parms.update(self.job_parms)

        # Build the parameters in the form expected by run_job
        job_parms = [jwrap.create_job_parameter(key, str(val))
                     for key, val in six.iteritems(add_parms)]

        LOG.debug("Executing %(suff)s for partition %(lpar_nm)s with "
                  "timeout=%(timeout)d, synchronous=%(synchronous)s, and "
                  "params %(params)s",
                  dict(suff=self.job_suffix, lpar_nm=self.part.name,
                       timeout=timeout, synchronous=synchronous,
                       params=add_parms))
        # Run the Job, letting exceptions raise up.
        jwrap.run_job(self.part.uuid, job_parms=job_parms, timeout=timeout,
                      synchronous=synchronous)


@lgc.logcall_args
def power_on(part, host_uuid, add_parms=None, synchronous=True):
    """Will Power On a Logical Partition or Virtual I/O Server.

    :param part: The LPAR/VIOS wrapper of the partition to power on.
    :param host_uuid: Not used.  Retained for backward compatibility.
    :param add_parms: dict of parameters to pass directly to the job template
    :param synchronous: If True (the default), this method will not return
                        until the PowerOn Job completes (whether success or
                        failure) or times out.  If False, this method will
                        return as soon as the Job has started on the server
                        (that is, achieved any state beyond NOT_ACTIVE).  Note
                        that timeout is still possible in this case.
    :raise VMPowerOnFailure: If the operation failed.
    :raise VMPowerOnTimeout: If the operation timed out.
    """
    PowerOp.start(part, add_parms, synchronous=synchronous)


def _pwroff_soft_ibmi_flow(part, force_immediate, restart, timeout, add_parms):
    """Normal (non-hard) power-off flow for IBMi partitions.

    ===================================                            =====
    add_params includes immediate=true? <--START                   raise
    ===================================                            =====
        |                  |                                         ^
        NO                YES                                       YES
        V                  V                                         |
    =========          ============          ==========          =========
    OS normal -FAIL*-> OS immediate -FAIL*-> VSP normal -FAIL*-> NO_RETRY?
    =========          ============          ==========          =========
        \_________________ | ___________________/                    |
                          \|/                                        NO
                        SUCCESS                                      V
                           V         *VMPowerOffTimeout OR     ============
                      ===========     VMPowerOffFailure        return False
                      return True                              ============
                      ===========

    :param part force_immediate restart timeout add_parms: See power_off.
    :return: True if the power-off succeeded; False otherwise.  The caller
             (power_off) should perform VSP hard shutdown if True is returned.
    :raise VMPowerOffTimeout: If the last power-off attempt timed out.
    :raise VMPowerOffFailure: If the last power-off attempt failed.
    """
    # The immediate option may be specified via add_parms
    immed = add_parms and add_parms.get('immediate') == 'true'
    # If immediate was already specified, skip OS-normal.
    if not immed:
        # ==> OS normal
        try:
            PowerOp.stop(part, oper=PowerOp.OP_PWROFF_OS, hard=False,
                         restart=restart, add_parms=add_parms, timeout=timeout)
            return True
        except pexc.VMPowerOffFailure:
            LOG.warning(_("IBMi OS normal shutdown failed; trying OS "
                          "immediate shutdown.  Partition: %s"), part.name)
            # Fall through to OS immediate

    # ==> OS immediate
    try:
        PowerOp.stop(part, oper=PowerOp.OP_PWROFF_OS, hard=True,
                     restart=restart, add_parms=add_parms, timeout=timeout)
        return True
    except pexc.VMPowerOffFailure:
        LOG.warning(_("IBMi OS immediate shutdown failed; trying VSP normal "
                      "shutdown.  Partition: %s"), part.name)
        # Fall through to VSP normal

    # ==> VSP normal
    try:
        PowerOp.stop(part, oper=PowerOp.OP_PWROFF_VSP, hard=False,
                     restart=restart, add_parms=add_parms, timeout=timeout)
        return True
    except pexc.VMPowerOffFailure:
        LOG.warning(_("IBMi VSP normal shutdown failed.  Partition: %s"),
                    part.name)
        # If NO_RETRY, that's it.
        if force_immediate == Force.NO_RETRY:
            LOG.warning(_("NO_RETRY specfied; skipping VSP hard shutdown."))
            raise

    return False


def _pwroff_soft_standard_flow(part, force_immediate, restart, timeout,
                               add_parms):
    """Normal (non-hard) power-off flow for non-IBMi partitions.

    START
    |     +-------VMPowerOffTimeout---------------------------------------+
    V     |                                                               V
    ============  VMPowerOffFailure   ==========  VMPowerOffFailure   =========
    OS immediate ----   or      ----> VSP normal ----   or      ----> NO_RETRY?
    ============   OSShutdownNoRMC    ==========  VMPowerOffTimeout   =========
          | ______________________________/                           /     |
          |/                                                         /      |
       SUCCESS                                                     NO      YES
          V                                                        V        V
     ===========                                            ============  =====
     return True                                            return False  raise
     ===========                                            ============  =====



    :param part force_immediate restart timeout add_parms: See power_off.
    :return: True if the power-off succeeded; False otherwise.
    :raise VMPowerOffTimeout: If the last power-off attempt timed out.
    :raise VMPowerOffFailure: If the last power-off attempt failed.
    """
    # For backward compatibility, OS shutdown is always immediate.  We don't
    # let PowerOn decide whether to use OS or VSP; instead we trap
    # OSShutdownNoRMC (which is very quick) so we can keep this progression
    # linear.

    # ==> OS immediate
    try:
        PowerOp.stop(part, oper=PowerOp.OP_PWROFF_OS, hard=True,
                     restart=restart, add_parms=add_parms,
                     timeout=timeout)
        return True
    except pexc.VMPowerOffTimeout:
        LOG.warning(_("Non-IBMi OS immediate shutdown timed out; skipping "
                      "normal VSP shutdown.  Partition: %s"), part.name)
        # If NO_RETRY, that's it.
        if force_immediate == Force.NO_RETRY:
            LOG.warning(_("NO_RETRY specfied; skipping VSP hard shutdown."))
            raise
        return False
    except pexc.VMPowerOffFailure:
        LOG.warning(_("Non-IBMi OS immediate shutdown failed; trying VSP "
                      "normal shutdown.  Partition: %s"), part.name)
        # Fall through to VSP normal
    except pexc.OSShutdownNoRMC as error:
        LOG.warning(error.args[0])
        # Fall through to VSP normal

    # ==> VSP normal
    try:
        PowerOp.stop(part, oper=PowerOp.OP_PWROFF_VSP, hard=False,
                     restart=restart, add_parms=add_parms, timeout=timeout)
        return True
    except pexc.VMPowerOffFailure:
        LOG.warning(_("Non-IBMi VSP normal shutdown failed.  Partition: %s"),
                    part.name)
        # If NO_RETRY, that's it.
        if force_immediate == Force.NO_RETRY:
            LOG.warning(_("NO_RETRY specfied; skipping VSP hard shutdown."))
            raise

    return False


@lgc.logcall_args
def power_off(part, host_uuid, force_immediate=Force.ON_FAILURE, restart=False,
              timeout=CONF.pypowervm_job_request_timeout, add_parms=None):
    """Will Power Off a Logical Partition or Virtual I/O Server.

    Depending on the force_immediate flag and the partition's type and RMC
    state, this method may attempt increasingly aggressive mechanisms for
    shutting down the OS if initial attempts fail or time out.

    :param part: The LPAR/VIOS wrapper of the instance to power off.
    :param host_uuid: Not used.  Retained for backward compatibility.
    :param force_immediate: One of the Force enum values, defaulting to
                            Force.ON_FAILURE, which behave as follows:
            - Force.TRUE: The force-immediate option is included on the first
                          pass.
            - Force.NO_RETRY: The force-immediate option is not included.  If
                              the power-off fails or times out,
                              VMPowerOffFailure is raised immediately.
            - Force.ON_FAILURE: The force-immediate option is not included on
                                the first pass; but if the power-off fails
                                (including timeout), it is retried with the
                                force-immediate option added.
    :param restart: Boolean.  Perform a restart after the power off.
    :param timeout: value in seconds for specifying how long to wait for the
                    instance to stop.
    :param add_parms: dict of parameters to pass directly to the job template
    :raise VMPowerOffFailure: If the operation failed (possibly after retrying)
    :raise VMPowerOffTimeout: If the operation timed out (possibly after
                              retrying).
    """
    # If force_immediate=TRUE, always VSP hard shutdown.
    if force_immediate == Force.TRUE:
        PowerOp.stop(part, oper=PowerOp.OP_PWROFF_VSP, hard=True,
                     restart=restart, add_parms=add_parms, timeout=timeout)
        return

    # Do the progressive-retry sequence appropriate to the partition type and
    # the force_immediate flag.
    if part.env == bp.LPARType.OS400:
        # The IBMi progression.
        if _pwroff_soft_ibmi_flow(part, force_immediate, restart, timeout,
                                  add_parms):
            return
        # Fall through to VSP hard
    else:
        # The non-IBMi progression.
        if _pwroff_soft_standard_flow(part, force_immediate, restart, timeout,
                                      add_parms):
            return
        # Fall through to VSP hard

    # If we got here, force_immediate == ON_FAILURE, so fall back to VSP hard.
    # Let this one finish or raise.
    # ==> VSP hard
    LOG.warning(_("VSP hard shutdown with default timeout.  Partition: %s"),
                part.name)
    PowerOp.stop(part, oper=PowerOp.OP_PWROFF_VSP, hard=True,
                 restart=restart, add_parms=add_parms)
