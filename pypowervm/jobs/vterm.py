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

from nova.openstack.common import log as logging

from pypowervm.wrappers import constants as pvm_consts
from pypowervm.wrappers import job

LOG = logging.getLogger(__name__)


def _close_vterm(adapter, lpar_uuid):
        # Close vterm on the lpar
        # :param lpar_uuid: partition uuid
        resp = adapter.read(pvm_consts.LPAR, lpar_uuid,
                            suffixType=pvm_consts.SUFFIX_TYPE_DO,
                            suffixParm=pvm_consts.
                            SUFFIX_PARM_CLOSE_VTERM)
        job_wrapper = job.Job(resp.entry)

        try:
            job_wrapper.run_job(adapter, lpar_uuid)
        except Exception as e:
                # just log the error.
                # delete will handle error from HMC if failed to delete lpar
                LOG.debug('Failed to close vterm %s' % e)