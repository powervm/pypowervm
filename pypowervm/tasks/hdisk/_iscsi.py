# Copyright 2016 IBM Corp.
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

from oslo_log import log as logging

import pypowervm.const as c
from pypowervm.i18n import _
from pypowervm.wrappers import job
import pypowervm.wrappers.managed_system as ms

LOG = logging.getLogger(__name__)


def discover_volume(adapter, host_uuid, host_ip, user, password, IQN):
    """Runs iscsi discovery and login commands

    :param host_ip: The ip address of the iscsi target.
    :param user: The username needed for authentication.
    :param password: The password needed for authentication.
    :param IQN: The IQN of the created volume on the target.
    :return: The device name of the created volume.
    """
    resp = adapter.read(ms.System.schema_type, host_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=('ISCSIDiscovery'))
    job_wrapper = job.Job.wrap(resp)
    # Create job parameters
    job_parms = [job_wrapper.create_job_parameter('hostIp', host_ip)]
    job_parms.append(job_wrapper.create_job_parameter('password', password))
    job_parms.append(job_wrapper.create_job_parameter('user', user))
    try:
        job_wrapper.run_job(host_uuid, job_parms=job_parms, timeout=120)
        results = job_wrapper.get_job_results_as_dict()
    except Exception as error:
        LOG.error(_("Error during the discovery or login process for iSCSI "
                    "with host_ip %s"), host_ip)
        raise error
    # DEV_OUTPUT: [IQN1 dev1, IQN2 dev2]
    output = results.get('DEV_OUTPUT')
    # Find dev corresponding to given IQN
    return [dev.split()[1] for dev in output if dev.split()[0] == IQN][0]
