# Copyright 2014, 2017 IBM Corp.
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
import pypowervm.tasks.power_opts as popts
import pypowervm.wrappers.base_partition as bp
from pypowervm.wrappers import job

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

# Error codes indicate osshutdown is not supported
_OSSHUTDOWN_RMC_ERRS = ['HSCL0DB4', 'PVME01050905', 'PVME01050402']
# Error codes indicate partition is already powered off
_ALREADY_POWERED_OFF_ERRS = ['HSCL1558', 'PVME04000005', 'PVME01050901']
# Error codes indicate partition is already powered on
_ALREADY_POWERED_ON_ERRS = ['HSCL3681', 'PVME01042026']

BootMode = popts.BootMode
KeylockPos = popts.KeylockPos
RemoveOptical = popts.RemoveOptical
Force = popts.Force


class PowerOp(object):
    """Provides granular control over a partition PowerOn/Off Job.

    Use the start or stop @classmethod to invoke the appropriate Job.  Jobs
    invoked through these methods are never retried.  If they fail or time out,
    they raise relevant exceptions - see the methods' docstrings for details.
    """
    @classmethod
    def start(cls, part, opts=None, timeout=CONF.pypowervm_job_request_timeout,
              synchronous=True):
        """Power on a partition.

        :param part: Partition (LPAR or VIOS) wrapper indicating the partition
                     to power on.
        :param opts: An instance of power_opts.PowerOnOpts indicating
                     additional options to specify to the PowerOn operation.
                     By default, no additional options are used.
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
        try:
            cls._run(part, opts or popts.PowerOnOpts(), timeout,
                     synchronous=synchronous)
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
    def stop(cls, part, opts=None, timeout=CONF.pypowervm_job_request_timeout,
             synchronous=True):
        """Power off a partition.

        :param part: LPAR/VIOS wrapper indicating the partition to power off.
        :param opts: An instance of power_opts.PowerOffOpts indicating the type
                     of shutdown to perform, and any additional options.  If
                     not specified, PowerOffOpts.soft_detect is used, with no
                     restart.
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
        :return: A PowerOp instance which can be invoked via the run method.
        :raise OSShutdownNoRMC: OP_PWROFF_OS was requested on a non-IBMi
                                partition with no RMC connection.
        """
        if opts is None:
            opts = popts.PowerOffOpts().soft_detect(part)

        if opts.is_os and not opts.can_os_shutdown(part):
            raise pexc.OSShutdownNoRMC(lpar_nm=part.name)

        try:
            cls._run(part, opts, timeout, synchronous=synchronous)
        except pexc.JobRequestTimedOut as error:
            LOG.exception(error)
            raise pexc.VMPowerOffTimeout(lpar_nm=part.name, timeout=timeout)
        except pexc.JobRequestFailed as error:
            emsg = six.text_type(error)
            # If already powered off and not a reboot, don't send exception
            if (any(err_prefix in emsg
                    for err_prefix in _ALREADY_POWERED_OFF_ERRS) and
                    not opts.is_restart):
                LOG.warning(_("Partition %s already powered off."), part.name)
                return
            LOG.exception(error)
            raise pexc.VMPowerOffFailure(lpar_nm=part.name, reason=emsg)

    @classmethod
    def _run(cls, part, opts, timeout, synchronous=True):
        """Fetch, fill out, and run a Power* Job for this PowerOp.

        Do not invoke this method directly; it is used by the start and stop
        class methods.

        :param part: LPAR/VIOS wrapper of the partition to power on/off.
        :param opts: Instance of power_opts.PowerOnOpts or PowerOffOpts
                     indicating the type of operation to perform, and any
                     additional options.
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
        jwrap = job.Job.wrap(part.adapter.read(
            part.schema_type, part.uuid, suffix_type=c.SUFFIX_TYPE_DO,
            suffix_parm=opts.JOB_SUFFIX))

        LOG.debug("Executing power operation for partition %(lpar_nm)s with "
                  "timeout=%(timeout)d and synchronous=%(synchronous)s: "
                  "%(opts)s",
                  dict(lpar_nm=part.name, timeout=timeout,
                       synchronous=synchronous, opts=str(opts)))
        # Run the Job, letting exceptions raise up.
        jwrap.run_job(part.uuid, job_parms=opts.bld_jparms(), timeout=timeout,
                      synchronous=synchronous)


def _legacy_power_opts(klass, add_parms):
    """Detect (and warn) if add_parms is a legacy dict vs. a Power*Opts.

    Usage:
        opts, legacy = _legacy_power_opts(PowerOnOpts, add_parms)
        if legacy:
            # Do other stuff based on legacy behavior
        else:
            # Do other stuff based on new behavior

    :param klass: The class we expect, either PowerOnOpts or PowerOffOpts.
    :param add_parms: The add_parms argument to check.
    :return: An instance of klass, which is either add_parms, constructed by
             passing it to the klass __init__'s legacy_add_parms.
    :return: True if add_parms was a legacy dict; False otherwise.
    """
    if isinstance(add_parms, klass):
        return add_parms, False
    else:
        if add_parms is not None:
            import warnings
            warnings.warn(_("Specifying add_parms as a dict is deprecated. "
                            "Please specify a %s instance instead.") %
                          klass.__name__, DeprecationWarning)
        return klass(legacy_add_parms=add_parms), True


@lgc.logcall_args
def power_on(part, host_uuid, add_parms=None, synchronous=True):
    """Will Power On a Logical Partition or Virtual I/O Server.

    :param part: The LPAR/VIOS wrapper of the partition to power on.
    :param host_uuid: Not used.  Retained for backward compatibility.
    :param add_parms: A power_opts.PowerOnOpts instance; or (deprecated) a dict
                      of parameters to pass directly to the job template.  If
                      unspecified, a default PowerOnOpts instance is used, with
                      no additional parameters.
    :param synchronous: If True (the default), this method will not return
                        until the PowerOn Job completes (whether success or
                        failure) or times out.  If False, this method will
                        return as soon as the Job has started on the server
                        (that is, achieved any state beyond NOT_ACTIVE).  Note
                        that timeout is still possible in this case.
    :raise VMPowerOnFailure: If the operation failed.
    :raise VMPowerOnTimeout: If the operation timed out.
    """
    PowerOp.start(
        part, opts=_legacy_power_opts(popts.PowerOnOpts, add_parms)[0],
        synchronous=synchronous)


def _pwroff_soft_ibmi_flow(part, opts, timeout):
    """Normal (non-hard) power-off retry flow for IBMi partitions.

          ==================
          opts.is_immediate? <--START
          ==================
           |             |
           NO           YES
           V             V
    =========          ============          ==========          ============
    OS normal -FAIL*-> OS immediate -FAIL*-> VSP normal -FAIL*-> return False
    =========          ============          ==========          ============
        |_________________ | ___________________|
                          |||
                        SUCCESS
                           V         *VMPowerOffTimeout OR
                      ===========     VMPowerOffFailure
                      return True
                      ===========

    :param part timeout: See power_off.
    :param opts: A PowerOffOpts instance.  The operation and immediate params
                 are overwritten at each stage of this method.  Any other
                 options (such as restart) remain unaffected.
    :return: True if the power-off succeeded; False otherwise.  The caller
             (power_off) should perform VSP hard shutdown if False is returned.
    :raise VMPowerOffTimeout: If the last power-off attempt timed out.
    :raise VMPowerOffFailure: If the last power-off attempt failed.
    """
    # If immediate was already specified, skip OS-normal.
    if not opts.is_immediate:
        # ==> OS normal
        try:
            PowerOp.stop(part, opts=opts.os_normal(), timeout=timeout)
            return True
        except pexc.VMPowerOffFailure:
            LOG.warning(_("IBMi OS normal shutdown failed.  Trying OS "
                          "immediate shutdown.  Partition: %s"), part.name)
            # Fall through to OS immediate, with default timeout
            timeout = CONF.pypowervm_job_request_timeout

    # ==> OS immediate
    try:
        PowerOp.stop(part, opts=opts.os_immediate(), timeout=timeout)
        return True
    except pexc.VMPowerOffFailure:
        LOG.warning(_("IBMi OS immediate shutdown failed.  Trying VSP normal "
                      "shutdown.  Partition: %s"), part.name)
        # Fall through to VSP normal

    # ==> VSP normal
    try:
        PowerOp.stop(part, opts=opts.vsp_normal(), timeout=timeout)
        return True
    except pexc.VMPowerOffFailure:
        LOG.warning(_("IBMi VSP normal shutdown failed.  Trying VSP hard "
                      "shutdown.  Partition: %s"), part.name)

    return False


def _pwroff_soft_standard_flow(part, opts, timeout):
    """Normal (non-hard) power-off retry flow for non-IBMi partitions.

    START
    |     +---VMPowerOffTimeout-------------------------------------+
    V     |                                                         V
    ========  VMPowerOffFailure  ==========  VMPowerOffFailure  ============
    OS immed ----   or      ---> VSP normal ----   or      ---> return False
    ========   OSShutdownNoRMC   ==========  VMPowerOffTimeout  ============
          | _________________________/
          |/
       SUCCESS
          V
     ===========
     return True
     ===========

    :param part timeout: See power_off.
    :param opts: A PowerOffOpts instance.  The operation and immediate params
                 are overwritten at each stage of this method.  Any other
                 options (such as restart) remain unaffected.
    :return: True if the power-off succeeded; False otherwise.  The caller
             should perform VSP hard shutdown if False is returned.
    :raise VMPowerOffTimeout: If the last power-off attempt timed out.
    :raise VMPowerOffFailure: If the last power-off attempt failed.
    """
    # For backward compatibility, OS shutdown is always immediate.  We don't
    # let PowerOn decide whether to use OS or VSP; instead we trap
    # OSShutdownNoRMC (which is very quick) so we can keep this progression
    # linear.

    # ==> OS immediate
    try:
        PowerOp.stop(part, opts=opts.os_immediate(), timeout=timeout)
        return True
    except pexc.VMPowerOffTimeout:
        LOG.warning(_("Non-IBMi OS immediate shutdown timed out.  Trying VSP "
                      "hard shutdown.  Partition: %s"), part.name)
        return False
    except pexc.VMPowerOffFailure:
        LOG.warning(_("Non-IBMi OS immediate shutdown failed.  Trying VSP "
                      "normal shutdown.  Partition: %s"), part.name)
        # Fall through to VSP normal, but with default timeout
        timeout = CONF.pypowervm_job_request_timeout
    except pexc.OSShutdownNoRMC as error:
        LOG.warning(error.args[0])
        # Fall through to VSP normal

    # ==> VSP normal
    try:
        PowerOp.stop(part, opts.vsp_normal(), timeout=timeout)
        return True
    except pexc.VMPowerOffFailure:
        LOG.warning(_("Non-IBMi VSP normal shutdown failed.  Trying VSP hard "
                      "shutdown.  Partition: %s"), part.name)

    return False


def _power_off_single(part, opts, force_immediate, timeout):
    """No-retry single power-off operation.

    :param part force_immediate timeout: See power_off.
                                    force_immediate is either TRUE or NO_RETRY.
    :param opts: A PowerOffOpts instance.  The operation and immediate params
                 are overwritten by this method.  Any other options (such as
                 restart) remain unaffected.
    :raise VMPowerOffFailure: If the operation failed.
    :raise VMPowerOffTimeout: If the operation timed out.
    """
    # If force_immediate=TRUE, always VSP hard shutdown.
    if force_immediate == Force.TRUE:
        PowerOp.stop(part, opts=opts.vsp_hard(), timeout=timeout)
    # If no retries, just do the single "soft" power-off requested
    elif force_immediate == Force.NO_RETRY:
        # opts is already set up for soft_detect
        PowerOp.stop(part, opts=opts, timeout=timeout)

    return


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
    :param restart: DEPRECATED: Use a PowerOffOpts instance for add_parms, with
                    restart specified therein.
                    Boolean.  Perform a restart after the power off.  If
                    add_parms is a PowerOffOpts instance, this parameter is
                    ignored.
    :param timeout: Time in seconds to wait for the instance to stop.
    :param add_parms: A power_opts.PowerOffOpts instance; or (deprecated) a
                      dict of parameters to pass directly to the job template.
                      If unspecified, a default PowerOffOpts instance is used,
                      with operation/immediate/restart depending on the
                      force_immediate and restart parameters, and no additional
                      options.
    :raise VMPowerOffFailure: If the operation failed (possibly after retrying)
    :raise VMPowerOffTimeout: If the operation timed out (possibly after
                              retrying).
    """
    opts, legacy = _legacy_power_opts(popts.PowerOffOpts, add_parms)
    if legacy:
        # Decide whether to insist on 'immediate' for OS shutdown.  Do that
        # only if add_parms explicitly included immediate=true.  Otherwise, let
        # soft_detect decide.
        opts.soft_detect(part, immed_if_os=opts.is_immediate or None)
        # Add the restart option if necessary.
        opts.restart(value=restart)

    if force_immediate != Force.ON_FAILURE:
        return _power_off_single(part, opts, force_immediate, timeout)

    # Do the progressive-retry sequence appropriate to the partition type and
    # the force_immediate flag.
    if part.env == bp.LPARType.OS400:
        # The IBMi progression.
        if _pwroff_soft_ibmi_flow(part, opts, timeout):
            return
            # Fall through to VSP hard
    else:
        # The non-IBMi progression.
        if _pwroff_soft_standard_flow(part, opts, timeout):
            return
            # Fall through to VSP hard

    # If we got here, force_immediate == ON_FAILURE, so fall back to VSP hard.
    # Let this one finish or raise.
    # ==> VSP hard
    LOG.warning(_("VSP hard shutdown with default timeout.  Partition: %s"),
                part.name)
    PowerOp.stop(part, opts.vsp_hard())
