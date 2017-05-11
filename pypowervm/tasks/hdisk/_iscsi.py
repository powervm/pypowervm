# Copyright 2016 IBM Corp.
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
import ast
from oslo_log import log as logging

import pypowervm.const as c
from pypowervm import exceptions as pexc
from pypowervm.i18n import _
from pypowervm.wrappers import job
from pypowervm.wrappers.virtual_io_server import VIOS

LOG = logging.getLogger(__name__)
_JOB_NAME = "ISCSIDiscovery"
_ISCSI_LOGOUT = "ISCSILogout"


class TransportType(object):
    """Valid values for iSCSI transport types."""
    ISCSI = 'iscsi'
    ISER = 'iser'


class ISCSIStatus(object):
    """ISCSI status codes."""
    ISCSI_SUCCESS = '0'
    ISCSI_ERR = '1'
    ISCSI_ERR_SESS_NOT_FOUND = '3'
    ISCSI_ERR_LOGIN = '5'
    ISCSI_ERR_INVAL = '7'
    ISCSI_ERR_TRANS_TIMEOUT = '8'
    ISCSI_ERR_INTERNAL = '9'
    ISCSI_ERR_LOGOUT = '10'
    ISCSI_ERR_SESS_EXISTS = '15'
    ISCSI_ERR_NO_OBJS_FOUND = '21'
    ISCSI_ERR_HOST_NOT_FOUND = '23'
    ISCSI_ERR_LOGIN_AUTH_FAILED = '24'
    ISCSI_COMMAND_NOT_FOUND = '127'


class ISCSIInputData(object):
    """ISCSI Input parameters required for discovery"""

    def __init__(self, host_ip, user, password, iqn, target_lun,
                 transport_type=None):
        self.host_ip = host_ip
        self.user = user
        self.password = password
        self.iqn = iqn
        self.lun = target_lun
        self.transport_type = transport_type

    def __eq__(self, other):
        if other is None or not isinstance(other, ISCSIInputData):
            return False

        return (self.host_ip == other.host_ip and
                self.user == other.user and
                self.password == other.password and
                self.iqn == other.iqn and
                self.lun == other.lun and
                self.transport_type == other.transport_type)

    def __ne__(self, other):
        return not self.__eq__(other)


def good_iscsi_discovery(vios_uuid, status, cmd=None):
    """Processes the iscsiadm return codes"""
    if status == ISCSIStatus.ISCSI_COMMAND_NOT_FOUND:
        LOG.warning(_("ISCSIDiscovery Failed on vios %s, "
                      "Command not found. Retry on next."), vios_uuid)
        return False
    if cmd == _JOB_NAME and status not in [ISCSIStatus.ISCSI_SUCCESS,
                                           ISCSIStatus.ISCSI_ERR_SESS_EXISTS]:
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=status)

    if (cmd == _ISCSI_LOGOUT and status not in
            [ISCSIStatus.ISCSI_SUCCES,
             ISCSIStatus.ISCSI_ERR_NO_OBJS_FOUND]):
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=status)

    return True


def _get_iscsi_devname(output, iscsi_data):
    # Find dev corresponding to given IQN
    for dev in output:
        if len(dev.split()) != 3:
            LOG.warning(_("Invalid device output: %(dev)s"), {'dev': dev})
            continue
        outiqn, outname, udid = dev.split()
        if outiqn == scsi_data.iqn:
            return outname, udid
    LOG.error(_("Expected IQN: %(IQN)s not found on iscsi target "
                "%(host_ip)s"), {'IQN': iscsi_data.iqn,
                                 'host_ip': iscsi_data.host_ip})
    return None, None


def discover_iscsi(adapter, vios_uuid, iscsi_data):
    """Runs iscsi discovery and login job

    :param adapter: pypowervm adapter
    :param host_ip: The ip address of the iscsi target.
    :param user: The username needed for authentication.
    :param password: The password needed for authentication.
    :param iqn: The IQN (iSCSI Qualified Name) of the created volume on the
                target. (e.g. iqn.2016-06.world.srv:target00)
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param target_lun: LUN ID of the device to be discovered.
    :param transport_type: The type of the volume to be connected. Must be a
                           valid TransportType.
    :return: The device name of the created volume.
    :return: The UniqueDeviceId of the create volume.
    """

    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=(_JOB_NAME))
    job_wrapper = job.Job.wrap(resp)

    # Create job parameters
    job_parms = [job_wrapper.create_job_parameter('hostIP',
                                                  iscsi_data.host_ip)]
    job_parms.append(job_wrapper.create_job_parameter('password',
                                                      iscsi_data.password))
    job_parms.append(job_wrapper.create_job_parameter('user',
                                                      iscsi_data.user))
    job_parms.append(job_wrapper.create_job_parameter('targetIQN',
                                                      iscsi_data.iqn))
    job_parms.append(job_wrapper.create_job_parameter('targetLUN',
                                                      iscsi_data.lun))
    if iscsi_data.transport_type is not None:
        job_parms.append(
            job_wrapper.create_job_parameter('transportType',
                                             iscsi_data.transport_type))
    try:
        job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
        results = job_wrapper.get_job_results_as_dict()

        # RETURN_CODE: for iscsiadm status
        if good_iscsi_discovery(vios_uuid, results.get('RETURN_CODE'),
                                _JOB_NAME):
            # DEV_OUTPUT: ["IQN1 dev1 udid", "IQN2 dev2 udid"]
            output = ast.literal_eval(results.get('DEV_OUTPUT'))

            # Find dev corresponding to given IQN
            return _get_iscsi_devname(output, iscsi_data)

    except pexc.JobRequestFailed as error:
        LOG.exception(error)
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=1)


def discover_iscsi_initiator(adapter, vios_uuid):
    """Discovers the initiator name.

    :param adapter: pypowervm adapter
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :return: The iscsi initiator name.
    """
    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=(_JOB_NAME))
    job_wrapper = job.Job.wrap(resp)

    try:
        job_wrapper.run_job(vios_uuid, timeout=120)
        results = job_wrapper.get_job_results_as_dict()

        # process iscsi return code.
        if good_iscsi_discovery(vios_uuid, results.get('RETURN_CODE'),
                                _JOB_NAME):
            # InitiatorName: iqn.2010-10.org.openstack:volume-4a75e9f7-dfa3
            return results.get('InitiatorName')
        return None

    except pexc.JobRequestFailed as error:
        LOG.exception(error)
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=1)


def remove_iscsi(adapter, targetIQN, vios_uuid):
    """Logout of an iSCSI session.

    The iSCSI volume with the given targetIQN must not have any mappings from
    the VIOS to a client when this is called.

    :param adapter: pypowervm adapter
    :param targetIQN: The IQN (iSCSI Qualified Name) of the created volume on
                      the target. (e.g. iqn.2016-06.world.srv:target00)
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :return: True on Success and False on Failure
    """
    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=(_ISCSI_LOGOUT))
    job_wrapper = job.Job.wrap(resp)

    job_parms = [job_wrapper.create_job_parameter('targetIQN', targetIQN)]
    try:
        job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
        results = job_wrapper.get_job_results_as_dict()

        # RETURN_CODE: for iscsiadm status
        return good_iscsi_discovery(vios_uuid, results.get('RETURN_CODE'),
                                    _ISCSI_LOGOUT)

    except pexc.JobRequestFailed as error:
        LOG.exception(error)
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=1)
