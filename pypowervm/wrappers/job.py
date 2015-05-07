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

import logging
import time

from oslo.config import cfg
import six

import pypowervm.const as pc
import pypowervm.entities as ent
import pypowervm.exceptions as pvmex
from pypowervm.i18n import _
import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)

job_opts = [
    cfg.IntOpt('powervm_job_request_timeout',
               default=1800,
               help='Default timeout in seconds for Job requests to the API')
]

CONF = cfg.CONF
CONF.register_opts(job_opts)

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
                exc = pvmex.JobRequestFailed(
                    operation_name=self.op, error=stack_trace)
                LOG.error(_('%s') % exc)
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
                sensitive=False):
        """Invokes and polls a job.

        Adds job parameters to the job element if specified and calls the
        create_job method. It then monitors the job for completion and sends a
        JobRequestFailed exception if it did not complete successfully.

        :param uuid: uuid of the target
        :param job_parms: list of JobParamters to add
        :param timeout: maximum number of seconds for job to complete
        :raise JobRequestFailed: if the job did not complete successfully.
        :raise JobRequestTimedOut: if the job timed out.
        """
        job = self.entry.element
        entry_type = self._get_val_str(_JOB_GROUP_NAME)
        if job_parms:
            self.add_job_parameters_to_existing(*job_parms)
        try:
            pvmresp = self.adapter.create_job(job, entry_type, uuid,
                                              sensitive=sensitive)
            self.entry = pvmresp.entry
        except pvmex.Error as exc:
            LOG.exception(exc)
            raise pvmex.JobRequestFailed(
                operation_name=self.op, error=exc)
        status, message, timed_out = self.monitor_job(timeout=timeout,
                                                      sensitive=sensitive)
        if timed_out:
            try:
                self.cancel_job()
            except pvmex.JobRequestFailed as e:
                LOG.warn(six.text_type(e))
            exc = pvmex.JobRequestTimedOut(
                operation_name=self.op, seconds=str(timeout))
            LOG.exception(exc)
            raise exc
        if status != JobStatus.COMPLETED_OK:
            self.delete_job()
            exc = pvmex.JobRequestFailed(
                operation_name=self.op, error=message)
            LOG.exception(exc)
            raise exc
        self.delete_job()

    def monitor_job(self, job_id=None,
                    timeout=CONF.pypowervm_job_request_timeout,
                    sensitive=False):
        """Polls a job.

        Waits on a job until it is no longer running.  If a timeout is given,
        it times out in the given amount of time.

        :param job_id: job id
        :param timeout: maximum number of seconds to keep checking job status
        :returns status: String containing the job status
        :returns message: String containing the job results message
        :returns timed_out: boolean True if timed out waiting for job
                            completion
        """
        if job_id is None:
            job_id = self.job_id
        status = self.job_status
        start_time = time.time()
        timed_out = False
        while status == JobStatus.RUNNING or status == JobStatus.NOT_ACTIVE:
            if timeout:
                # wait up to timeout seconds
                if (time.time() - start_time) > timeout:
                    timed_out = True
                    break
            time.sleep(1)
            pvmresp = self.adapter.read_job(job_id, sensitive=sensitive)
            self.entry = pvmresp.entry
            status = self.job_status

        message = ''
        if not timed_out and status != JobStatus.COMPLETED_OK:
            message = self.get_job_message()
        return status, message, timed_out

    def cancel_job(self, timeout=CONF.pypowervm_job_request_timeout,
                   sensitive=False):
        """Cancels and deletes incomplete/running jobs.

        :param timeout: maximum number of seconds to keep checking job status
        :param sensitive: If True, payload will be hidden in the logs
        :raise JobRequestFailed: if the job did not cancel within the
        expected timeout.
        """

        job_id = self.job_id
        try:
            self.adapter.update(None, None, root_type=_JOBS, root_id=job_id,
                                suffix_type='cancel')
        except pvmex.Error as exc:
            LOG.exception(exc)
        status, message, timed_out = self.monitor_job(timeout=timeout,
                                                      sensitive=sensitive)
        if timed_out:
            error = (_("Job %(job_id)s failed to cancel after %(timeout)s "
                       "seconds.") % dict(job_id=job_id,
                                          timeout=six.text_type(timeout)))
            exc = pvmex.JobRequestFailed(error)
            raise exc
        self.delete_job(job_id, status)

    def delete_job(self, job_id=None, status=None):
        """Cleans up completed jobs.

        JobRequestFailed exception sent if job is in running status.

        :param job_id: job id
        :param status: job status
        :raise JobRequestFailed: if the Job is detected to be running.
        """
        if not job_id:
            job_id = self.job_id
        if not status:
            status = self.job_status
        if status == JobStatus.RUNNING:
            error = (_("Job %s not deleted. Job is in running state.")
                     % job_id)
            exc = pvmex.JobRequestFailed(error)
            LOG.exception(exc)
            raise exc
        try:
            self.adapter.delete(_JOBS, job_id)
        except pvmex.Error as exc:
            LOG.exception(exc)
