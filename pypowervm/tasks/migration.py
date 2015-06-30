# Copyright 2015 IBM Corp.

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

from oslo.config import cfg

import pypowervm.const as c
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as wlpar

LOG = logging.getLogger(__name__)

CONF = cfg.CONF
CONF.import_opt('powervm_job_request_timeout', 'pypowervm.wrappers.job')

_SUFFIX_PARM_MIGRATE = 'Migrate'
_SUFFIX_PARM_MIGRATE_VALIDATE = 'MigrateValidate'
_SUFFIX_PARM_MIGRATE_ABORT = 'MigrateAbort'
_SUFFIX_PARM_MIGRATE_RECOVER = 'MigrateRecover'

TGT_MGD_SYS = 'TargetManagedSystemName'
TGT_RMT_HMC = 'TargetRemoteHMCIPAddress'
TGT_RMT_HMC_USR = 'TargetRemoteHMCUserID'
VFC_MAPPINGS = 'VirtualFCMappings'
VSCSI_MAPPINGS = 'VirtualSCSIMappings'
DEST_MSP = 'DestMSPIPaddr'
SRC_MSP = 'SourceMSPIPaddr'


def migrate_lpar(lpar, tgt_mgd_sys, validate_only=False,
                 tgt_mgmt_svr=None, tgt_mgmt_usr=None,
                 virtual_fc_mappings=None, virtual_scsi_mappings=None,
                 dest_msp_name=None, source_msp_name=None,
                 timeout=CONF.powervm_job_request_timeout):

    """Method to migrate a logical partition.

    :param lpar: The LPAR wrapper of the logical partition to migrate.
    :param tgt_mgd_sys: The name of the managed system to migrate to.
    :param validate_only: Indication of whether to just validate the migration
        or actually perform it.
    :param tgt_mgmt_svr: The ip of the PowerVM management platform managing
        the target host.
    :param tgt_mgmt_usr: The user id to use on the target PowerVM management
        platform.
    :param virtual_fc_mappings: The virtual fiber channel mappings to move
        during the migration.  See information below.
    :param virtual_scsi_mappings: The virtual scsi mappings to move during the
        migration. See information below.
    :param dest_msp_name: The name of the destination VIOS to use for the mover
        partition.
    :param source_msp_name: The name of the source VIOS to use for the mover
        partition.
    :param timeout: maximum number of seconds for job to complete

    virtual_fc_mappings:

    Comma separated list of virtual fibre channel adapter
    mappings, with each mapping having the following format:

    virtual-slot-number/vios-lpar-name/vios-lpar-ID
    [/[vios-virtual-slot-number][/[vios-fc-port-name]]]

    The first two '/' characters must be present. The third '/' character is
    optional, but it must be present if vios-virtual-slot-number or
    vios-fc-port-name is specified.  The last '/' character is optional but it
    must be present if vios-fc-port-name is specified.

    Optional values may be omitted. Optional values are vios-lpar-name
    or vios-lpar-ID (one of those values is required, but not both),
    vios-virtual-slot-number, and vios-fc-port-name.

    For example:
    4//1/14/fcs0 specifies a mapping of the virtual fibre channel client
    adapter with slot number 4 to the virtual fibre channel server adapter with
    slot number 14 in the VIOS partition with ID 1 on the destination managed
    system. In addition, the mapping specifies to use physical fibre channel
    port fcs0.

    virtual_scsi_mappings:

    Comma separated list of virtual SCSI adapter mappings, with each mapping
    having the following format:

    virtual-slot-number/vios-lpar-name/vios-lpar-ID
    [/vios-virtual-slot-number]

    The first two '/' characters must be present.  The last '/' character is
    optional, but it must be present if vios-virtual-slot-number is specified.
    Optional values may be omitted. Optional values are vios-lpar-name or
    vios-lpar-ID (one of those values is required, but not both), and
    vios-virtual-slot-number.

    For example:
    12/vios1//16 specifies a mapping of the virtual SCSI adapter with slot
    number 12 to slot number 16 on the VIOS partition vios1 on the destination
    managed system.
    """

    op = (_SUFFIX_PARM_MIGRATE_VALIDATE
          if validate_only else _SUFFIX_PARM_MIGRATE)
    resp = lpar.adapter.read(wlpar.LPAR.schema_type, lpar.uuid,
                             suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm=op)
    job_wrapper = job.Job.wrap(resp.entry)
    job_parms = [job_wrapper.create_job_parameter(TGT_MGD_SYS,
                                                  str(tgt_mgd_sys))]
    for kw, val in [(TGT_RMT_HMC, tgt_mgmt_svr),
                    (TGT_RMT_HMC_USR, tgt_mgmt_usr),
                    (VFC_MAPPINGS, virtual_fc_mappings),
                    (VSCSI_MAPPINGS, virtual_scsi_mappings),
                    (DEST_MSP, dest_msp_name), (SRC_MSP, source_msp_name)]:
        if val:
            job_parms.append(
                job_wrapper.create_job_parameter(kw, str(val)))

    job_wrapper.run_job(lpar.uuid, job_parms=job_parms, timeout=timeout)


def migrate_recover(lpar, force=False,
                    timeout=CONF.powervm_job_request_timeout):

    """Method to recover a failed logical partition migration.

    :param lpar: The LPAR wrapper of the logical partition to recover.
    :param force: Boolean specifying whether to force the migration to recover
        when errors are encountered.
    :param timeout: maximum number of seconds for job to complete
    """
    resp = lpar.adapter.read(wlpar.LPAR.schema_type, lpar.uuid,
                             suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm=_SUFFIX_PARM_MIGRATE_RECOVER)
    job_wrapper = job.Job.wrap(resp.entry)
    job_parms = []
    if force:
        job_parms.append(job_wrapper.create_job_parameter('Force', 'true'))

    job_wrapper.run_job(lpar.uuid, job_parms=job_parms, timeout=timeout)


def migrate_abort(lpar, timeout=CONF.powervm_job_request_timeout):

    """Method to abort a logical partition migration.

    :param lpar: The LPAR wrapper of the logical partition to abort the
        migration operation.
    :param timeout: maximum number of seconds for job to complete
    """

    resp = lpar.adapter.read(wlpar.LPAR.schema_type, lpar.uuid,
                             suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm=_SUFFIX_PARM_MIGRATE_ABORT)
    job_wrapper = job.Job.wrap(resp.entry)
    job_wrapper.run_job(lpar.uuid, job_parms=None, timeout=timeout)


def generate_lpm_mappings(lpar, vios_wraps):

    """Generates the required VFC/SCSI Mapping strings for migration.

    To perform migration of a LPAR, the VFC/SCSI mapping command data input
    has to be sent to the calling API in the specific format. This method is
    used to generate the properly formatted mapping strings of 
    virtual_fc_mappings and virtual_scsi_mappings for a given lpar. 
    This method will iterate through all the available  VIOS's and find the
    matching mappings for the lpar and return a comma separated list of 
    VFC and VSCSI Mappings which can be fed to migrate_lpar calling function
    command input.
    Details of the format can be found in migrated_lpar function description.
    :param lpar: LPAR wrapper for which the mappings needs to be created.
    :param vios_wraps: List of pypowervm vios wrappers called with XAGs for
                       ViosSCSIMapping and ViosFCMapping. If the VIOS wrapper does not
                       have xags then no mappings will be returned.
    :returns: Comma separated list of Virtual Fibre-Channel and Virtual SCSI
              mapping strings.
    """
    vfc_maps = []
    scsi_maps = []
    for vios_w in vios_wraps:
        vfc_mapping = _generate_vfc_mappings(lpar, vios_w.vfc_mappings,
                                             vios_w.name)
        scsi_mapping = _generate_scsi_mappings(lpar, vios_w.scsi_mappings,
                                               vios_w.name)
        if len(vfc_mapping):
            vfc_maps.extend(vfc_mapping)
        if len(scsi_mapping):
            scsi_maps.extend(scsi_mapping)
    return ','.join(vfc_maps), ','.join(scsi_maps)


def _generate_vfc_mappings(lpar, vfc_mappings, vios_name):
    """Generates the VFC mappings strings for LPAR migration per vios.

    :param lpar: LPAR wrapper for which the mappings need to be created.
    :vfc_mappings: Virtual Fibre Channel Mapping list of a single vios.
    :vios_name: Vios name which contain the VFC mappings.
    :return: formatted vfc mapping list.
     """
    mapping_list = []
    for vfc_map in vfc_mappings:
        if (vfc_map.client_adapter and
                vfc_map.client_adapter.lpar_id == lpar.id):
            # For virtual_fc_mappings the format is:
            # Comma separated list of virtual fibre channel adapter
            # mappings, with each mapping having the following format:
            # virtual-slot-number/vios-lpar-name/vios-lpar-ID
            # [/[vios-virtual-slot-number][/[vios-fc-port-name]]]
            mapping = (str(vfc_map.client_adapter.slot_number) + "/" +
                       vios_name + "/" + str(vfc_map.server_adapter.vios_id) +
                       "/" + str(vfc_map.server_adapter.slot_number) + "/" +
                       vfc_map.server_adapter.map_port)
            mapping_list.append(mapping)
    LOG.debug("VIOS = %(v)s VFC Mappings=%(map)s" % {'v': vios_name,
                                                     'map': mapping_list})
    return mapping_list


def _generate_scsi_mappings(lpar, scsi_mappings, vios_name):
    """Generates the SCSI mappings strings for LPAR migration per vios.

    :param lpar: LPAR wrapper for which the mappings need to be created.
    :param vfc_mappings: Virtual SCSI Mapping list of a single vios.
    :param vios_name: Vios name which contain the SCSI mappings.
    :return: formatted scsi mapping list.
    """
    mapping_list = []
    for scsi_map in scsi_mappings:
        if (scsi_map.client_adapter and
                scsi_map.client_adapter.lpar_id == lpar.id):
            # For virtual_scsi_mappings the format is:
            # Comma separated list of virtual SCSI adapter mappings,
            # with each mapping having the following format:
            # virtual-slot-number/vios-lpar-name/vios-lpar-ID
            # [/vios-virtual-slot-number]
            mapping = (str(scsi_map.client_adapter.slot_number) + "/" +
                       vios_name + "/" + str(scsi_map.server_adapter.vios_id) +
                       "/" + str(scsi_map.server_adapter.slot_number))
            mapping_list.append(mapping)
    LOG.debug("VIOS = %(v)s SCSI Mappings=%(map)s" % {'v': vios_name,
                                                      'map': mapping_list})
    return mapping_list
