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

from pypowervm import adapter as adpt
from pypowervm import const as c
from pypowervm import exceptions as pvm_exc
from pypowervm.tests.test_utils import pvmhttp
import pypowervm.wrappers.job as job


def load_file(file_name, adapter=None):
    """Helper method to load the responses from a given location."""
    return pvmhttp.load_pvm_resp(file_name, adapter).get_response()


def raiseRetryException():
    """Used for other tests wishing to raise an exception to a force retry."""
    resp = adpt.Response('reqmethod', 'reqpath', c.HTTPStatus.ETAG_MISMATCH,
                         'reason', 'headers')
    http_exc = pvm_exc.HttpError(resp)
    raise http_exc


def get_parm_checker(test_obj, exp_uuid, exp_job_parms, exp_job_mappings=[],
                     exp_timeout=None):
    # Utility method to return a dynamic parameter checker for tests

    # Build the expected job parameter strings
    exp_job_parms_str = [job.Job.create_job_parameter(k, v).toxmlstring()
                         for k, v in exp_job_parms]
    exp_job_parms_str += [
        job.Job.create_job_parameter(k, ",".join(v)).toxmlstring()
        for k, v in exp_job_mappings]

    def parm_checker(uuid, job_parms=None, timeout=None):
        # Check simple parms
        test_obj.assertEqual(exp_uuid, uuid)
        test_obj.assertEqual(exp_timeout, timeout)

        # Check the expected and actual number of job parms are equal
        test_obj.assertEqual(len(exp_job_parms_str), len(job_parms))

        # Ensure each parameter is in the list of expected.
        for parm in job_parms:
            test_obj.assertIn(parm.toxmlstring(), exp_job_parms_str)

    # We return our custom checker
    return parm_checker
