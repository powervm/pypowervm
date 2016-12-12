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

_SUFFIX_PARM_POWER_ON = 'PowerOn'
_SUFFIX_PARM_POWER_OFF = 'PowerOff'
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


@lgc.logcall
def power_on(part, host_uuid, add_parms=None, synchronous=True):
    """Will Power On a Logical Partition or Virtual I/O Server.

    :param part: The LPAR/VIOS wrapper of the partition to power on.
    :param host_uuid: TEMPORARY - The host system UUID that the instance
                      resides on.
    :param add_parms: dict of parameters to pass directly to the job template
    :param synchronous: If True (the default), this method will not return
                        until the PowerOn Job completes (whether success or
                        failure) or times out.  If False, this method will
                        return as soon as the Job has started on the server
                        (that is, achieved any state beyond NOT_ACTIVE).  Note
                        that timeout is still possible in this case.
    """
    return _power_on_off(part, _SUFFIX_PARM_POWER_ON, host_uuid,
                         add_parms=add_parms, synchronous=synchronous)


@lgc.logcall
def power_off(part, host_uuid, force_immediate=Force.ON_FAILURE, restart=False,
              timeout=CONF.pypowervm_job_request_timeout, add_parms=None):
    """Will Power Off a Logical Partition or Virtual I/O Server.

    :param part: The LPAR/VIOS wrapper of the instance to power off.
    :param host_uuid: TEMPORARY - The host system UUID that the instance
                      resides on.
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
    """
    return _power_on_off(part, _SUFFIX_PARM_POWER_OFF, host_uuid,
                         force_immediate=force_immediate, restart=restart,
                         timeout=timeout, add_parms=add_parms)


def _power_on_off(part, suffix, host_uuid, force_immediate=Force.ON_FAILURE,
                  restart=False, timeout=CONF.pypowervm_job_request_timeout,
                  add_parms=None, synchronous=True):
    """Internal function to power on or off an instance.

    :param part: The LPAR/VIOS wrapper of the instance to act on.
    :param suffix: power option - 'PowerOn' or 'PowerOff'.
    :param host_uuid: TEMPORARY - The host system UUID that the LPAR/VIOS
                      resides on
    :param force_immediate: (For PowerOff suffix only) One of the Force enum
                            values (defaulting to Force.ON_FAILURE), which
                            behave as follows:
            - Force.TRUE: The force-immediate option is included on the first
                          pass.
            - Force.NO_RETRY: The force-immediate option is not included.  If
                              the power-off fails or times out,
                              VMPowerOffFailure is raised immediately.
            - Force.ON_FAILURE: The force-immediate option is not included on
                                the first pass; but if the power-off fails
                                (including timeout), it is retried with the
                                force-immediate option added.
    :param restart: Boolean.  Do a restart after power off (for PowerOff suffix
                    only)
    :param timeout: Value in seconds for specifying how long to wait for the
                    LPAR/VIOS to stop (for PowerOff suffix only)
    :param add_parms: dict of parameters to pass directly to the job template
    :param synchronous: If True (the default), this method will not return
                        until the Job completes (whether success or failure) or
                        times out.  If False, this method will return as soon
                        as the Job has started on the server (that is, achieved
                        any state beyond NOT_ACTIVE).  Note that timeout is
                        still possible in this case.
    """
    complete = False
    uuid = part.uuid
    adapter = part.adapter
    normal_vsp_power_off = False
    add_immediate = part.env != bp.LPARType.OS400
    while not complete:
        resp = adapter.read(part.schema_type, uuid,
                            suffix_type=c.SUFFIX_TYPE_DO,
                            suffix_parm=suffix)
        job_wrapper = job.Job.wrap(resp.entry)
        job_parms = []
        if suffix == _SUFFIX_PARM_POWER_OFF:
            operation = 'osshutdown'
            if force_immediate == Force.TRUE:
                operation = 'shutdown'
                add_immediate = True
            # Do normal vsp shutdown if flag on or
            # if RMC not active (for non-IBMi)
            elif (normal_vsp_power_off or
                  (part.env != bp.LPARType.OS400 and
                   part.rmc_state != bp.RMCState.ACTIVE)):
                operation = 'shutdown'
                add_immediate = False
            job_parms.append(
                job_wrapper.create_job_parameter('operation', operation))
            if add_immediate:
                job_parms.append(
                    job_wrapper.create_job_parameter('immediate', 'true'))
            if restart:
                job_parms.append(
                    job_wrapper.create_job_parameter('restart', 'true'))

        # Add add_parms to the job
        if add_parms is not None:
            for kw in add_parms.keys():
                # Skip any parameters already set.
                if kw not in ['operation', 'immediate', 'restart']:
                    job_parms.append(job_wrapper.create_job_parameter(
                        kw, str(add_parms[kw])))
        try:
            job_wrapper.run_job(uuid, job_parms=job_parms, timeout=timeout,
                                synchronous=synchronous)
            complete = True
        except pexc.JobRequestTimedOut as error:
            if suffix == _SUFFIX_PARM_POWER_OFF:
                if operation == 'osshutdown' and (force_immediate ==
                                                  Force.ON_FAILURE):
                    # This has timed out, we loop again and attempt to
                    # force immediate vsp. Unless IBMi, in which case we
                    # will try an immediate osshutdown and then
                    # a vsp normal before then jumping to immediate vsp.
                    timeout = CONF.pypowervm_job_request_timeout
                    if part.env == bp.LPARType.OS400:
                        if not add_immediate:
                            add_immediate = True
                        else:
                            normal_vsp_power_off = True
                    else:
                        force_immediate = Force.TRUE
                # normal vsp power off did not work, try hard vsp power off
                elif normal_vsp_power_off:
                    timeout = CONF.pypowervm_job_request_timeout
                    force_immediate = Force.TRUE
                    normal_vsp_power_off = False
                else:
                    LOG.exception(error)
                    emsg = six.text_type(error)
                    raise pexc.VMPowerOffFailure(reason=emsg,
                                                 lpar_nm=part.name)
            else:
                # Power On timed out
                LOG.exception(error)
                emsg = six.text_type(error)
                raise pexc.VMPowerOnFailure(reason=emsg, lpar_nm=part.name)
        except pexc.JobRequestFailed as error:
            emsg = six.text_type(error)
            LOG.exception(_('Error: %s') % emsg)
            if suffix == _SUFFIX_PARM_POWER_OFF:
                # If already powered off and not a reboot,
                # don't send exception
                if (any(err_prefix in emsg
                        for err_prefix in _ALREADY_POWERED_OFF_ERRS) and
                        not restart):
                    complete = True
                # If failed for other reasons,
                # retry with normal vsp power off except for IBM i
                # where we try immediate osshutdown first
                elif operation == 'osshutdown' and (force_immediate ==
                                                    Force.ON_FAILURE):
                    timeout = CONF.pypowervm_job_request_timeout
                    if (part.env == bp.LPARType.OS400 and not add_immediate):
                        add_immediate = True
                    else:
                        force_immediate = Force.NO_RETRY
                        normal_vsp_power_off = True
                # normal vsp power off did not work, try hard vsp power off
                elif normal_vsp_power_off:
                    timeout = CONF.pypowervm_job_request_timeout
                    force_immediate = Force.TRUE
                    normal_vsp_power_off = False
                else:
                    raise pexc.VMPowerOffFailure(reason=emsg,
                                                 lpar_nm=part.name)
            else:
                # If already powered on, don't send exception
                if (any(err_prefix in emsg
                        for err_prefix in _ALREADY_POWERED_ON_ERRS)):
                    complete = True
                else:
                    raise pexc.VMPowerOnFailure(reason=emsg, lpar_nm=part.name)
