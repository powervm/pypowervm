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
import pypowervm.wrappers.managed_system as ms

LOG = logging.getLogger(__name__)

CONF = cfg.CONF
CONF.import_opt('powervm_job_request_timeout', 'pypowervm.wrappers.job')

_SUFFIX_PARM_POWER_ON = 'PowerOn'
_SUFFIX_PARM_POWER_OFF = 'PowerOff'


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
def power_off(part, host_uuid, force_immediate=False, restart=False,
              timeout=CONF.powervm_job_request_timeout, add_parms=None):
    """Will Power Off a Logical Partition or Virtual I/O Server.

    :param part: The LPAR/VIOS wrapper of the instance to power off.
    :param host_uuid: TEMPORARY - The host system UUID that the instance
                      resides on.
    :param force_immediate: Boolean.  Perform an immediate power off.
    :param restart: Boolean.  Perform a restart after the power off.
    :param timeout: value in seconds for specifying how long to wait for the
                    instance to stop.
    :param add_parms: dict of parameters to pass directly to the job template
    """
    return _power_on_off(part, _SUFFIX_PARM_POWER_OFF, host_uuid,
                         force_immediate=force_immediate, restart=restart,
                         timeout=timeout, add_parms=add_parms)


def _power_on_off(part, suffix, host_uuid, force_immediate=False,
                  restart=False, timeout=CONF.powervm_job_request_timeout,
                  add_parms=None, synchronous=True):
    """Internal function to power on or off an instance.

    :param part: The LPAR/VIOS wrapper of the instance to act on.
    :param suffix: power option - 'PowerOn' or 'PowerOff'.
    :param host_uuid: TEMPORARY - The host system UUID that the LPAR/VIOS
                      resides on
    :param force_immediate: Boolean.  Do immediate shutdown (for PowerOff
                            suffix only)
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
    try:
        while not complete:
            resp = adapter.read(part.schema_type, uuid,
                                suffix_type=c.SUFFIX_TYPE_DO,
                                suffix_parm=suffix)
            job_wrapper = job.Job.wrap(resp.entry)
            job_parms = []
            if suffix == _SUFFIX_PARM_POWER_OFF:
                operation = 'shutdown'
                add_immediate = False
                if force_immediate:
                    add_immediate = True
                elif part is not None:
                    if part.rmc_state == bp.RMCState.ACTIVE:
                        operation = 'osshutdown'
                    elif (part.env == bp.LPARType.OS400 and
                            part.ref_code == '00000000'):
                        operation = 'osshutdown'
                    else:
                        add_immediate = True
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
                        job_parms.append(
                            job_wrapper.create_job_parameter(
                                kw, str(add_parms[kw])))
            try:
                job_wrapper.run_job(uuid, job_parms=job_parms, timeout=timeout,
                                    synchronous=synchronous)
                complete = True
            except pexc.JobRequestTimedOut as error:
                if (suffix == _SUFFIX_PARM_POWER_OFF and
                        operation == 'osshutdown'):
                    # This has timed out, we loop again and attempt to
                    # force immediate now.  Should not re-hit this exception
                    # block
                    timeout = CONF.powervm_job_request_timeout
                    force_immediate = True
                else:
                    emsg = six.text_type(error)
                    LOG.exception(_('Error: %s') % emsg)
                    if suffix == _SUFFIX_PARM_POWER_OFF:
                        raise pexc.VMPowerOffFailure(reason=emsg,
                                                     lpar_nm=part.name)
                    else:
                        raise pexc.VMPowerOnFailure(reason=emsg,
                                                    lpar_nm=part.name)
            except pexc.JobRequestFailed as error:
                emsg = six.text_type(error)
                LOG.exception(_('Error: %s') % emsg)
                if suffix == _SUFFIX_PARM_POWER_OFF:
                    # If already powered off and not a reboot,
                    # don't send exception
                    if 'HSCL1558' in emsg and not restart:
                        complete = True
                    # If failed because RMC is now down, retry with force
                    elif 'HSCL0DB4' in emsg and operation == 'osshutdown':
                        timeout = CONF.powervm_job_request_timeout
                        force_immediate = True
                    else:
                        raise pexc.VMPowerOffFailure(reason=emsg,
                                                     lpar_nm=part.name)
                else:
                    # If already powered on, don't send exception
                    if 'HSCL3681' in emsg:
                        complete = True
                    else:
                        raise pexc.VMPowerOnFailure(reason=emsg,
                                                    lpar_nm=part.name)

    # Invalidate the LPARentry in the adapter cache so the consumers get
    # the current LPAR state by forcing a subsequent read. Feeds must be
    # invalidated too, since the adapter will use them if an entry is not in
    # the cache.
    finally:
        try:
            adapter.invalidate_cache_elem(
                ms.System.schema_type, root_id=host_uuid,
                child_type=part.schema_type, child_id=uuid,
                invalidate_feeds=True)
        except Exception as e:
            LOG.exception(_('Error invalidating adapter cache for LPAR '
                            ' %(lpar_name) with UUID %(lpar_uuid)s: %(exc)s') %
                          {'lpar_name': part.name, 'lpar_uuid': uuid,
                           'exc': six.text_type(e)})
