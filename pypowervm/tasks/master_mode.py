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

"""Tasks to request and release master mode."""

import logging

from oslo_config import cfg

import pypowervm.const as c
import pypowervm.log as lgc
from pypowervm.wrappers import job
import pypowervm.wrappers.managed_system as ms

LOG = logging.getLogger(__name__)

CONF = cfg.CONF
CONF.import_opt('powervm_job_request_timeout', 'pypowervm.wrappers.job')

_SUFFIX_PARM_REQUEST_MASTER = 'RequestMaster'
_SUFFIX_PARM_RELEASE_MASTER = 'ReleaseMaster'

CO_MGMT_MASTER_STATUS = "coManagementMasterStatus"


class MasterMode(object):
    NORMAL = "norm"
    TEMP = "temp"


@lgc.logcall
def request_master(msys, mode=MasterMode.NORMAL,
                   timeout=CONF.powervm_job_request_timeout):
    resp = msys.adapter.read(ms.System.schema_type, msys.uuid,
                             suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm=_SUFFIX_PARM_REQUEST_MASTER)
    job_wrapper = job.Job.wrap(resp.entry)
    job_parms = [job_wrapper.create_job_parameter(CO_MGMT_MASTER_STATUS,
                                                  mode)]
    job_wrapper.run_job(msys.uuid, job_parms=job_parms, timeout=timeout)


@lgc.logcall
def release_master(msys, timeout=CONF.powervm_job_request_timeout):
    resp = msys.adapter.read(ms.System.schema_type, msys.uuid,
                             suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm=_SUFFIX_PARM_RELEASE_MASTER)
    job_wrapper = job.Job.wrap(resp.entry)
    job_wrapper.run_job(msys.uuid, timeout=timeout)
