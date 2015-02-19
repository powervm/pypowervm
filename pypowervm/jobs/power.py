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

import logging

from oslo.config import cfg

from pypowervm import exceptions as pexc
from pypowervm.i18n import _
from pypowervm import log as lgc
from pypowervm.wrappers import constants as c
from pypowervm.wrappers import job

import six

LOG = logging.getLogger(__name__)

CONF = cfg.CONF
CONF.import_opt('powervm_job_request_timeout', 'pypowervm.wrappers.job')

# Valid values for bootmode parameter on power_on
BOOTMODE_NORM = 'norm'
BOOTMODE_SMS = 'sms'
BOOTMODE_DD = 'dd'
BOOTMODE_DS = 'ds'
BOOTMODE_OF = 'of'


@lgc.logcall
def power_on(adapter, lpar, host_uuid, add_parms=None):
    """Will Power On a Logical Partition.

    :param adapter: The pypowervm adapter object.
    :param lpar: The LogicalPartition wrapper of the instance to power on.
    :param host_uuid: TEMPORARY - The host system UUID that the instance
                      resides on.
    :param add_parms: dict of parameters to pass directly to the job template
    """
    return _power_on_off(
        adapter, lpar, c.SUFFIX_PARM_POWER_ON, host_uuid, add_parms=add_parms)


@lgc.logcall
def power_off(adapter, lpar, host_uuid, force_immediate=False,
              restart=False, timeout=CONF.powervm_job_request_timeout,
              add_parms=None):
    """Will Power Off a LPAR.

    :param adapter: The pypowervm adapter object.
    :param lpar: The LogicalPartition wrapper of the instance to power off.
    :param host_uuid: TEMPORARY - The host system UUID that the instance
                      resides on.
    :param force_immediate: Boolean.  Perform an immediate power off.
    :param restart: Boolean.  Perform a restart after the power off.
    :param timeout: value in seconds for specifying how long to wait for the
                    instance to stop.
    :param add_parms: dict of parameters to pass directly to the job template
    """
    return _power_on_off(adapter, lpar, c.SUFFIX_PARM_POWER_OFF, host_uuid,
                         force_immediate, restart, timeout,
                         add_parms=add_parms)


def _power_on_off(adapter, lpar, suffix, host_uuid,
                  force_immediate=False, restart=False,
                  timeout=CONF.powervm_job_request_timeout, add_parms=None):
    """Internal function to power on or off an instance.

    :param adapter: The pypowervm adapter.
    :param lpar: The LogicalPartition wrapper of the instance to act on.
    :param suffix: power option - 'PowerOn' or 'PowerOff'.
    :param host_uuid: TEMPORARY - The host system UUID that the LPAR resides on
    :param force_immediate: Boolean.  Do immediate shutdown
                            (for PowerOff suffix only)
    :param restart: Boolean.  Do a restart after power off
                            (for PowerOff suffix only)
    :param timeout: Value in seconds for specifying
                    how long to wait for the LPAR to stop
                    (for PowerOff suffix only)
    :param add_parms: dict of parameters to pass directly to the job template
    """
    complete = False
    uuid = lpar.uuid
    try:
        while not complete:
            resp = adapter.read(c.LPAR, uuid, suffix_type=c.SUFFIX_TYPE_DO,
                                suffix_parm=suffix)
            job_wrapper = job.Job(resp.entry)
            job_parms = []
            if suffix == c.SUFFIX_PARM_POWER_OFF:
                operation = 'shutdown'
                add_immediate = False
                if force_immediate:
                    add_immediate = True
                elif lpar is not None:
                    rmc_state = lpar.check_dlpar_connectivity()[1]
                    if rmc_state == 'active':
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
                job_wrapper.run_job(adapter, uuid, job_parms=job_parms,
                                    timeout=timeout)
                complete = True
            except pexc.JobRequestTimedOut as error:
                if (suffix == c.SUFFIX_PARM_POWER_OFF and
                        operation == 'osshutdown'):
                    # This has timed out, we loop again and attempt to
                    # force immediate now.  Should not re-hit this exception
                    # block
                    timeout = CONF.powervm_job_request_timeout
                    force_immediate = True
                else:
                    emsg = six.text_type(error)
                    LOG.exception(_('Error: %s') % emsg)
                    if suffix == c.SUFFIX_PARM_POWER_OFF:
                        raise pexc.VMPowerOffFailure(reason=emsg,
                                                     lpar_nm=lpar.name)
                    else:
                        raise pexc.VMPowerOnFailure(reason=emsg,
                                                    lpar_nm=lpar.name)
            except pexc.JobRequestFailed as error:
                emsg = six.text_type(error)
                LOG.exception(_('Error: %s') % emsg)
                if suffix == c.SUFFIX_PARM_POWER_OFF:
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
                                                     lpar_nm=lpar.name)
                else:
                    # If already powered on, don't send exception
                    if 'HSCL3681' in emsg:
                        complete = True
                    else:
                        raise pexc.VMPowerOnFailure(reason=emsg,
                                                    lpar_nm=lpar.name)

    # Invalidate the LPARentry in the adapter cache so the consumers get
    # the current LPAR state by forcing a subsequent read. Feeds must be
    # invalidated too, since the adapter will use them if an entry is not in
    # the cache.
    finally:
        try:
            adapter.invalidate_cache_elem(c.MGT_SYS, root_id=host_uuid,
                                          child_type=c.LPAR, child_id=uuid,
                                          invalidate_feeds=True)
        except Exception as e:
            LOG.exception(_('Error invalidating adapter cache for LPAR '
                            ' %(lpar_name) with UUID %(lpar_uuid)s: %(exc)s') %
                          {'lpar_name': lpar.name, 'lpar_uuid': uuid,
                           'exc': six.text_type(e)})
