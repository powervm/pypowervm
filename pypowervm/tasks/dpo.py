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
import json
from oslo_log import log as logging
import pypowervm.adapter as adp
import pypowervm.const as c
from pypowervm.wrappers import dpo as dpo_w
from pypowervm.wrappers import entry_wrapper as ew
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
        job_result = job_w.get_job_results_message()
        lpars = json.loads(job_result)
        return lpars
    except Exception:
        LOG.exception('DPO Job failed')
        raise


def dpo_objects():
    vals = dpo_job()
    dposob = []
    for dpo in vals:
        id = dpo.get("LPAR_ID")
        vm = dpo.get("LPAR_NAME")
        affinity = dpo.get("CURRENT_AFFINITY_SCORE")
        dpoob = dpo_w.DPO.bld(ew.EntryWrapper.adapter,
                              id, vm, affinity)
        dposob.append(dpoob)
    return dposob
