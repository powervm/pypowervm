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

import mock
import testtools

import pypowervm.exceptions as ex
import pypowervm.tests.test_fixtures as fx
from pypowervm.tests.test_utils import pvmhttp
import pypowervm.wrappers.job as jwrap

JOB_REQUEST_FILE = "job_request_power_off.txt"
JOB_RESPONSE_OK = "job_response_completed_ok.txt"
JOB_RESPONSE_FAILED = "job_response_completed_failed.txt"
JOB_RESPONSE_EXCEPTION = "job_response_exception.txt"

EXPECTED_ID = '1375391227297'
EXPECTED_STATUS = jwrap.JobStatus.COMPLETED_WITH_ERROR
EXPECTED_EXCEPTION_MESSAGE = 'This is an exception message'
EXPECTED_RESULTS_VALUE = 'This is an error message'
EXPECTED_GROUP_NAME = 'LogicalPartition'
EXPECTED_OPERATION_NAME = 'PowerOff'


class TestJobEntryWrapper(testtools.TestCase):

    def setUp(self):
        super(TestJobEntryWrapper, self).setUp()

        self.adpt = self.useFixture(fx.AdapterFx()).adpt

        def load(fname):
            resp = pvmhttp.load_pvm_resp(fname, adapter=self.adpt).response
            self.assertIsNotNone(resp, "Could not load %s " % fname)
            return jwrap.Job.wrap(resp)

        self._request_wrapper = load(JOB_REQUEST_FILE)
        self._ok_wrapper = load(JOB_RESPONSE_OK)
        self._failed_wrapper = load(JOB_RESPONSE_FAILED)
        self._exception_wrapper = load(JOB_RESPONSE_EXCEPTION)
        self._exception_wrapper.op = 'CLIRunner'

        # Create a bad wrapper to use when retrieving properties which don't
        # exist
        self._bad_wrapper = load(JOB_REQUEST_FILE)

        self.set_test_property_values()

    def set_single_value(self, entry, property_name, value):
        prop = entry.element.find(property_name)
        self.assertNotEqual(prop, None,
                            "Could not find property %s." % property_name)

        prop.text = str(value)

    def set_test_property_values(self):
        """Set expected values in entry so test code can work consistently."""
        self.set_single_value(self._ok_wrapper.entry,
                              jwrap._JOB_ID, EXPECTED_ID)
        self.set_single_value(self._request_wrapper.entry,
                              jwrap._JOB_GROUP_NAME,
                              EXPECTED_GROUP_NAME)
        self.set_single_value(self._request_wrapper.entry,
                              jwrap._JOB_OPERATION_NAME,
                              EXPECTED_OPERATION_NAME)
        self.set_single_value(self._failed_wrapper.entry,
                              jwrap._JOB_STATUS,
                              EXPECTED_STATUS)
        self.set_single_value(self._exception_wrapper.entry,
                              jwrap._JOB_MESSAGE,
                              EXPECTED_EXCEPTION_MESSAGE)
        # results value containing the message is the second one in a list
        props = self._failed_wrapper.entry.element.findall(
            jwrap._JOB_RESULTS_VALUE)
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
            method_name)
        if callable(value):
            value = value()
        self.verify_equal(method_name, value, expected_value)

        bad_value = self._bad_wrapper.__getattribute__(method_name)
        if callable(bad_value):
            bad_value = bad_value()
        self.verify_equal(method_name, bad_value, expected_bad_value)

    def test_get_job_id(self):
        self.call_simple_getter(self._ok_wrapper,
                                "job_id", EXPECTED_ID, None)

    def test_get_job_status(self):
        self.call_simple_getter(self._failed_wrapper,
                                "job_status", EXPECTED_STATUS, None)

    def test_get_job_message(self):
        self.call_simple_getter(self._exception_wrapper,
                                "get_job_message",
                                EXPECTED_EXCEPTION_MESSAGE, '')

    def test_get_job_resp_exception_msg(self):
        self.call_simple_getter(self._exception_wrapper,
                                "get_job_resp_exception_msg",
                                EXPECTED_EXCEPTION_MESSAGE, '')

    def test_get_job_results_message(self):
        self.call_simple_getter(self._failed_wrapper,
                                "get_job_results_message",
                                EXPECTED_RESULTS_VALUE, '')

    def test_job_parameters(self):
        input_name1 = 'JobParmName1'
        input_name2 = 'JobParmName2'
        input_value1 = 'JobParmValue1'
        input_value2 = 'JobParmValue2'
        wrapper = self._request_wrapper
        job_parms = [
            wrapper.create_job_parameter(input_name1, input_value1),
            wrapper.create_job_parameter(input_name2, input_value2)]
        wrapper.add_job_parameters_to_existing(*job_parms)
        elements = wrapper.entry.element.findall(
            'JobParameters/JobParameter/ParameterName')
        names = []
        for element in elements:
            names.append(element.text)
        self.assertEqual(input_name1, names[0],
                         "Job names don't match")
        self.assertEqual(input_name2, names[1],
                         "Job names don't match")
        elements = wrapper.entry.element.findall(
            'JobParameters/JobParameter/ParameterValue')
        values = []
        for element in elements:
            values.append(element.text)
        self.assertEqual(input_value1, values[0],
                         "Job values don't match")
        self.assertEqual(input_value2, values[1],
                         "Job values don't match")

    @mock.patch('pypowervm.wrappers.job.Job._monitor_job')
    @mock.patch('pypowervm.wrappers.job.Job.cancel_job')
    @mock.patch('pypowervm.wrappers.job.Job.delete_job')
    @mock.patch('pypowervm.wrappers.job.Job.job_status')
    def test_run_job(self, mock_status, mock_del, mock_cancel, mock_monitor):
        mock_status.__get__ = mock.Mock(
            return_value=jwrap.JobStatus.COMPLETED_OK)
        wrapper = self._request_wrapper
        # Synchronous
        # No timeout
        mock_monitor.return_value = False
        wrapper.run_job('uuid')
        self.adpt.create_job.assert_called_with(mock.ANY, 'LogicalPartition',
                                                'uuid', sensitive=False)
        self.assertEqual(1, mock_monitor.call_count)
        self.assertEqual(0, mock_cancel.call_count)
        self.assertEqual(1, mock_del.call_count)

        # Time out
        mock_monitor.reset_mock()
        mock_del.reset_mock()
        mock_monitor.return_value = True
        self.assertRaises(ex.JobRequestTimedOut, wrapper.run_job, 'uuid')
        self.assertEqual(1, mock_monitor.call_count)
        self.assertEqual(1, mock_cancel.call_count)
        self.assertEqual(0, mock_del.call_count)

        # Non-OK status
        mock_status.__get__.return_value = jwrap.JobStatus.COMPLETED_WITH_ERROR
        mock_monitor.reset_mock()
        mock_cancel.reset_mock()
        mock_monitor.return_value = False
        self.assertRaises(ex.JobRequestFailed, wrapper.run_job, 'uuid')
        self.assertEqual(0, mock_cancel.call_count)
        self.assertEqual(1, mock_del.call_count)

        # Asynchronous.  With no timeout, return right after monitor.  "Bad"
        # result isn't checked, delete is not called.
        mock_del.reset_mock()
        wrapper.run_job('uuid', synchronous=False)
        self.assertEqual(0, mock_del.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.poll_while_status')
    @mock.patch('pypowervm.wrappers.job.PollAndDeleteThread')
    def test_montor_job(self, mock_thread, mock_poll):
        wrapper = self._ok_wrapper
        # Synchronous is a pass-through to poll_while_status
        mock_poll.return_value = 'abc123'
        self.assertEqual('abc123', wrapper._monitor_job())
        mock_poll.assert_called_once_with(['RUNNING', 'NOT_STARTED'], mock.ANY,
                                          mock.ANY)
        self.assertEqual(0, mock_thread.call_count)

        # Asynchronous
        # Time out
        mock_poll.reset_mock()
        mock_poll.return_value = True
        self.assertTrue(wrapper._monitor_job(synchronous=False))
        mock_poll.assert_called_once_with(['NOT_STARTED'], mock.ANY, mock.ANY)
        self.assertEqual(0, mock_thread.call_count)

        # No timeout
        mock_poll.reset_mock()
        mock_poll.return_value = False
        thread_inst = mock.Mock()
        mock_thread.return_value = thread_inst
        self.assertFalse(wrapper._monitor_job(synchronous=False))
        mock_thread.assert_called_once_with(wrapper, False)
        thread_inst.start.assert_called_once_with()

    @mock.patch('time.time')
    @mock.patch('time.sleep')
    @mock.patch('pypowervm.wrappers.job.Job.job_status')
    def test_poll_while_status(self, mock_status, mock_sleep, mock_time):
        wrapper = self._ok_wrapper
        mock_status.__get__ = mock.Mock(return_value=jwrap.JobStatus.RUNNING)
        # Short-circuit if the status is already not in the list
        self.assertFalse(wrapper.poll_while_status(
            [jwrap.JobStatus.NOT_ACTIVE], 10, False))
        self.assertEqual(0, mock_sleep.call_count)
        self.assertEqual(1, mock_time.call_count)

        # Engineer a timeout after the third run
        mock_time.reset_mock()
        mock_time.side_effect = [0, 1, 2, 3, 4, 5]
        self.assertTrue(wrapper.poll_while_status(
            [jwrap.JobStatus.RUNNING], 3, False))
        self.assertEqual(3, mock_sleep.call_count)
        # Initial setup, bail on the fourth iteration
        self.assertEqual(5, mock_time.call_count)

        # "Infinite" timeout, status eventually becomes one not in the list
        mock_status.__get__.side_effect = ['a', 'b', 'c', 'd', 'e', 'f']
        mock_time.reset_mock()
        mock_time.side_effect = [0, 1, 2, 3, 4, 5]
        mock_sleep.reset_mock()
        self.assertFalse(wrapper.poll_while_status(['a', 'b', 'c', 'd', 'e'],
                                                   0, False))
        self.assertEqual(5, mock_sleep.call_count)
        # Only the initial timer setup
        self.assertEqual(6, mock_time.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.poll_while_status')
    @mock.patch('pypowervm.wrappers.job.Job.delete_job')
    def test_poll_and_delete_thread(self, mock_del, mock_poll):
        # OK
        jwrap.PollAndDeleteThread(self._ok_wrapper, 'sens').run()
        mock_poll.assert_called_once_with(['RUNNING'], 0, 'sens')
        mock_del.assert_called_once_with()

        # Not OK
        mock_poll.reset_mock()
        mock_del.reset_mock()
        with self.assertLogs(jwrap.__name__, 'ERROR'):
            jwrap.PollAndDeleteThread(self._failed_wrapper, 'sens').run()
        mock_poll.assert_called_once_with(['RUNNING'], 0, 'sens')
        mock_del.assert_called_once_with()

    @mock.patch('pypowervm.wrappers.job.Job.poll_while_status')
    @mock.patch('pypowervm.wrappers.job.Job.delete_job')
    def test_cancel_job_thread(self, mock_del, mock_poll):
        jwrap.CancelJobThread(self._ok_wrapper, 'sens').run()
        mock_poll.assert_called_once_with(['RUNNING', 'NOT_STARTED'],
                                          0, 'sens')
        mock_del.assert_called_once_with()

    @mock.patch('pypowervm.wrappers.job.CancelJobThread.start')
    @mock.patch('pypowervm.wrappers.job.Job.delete_job')
    @mock.patch('pypowervm.wrappers.job.Job._monitor_job')
    def test_cancel_job(self, mock_monitor, mock_delete, mock_start):
        wrapper = self._ok_wrapper
        self.adpt.update.side_effect = ex.Error('error')
        mock_monitor.return_value = False
        wrapper.cancel_job()
        self.adpt.update.assert_called_with(
            None, None, root_type='jobs', root_id=wrapper.job_id,
            suffix_type='cancel')
        self.assertEqual(0, mock_delete.call_count)
        self.adpt.update.reset_mock()
        self.adpt.update.side_effect = None
        mock_start.reset_mock()
        mock_monitor.return_value = False
        wrapper.cancel_job()
        self.adpt.update.assert_called_with(
            None, None, root_type='jobs', root_id=wrapper.job_id,
            suffix_type='cancel')
        self.assertEqual(1, mock_start.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.job_status')
    def test_delete_job(self, mock_status):
        wrapper = self._ok_wrapper
        mock_status.__get__ = mock.Mock(return_value=jwrap.JobStatus.RUNNING)
        with self.assertLogs(jwrap.__name__, 'ERROR'):
            self.assertRaises(ex.Error, wrapper.delete_job)
        mock_status.__get__.return_value = jwrap.JobStatus.COMPLETED_OK
        wrapper.delete_job()
        self.adpt.delete.assert_called_with('jobs', wrapper.job_id)
        self.adpt.delete.reset_mock()
        self.adpt.delete.side_effect = ex.Error('foo')
        with self.assertLogs(jwrap.__name__, 'ERROR'):
            wrapper.delete_job()
        self.adpt.delete.assert_called_with('jobs', wrapper.job_id)
