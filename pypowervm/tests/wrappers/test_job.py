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

import unittest

import pypowervm.adapter as adp
from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.job as jwrap

JOB_REQUEST_FILE = "job_request_power_off.txt"
JOB_RESPONSE_OK = "job_response_completed_ok.txt"
JOB_RESPONSE_FAILED = "job_response_completed_failed.txt"
JOB_RESPONSE_EXCEPTION = "job_response_exception.txt"

EXPECTED_ID = '1375391227297'
EXPECTED_STATUS = c.PVM_JOB_STATUS_COMPLETED_WITH_ERROR
EXPECTED_EXCEPTION_MESSAGE = 'This is an exception message'
EXPECTED_RESULTS_VALUE = 'This is an error message'
EXPECTED_GROUP_NAME = 'LogicalPartition'
EXPECTED_OPERATION_NAME = 'PowerOff'


ZERO_STR = '0'
ZERO_INT = 0


class TestJobEntryWrapper(unittest.TestCase):

    _request_wrapper = None
    _ok_wrapper = None
    _failed_wrapper = None
    _exception_wrapper = None
    _bad_wrapper = None

    def setUp(self):
        super(TestJobEntryWrapper, self).setUp()
        # request wrapper
        request = pvmhttp.load_pvm_resp(JOB_REQUEST_FILE).response
        self.assertNotEqual(request, None,
                            "Could not load %s " %
                            JOB_REQUEST_FILE)
        TestJobEntryWrapper._request_wrapper = jwrap.Job(request.entry)
        # ok wrapper
        response = pvmhttp.load_pvm_resp(JOB_RESPONSE_OK).response
        self.assertNotEqual(response, None,
                            "Could not load %s " %
                            JOB_RESPONSE_OK)
        TestJobEntryWrapper._ok_wrapper = jwrap.Job(response.entry)
        # failed wrapper
        response = pvmhttp.load_pvm_resp(JOB_RESPONSE_FAILED).response
        self.assertNotEqual(response, None,
                            "Could not load %s " %
                            JOB_RESPONSE_FAILED)
        TestJobEntryWrapper._failed_wrapper = jwrap.Job(response.entry)
        # exception wrapper
        response = pvmhttp.load_pvm_resp(JOB_RESPONSE_EXCEPTION).response
        self.assertNotEqual(response, None,
                            "Could not load %s " %
                            JOB_RESPONSE_EXCEPTION)
        TestJobEntryWrapper._exception_wrapper = jwrap.Job(response.entry)
        TestJobEntryWrapper._exception_wrapper.op = 'CLIRunner'

        # Create a bad wrapper to use when retrieving properties which don't
        # exist
        TestJobEntryWrapper._bad_wrapper = jwrap.Job(request.entry)

        self.set_test_property_values()

        self._fake_oper = adp.Adapter(None, use_cache=False)

    def set_single_value(self, entry, property_name, value):
        prop = entry.element.find(property_name)
        self.assertNotEqual(prop, None,
                            "Could not find property %s." % property_name)

        prop.text = str(value)

    def set_test_property_values(self):
        """Set expected values in entry so test code can work consistently."""
        tc = TestJobEntryWrapper
        self.set_single_value(tc._ok_wrapper._entry,
                              c.JOB_ID, EXPECTED_ID)
        self.set_single_value(tc._request_wrapper._entry,
                              c.JOB_GROUP_NAME,
                              EXPECTED_GROUP_NAME)
        self.set_single_value(tc._request_wrapper._entry,
                              c.JOB_OPERATION_NAME,
                              EXPECTED_OPERATION_NAME)
        self.set_single_value(tc._failed_wrapper._entry,
                              c.JOB_STATUS,
                              EXPECTED_STATUS)
        self.set_single_value(tc._exception_wrapper._entry,
                              c.JOB_MESSAGE,
                              EXPECTED_EXCEPTION_MESSAGE)
        # results value containing the message is the second one in a list
        props = tc._failed_wrapper._entry.element.findall(
            c.JOB_RESULTS_VALUE)
        props[1].text = str(EXPECTED_RESULTS_VALUE)

    def verify_equal(self, method_name, returned_value, expected_value):
        if returned_value is not None and expected_value is not None:
            returned_type = type(returned_value)
            expected_type = type(expected_value)
            self.assertEqual(returned_type, expected_type,
                             "%s: type mismatch.  "
                             "Returned %s(%s). Expected %s(%s)" %
                             (method_name,
                              returned_value, returned_type,
                              expected_value, expected_type))

        self.assertEqual(returned_value, expected_value,
                         "%s returned %s instead of %s"
                         % (method_name, returned_value, expected_value))

    def call_simple_getter(self,
                           wrapper,
                           method_name,
                           expected_value,
                           expected_bad_value):

        # Use __getattribute__ to dynamically call the method
        value = wrapper.__getattribute__(
            method_name)()
        self.verify_equal(method_name, value, expected_value)

        bad_value = TestJobEntryWrapper._bad_wrapper.__getattribute__(
            method_name)()
        self.verify_equal(method_name, bad_value, expected_bad_value)

    def test_get_job_id(self):
        self.call_simple_getter(TestJobEntryWrapper._ok_wrapper,
                                "get_job_id", EXPECTED_ID, None)

    def test_get_job_status(self):
        self.call_simple_getter(TestJobEntryWrapper._failed_wrapper,
                                "get_job_status", EXPECTED_STATUS, None)

    def test_get_job_message(self):
        self.call_simple_getter(TestJobEntryWrapper._exception_wrapper,
                                "get_job_message",
                                EXPECTED_EXCEPTION_MESSAGE, '')

    def test_get_job_response_exception_message(self):
        self.call_simple_getter(TestJobEntryWrapper._exception_wrapper,
                                "get_job_response_exception_message",
                                EXPECTED_EXCEPTION_MESSAGE, '')

    def test_get_job_results_message(self):
        self.call_simple_getter(TestJobEntryWrapper._failed_wrapper,
                                "get_job_results_message",
                                EXPECTED_RESULTS_VALUE, '')

    def test_job_parameters(self):
        input_name1 = 'JobParmName1'
        input_name2 = 'JobParmName2'
        input_value1 = 'JobParmValue1'
        input_value2 = 'JobParmValue2'
        wrapper = TestJobEntryWrapper._request_wrapper
        job_parms = [
            wrapper.create_job_parameter(input_name1, input_value1),
            wrapper.create_job_parameter(input_name2, input_value2)]
        wrapper.add_job_parameters_to_existing(*job_parms)
        elements = wrapper._entry.element.findall(
            './JobParameters/JobParameter/ParameterName')
        names = []
        for element in elements:
            names.append(element.text)
        self.assertEqual(input_name1, names[0],
                         "Job names don't match")
        self.assertEqual(input_name2, names[1],
                         "Job names don't match")
        elements = wrapper._entry.element.findall(
            './JobParameters/JobParameter/ParameterValue')
        values = []
        for element in elements:
            values.append(element.text)
        self.assertEqual(input_value1, values[0],
                         "Job values don't match")
        self.assertEqual(input_value2, values[1],
                         "Job values don't match")

        # run_job, monitor_job and delete_job are unit tested in
        # file lpar/test_lpar_power_operations

if __name__ == "__main__":
    unittest.main()
