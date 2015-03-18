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

import logging

from pypowervm.i18n import _
import pypowervm.wrappers.constants as pvm_consts
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as lpar

import six

LOG = logging.getLogger(__name__)

_SUFFIX_PARM_CLOSE_VTERM = 'CloseVterm'


def close_vterm(adapter, lpar_uuid):
    """Close the vterm associated with an lpar

    :param adapter: The adapter to talk over the API.
    :param lpar_uuid: partition uuid

    """
    # Close vterm on the lpar
    resp = adapter.read(lpar.LPAR.schema_type, lpar_uuid,
                        suffixType=pvm_consts.SUFFIX_TYPE_DO,
                        suffixParm=_SUFFIX_PARM_CLOSE_VTERM)
    job_wrapper = job.Job.wrap(resp.entry)

    try:
        job_wrapper.run_job(adapter, lpar_uuid)
    except Exception as e:
        # just log the error.
        emsg = six.text_type(e)
        LOG.exception(_('Unable to close vterm: %s') % emsg)
        raise
