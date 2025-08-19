# Copyright 2015, 2018 IBM Corp.
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

"""Tasks specific to DPO (LPARs and VIOSes)."""
from oslo_log import log as logging
import pypowervm.adapter as adp
import pypowervm.const as c
from pypowervm.wrappers import job
from pypowervm.wrappers import managed_system as pvm_ms

LOG = logging.getLogger(__name__)


def dpo_job():
    adap = adp.Adapter()
    # Build up the job & invoke
    ms_uuid = pvm_ms.System.get(adap)[0].uuid

    resp = adap.read(
        pvm_ms.System.schema_type, root_id=ms_uuid,
        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm='GetDPOStatus')
    job_w = job.Job.wrap(resp.entry)

    try:
        job_w.run_job(ms_uuid, job_parms=None)
        job_result = job_w.get_job_results_as_dict()
        return job_result
    except Exception:
        LOG.exception('DPO Job failed')
        raise
