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

"""Manage LPAR virtual terminals."""

import logging
import subprocess

import pypowervm.const as c
from pypowervm import exceptions as pvm_exc
from pypowervm.i18n import _
from pypowervm.utils import psutil_compat as psutil
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
    if adapter.traits.local_api:
        _close_vterm_local(adapter, lpar_uuid)
    else:
        _close_vterm_non_local(adapter, lpar_uuid)


def _close_vterm_non_local(adapter, lpar_uuid):
    """Job to force the close of the terminal when the API is remote.

    :param adapter: The adapter to talk over the API.
    :param lpar_uuid: partition uuid
    """
    # Close vterm on the lpar
    resp = adapter.read(pvm_lpar.LPAR.schema_type, lpar_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=_SUFFIX_PARM_CLOSE_VTERM)
    job_wrapper = job.Job.wrap(resp.entry)

    try:
        job_wrapper.run_job(lpar_uuid)
    except Exception:
        LOG.exception(_('Unable to close vterm.'))
        raise


def _close_vterm_local(adapter, lpar_uuid):
    """Forces the close of the terminal on a local system.

    Will check for a VNC server as well in case it was started via that
    mechanism.

    :param adapter: The adapter to talk over the API.
    :param lpar_uuid: partition uuid
    """
    lpar_id = _get_lpar_id(adapter, lpar_uuid)

    # Input data for the commands.
    tty = _check_for_tty(lpar_id)
    if tty:
        # Clear out the TTY upon lpar deletion.
        _clear_tty(tty)

        # Find the VNC processes (if any) and remove them.
        port = 5900 + int(tty)
        vnc_processes = _has_vnc_running(tty, port)
        for vnc_process in vnc_processes:
            _kill_proc(vnc_process)

    # Lastly, always can run the rmvterm
    # TODO(thorst) remove sudo when rmvtermutil no longer requires it.
    cmd = ['sudo', 'rmvtermutil', '--id', lpar_id]
    _run_proc(cmd)


def _kill_proc(process):
    """Kills a process."""
    # TODO(thorst) remove when sudo is no longer needed.  Revert to
    # process.kill
    cmd = ['sudo', 'kill', str(process.pid)]
    # The wait is so that we don't get the error if we kill the sudo process
    # first.  If we wait, then the children process kills will throw an error
    # because they were killed with the parent...so it errors trying to kill
    # something that isn't there.  This is temporary until the sudo is removed.
    _run_proc(cmd, wait=False)


def open_vnc_vterm(adapter, lpar_uuid, bind_ip='127.0.0.1'):
    """Opens a VNC vTerm to a given LPAR.

    :param adapter: The adapter to drive the PowerVM API
    :param lpar_uuid: Partition UUID.
    :param bind_ip: The IP Address to bind the VNC to.  Defaults to 127.0.0.1,
                    the localhost IP Address.
    :return: The VNC Port that the terminal is running on.
    """
    # This API can only run if local.
    if not adapter.traits.local_api:
        raise pvm_exc.ConsoleNotLocal()

    lpar_id = _get_lpar_id(adapter, lpar_uuid)

    # First check for the existing tty
    tty = _check_for_tty(lpar_id)

    # If the TTY is not already running, create a new one.
    if not tty:
        # While the TTY may not be open, we should just close it just in
        # case an improperly closed LPAR was hanging around.
        # TODO(thorst) remove sudo when rmvtermutil is updated.
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

    # When this is invoked, we always clear out the TTY screen.  This is
    # for security reasons (old LPAR or what not).
    _clear_tty(tty)

    # Do a simple check to see if the VNC appears to already be running.
    if not _has_vnc_running(tty, port, listen_ip=bind_ip):
        # Kick off a VNC if it is not already running.
        # TODO(thorst) sudo to be removed when mkvtermutil is updated
        cmd = ['sudo', '-S', 'linuxvnc', tty, '-rfbport', str(port),
               '-listen', bind_ip]
        _run_proc(cmd, wait=False)
    return port


def _clear_tty(tty):
    # Example clear screen command (from command line):
    #   sh -c "echo 'printf \033c' > /dev/tty2"
    # TODO(thorst) remove the sudo
    cmd = ['sudo', 'sh', '-c', 'echo \'printf \\033c\' > /dev/tty%s' % tty]
    _run_proc(cmd, shell=True)


def _check_for_tty(lpar_id):
    """Will return the tty for the lpar_id, if it is already running.

    :param lpar_id: The ID of the LPAR to query for the TTY.
    """
    # The process typically shows as:
    #    /bin/bash /sbin/mkvtermutil --id X
    # There are some variations, so we key off the base name.
    search_str = 'mkvtermutil --id ' + str(lpar_id)
    for process in psutil.process_iter():
        cmd = ' '.join(process.cmdline)
        if search_str not in cmd:
            continue

        # Must have matched our command.  Check to see if it has a tty.
        if not process.terminal:
            continue

        tty_pos = process.terminal.find('tty')
        return process.terminal[tty_pos + 3:]
    return None


def _has_vnc_running(tty, port, listen_ip=None):
    """Simple, coarse check to see if linuxvnc is running for a tty.

    :param tty: The tty for the VNC.
    :param port: The VNC Port number.
    :param listen_ip: Optional IP Address that the VNC server should be
                      listening against.
    :return: A list of processes that have the VNC process running.  Should
             typically only be 0-1, but a list in case end users opened any.
    """
    vnc_processes = []

    # There are some variations on given systems.  Sometimes it will add a
    # space between the linuxvnc and the -rfbport.  This multi search string
    # gives us a means to find the correct identifier.
    search_strs = [('linuxvnc ' + tty), ('-rfbport ' + str(port))]
    if listen_ip is not None:
        search_strs.append('-listen ' + listen_ip)

    for process in psutil.process_iter():
        cmd = ' '.join(process.cmdline)
        contains = True
        for search_str in search_strs:
            if search_str not in cmd:
                contains = False
                break

        if contains:
            vnc_processes.append(process)
    return vnc_processes


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


def _get_lpar_id(adapter, lpar_uuid):
    lpar_resp = adapter.read(pvm_lpar.LPAR.schema_type, root_id=lpar_uuid,
                             suffix_type='quick', suffix_parm='PartitionID')
    return lpar_resp.body
