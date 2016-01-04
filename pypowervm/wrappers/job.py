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

"""EntryWrapper, constants, and enums around Job ('web' namespace)."""

import threading
import time

from oslo_config import cfg
from oslo_log import log as logging
import six

import pypowervm.const as pc
import pypowervm.entities as ent
import pypowervm.exceptions as pvmex
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

_JOBS = 'jobs'
_REQ_OP = 'RequestedOperation'
_JOB_GROUP_NAME = u.xpath(_REQ_OP, 'GroupName')
_JOB_OPERATION_NAME = u.xpath(_REQ_OP, 'OperationName')
_JOB_PARAM = u.xpath('Results', 'JobParameter')
_JOB_RESULTS_NAME = u.xpath(_JOB_PARAM, 'ParameterName')
_JOB_RESULTS_VALUE = u.xpath(_JOB_PARAM, 'ParameterValue')
_RESPONSE_EXCEPTION = 'ResponseException'
_JOB_MESSAGE = u.xpath(_RESPONSE_EXCEPTION, 'Message')
_JOB_STACKTRACE = u.xpath(_RESPONSE_EXCEPTION, 'StackTrace')
_JOB_STATUS = 'Status'
_JOB_ID = 'JobID'


class JobStatus(object):
    NOT_ACTIVE = 'NOT_STARTED'
    RUNNING = 'RUNNING'
    COMPLETED_OK = 'COMPLETED_OK'
    COMPLETED_WITH_WARNINGS = 'COMPLETED_WITH_WARNINGS'
    COMPLETED_WITH_ERROR = 'COMPLETED_WITH_ERROR'


class PollAndDeleteThread(threading.Thread):
    def __init__(self, job, sensitive):
        super(PollAndDeleteThread, self).__init__()
        self.job = job
        self.sensitive = sensitive

    def run(self):
        self.job.poll_while_status([JobStatus.RUNNING], 0, self.sensitive)
        self.job.delete_job()
        # If the Job failed, we still want to log it.
        if self.job.job_status != JobStatus.COMPLETED_OK:
            exc = pvmex.JobRequestFailed(
                operation_name=self.job.op, error=self.job.get_job_message())
            LOG.error(exc.args[0])


class CancelJobThread(threading.Thread):
    def __init__(self, job, sensitive):
        super(CancelJobThread, self).__init__()
        self.job = job
        self.sensitive = sensitive

    def run(self):
        self.job._monitor_job(timeout=0, sensitive=self.sensitive)
        self.job.delete_job()


@ewrap.EntryWrapper.pvm_type('Job', ns=pc.WEB_NS)
class Job(ewrap.EntryWrapper):
    """Wrapper object for job response schema."""

    @classmethod
    def wrap(cls, response_or_entry, etag=None):
        wrap = super(Job, cls).wrap(response_or_entry, etag=etag)
        wrap.op = wrap._get_val_str(_JOB_OPERATION_NAME)
        return wrap

    @staticmethod
    def create_job_parameter(name, value, cdata=False):
        """Creates a JobParameter Element.

           :param name: ParameterName text value
           :param value: ParameterValue text value
           :param cdata: If True, the value text will be wrapped in CDATA tags
           :returns: JobParameter Element
        """
        # JobParameter doesn't need adapter today
        adapter = None

        job_parm = ent.Element('JobParameter', adapter,
                               attrib={'schemaVersion': 'V1_0'},
                               ns=pc.WEB_NS)
        job_parm.append(ent.Element('ParameterName', adapter,
                                    text=name, ns=pc.WEB_NS))
        job_parm.append(ent.Element('ParameterValue', adapter,
                                    text=value, ns=pc.WEB_NS, cdata=cdata))
        return job_parm

    def add_job_parameters_to_existing(self, *add_parms):
        """Adds JobParameter Elements to existing JobParameters xml.

           Must be a job response entry.
           :param add_parms: list of JobParamters to add
        """
        job_parms = self.entry.element.find('JobParameters')
        for parm in add_parms:
            job_parms.append(parm)

    @property
    def job_id(self):
        """Gets the job ID string.

        :returns: String containing the job ID
        """
        return self._get_val_str(_JOB_ID)

    @property
    def job_status(self):
        """Gets the job status string.

        :returns: String containing the job status
        """
        return self._get_val_str(_JOB_STATUS)

    def get_job_resp_exception_msg(self, default=''):
        """Gets the job message string from the ResponseException.

        :returns: String containing the job message or
                  default (defaults to empty string) if not found
        """
        job_message = self._get_val_str(_JOB_MESSAGE, default)
        if job_message:
            # See if there is a stack trace to log
            stack_trace = self._get_val_str(_JOB_STACKTRACE, default)
            if stack_trace:
                LOG.error(pvmex.JobRequestFailed(operation_name=self.op,
                                                 error=stack_trace))
        return job_message

    def get_job_results_message(self, default=''):
        """Gets the job result message string.

        :returns: String containing the job result message or
                  default (defaults to empty string) if not found
        """
        message = default
        parm_names = self._get_vals(_JOB_RESULTS_NAME)
        parm_values = self._get_vals(_JOB_RESULTS_VALUE)
        for i in range(len(parm_names)):
            if parm_names[i] == 'result':
                message = parm_values[i]
                break
        return message

    def get_job_results_as_dict(self, default=None):
        """Gets the job results as a dictionary.

        :returns: Dictionary with result parm names and parm
                  values as key, value pairs.
        """
        results = default if default else {}
        parm_names = self._get_vals(_JOB_RESULTS_NAME)
        parm_values = self._get_vals(_JOB_RESULTS_VALUE)
        for i in range(len(parm_names)):
            results[parm_names[i]] = parm_values[i]
        return results

    def get_job_message(self, default=''):
        """Gets the job message string.

        It checks job results message first, if results message is not found,
        it checks for a ResponseException message. If neither is found, it
        returns the default.

        :returns: String containing the job message or
                  default (defaults to empty string) if not found
        """
        message = self.get_job_results_message(default=default)
        if not message:
            message = self.get_job_resp_exception_msg(default=default)
        return message

    def run_job(self, uuid, job_parms=None,
                timeout=CONF.pypowervm_job_request_timeout,
                sensitive=False, synchronous=True):
        """Invokes and polls a job.

        Adds job parameters to the job element if specified and calls the
        create_job method. It then monitors the job for completion and sends a
        JobRequestFailed exception if it did not complete successfully.

        :param uuid: uuid of the target
        :param job_parms: list of JobParamters to add
        :param timeout: maximum number of seconds for job to complete
        :param sensitive: If True, mask the Job payload in the logs.
        :param synchronous: If True (the default), wait for the Job to complete
                            or time out.  If False, return as soon as the Job
                            starts.  Note that this may still involve polling
                            (if the Job is waiting in queue to start), and may
                            still time out (if the Job hasn't started within
                            the requested timeout.)
        :raise JobRequestFailed: if the job did not complete successfully.
        :raise JobRequestTimedOut: if the job timed out.
        """
        if job_parms:
            self.add_job_parameters_to_existing(*job_parms)
        try:
            self.entry = self.adapter.create_job(
                self.entry.element, self._get_val_str(_JOB_GROUP_NAME), uuid,
                sensitive=sensitive).entry
        except pvmex.Error as exc:
            LOG.exception(exc)
            raise pvmex.JobRequestFailed(operation_name=self.op, error=exc)
        timed_out = self._monitor_job(
            timeout=timeout, sensitive=sensitive, synchronous=synchronous)
        if timed_out:
            try:
                self.cancel_job()
            except pvmex.JobRequestFailed as e:
                LOG.warning(six.text_type(e))
            exc = pvmex.JobRequestTimedOut(
                operation_name=self.op, seconds=timeout)
            LOG.error(exc.args[0])
            raise exc
        if not synchronous:
            # _monitor_job spawned a subthread that will delete_job when done.
            return
        self.delete_job()
        if self.job_status != JobStatus.COMPLETED_OK:
            exc = pvmex.JobRequestFailed(
                operation_name=self.op, error=self.get_job_message(''))
            LOG.error(exc.args[0])
            raise exc

    def poll_while_status(self, statuses, timeout, sensitive):
        """Poll the Job as long as its status is in the specified list.

        :param statuses: Iterable of JobStatus enum values.  This method
                         continues to poll the Job as long as its status is
                         in the specified list, or until the timeout is
                         reached (whichever comes first).
        :param timeout: Maximum number of seconds to keep checking job status.
                        If zero, poll indefinitely.
        :param sensitive: If True, mask the Job payload in the logs.
        :return: timed_out: True if the timeout was reached before the Job
                            left the specified set of states.
        """
        start_time = time.time()
        iteration_count = 1
        while self.job_status in statuses:
            elapsed_time = time.time() - start_time
            if timeout:
                # wait up to timeout seconds
                if elapsed_time > timeout:
                    return True
            # Log a warning every 5 minutes
            if not iteration_count % 300:
                msg = _("Job %(job_id)s monitoring for %(time)i seconds.")
                LOG.warning(msg, {'job_id': self.job_id, 'time': elapsed_time})
            time.sleep(1)
            self.entry = self.adapter.read_job(
                self.job_id, sensitive=sensitive).entry
            iteration_count += 1
        return False

    def _monitor_job(self, timeout=CONF.pypowervm_job_request_timeout,
                     sensitive=False, synchronous=True):
        """Polls a job.

        Waits on a job until it is no longer running.  If a timeout is given,
        it times out in the given amount of time.

        :param timeout: maximum number of seconds to keep checking job status
        :param sensitive: If True, mask the Job payload in the logs.
        :param synchronous: If True (the default), wait for the Job to complete
                            or time out.  If False, return as soon as the Job
                            starts.  Note that this may still involve polling
                            (if the Job is waiting in queue to start), and may
                            still time out (if the Job hasn't started within
                            the requested timeout.)  If synchronous=True, the
                            caller must delete the Job (self.delete_job()); if
                            False, this method spawns a subthread that deletes
                            it when it finishes.
        :returns timed_out: boolean True if timed out waiting for job
                            completion
        """
        if synchronous:
            return self.poll_while_status(
                [JobStatus.RUNNING, JobStatus.NOT_ACTIVE], timeout, sensitive)

        # Asynchronous: wait for the Job to start, then spawn a thread to wait
        # (indefinitely) for it to finish, and delete it when done.
        if self.poll_while_status([JobStatus.NOT_ACTIVE], timeout, sensitive):
            return True

        PollAndDeleteThread(self, sensitive).start()
        return False

    def cancel_job(self, sensitive=False):
        """Cancels and deletes incomplete/running jobs.

        This method spawns a thread to monitor the job being cancelled
        and delete it.

        :param sensitive: If True, payload will be hidden in the logs
        """

        job_id = self.job_id
        msg = _("Issuing cancel request for job %(job_id)s. Will poll the "
                "job indefinitely for termination.")
        LOG.warning(msg, {'job_id': job_id})
        try:
            self.adapter.update(None, None, root_type=_JOBS, root_id=job_id,
                                suffix_type='cancel')
        except pvmex.Error as exc:
            LOG.exception(exc)
        CancelJobThread(self, sensitive).start()

    def delete_job(self):
        """Cleans this Job off of the REST server, if it is completed.

        :raise JobRequestFailed: if the Job is detected to be running.
        """
        if self.job_status == JobStatus.RUNNING:
            error = (_("Job %s not deleted. Job is in running state.")
                     % self.job_id)
            LOG.error(error)
            raise pvmex.Error(error)
        try:
            self.adapter.delete(_JOBS, self.job_id)
        except pvmex.Error as exc:
            LOG.exception(exc)
