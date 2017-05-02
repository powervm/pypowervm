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

"""Tasks around IBMi VM changes."""

from oslo_config import cfg
from oslo_log import log as logging

import pypowervm.const as c
import pypowervm.exceptions as pvmex
from pypowervm import i18n
import pypowervm.tasks.scsi_mapper as pvm_smap
import pypowervm.tasks.vfc_mapper as pvm_vfcmap
import pypowervm.wrappers.base_partition as pvm_bp
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as pvm_lpar
from pypowervm.wrappers import virtual_io_server as pvm_vios

LOG = logging.getLogger(__name__)

# TODO(IBM) translation
_LI = i18n._


def update_ibmi_settings(adapter, lpar_w, boot_type):
    """Update TaggedIO, Keylock postion and IPL Source of IBMi VM.

    TaggedIO of IBMi vm will be updated to identify the load source,
    alternative load source and console type. Keylock position will be set
    to the value of NORMAL in KeylockPos enumration. IPL Source will be set
    to the value of B in IPLSrc enumration.
    :param adapter: The pypowervm adapter.
    :param lpar_w: The lpar wrapper.
    :param boot_type: The boot connectivity type of the VM. It is a string
                      value that represents one of the values in the
                      BootStorageType enumeration.
    :return: The updated LPAR wrapper. The update is not executed against the
             system, but rather the wrapper itself is updated locally.
    """
    load_source = None
    alt_load_source = None
    client_adapters = []
    if boot_type == pvm_lpar.BootStorageType.VFC:
        msg = _LI("Setting Virtual Fibre Channel slot as load source for VM "
                  "%s") % lpar_w.name
        LOG.info(msg)
        for vios_wrap in pvm_vios.VIOS.get(adapter, xag=[c.XAG.VIO_FMAP]):
            existing_maps = pvm_vfcmap.find_maps(
                vios_wrap.vfc_mappings, lpar_w.id)
            client_adapters.extend([vfcmap.client_adapter
                                    for vfcmap in existing_maps
                                    if vfcmap.client_adapter is not None])
    else:
        # That boot volume, which is vscsi physical volume, ssp lu
        # and local disk, could be handled here.
        msg = _LI("Setting Virtual SCSI slot slot as load source for VM "
                  "%s") % lpar_w.name
        LOG.info(msg)
        for vios_wrap in pvm_vios.VIOS.get(adapter, xag=[c.XAG.VIO_SMAP]):
            existing_maps = pvm_smap.find_maps(
                vios_wrap.scsi_mappings, lpar_w.id)
            client_adapters.extend([smap.client_adapter
                                    for smap in existing_maps
                                    if smap.client_adapter is not None])
    slot_nums = set(s.lpar_slot_num for s in client_adapters)
    slot_nums = list(slot_nums)
    slot_nums.sort()
    if len(slot_nums) > 0:
        load_source = slot_nums.pop(0)
    if len(slot_nums) > 0:
        alt_load_source = slot_nums.pop(0)
    if load_source is not None:
        if alt_load_source is None:
            alt_load_source = load_source
        lpar_w.io_config.tagged_io = pvm_bp.TaggedIO.bld(
            adapter, load_src=load_source, console='HMC',
            alt_load_src=alt_load_source)
    else:
        raise pvmex.IBMiLoadSourceNotFound(vm_name=lpar_w.name)
    lpar_w.desig_ipl_src = pvm_lpar.IPLSrc.B
    lpar_w.keylock_pos = pvm_bp.KeylockPos.NORMAL
    return lpar_w


class IBMiPanelOperations(object):
    DUMPRESTART = 'dumprestart'
    DSTON = 'dston'
    RETRYDUMP = 'retrydump'
    REMOTEDSTOFF = 'remotedstoff'
    REMOTEDSTON = 'remotedston'
    IOPRESET = 'iopreset'
    IOPDUMP = 'iopdump'
    CONSOLESERVICE = 'consoleservice'

    ALL_VALUES = (DUMPRESTART, DSTON, RETRYDUMP, REMOTEDSTOFF, REMOTEDSTON,
                  IOPRESET, IOPDUMP, CONSOLESERVICE)

CONF = cfg.CONF
IBMI_PANEL_JOB_SUFFIX = 'PanelFunction'
IBMI_PARAM_KEY = 'operation'


def start_panel_job(part, opt=None, timeout=CONF.pypowervm_job_request_timeout,
                    synchronous=True):
    """Run an IBMi Panel job operation.

    :param part: Partition (LPAR or VIOS) wrapper indicating the partition
                 to run the panel function against.
    :param opt: One of the IBMiPanelOperations enum values to run.
    :param timeout: value in seconds for specifying how long to wait for
                    the Job to complete.
    :param synchronous: If True, this method will not return until the Job
                        completes (whether success or failure) or times
                        out.  If False, this method will return as soon as
                        the Job has started on the server (that is,
                        achieved any state beyond NOT_ACTIVE).  Note that
                        timeout is still possible in this case.
    """
    if not part:
        raise pvmex.PanelFunctionRequiresPartition()
    if opt not in IBMiPanelOperations.ALL_VALUES:
        raise pvmex.InvalidIBMiPanelFunctionOperation(
            op_name=opt,
            valid_ops=', '.join(IBMiPanelOperations.ALL_VALUES))
    if part.env != pvm_bp.LPARType.OS400:
        raise pvmex.PartitionIsNotIBMi(part_name=part.name)

    # Fetch the Job template wrapper
    jwrap = job.Job.wrap(part.adapter.read(
        part.schema_type, part.uuid, suffix_type=c.SUFFIX_TYPE_DO,
        suffix_parm=IBMI_PANEL_JOB_SUFFIX))

    # Run the Job, letting exceptions raise up.
    jwrap.run_job(
        part.uuid,
        job_parms=[job.Job.create_job_parameter(IBMI_PARAM_KEY, opt)],
        timeout=timeout, synchronous=synchronous)
