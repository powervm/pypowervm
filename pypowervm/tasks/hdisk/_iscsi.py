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
from pypowervm.wrappers import job
from pypowervm.wrappers.virtual_io_server import VIOS


LOG = logging.getLogger(__name__)
_JOB_NAME = "ISCSIDiscovery"
_ISCSI_LOGOUT = "ISCSILogout"


class TransportType(object):
    """Valid values for iSCSI transport types."""
    ISCSI = 'iscsi'
    ISER = 'iser'
    BE2ISCSI = 'be2iscsi'
    BNX2I = 'bnx2i'
    CXGB3I = 'cxgb3i'
    DEFAULT = 'default'
    CXGB4I = 'cxgb4i'
    QLA4XXX = 'qla4xxx'
    OCS = 'ocs'


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


_GOOD_DISCOVERY_STATUSES = [ISCSIStatus.ISCSI_SUCCESS,
                            ISCSIStatus.ISCSI_ERR_SESS_EXISTS]
_GOOD_LOGOUT_STATUSES = [ISCSIStatus.ISCSI_SUCCESS,
                         ISCSIStatus.ISCSI_ERR_NO_OBJS_FOUND]


def _find_dev_by_iqn(cmd_output, iqn, host_ip):
    # Find dev corresponding to given IQN
    for dev in cmd_output:
        try:
            outiqn, outname, udid = dev.split()
            if outiqn == iqn:
                return outname, udid
        except ValueError:
            LOG.warning("Invalid device output: %(dev)s" % {'dev': dev})
            continue

    LOG.error("Expected IQN %(IQN)s not found on iscsi target %(host_ip)s" %
              {'IQN': iqn, 'host_ip': host_ip})
    return None, None


def _add_parameter(job_w, job_parms, name, value):
    """Adds key/value to job parameter list

    Checks for null value and does any conversion needed for value to be a
    string
    :param job_w: Job wrapper
    :param job_parms: List of parameters for the job
    :param key: Parameter name
    :param value: Parameter value
    """
    if value and 'None' != value:
        if isinstance(value, list):
            if not isinstance(value[0], str):
                value = [str(val) for val in value]
            value = ",".join(value)
        job_parms.append(job_w.create_job_parameter(name, value))


def discover_iscsi(adapter, host_ip, user, password, iqn, vios_uuid,
                   transport_type=None, lunid=None, auth=None,
                   discover_auth=None, discover_user=None, discover_pass=None,
                   iqns=None, portals=None, luns=None, multipath=False):
    """Runs iscsi discovery and login job

    :param adapter: pypowervm adapter
    :param host_ip: The ip address of the iscsi target (ip:port).
    :param user: The username needed for authentication.
    :param password: The password needed for authentication.
    :param iqn(s): The IQN (iSCSI Qualified Name) of the created volume on the
                   target. (e.g. iqn.2016-06.world.srv:target00)
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param transport_type: The type of the volume to be connected. Must be a
                           valid TransportType.
    :param lunid: Target LUN ID of the volume.
    :param auth: Authentication type
    :param discover_auth: Disocvery authentication type.
    :param discover_user: The username needed for discovery authentication.
    :param discover_pass: The password needed for discovery authentication.
    :param portals: List of host_ip (ip:port)
    :param luns: List of lunids.
    :param multipath: Whether the connection is multipath or not.
    :return: The device name of the created volume.
    :return: The UniqueDeviceId of the create volume.
    :raise: ISCSIDiscoveryFailed in case of Failure.
    """

    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=(_JOB_NAME))
    job_wrapper = job.Job.wrap(resp)

    # Create job parameters
    job_parms = []
    _add_parameter(job_wrapper, job_parms, 'password', password)
    _add_parameter(job_wrapper, job_parms, 'user', user)
    _add_parameter(job_wrapper, job_parms, 'auth', auth)
    _add_parameter(job_wrapper, job_parms, 'discoverAuth', discover_auth)
    _add_parameter(job_wrapper, job_parms, 'discoverUser', discover_user)
    _add_parameter(job_wrapper, job_parms, 'discoverPassword', discover_pass)
    _add_parameter(job_wrapper, job_parms, 'transportType', transport_type)
    _add_parameter(job_wrapper, job_parms, 'targetIQN', iqn)
    _add_parameter(job_wrapper, job_parms, 'targetIQNs', iqns)
    _add_parameter(job_wrapper, job_parms, 'hostIP', host_ip)
    _add_parameter(job_wrapper, job_parms, 'targetPORTALs', portals)
    _add_parameter(job_wrapper, job_parms, 'targetLUN', str(lunid))
    _add_parameter(job_wrapper, job_parms, 'targetLUNs', luns)
    _add_parameter(job_wrapper, job_parms, 'multipath', str(multipath))
    try:
        job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
    except pexc.JobRequestFailed:
        results = job_wrapper.get_job_results_as_dict()
        # Ignore if the command is performed on NotSupported AIX VIOS
        if results.get('RETURN_CODE') != ISCSIStatus.ISCSI_COMMAND_NOT_FOUND:
            raise
        return None, None

    results = job_wrapper.get_job_results_as_dict()

    # RETURN_CODE: for iscsiadm status
    status = results.get('RETURN_CODE')
    if status not in _GOOD_DISCOVERY_STATUSES:
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=status)

    # DEV_OUTPUT: ["IQN1 dev1 udid", "IQN2 dev2 udid"]
    output = ast.literal_eval(results.get('DEV_OUTPUT'))

    # Find dev corresponding to given IQN
    return _find_dev_by_iqn(output, iqn, host_ip)


def discover_iscsi_initiator(adapter, vios_uuid):
    """Discovers the initiator name.

    :param adapter: pypowervm adapter
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :return: The iscsi initiator name.
    :raise: ISCSIDiscoveryFailed in case of failure.
    """
    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=(_JOB_NAME))
    job_wrapper = job.Job.wrap(resp)

    job_wrapper.run_job(vios_uuid, timeout=120)
    results = job_wrapper.get_job_results_as_dict()

    # process iscsi return code.
    status = results.get('RETURN_CODE')
    if status not in _GOOD_DISCOVERY_STATUSES:
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=status)

    # InitiatorName: iqn.2010-10.org.openstack:volume-4a75e9f7-dfa3
    return results.get('InitiatorName')


def remove_iscsi(adapter, targetIQN, vios_uuid, transport=None, lun=None,
                 iqns=None, portal=None, portals=None, luns=None,
                 multipath=False):
    """Logout of an iSCSI session.

    The iSCSI volume with the given targetIQN must not have any mappings from
    the VIOS to a client when this is called.

    :param adapter: pypowervm adapter
    :param targetIQN: The IQN (iSCSI Qualified Name) of the created volume on
                      the target. (e.g. iqn.2016-06.world.srv:target00)
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param iqns: List of targetIQNs.
    :param portal(s): The portal associated with the created volume (ip:port).
    :param lun(s): The lun to be removed.
    :param transport: The type of the volume to be connected. Must be a
                      valid TransportType.
    :param multipath: Whether the connection is multipath or not.
    :raise: ISCSILogoutFailed in case of Failure.
    """
    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=(_ISCSI_LOGOUT))
    job_wrapper = job.Job.wrap(resp)
    job_parms = []
    _add_parameter(job_wrapper, job_parms, 'transport', transport)
    _add_parameter(job_wrapper, job_parms, 'targetIQN', targetIQN)
    _add_parameter(job_wrapper, job_parms, 'targetIQNs', iqns)
    _add_parameter(job_wrapper, job_parms, 'targetPORTAL', portal)
    _add_parameter(job_wrapper, job_parms, 'targetPORTALs', portals)
    _add_parameter(job_wrapper, job_parms, 'targetLUN', str(lun))
    _add_parameter(job_wrapper, job_parms, 'targetLUNs', luns)
    _add_parameter(job_wrapper, job_parms, 'multipath', str(multipath))
    job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
    results = job_wrapper.get_job_results_as_dict()
    status = results.get('RETURN_CODE')
    if status not in _GOOD_LOGOUT_STATUSES:
        raise pexc.ISCSILogoutFailed(vios_uuid=vios_uuid, status=status)
