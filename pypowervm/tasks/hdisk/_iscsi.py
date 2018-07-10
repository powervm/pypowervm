# Copyright 2016, 2018 IBM Corp.
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
import six

from oslo_log import log as logging
from oslo_utils import excutils

import pypowervm.const as c
from pypowervm import exceptions as pexc
from pypowervm.i18n import _
import pypowervm.tasks.storage as tsk_stg
import pypowervm.utils.transaction as tx
from pypowervm.wrappers import job
from pypowervm.wrappers.virtual_io_server import VIOS


LOG = logging.getLogger(__name__)
_JOB_NAME = "ISCSIDiscovery"
_ISCSI_REMOVE = "ISCSIRemove"


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
    ISCSI_ERR_ODM_QUERY = '27'
    ISCSI_COMMAND_NOT_FOUND = '127'


_GOOD_DISCOVERY_STATUSES = [ISCSIStatus.ISCSI_SUCCESS,
                            ISCSIStatus.ISCSI_ERR_SESS_EXISTS]
_GOOD_REMOVE_STATUSES = [ISCSIStatus.ISCSI_SUCCESS,
                         ISCSIStatus.ISCSI_ERR_NO_OBJS_FOUND]


def _log_iscsi_status(status):
    """Logs the message based on the status code."""

    if status == ISCSIStatus.ISCSI_SUCCESS:
        LOG.info(_("ISCSI command completed successfully"))
    elif status == ISCSIStatus.ISCSI_ERR_SESS_EXISTS:
        LOG.info(_("ISCSI session already exists and logged in"))
    elif status == ISCSIStatus.ISCSI_COMMAND_NOT_FOUND:
        LOG.warning(_("ISCSI command performed on unsupported VIOS, "
                      "host."))
    elif status == ISCSIStatus.ISCSI_ERR_ODM_QUERY:
        LOG.warning(_("ISCSI discovery found stale entries in "
                      "the ODM database."))
    elif status == ISCSIStatus.ISCSI_ERR_SESS_NOT_FOUND:
        LOG.warning(_("ISCSI session could not be found "))
    elif status == ISCSIStatus.ISCSI_ERR_NO_OBJS_FOUND:
        LOG.warning(_("No records/targets/sessions/portals "
                      "found to execute operation on"))
    elif status == ISCSIStatus.ISCSI_ERR_INTERNAL:
        LOG.error(_("ISCSI command failed with internal error "
                    "status = %s"), status)
    elif status == ISCSIStatus.ISCSI_ERR:
        LOG.error(_("ISCSI generic error code"))
    elif status == ISCSIStatus.ISCSI_ERR_LOGIN:
        LOG.error(_("ISCSI session login failure"))
    elif status == ISCSIStatus.ISCSI_ERR_INVAL:
        LOG.error(_("ISCSI command invalid arguments"))
    elif status == ISCSIStatus.ISCSI_ERR_TRANS_TIMEOUT:
        LOG.error(_("ISCSI connection timer exired while trying to connect."))
    elif status == ISCSIStatus.ISCSI_ERR_HOST_NOT_FOUND:
        LOG.error(_("ISCSI command could not lookup host"))
    else:
        LOG.error(_('ISCSI command returned unexpected status = %s') % status)


def good_discovery(status, device_name):
    """Checks the hdisk discovery results for a good discovery.

    Acceptable discovery statuses are _GOOD_DISCOVERY_STATUSES
   """
    return (device_name is not None and status in
            _GOOD_DISCOVERY_STATUSES)


def _find_dev_by_iqn(cmd_output, iqn, host_ip):
    """Find device name and udid corresponding to an IQN

    The iqn parameter can be a singular iqn or a list of iqns. If a list of
    iqns is given, we can return the device name and udid for any of the iqns,
    since this implies a multipath device which would have the same return
    values for all iqns.

    :param cmd_output: A list of "iqn device_name udid"
    :param host_ip: The portal or list of portals for the iscsi target. A
                    portal looks like ip:port.
    :param iqn: The IQN (iSCSI Qualified Name) or list of IQNs for the created
                volume on the target (e.g. iqn.2016-06.world.srv:target00).
    :return: The device name of the created volume.
    :return: The UniqueDeviceId of the create volume.
    """
    for dev in cmd_output:
        try:
            outiqn, outname, udid = dev.split()
            if ((isinstance(iqn, six.string_types) and outiqn == iqn) or
                    outiqn in iqn):
                return outname, udid
        except ValueError:
            LOG.warning("Invalid device output: %(dev)s" % {'dev': dev})
            continue

    LOG.error("Expected IQN %(IQN)s not found on iscsi target %(host_ip)s" %
              {'IQN': iqn, 'host_ip': host_ip})
    return None, None


def _process_iscsi_result(result, iqn, host_ip):
    """Process iSCSIDiscovery Job results

    Checks the job result return status code and return.
    :param result: ISCSI command job result.
    :param iqn: The IQN or list of IQNs for the created volume on the target.
    :host_ip: The portal or list of portals for the iscsi target.
    :return: status, device_name and udid
    """
    status = result.get('RETURN_CODE')
    # Ignore if command performed on unsupported AIX VIOS
    if not status:
        LOG.warning("ISCSI discovery job failed, no command status returned")
        return None, None, None

    if status == ISCSIStatus.ISCSI_COMMAND_NOT_FOUND:
        LOG.warning(_("ISCSI command performed on unsupported VIOS "))
        return None, None, None

    # DEV_OUTPUT: ["IQN1 dev1 udid", "IQN2 dev2 udid"]
    output = ast.literal_eval(result.get('DEV_OUTPUT', '[]'))

    # Find dev corresponding to given IQN
    dev_name, udid = _find_dev_by_iqn(output, iqn, host_ip)

    return status, dev_name, udid


def _add_parameter(job_parms, name, value):
    """Adds key/value to job parameter list

    Checks for null value and does any conversion needed for value to be a
    string

    :param job_parms: List of parameters for the job which will be updated by
                      this method.
    :param key: Parameter name
    :param value: Parameter value
    """
    if value or value == 0 or value is False:
        if isinstance(value, (six.string_types, int, bool)):
            value = six.text_type(value)
        else:
            value = '[' + ','.join([str(val) for val in value]) + ']'
        job_parms.append(job.Job.create_job_parameter(name, value))


def _discover_iscsi(adapter, host_ip, vios_uuid, multipath, **kwargs):
    """Runs iscsi discovery and login job

    :param adapter: pypowervm adapter
    :param host_ip: The portal or list of portals for the iscsi target. A
                    portal looks like ip:port.
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param multipath: Whether the connection is multipath or not.
    :param kwargs: List of iSCSI authentication parameters.
    :return: status code of the iSCSIDiscover job
    :return: The device name of the created volume.
    :return: The UniqueDeviceId of the create volume.
    """

    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=(_JOB_NAME))
    job_wrapper = job.Job.wrap(resp)

    # Create job parameters
    job_parms = []
    _add_parameter(job_parms, 'auth', kwargs.get('auth'))
    _add_parameter(job_parms, 'user', kwargs.get('user'))
    _add_parameter(job_parms, 'password', kwargs.get('password'))
    _add_parameter(job_parms, 'ifaceName', (kwargs.get('iface_name') or
                                            kwargs.get('transport_type')))
    _add_parameter(job_parms, 'targetIQN', kwargs.get('iqn'))
    _add_parameter(job_parms, 'hostIP', host_ip)
    _add_parameter(job_parms, 'targetLUN', kwargs.get('lunid'))
    _add_parameter(job_parms, 'multipath', multipath)
    if multipath:
        _add_parameter(job_parms, 'discoveryAuth',
                       kwargs.get('discovery_auth'))
        _add_parameter(job_parms, 'discoveryUser',
                       kwargs.get('discovery_username'))
        _add_parameter(job_parms, 'discoveryPassword',
                       kwargs.get('discovery_password'))

    try:
        job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
    except pexc.JobRequestFailed:
        with excutils.save_and_reraise_exception(reraise=False) as exc_ctx:
            # Process return code if available, else re-raise
            results = job_wrapper.get_job_results_as_dict()
            if not results.get('RETURN_CODE', None):
                LOG.error("iSCSI Discovery Job Failed, no RETURN_CODE.")
                exc_ctx.reraise = True

    results = job_wrapper.get_job_results_as_dict()

    return _process_iscsi_result(results, kwargs.get('iqn'), host_ip)


def discover_iscsi(adapter, host_ip, user, password, iqn, vios_uuid,
                   transport_type=None, lunid=None, iface_name=None, auth=None,
                   discovery_auth=None, discovery_username=None,
                   discovery_password=None, multipath=False):

    """Initiates the iSCSI discovery and login job

    :param adapter: pypowervm adapter
    :param host_ip: The portal or list of portals for the iscsi target. A
                    portal looks like ip:port.
    :param user: The username needed for authentication.
    :param password: The password needed for authentication.
    :param iqn: The IQN (iSCSI Qualified Name) or list of IQNs for the created
                volume on the target (e.g. iqn.2016-06.world.srv:target00).
    :param vios_uuid: The uuid of the VIOS (VIOS must be a Novalink VIOS type).
    :param transport_type: (Deprecated) Transport type of the volume to be
                           connected. Use iface_name instead.
    :param lunid: Target LUN ID or list of LUN IDs for the volume.
    :param iface_name: Iscsi iface name to use for the connection.
    :param auth: Authentication type
    :param discovery_auth: Discovery authentication type.
    :param discovery_username: The username needed for discovery
                               authentication.
    :param discovery_password: The password needed for discovery
                               authentication.
    :param multipath: Whether the connection is multipath or not.
    :return: The device name of the created volume.
    :return: The UniqueDeviceId of the create volume.
    :raise: ISCSIDiscoveryFailed in case of bad return code.
    :raise: JobRequestFailed in case of failure
    """

    kwargs = {
        'user': user, 'password': password,
        'iqn': iqn, 'transport_type': transport_type,
        'lunid': lunid, 'iface_name': iface_name,
        'auth': auth, 'discovery_auth': discovery_auth,
        'discovery_username': discovery_username,
        'discovery_password': discovery_password
        }

    status, devname, udid = _discover_iscsi(adapter, host_ip, vios_uuid,
                                            multipath, **kwargs)
    if status:
        _log_iscsi_status(status)

    # If status is ISCSI_ERR_ODM_QUERY, then there are chance of stale iscsi
    # disks, cleanup and re-discover.
    if status == ISCSIStatus.ISCSI_ERR_ODM_QUERY:
        vwrap = VIOS.get(adapter, uuid=vios_uuid, xag=[c.XAG.VIO_SMAP])
        # Check for stale lpars with SCSI mappings
        scrub_ids = tsk_stg.find_stale_lpars(vwrap)
        if scrub_ids:
            LOG.info(_("Scrub stale storage for LPAR IDs %s and "
                       "retry iSCSI discovery."), scrub_ids)
            # Scrub from just the VIOS in question.
            scrub_task = tx.FeedTask('scrub_vios_%s' % vios_uuid, [vwrap])
            tsk_stg.add_lpar_storage_scrub_tasks(scrub_ids, scrub_task)
            scrub_task.execute()

        # iSCSI Discover does not autoclean the hdisk, so remove iscsi hdisk.
        remove_iscsi(adapter, iqn, vios_uuid, iface_name, lunid, host_ip,
                     multipath)

        # Re-discover the volume
        status, devname, udid = _discover_iscsi(adapter, host_ip, vios_uuid,
                                                multipath, **kwargs)

    if not good_discovery(status, devname):
        raise pexc.ISCSIDiscoveryFailed(vios_uuid=vios_uuid, status=status)

    return devname, udid


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


def remove_iscsi(adapter, targetIQN, vios_uuid, iface_name=None, lun=None,
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
    :param iface_name: Name of the iface used for the connection.
    :param lun: The lun or list of luns to be removed.
    :param portal: The portal or list of portals associated with the created
                   volume (ip:port).
    :param multipath: Whether the connection is multipath or not.
    :raise: ISCSIRemoveFailed in case of bad return code.
    :raise: JobRequestFailed in case of failure.
    """
    resp = adapter.read(VIOS.schema_type, vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO,
                        suffix_parm=(_ISCSI_REMOVE))
    job_wrapper = job.Job.wrap(resp)
    job_parms = []
    _add_parameter(job_parms, 'ifaceName', iface_name)
    _add_parameter(job_parms, 'targetIQN', targetIQN)
    _add_parameter(job_parms, 'targetPORTAL', portal)
    _add_parameter(job_parms, 'targetLUN', lun)
    _add_parameter(job_parms, 'multipath', multipath)
    try:
        job_wrapper.run_job(vios_uuid, job_parms=job_parms, timeout=120)
    except pexc.JobRequestFailed:
        results = job_wrapper.get_job_results_as_dict()
        # Ignore if the command is performed on NotSupported AIX VIOS
        if results.get('RETURN_CODE') != ISCSIStatus.ISCSI_COMMAND_NOT_FOUND:
            raise
        return
    results = job_wrapper.get_job_results_as_dict()
    status = results.get('RETURN_CODE')
    if status not in _GOOD_REMOVE_STATUSES:
        raise pexc.ISCSIRemoveFailed(vios_uuid=vios_uuid, status=status)
