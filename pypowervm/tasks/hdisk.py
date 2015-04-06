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

import itertools
import logging

from lxml import etree

import pypowervm.entities as ent
import pypowervm.exceptions as pexc
from pypowervm.i18n import _
from pypowervm.wrappers import constants as c
from pypowervm.wrappers import job as pvm_job
from pypowervm.wrappers import virtual_io_server as pvm_vios

LOG = logging.getLogger(__name__)

LUA_CMD_VERSION = '3'
LUA_VERSION = '2.0'
LUA_RECOVERY = 'LUARecovery'

LUA_TYPE_IBM = "IBM"
LUA_TYPE_EMC = "EMC"
LUA_TYPE_NETAPP = "NETAPP"
LUA_TYPE_HDS = "HDS"
LUA_TYPE_HP = "HP"
LUA_TYPE_OTHER = "OTHER"

# LUA Recovery status codes
LUA_STATUS_DEVICE_IN_USE = '1'
LUA_STATUS_ITL_NOT_RELIABLE = '2'
LUA_STATUS_DEVICE_AVAILABLE = '3'
LUA_STATUS_STORAGE_NOT_INTEREST = '4'
LUA_STATUS_LUA_NOT_INTEREST = '5'
LUA_STATUS_INCORRECT_ITL = '6'
LUA_STATUS_FOUND_DEVICE_UNKNOWN_UDID = '7'
LUA_STATUS_FOUND_ITL_ERR = '8'


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
        # PowerVM keeps LUN identifiers in hex format.  Python conversion to
        # hex adds a 0x at beginning (thus the [2:] to strip that off).
        # Identifier on end is always the 0's.
        self.lun = hex(int(lun))[2:] + "000000000000"

    def __eq__(self, other):
        if other is None or not isinstance(other, ITL):
            return False

        return (self.initiator == other.initiator and
                self.target == other.target and
                self.lun == other.lun)

    def __ne__(self, other):
        return not self.__eq__(other)


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


def discover_hdisk(adapter, vios_uuid, itls, vendor=LUA_TYPE_IBM):
    """This method should be invoked after a new disk should be discovered.

    When a new disk is created externally (say on a block device), the Virtual
    I/O Server may or may not discover it immediately.  This method forces
    a discovery on a given Virtual I/O Server.

    :param adapter: The pypowervm adapter.
    :param vios_uuid: The Virtual I/O Server UUID.
    :param itls: A list of ITL objects.
    :param vendor: The vendor for the LUN.  See the LUA_TYPE_* constants.
    :return status: The status code from the discover process.
                    See LUA_STATUS_* constants.
    :return dev_name: The name of the discovered hdisk.
    :return udid: The UDID of the device.
    """

    # Build the LUA recovery XML
    lua_xml = _lua_recovery_xml(itls, vendor=vendor)

    # Build up the job & invoke
    resp = adapter.read(pvm_vios.VIOS.schema_type, root_id=vios_uuid,
                        suffix_type=c.SUFFIX_TYPE_DO, suffix_parm=LUA_RECOVERY)
    job_wrapper = pvm_job.Job.wrap(resp)
    job_parms = [job_wrapper.create_job_parameter('inputXML', lua_xml,
                                                  cdata=True)]
    job_wrapper.run_job(adapter, vios_uuid, job_parms=job_parms)

    # Get the job result, and parse the output.
    job_result = job_wrapper.get_job_results_as_dict()
    status, devname, udid = _process_lua_result(job_result)
    return status, devname, udid


def _lua_recovery_xml(itls, vendor=LUA_TYPE_IBM):
    """Builds the XML that is used as input for the lua_recovery job.

    The lua_recovery provides a very quick way for the system to discover
    an hdisk on the system.  This method builds the input into the lua_recovery
    job.
    :param itls: The list of ITL objects that define the various connections
                 between the server port (initiator), disk port (target) and
                 disk itself.
    :param vendor: The LUA vendor.  See the LUA_TYPE_* Constants.
    :return: The CDATA XML that is used for the lua_recovery job.
    """
    root = ent.Element("XML_LIST", ns='')

    # The general attributes
    # TODO(IBM) Need to determine value of making these constants modifiable
    general = ent.Element("general", ns='')
    general.append(ent.Element("cmd_version", text=LUA_CMD_VERSION, ns=''))
    general.append(ent.Element("version", text=LUA_VERSION, ns=''))
    root.append(general)

    # TODO(IBM) This can be re-evaluated.  Set to true if you know for sure
    # the ITLs are alive.  If there are any bad ITLs, this should be false.
    root.append(ent.Element("reliableITL", text="false", ns=''))

    # There is only one device in the device list.
    device_list = ent.Element("deviceList", ns='')
    device = ent.Element("device", ns='')
    device.append(ent.Element("vendor", text=vendor, ns=''))
    device.append(ent.Element("deviceTag", text="1", ns=''))

    itl_list = ent.Element("itlList", ns='')
    itl_list.append(ent.Element("number", text="%d" % (len(itls)), ns=''))

    for itl in itls:
        itl_elem = ent.Element("itl", ns='')

        itl_elem.append(ent.Element("Iwwpn", text=itl.initiator, ns=''))
        itl_elem.append(ent.Element("Twwpn", text=itl.target, ns=''))
        itl_elem.append(ent.Element("lua", text=itl.lun, ns=''))

        itl_list.append(itl_elem)

    device.append(itl_list)
    device_list.append(device)
    root.append(device_list)

    return root.toxmlstring().decode('utf-8')


def _process_lua_result(result):
    """Processes the Output XML returned by LUARecovery.

    :return status: The status code from the discover process.
                    See LUA_STATUS_* constants.
    :return dev_name: The name of the discovered hdisk.
    :return udid: The UDID of the device.
    """

    if result is not None:
        root = etree.fromstring(result['StdOut'])
        for child in root:
            if child.tag == "deviceList":
                for gchild in child:
                    status = None
                    dev_name = None
                    udid = None
                    message = None
                    for ggchild in gchild:
                        if ggchild.tag == "status":
                            status = ggchild.text
                        elif ggchild.tag == "pvName":
                            dev_name = ggchild.text
                        elif ggchild.tag == "udid":
                            udid = ggchild.text
                        elif ggchild.tag == "msg":
                            for mchild in ggchild:
                                if mchild.tag == "msgText":
                                    message = mchild.text
                    _validate_lua_status(status, dev_name, udid, message)
                    return status, dev_name, udid
    return None, None, None


def _validate_lua_status(status, dev_name, udid, message):
    """Logs any issues with the LUA."""

    if status == LUA_STATUS_DEVICE_AVAILABLE:
        LOG.info(_("LUA Discovery Successful Device Found: %s"),
                 dev_name)
    elif status == LUA_STATUS_FOUND_ITL_ERR:
        # Message is already set.
        LOG.warn(_("ITL Error encountered: %s"), message)
        pass
    elif status == LUA_STATUS_DEVICE_IN_USE:
        LOG.warn(_("%s Device is currently in use"), dev_name)
    elif status == LUA_STATUS_FOUND_DEVICE_UNKNOWN_UDID:
        LOG.warn(_("%s Device discovered with unknown uuid"), dev_name)
    elif status == LUA_STATUS_INCORRECT_ITL:
        LOG.warn(_("Failed to Discover the Device : %s"), dev_name)
    return status, dev_name, message, udid


def remove_hdisk(adapter, host_name, dev_name, vios_uuid):
    """Command to remove the device from the VIOS.

    :param adapter: The pypowervm adapter.
    :param host_name: The name of the host.
    :param dev_name: The name of the device to remove.
    :param vios_uuid: The Virtual I/O Server UUID.
    """
    # TODO(IBM): The implementation will be replaced when
    # new API available.
    try:
        # Execute a read on the vios to get the vios name
        resp = adapter.read(pvm_vios.VIOS.schema_type, root_id=vios_uuid)
        vios_w = pvm_vios.VIOS.wrap(resp)
        # build command
        rm_cmd = ('viosvrcmd -m ' + host_name + ' -p ' + vios_w.name +
                  ' -c \"rmdev -dev ' + dev_name + '\"')
        LOG.debug('RMDEV Command Input: %s' % rm_cmd)

        # Get the response for the CLIRunner command
        resp = adapter.read(c.MGT_CONSOLE, None,
                            suffixType=c.SUFFIX_TYPE_DO,
                            suffixParm='CLIRunner')

        # Create the job parameters
        job_wrapper = pvm_job.Job.wrap(resp)
        ack_parm = 'acknowledgeThisAPIMayGoAwayInTheFuture'
        job_parms = [job_wrapper.create_job_parameter('cmd', rm_cmd),
                     job_wrapper.create_job_parameter(ack_parm,
                                                      'true')]

        job_wrapper.run_job(adapter, None, job_parms=job_parms)
        return job_wrapper.job_status()
    except pexc.JobRequestFailed as error:
        LOG.info(_('CLIRunner Error: %s') % error)
