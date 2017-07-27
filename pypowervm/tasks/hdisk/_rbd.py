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
from oslo_log import log as logging

import pypowervm.const as c
from pypowervm.wrappers import job
from pypowervm.wrappers.virtual_io_server import VIOS

LOG = logging.getLogger(__name__)
_JOB_NAME = "RBDExists"


def rbd_exists(adapter, vios_uuid, name):
    """Check if rbd exists on vios

    :param adapter: pypowervm adapter
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param name: Name of the rbd volume (pool/image)
    :return: The device name of the created volume.
    """

    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=(_JOB_NAME))
    job_wrapper = job.Job.wrap(resp)

    # Create job parameters
    job_parms = [job_wrapper.create_job_parameter('name', name)]
    job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
    results = job_wrapper.get_job_results_as_dict()

    return True if results.get('exists') == "true" else False
