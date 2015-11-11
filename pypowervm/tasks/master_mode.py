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

"""Tasks to request and release master mode."""

from oslo_config import cfg
from oslo_log import log as logging

import pypowervm.const as c
import pypowervm.log as lgc
from pypowervm.wrappers import job
import pypowervm.wrappers.managed_system as ms

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

_SUFFIX_PARM_REQUEST_MASTER = 'RequestMaster'
_SUFFIX_PARM_RELEASE_MASTER = 'ReleaseMaster'

CO_MGMT_MASTER_STATUS = "coManagementMasterStatus"


class MasterMode(object):
    """Valid master modes used when requesting master.

    NORMAL: Default mode
    TEMP:   When released, the original master is immediately restored.
    """
    NORMAL = "norm"
    TEMP = "temp"


@lgc.logcall
def request_master(msys, mode=MasterMode.NORMAL,
                   timeout=CONF.pypowervm_job_request_timeout):
    """Request master mode for the provided Managed System.

    :param msys: Managed System wrapper requesting master mode
    :param mode: The requested master mode type.
                 There are 2 options:
                     MasterMode.NORMAL ("norm"): default
                     MasterMode.TEMP ("temp"): when released, the original
                                               master is immediately restored
    :param timeout: maximum number of seconds for job to complete
    """
    resp = msys.adapter.read(ms.System.schema_type, msys.uuid,
                             suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm=_SUFFIX_PARM_REQUEST_MASTER)
    job_wrapper = job.Job.wrap(resp.entry)
    job_parms = [job_wrapper.create_job_parameter(CO_MGMT_MASTER_STATUS,
                                                  mode)]
    job_wrapper.run_job(msys.uuid, job_parms=job_parms, timeout=timeout)


@lgc.logcall
def release_master(msys, timeout=CONF.pypowervm_job_request_timeout):
    """Release master mode for the provided Managed System.

    :param msys: Managed System wrapper requesting master mode
    :param timeout: maximum number of seconds for job to complete
    """
    resp = msys.adapter.read(ms.System.schema_type, msys.uuid,
                             suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm=_SUFFIX_PARM_RELEASE_MASTER)
    job_wrapper = job.Job.wrap(resp.entry)
    job_wrapper.run_job(msys.uuid, timeout=timeout)
