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

"""Tasks around VIOS-backed 'physical' fibre channel disks."""

import itertools

from lxml import etree
from oslo_log import log as logging

from pypowervm import const as c
import pypowervm.entities as ent
import pypowervm.exceptions as pexc
from pypowervm.i18n import _
import pypowervm.tasks.storage as tsk_stg
import pypowervm.utils.transaction as tx
from pypowervm.wrappers import job as pvm_job
from pypowervm.wrappers import virtual_io_server as pvm_vios

LOG = logging.getLogger(__name__)

_LUA_CMD_VERSION = '3'
_LUA_VERSION = '2.0'
_LUA_RECOVERY = 'LUARecovery'
_RM_HDISK = 'RemoveDevice'

_MGT_CONSOLE = 'ManagementConsole'


class LUAType(object):
    """LUA Vendors."""
    IBM = "IBM"
    EMC = "EMC"
    NETAPP = "NETAPP"
    HDS = "HDS"
    HP = "HP"
    OTHER = "OTHER"


class LUAStatus(object):
    """LUA Recovery status codes."""
    DEVICE_IN_USE = '1'
    ITL_NOT_RELIABLE = '2'
    DEVICE_AVAILABLE = '3'
    STORAGE_NOT_INTEREST = '4'
    LUA_NOT_INTEREST = '5'
    INCORRECT_ITL = '6'
    FOUND_DEVICE_UNKNOWN_UDID = '7'
    FOUND_ITL_ERR = '8'


def normalize_lun(scsi_id):
    """Normalize the lun id to Big Endian

    :param scsi_id: Volume lun id
    :return: Converted LUN id in Big Endian as per the RFC 4455
    """
    # PowerVM keeps LUN identifiers in hex format.
    lun = '%x' % int(scsi_id)
    # For drivers which support complex LUA lun-id exceeding more than 2
    # bytes in such cases we need to append 8 zeros else 12 zeros to
    # pass 8 byte lun-id
    if len(lun) == 8:
        lun += "00000000"
    else:
        lun += "000000000000"

    return lun


class ITL(object):
    """The Nexus ITL.

    See SCSI ITL.  This is the grouping of the SCSI initiator, target and
    LUN.
    """

    def __init__(self, initiator, target, lun):
        """Create the ITL.

        :param initiator: The initiator WWPN.
        :param target: The target WWPN.
        :param lun: The LUN identifier.  Ex. 2 (an int).  The identifier will
                    be formatted from a generic integer LUN ID to match
                    PowerVM's LUN Identifier format.
        """
        self.initiator = initiator.lower().replace(':', '')
        self.target = target.lower().replace(':', '')
        self.lun = normalize_lun(lun)

    def __eq__(self, other):
        if other is None or not isinstance(other, ITL):
            return False

        return (self.initiator == other.initiator and
                self.target == other.target and
                self.lun == other.lun)

    def __hash__(self):
        return hash(self.initiator) ^ hash(self.target) ^ hash(self.lun)

    def __ne__(self, other):
        return not self.__eq__(other)


def good_discovery(status, device_name):
    """Checks the hdisk discovery results for a good discovery.

    Acceptable LUA discovery statuses are :-
    DEVICE_AVAILABLE: hdisk discovered on all the ITL paths and available.
    DEVICE_IN_USE: hdisk discovered on all the ITL paths and is in-use by
    the server.
    FOUND_ITL_ERR: hdisk is discovered on some of the ITL paths and available.
    This can happen if there are multiple ITL nexus paths are passed, and
    hdisk is discovered on few of the paths only. This can happen if multiple
    target wwpns and vios wwpns exists and only few are connected. If hdisk
    can be discovered on ANY of the paths its considered for good discovery.
   """
    return device_name is not None and status in [
        LUAStatus.DEVICE_AVAILABLE, LUAStatus.DEVICE_IN_USE,
        LUAStatus.FOUND_ITL_ERR]


def build_itls(i_wwpns, t_wwpns, lun):
    """This method builds the list of ITLs for all of the permutations.

    An ITL is specific to an initiator, target, and LUN.  However, with multi
    pathing, there are several scenarios where a given LUN will have many ITLs
    because of multiple initiators or targets.

    The initiators should be tied to a given Virtual I/O Server (or perhaps
    specific WWPNs within a VIOS).

    :param i_wwpns: List or set of initiator WWPNs.
    :param t_wwpns: List or set of target WWPNs.
    :param lun: The LUN identifier.  Ex. 2 (an int).  The identifier will be
                formatted from a generic integer LUN ID to match PowerVM's
                LUN Identifier format.
    :return: List of all the ITL permutations.
    """
    return [ITL(i, t, lun) for i, t in itertools.product(i_wwpns, t_wwpns)]


def discover_hdisk(adapter, vios_uuid, itls, vendor=LUAType.OTHER):
    """Attempt to discover a hard disk attached to a Virtual I/O Server.

    See lua_recovery.  This method attempts that call and analyzes the
    results.  On certain failure conditions (see below), this method will find
    stale LPARs, scrub storage artifacts associated with them, and then retry
    lua_recovery.  The retry is only attempted once; that result is returned
    regardless.

    The main objective of this method is to resolve errors resulting from
    incomplete cleanup of previous LPARs.  The stale LPAR's storage mappings
    can cause hdisk discovery to fail because it thinks the hdisk is already in
    use.

    Retry conditions: The scrub-and-retry will be triggered if:
    o dev_name is None; or
    o status is anything other than DEVICE_AVAILABLE or FOUND_ITL_ERR.  (The
      latter is acceptable because it means we discovered some, but not all, of
      the ITLs.  This is okay as long as dev_name is set.)

    :param adapter: The pypowervm adapter.
    :param vios_uuid: The Virtual I/O Server UUID.
    :param itls: A list of ITL objects.
    :param vendor: The vendor for the LUN.  See the LUAType.* constants.
    :return status: The status code from the discover process.
                    See LUAStatus.* constants.
    :return dev_name: The name of the discovered hdisk.
    :return udid: The UDID of the device.
    """
    # First attempt
    status, devname, udid = lua_recovery(adapter, vios_uuid, itls,
                                         vendor=vendor)
    # Do we need to scrub and retry?
    if not good_discovery(status, devname):
        vwrap = pvm_vios.VIOS.get(adapter, uuid=vios_uuid,
                                  xag=(c.XAG.VIO_SMAP, c.XAG.VIO_FMAP))

        scrub_ids = tsk_stg.find_stale_lpars(vwrap)
        if scrub_ids:
            # Detailed warning message by _log_lua_status
            LOG.warning(_("hdisk discovery failed; will scrub stale storage "
                          "for LPAR IDs %s and retry."), scrub_ids)
            # Scrub from just the VIOS in question.
            scrub_task = tx.FeedTask('scrub_vios_%s' % vios_uuid, [vwrap])
            tsk_stg.add_lpar_storage_scrub_tasks(scrub_ids, scrub_task)
            scrub_task.execute()
            status, devname, udid = lua_recovery(adapter, vios_uuid, itls,
                                                 vendor=vendor)
    return status, devname, udid


def lua_recovery(adapter, vios_uuid, itls, vendor=LUAType.OTHER):
    """Logical Unit Address Recovery - discovery of a FC-attached hdisk.

    When a new disk is created externally (say on a block device), the Virtual
    I/O Server may or may not discover it immediately.  This method forces a
    discovery on a given Virtual I/O Server.

    :param adapter: The pypowervm adapter.
    :param vios_uuid: The Virtual I/O Server UUID.
    :param itls: A list of ITL objects.
    :param vendor: The vendor for the LUN.  See the LUAType.* constants.
    :return status: The status code from the discover process.
                    See LUAStatus.* constants.
    :return dev_name: The name of the discovered hdisk.
    :return udid: The UDID of the device.
    """
    # Reduce the ITLs to ensure no duplicates
    itls = set(itls)

    # Build the LUA recovery XML
    lua_xml = _lua_recovery_xml(itls, adapter, vendor=vendor)

    # Build up the job & invoke
    resp = adapter.read(
        pvm_vios.VIOS.schema_type, root_id=vios_uuid,
        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=_LUA_RECOVERY)
    job_wrapper = pvm_job.Job.wrap(resp)
    job_parms = [job_wrapper.create_job_parameter('inputXML', lua_xml,
                                                  cdata=True)]
    job_wrapper.run_job(vios_uuid, job_parms=job_parms)

    # Get the job result, and parse the output.
    job_result = job_wrapper.get_job_results_as_dict()
    status, devname, udid = _process_lua_result(job_result)
    return status, devname, udid


def _lua_recovery_xml(itls, adapter, vendor=LUAType.OTHER):
    """Builds the XML that is used as input for the lua_recovery job.

    The lua_recovery provides a very quick way for the system to discover
    an hdisk on the system.  This method builds the input into the lua_recovery
    job.
    :param itls: The list of ITL objects that define the various connections
                 between the server port (initiator), disk port (target) and
                 disk itself.
    :param vendor: The LUA vendor.  See the LUAType.* Constants.
    :return: The CDATA XML that is used for the lua_recovery job.
    """
    # Used for building the internal XML.

    root = ent.Element("XML_LIST", adapter, ns='')

    # The general attributes
    # TODO(IBM) Need to determine value of making these constants modifiable
    general = ent.Element("general", adapter, ns='')
    general.append(ent.Element("cmd_version", adapter, text=_LUA_CMD_VERSION,
                               ns=''))
    general.append(ent.Element("version", adapter, text=_LUA_VERSION, ns=''))
    root.append(general)

    # TODO(IBM) This can be re-evaluated.  Set to true if you know for sure
    # the ITLs are alive.  If there are any bad ITLs, this should be false.
    root.append(ent.Element("reliableITL", adapter, text="false", ns=''))

    # There is only one device in the device list.
    device_list = ent.Element("deviceList", adapter, ns='')
    device = ent.Element("device", adapter, ns='')
    device.append(ent.Element("vendor", adapter, text=vendor, ns=''))
    device.append(ent.Element("deviceTag", adapter, text="1", ns=''))

    itl_list = ent.Element("itlList", adapter, ns='')
    itl_list.append(ent.Element("number", adapter, text="%d" % (len(itls)),
                                ns=''))

    for itl in itls:
        itl_elem = ent.Element("itl", adapter, ns='')

        itl_elem.append(ent.Element("Iwwpn", adapter, text=itl.initiator,
                                    ns=''))
        itl_elem.append(ent.Element("Twwpn", adapter, text=itl.target, ns=''))
        itl_elem.append(ent.Element("lua", adapter, text=itl.lun, ns=''))

        itl_list.append(itl_elem)

    device.append(itl_list)
    device_list.append(device)
    root.append(device_list)

    return root.toxmlstring().decode('utf-8')


def _process_lua_result(result):
    """Processes the Output XML returned by LUARecovery.

    :return status: The status code from the discover process.
                    See LUAStatus.* constants.
    :return dev_name: The name of the discovered hdisk.
    :return udid: The UDID of the device.
    """
    if result is None:
        return None, None, None

    # The result may push to StdOut or to OutputXML (different versions push
    # to different locations).
    xml_resp = result.get('OutputXML')
    if xml_resp is None:
        xml_resp = result.get('StdOut')

    # If still none, nothing to do.
    if xml_resp is None:
        return None, None, None

    # The response is an XML block.  Put into an XML structure and get
    # the data out of it.
    root = etree.fromstring(xml_resp)
    base = 'deviceList/device/'
    estatus, edev_name, eudid, emessage = (
        root.find(base + x)
        for x in ('status', 'pvName', 'udid', 'msg/msgText'))
    status, dev_name, udid, message = (
        y.text if y is not None else None
        for y in (estatus, edev_name, eudid, emessage))
    _log_lua_status(status, dev_name, message)
    return status, dev_name, udid


def _log_lua_status(status, dev_name, message):
    """Logs any issues with the LUA."""

    if status == LUAStatus.DEVICE_AVAILABLE:
        LOG.info(_("LUA Recovery Successful. Device Found: %s"),
                 dev_name)
    elif status == LUAStatus.FOUND_ITL_ERR:
        # Message is already set.
        LOG.warning(_("ITL Error encountered: %s"), message)
    elif status == LUAStatus.DEVICE_IN_USE:
        LOG.warning(_("%s Device is currently in use."), dev_name)
    elif status == LUAStatus.FOUND_DEVICE_UNKNOWN_UDID:
        LOG.warning(_("%s Device discovered with unknown UDID."), dev_name)
    elif status == LUAStatus.INCORRECT_ITL:
        LOG.warning(_("Failed to Discover the Device : %s"), dev_name)


def remove_hdisk(adapter, host_name, dev_name, vios_uuid):
    """Command to remove the device from the VIOS.

    :param adapter: The pypowervm adapter.
    :param host_name: The name of the host.
    :param dev_name: The name of the device to remove.
    :param vios_uuid: The Virtual I/O Server UUID.
    """
    if adapter.traits.rmdev_job_available:
        _remove_hdisk_job(adapter, dev_name, vios_uuid)
    else:
        _remove_hdisk_classic(adapter, host_name, dev_name, vios_uuid)


def _remove_hdisk_job(adapter, dev_name, vios_uuid):
    """Runs the PowerVM Job to remove a hdisk.

    :param adapter: The pypowervm adapter.
    :param dev_name: The name of the device to remove.
    :param vios_uuid: The Virtual I/O Server UUID.
    """
    # Build up the job & invoke
    resp = adapter.read(
        pvm_vios.VIOS.schema_type, root_id=vios_uuid,
        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=_RM_HDISK)
    job_wrapper = pvm_job.Job.wrap(resp)
    job_parms = [job_wrapper.create_job_parameter('devName', dev_name)]

    # Run the job.  If the hdisk removal failed, the job will raise an
    # exception.  No output otherwise.
    job_wrapper.run_job(vios_uuid, job_parms=job_parms)


def _remove_hdisk_classic(adapter, host_name, dev_name, vios_uuid):
    """Command to remove the device from the VIOS.

    Runs a remote command to perform the action.

    :param adapter: The pypowervm adapter.
    :param host_name: The name of the host.
    :param dev_name: The name of the device to remove.
    :param vios_uuid: The Virtual I/O Server UUID.
    """
    try:
        # Execute a read on the vios to get the vios name
        resp = adapter.read(pvm_vios.VIOS.schema_type, root_id=vios_uuid)
        vios_w = pvm_vios.VIOS.wrap(resp)
        # build command
        rm_cmd = ('viosvrcmd -m ' + host_name + ' -p ' + vios_w.name +
                  ' -c \"rmdev -dev ' + dev_name + '\"')
        LOG.debug('RMDEV Command Input: %s' % rm_cmd)

        # Get the response for the CLIRunner command
        resp = adapter.read(_MGT_CONSOLE, None,
                            suffix_type=c.SUFFIX_TYPE_DO,
                            suffix_parm='CLIRunner')

        # Create the job parameters
        job_wrapper = pvm_job.Job.wrap(resp)
        ack_parm = 'acknowledgeThisAPIMayGoAwayInTheFuture'
        job_parms = [job_wrapper.create_job_parameter('cmd', rm_cmd),
                     job_wrapper.create_job_parameter(ack_parm,
                                                      'true')]

        job_wrapper.run_job(None, job_parms=job_parms)
        return job_wrapper.job_status()
    except pexc.JobRequestFailed as error:
        LOG.warning(_('CLIRunner Error: %s') % error)


def get_pg83_via_job(adapter, vios_uuid, udid):
    """Inventory call to fetch the encoded SCSI Page 0x83 descriptor for a PV.

    :param adapter: The pypowervm adapter through which to run the Job.
    :param vios_uuid: The UUID of the Virtual I/O Server owning the PV.
    :param udid: The UDID of the PV to query.
    :return: SCSI PG83 NAA descriptor, base64-encoded.  May be None.
    """
    # TODO(efried): Remove this method once VIOS supports pg83 in Events
    # Build the hdisk inventory input XML
    lua_xml = ('<uom:VIO xmlns:uom="http://www.ibm.com/xmlns/systems/power/fir'
               'mware/uom/mc/2012_10/" version="1.21" xmlns=""><uom:Request ac'
               'tion_str="QUERY_INVENTORY"><uom:InventoryRequest inventoryType'
               '="base"><uom:VioTypeFilter type="PV"/><uom:VioUdidFilter udid='
               '"%s"/></uom:InventoryRequest></uom:Request></uom:VIO>' % udid)

    # Build up the job & invoke
    job_wrapper = pvm_job.Job.wrap(adapter.read(
        pvm_vios.VIOS.schema_type, root_id=vios_uuid,
        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=_LUA_RECOVERY))
    job_wrapper.run_job(vios_uuid, job_parms=[
        job_wrapper.create_job_parameter('inputXML', lua_xml, cdata=True)])

    # Get the job result, and parse the output.
    result = job_wrapper.get_job_results_as_dict()

    # The result may push to StdOut or to OutputXML (different versions push
    # to different locations).
    if not result or not any((k in result for k in ('OutputXML', 'StdOut'))):
        LOG.warning(_('QUERY_INVENTORY LUARecovery Job succeeded, but result '
                      'contained neither OutputXML nor StdOut.'))
        return None
    xml_resp = result.get('OutputXML', result.get('StdOut'))
    LOG.debug('QUERY_INVENTORY result: %s' % xml_resp)

    return _parse_pg83_xml(xml_resp)


def _parse_pg83_xml(xml_resp):
    """Parse LUARecovery XML response, looking for pg83 descriptor.

    :param xml_resp: Tuple containing OutputXML and StdOut results of the
                     LUARecovery Job
    :return: pg83 descriptor text, or None if not found.
    """
    # QUERY_INVENTORY response may contain more than one element.  Each will be
    # delimited by its own <?xml?> tag.  etree will only parse one at a time.
    for chunk in xml_resp.split('<?xml version="1.0"?>'):
        if not chunk:
            continue
        try:
            parsed = etree.fromstring(chunk)
        except etree.XMLSyntaxError as e:
            LOG.warning(_('QUERY_INVENTORY produced invalid chunk of XML '
                          '(%(chunk)s).  Error: %(err)s'),
                        {'chunk': chunk, 'err': e.args[0]})
            continue
        for elem in parsed.getiterator():
            if (etree.QName(elem.tag).localname == 'PhysicalVolume_base' and
                    elem.attrib.get('desType') == "NAA"):
                return elem.attrib.get('descriptor')
    LOG.warning(_('Failed to find pg83 descriptor in XML output:\n%s'),
                xml_resp)
    return None
