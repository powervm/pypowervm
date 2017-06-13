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


def _pwroff_soft_ibmi_flow(part, restart, immediate, timeout):
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

    :param part restart timeout: See power_off.
    :param immediate: Boolean.  Indicates whether to try os-normal first
                      (False, the default) before progressing to os-immediate.
                      If True, skip trying os-normal shutdown.
    :return: True if the power-off succeeded; False otherwise.
    :raise VMPowerOffTimeout: If the last power-off attempt timed out.
    :raise VMPowerOffFailure: If the last power-off attempt failed.
    """
    opts = popts.PowerOffOpts().restart(value=restart)
    # If immediate was already specified, skip OS-normal.
    if not immediate:
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
        LOG.warning("IBMi VSP normal shutdown failed.  Partition: %s",
                    part.name)

    return False


def _pwroff_soft_standard_flow(part, restart, timeout):
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

    :param part restart timeout: See power_off.
    :return: True if the power-off succeeded; False otherwise.
    :raise VMPowerOffTimeout: If the last power-off attempt timed out.
    :raise VMPowerOffFailure: If the last power-off attempt failed.
    """
    # For backward compatibility, OS shutdown is always immediate.  We don't
    # let PowerOn decide whether to use OS or VSP; instead we trap
    # OSShutdownNoRMC (which is very quick) so we can keep this progression
    # linear.

    opts = popts.PowerOffOpts().restart(value=restart)
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
        LOG.warning("Non-IBMi VSP normal shutdown failed.  Partition: %s",
                    part.name)

    return False


def _power_off_progressive(part, timeout, restart, ibmi_immed=False):

    # Do the progressive-retry sequence appropriate to the partition type.
    if part.env == bp.LPARType.OS400:
        # The IBMi progression.
        if _pwroff_soft_ibmi_flow(part, restart, ibmi_immed, timeout):
            return
            # Fall through to VSP hard
    else:
        # The non-IBMi progression.
        if _pwroff_soft_standard_flow(part, restart, timeout):
            return
            # Fall through to VSP hard

    # If we got here, force_immediate == ON_FAILURE, so fall back to VSP hard.
    # Let this one finish or raise.
    # ==> VSP hard
    LOG.warning(_("VSP hard shutdown with default timeout.  Partition: %s"),
                part.name)
    PowerOp.stop(part, popts.PowerOffOpts().vsp_hard().restart(value=restart))


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

    DEPRECATED.  Use PowerOp.stop() for single power-off.
                 Use power_off_progressive for soft-retry flows.

    Depending on the force_immediate flag and the partition's type and RMC
    state, this method may attempt increasingly aggressive mechanisms for
    shutting down the OS if initial attempts fail or time out.

    :param part: The LPAR/VIOS wrapper of the instance to power off.
    :param host_uuid: Not used.  Retained for backward compatibility.
    :param force_immediate: DEPRECATED.
        - If you want Force.NO_RETRY behavior, use PowerOp.stop() with the
          specific operation/immediate settings desired.
        - If you want Force.TRUE behavior, use
          PowerOp.stop(..., opts=PowerOffOpts().vsp_hard())
        - If add_parms is a PowerOffOpts with an operation set, force_immediate
          (and restart) is ignored - the method call is equivalent to:
          PowerOp.stop(part, opts=add_parms, timeout=timeout)
        - This flag retains its legacy behavior only if add_parms is either a
          legacy dict or a PowerOffOpts with no operation set:
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
    import warnings
    warnings.warn("The power_off method is deprecated.  Please use either "
                  "PowerOp.stop or power_off_progressive.", DeprecationWarning)

    opts, legacy = _legacy_power_opts(popts.PowerOffOpts, add_parms)
    if legacy:
        # Decide whether to insist on 'immediate' for OS shutdown.  Do that
        # only if add_parms explicitly included immediate=true.  Otherwise, let
        # soft_detect decide.
        opts.soft_detect(part, immed_if_os=opts.is_immediate or None)
        # Add the restart option if necessary.
        opts.restart(value=restart)
    elif opts.is_param_set(popts.PowerOffOperation.KEY):
        # If a PowerOffOpt was provided with no operation, it's just being used
        # to specify e.g. restart, and we should fall through to the soft
        # flows.  But if an operation was specified, we just want to do that
        # single operation.  Setting NO_RETRY results in using whatever hard/
        # immediate setting is in the PowerOffOpt.
        force_immediate = Force.NO_RETRY

    if force_immediate != Force.ON_FAILURE:
        return _power_off_single(part, opts, force_immediate, timeout)

    # Do the progressive-retry sequence appropriate to the partition type and
    # the force_immediate flag.
    _power_off_progressive(part, timeout, restart,
                           ibmi_immed=opts.is_immediate)


def power_off_progressive(part, restart=False, ibmi_immed=False,
                          timeout=CONF.pypowervm_job_request_timeout):
    """Attempt soft power-off, retrying with increasing aggression on failure.

    IBMi partitions always start with OS shutdown.  If ibmi_immed == False,
    os-normal shutdown is tried first; then os-immediate; then vsp-normal; then
    vsp-hard.  If ibmi_immed == True, os-normal is skipped, but the rest of the
    progression is the same.

    For non-IBMi partitions:
    If RMC is up, os-immediate is tried first.  If this times out, vsp hard is
    performed next; otherwise, vsp-normal is attempted before vsp-hard.
    If RMC is down, vsp-normal is tried first, then vsp-hard.

    :param part: The LPAR/VIOS wrapper of the instance to power off.
    :param restart: Boolean.  Perform a restart after the power off.
    :param ibmi_immed: Boolean.  Indicates whether to try os-normal first
                        (False, the default) before progressing to
                        os-immediate.  If True, skip trying os-normal shutdown.
                        Only applies to IBMi partitions.
    :param timeout: Time in seconds to wait for the instance to stop.  This is
                    only applied to the first attempt in the progression.
    :raise VMPowerOffFailure: If the last attempt in the progression failed.
    :raise VMPowerOffTimeout: If the last attempt in the progression timed out.
    """
    _power_off_progressive(part, timeout, restart, ibmi_immed=ibmi_immed)
