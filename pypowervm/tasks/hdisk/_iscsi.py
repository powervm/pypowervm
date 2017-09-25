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


def _add_parameter(job_parms, job_w, name, value):
    """Adds key/value to job parameter list

    Checks for null value and does any conversion needed for value to be a
    string

    :param job_parms: List of parameters for the job
    :param job_w: Job wrapper
    :param key: Parameter name
    :param value: Parameter value
    """
    if value is not None and value != []:
        try:
            basestring
        except NameError:
            basestring = str
        if isinstance(value, list):
            if not isinstance(value[0], basestring):
                value = [str(val) for val in value]
            value = "[" + ",".join(value) + "]"
        elif not isinstance(value, basestring):
            value = str(value)
        job_parms.append(job_w.create_job_parameter(name, value))


def discover_iscsi(adapter, host_ip, user, password, iqn, vios_uuid,
                   transport_type=None, lunid=None, auth=None,
                   discovery_auth=None, discovery_username=None,
                   discovery_password=None, multipath=False):
    """Runs iscsi discovery and login job

    :param adapter: pypowervm adapter
    :param host_ip: The portal or list of portals for the iscsi target. A
                    portal looks like ip:port.
    :param user: The username needed for authentication.
    :param password: The password needed for authentication.
    :param iqn: The IQN (iSCSI Qualified Name) or list of IQNs for the created
                volume on the target (e.g. iqn.2016-06.world.srv:target00).
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param transport_type: Transport type of the volume to be connected. Must
                           be a valid TransportType.
    :param lunid: Target LUN ID or list of LUN IDs for the volume.
    :param auth: Authentication type
    :param discovery_auth: Discovery authentication type.
    :param discovery_username: The username needed for discovery
                               authentication.
    :param discovery_password: The password needed for discovery
                               authentication.
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
    _add_parameter(job_parms, job_wrapper, 'auth', auth)
    _add_parameter(job_parms, job_wrapper, 'user', user)
    _add_parameter(job_parms, job_wrapper, 'password', password)
    _add_parameter(job_parms, job_wrapper, 'transportType', transport_type)
    _add_parameter(job_parms, job_wrapper, 'targetIQN', iqn)
    _add_parameter(job_parms, job_wrapper, 'hostIP', host_ip)
    _add_parameter(job_parms, job_wrapper, 'targetLUN', lunid)
    _add_parameter(job_parms, job_wrapper, 'multipath', multipath)
    if multipath:
        _add_parameter(job_parms, job_wrapper, 'discoverAuth', discovery_auth)
        _add_parameter(job_parms, job_wrapper, 'discoverUser',
                       discovery_username)
        _add_parameter(job_parms, job_wrapper, 'discoverPassword',
                       discovery_password)

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
                 portal=None, multipath=False):
    """Remove an iSCSI lun from a session.

    If the last lun was removed from the session, also logout of the session.
    The iSCSI volume with the given targetIQN must not have any mappings from
    the VIOS to a client when this is called.

    :param adapter: pypowervm adapter
    :param targetIQN: The IQN (iSCSI Qualified Name) or list of IQNs for the
                      created volume on the target.
                      (e.g. iqn.2016-06.world.srv:target00)
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param portal: The portal or list of portals associated with the created
                   volume (ip:port).
    :param lun: The lun or list of luns to be removed.
    :param transport: Transport type of the volume to be connected. Must be a
                      valid TransportType.
    :param multipath: Whether the connection is multipath or not.
    :raise: ISCSILogoutFailed in case of Failure.
    """
    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=(_ISCSI_LOGOUT))
    job_wrapper = job.Job.wrap(resp)
    job_parms = []
    _add_parameter(job_parms, job_wrapper, 'transport', transport)
    _add_parameter(job_parms, job_wrapper, 'targetIQN', targetIQN)
    _add_parameter(job_parms, job_wrapper, 'targetPORTAL', portal)
    _add_parameter(job_parms, job_wrapper, 'targetLUN', lun)
    _add_parameter(job_parms, job_wrapper, 'multipath', multipath)
    job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
    results = job_wrapper.get_job_results_as_dict()
    status = results.get('RETURN_CODE')
    if status not in _GOOD_LOGOUT_STATUSES:
        raise pexc.ISCSILogoutFailed(vios_uuid=vios_uuid, status=status)
