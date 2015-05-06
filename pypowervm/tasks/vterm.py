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
import subprocess

import pypowervm.const as c
from pypowervm.i18n import _
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as pvm_lpar

import six

LOG = logging.getLogger(__name__)

_SUFFIX_PARM_CLOSE_VTERM = 'CloseVterm'


def close_vterm(adapter, lpar_uuid):
    """Close the vterm associated with an lpar

    :param adapter: The adapter to talk over the API.
    :param lpar_uuid: partition uuid

    """
    # Close vterm on the lpar
    resp = adapter.read(pvm_lpar.LPAR.schema_type, lpar_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=_SUFFIX_PARM_CLOSE_VTERM)
    job_wrapper = job.Job.wrap(resp.entry)

    try:
        job_wrapper.run_job(adapter, lpar_uuid)
    except Exception as e:
        # just log the error.
        emsg = six.text_type(e)
        LOG.exception(_('Unable to close vterm: %s') % emsg)
        raise


def open_vnc_vterm(adapter, lpar_uuid, bind_ip='127.0.0.1'):
    """Opens a VNC vTerm to a given LPAR.

    :param adapter: The adapter to drive the PowerVM API
    :param lpar_uuid: Partition UUID.
    :param bind_ip: The IP Address to bind the VNC to.  Defaults to 127.0.0.1,
                    the localhost IP Address.
    :return: The VNC Port that the terminal is running on.
    """
    lpar_resp = adapter.read(pvm_lpar.LPAR.schema_type, root_id=lpar_uuid,
                             suffix_type='quick', suffix_parm='PartitionID')
    lpar_id = lpar_resp.body

    # First check for the existing tty
    tty = _check_for_tty(lpar_id)

    # If the TTY is not already running, create a new one.
    if not tty:
        # While the TTY may not be open, we should just close it just in
        # case an old LPAR was hanging around.
        cmd = ['sudo', 'rmvtermutil', '--id', lpar_id]
        _run_proc(cmd)

        # Open a new terminal via the TTY.  This is done with the openvt
        # command.  The response is:
        #     openvt: Using VT /dev/ttyXXX
        # We need to parse out the tty.  It goes to stderr.
        # TODO(thorst) sudo to be removed when mkvtermutil is updated
        cmd = ['sudo', 'openvt', '-v', '--', 'mkvtermutil', '--id', lpar_id]
        stdout, stderr = _run_proc(cmd)
        tty = stderr[stderr.rfind('tty') + 3:]

    # VNC Ports start at 5900.  We map it to the TTY number as they can't
    # overlap.
    port = 5900 + int(tty)

    # Do a simple check to see if the VNC appears to already be running.
    if not _has_vnc_running(tty):
        # Kick off a VNC if it is not already running.
        # TODO(thorst) sudo to be removed when mkvtermutil is updated
        cmd = ['sudo', '-S', 'linuxvnc', tty, '-rfbport', str(port),
               '-listen', bind_ip]
        _run_proc(cmd, wait=False)
    return port


def _check_for_tty(lpar_id):
    """Will return the tty for the lpar_id, if it is already running.

    :param lpar_id: The ID of the LPAR to query for the TTY.
    """
    # TODO(thorst) sudo to be removed when mkvtermutil is updated
    cmd = ['sudo', 'ps', 'aux']
    search_str = 'mkvtermutil --id ' + str(lpar_id)
    stdout, stderr = _run_proc(cmd)

    # Split each line out
    process_lines = stdout.splitlines()
    for process_line in process_lines:
        # If the mkvtermutil isn't in there, go to next line
        if search_str not in process_line:
            continue

        # Break out the line, and try to get the tty from it.
        proc_elems = process_line.split()
        for proc_elem in proc_elems:
            if proc_elem.startswith('tty'):
                # Parse off the 'tty' prefix
                return proc_elem[3:]


def _has_vnc_running(tty):
    """Simple, coarse check to see if linuxvnc is running for a tty."""
    # TODO(thorst) sudo to be removed when mkvtermutil is updated
    cmd = ['sudo', 'ps', 'aux']
    search_str = 'linuxvnc ' + tty + '-rfbport'
    stdout, stderr = _run_proc(cmd)

    # Split each line out
    process_lines = stdout.splitlines()
    for process_line in process_lines:
        if search_str in process_line:
            return True
    return False


def _run_proc(cmd, wait=True, shell=False):
    """Simple wrapper to run a process.

    Will return the stdout.  If the return code is not 0, an exception will
    be raised and the stderr will be part of the exception.

    :param cmd: The command arguments.  Should be a list.
    :param wait: If true, will wait for the command to complete.
    :return: The stdout and stderr from the command.  If not waiting for
             the command, returns None, None
    """
    process = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               close_fds=True, env=None)
    if wait:
        if process.wait() != 0:
            stdout, stderr = process.communicate()
            err_text = six.text_type(stderr)
            msg = _('Unable to run process.  Error is %(error)s\n'
                    'Command being run: %(cmd)s') % {'error': err_text,
                                                     'cmd': cmd}
            LOG.exception(msg)
            raise Exception(msg)

        stdout, stderr = process.communicate()
        return stdout, stderr
    else:
        return None, None
