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

"""Specialized tasks for VSN."""

from oslo_log import log as logging
import pypowervm.adapter as adp
from pypowervm import const as c
from pypowervm.i18n import _
from pypowervm.wrappers import job as pvm_job
from pypowervm.wrappers import managed_system as pvm_ms


LOG = logging.getLogger(__name__)

_DEL_VSN = 'RemoveVSN'
_TRA_VSN = 'TransferVSN'


def delete_vsn(vsn):
    """Delete VSN from system.

    Note: The job will delete given VNS .

    vsn: Given vsn number to be Deleted
    """
    adap = adp.Adapter()
    # Build up the job & invoke
    ms_uuid = pvm_ms.System.get(adap)[0].uuid

    resp = adap.read(
        pvm_ms.System.schema_type, root_id=ms_uuid,
        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=_DEL_VSN)
    job_w = pvm_job.Job.wrap(resp.entry)
    job_p = [job_w.create_job_parameter('VirtualSerialNumber', vsn)]

    try:
        job_w.run_job(ms_uuid, job_parms=job_p)
    except Exception:
        LOG.exception(_('VSN Delete failed'))
        raise


def transfer_vsn(vsn, mgmt_usr, mgmt_svr, sys):
    """Transfer VSN from systemi to other system.

    Note: The job will transfer given VNS .
    """
    adap = adp.Adapter()
    # Build up the job & invoke
    ms_uuid = pvm_ms.System.get(adap)[0].uuid

    resp = adap.read(
        pvm_ms.System.schema_type, root_id=ms_uuid,
        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=_TRA_VSN)
    job_w = pvm_job.Job.wrap(resp.entry)
    job_p = [job_w.create_job_parameter('VirtualSerialNumber', vsn)]
    job_p.append(job_w.create_job_parameter('TargetManagedSystem',
                 sys))
    job_p.append(job_w.create_job_parameter('UserName',
                 mgmt_usr))
    job_p.append(job_w.create_job_parameter('Host',
                 mgmt_svr))

    try:
        job_w.run_job(ms_uuid, job_parms=job_p)
    except Exception:
        LOG.exception(_('VSN Transfer failed'))
        raise
