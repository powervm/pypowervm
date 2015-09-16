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

import logging

import pypowervm.wrappers.logical_partition as pvm_lpar
import pypowervm.wrappers.base_partition as pvm_bp
from pypowervm.wrappers import virtual_io_server as pvm_vios

LOG = logging.getLogger(__name__)


def update_load_src(adapter, lpar_w, boot_type):
    """Update load source of IBMi VM.

    Load source of IBMi vm will be set to the virtual adapter to which
    the boot volume is attached.
    :param adapter: The pypowervm adapter.
    :param lpar_w: The lpar wrapper.
    :param boot_type: The boot connectivity type of the VM.
    :returns: The updated lpar wrapper.
    """
    load_source = None
    alt_load_source = None
    client_adapters = []
    if boot_type == 'vscsi':
        LOG.info('Setting vscsi slot as load source for ' +
                 'VM %s' % lpar_w.name)
        vios_wraps = pvm_vios.VIOS.wrap(adapter.read(
            pvm_vios.VIOS.schema_type,
            xag=[pvm_vios.VIOS.xags.SCSI_MAPPING]))
        for vios_wrap in vios_wraps:
            client_adapters.extend(
                [smap.client_adapter for smap in
                    vios_wrap.scsi_mappings
                    if smap.client_adapter is not None and
                    smap.client_adapter.lpar_id == lpar_w.id])
    else:
        LOG.info('Setting npiv slot as load source for ' +
                 'VM %s' % lpar_w.name)
        vios_wraps = pvm_vios.VIOS.wrap(adapter.read(
            pvm_vios.VIOS.schema_type,
            xag=[pvm_vios.VIOS.xags.FC_MAPPING]))
        for vios_wrap in vios_wraps:
            client_adapters.extend(
                [smap.client_adapter for smap in
                    vios_wrap.vfc_mappings
                    if smap.client_adapter is not None and
                    smap.client_adapter.lpar_id == lpar_w.id])
    slot_num = set(s.slot_number for s in client_adapters)
    if len(slot_num) > 0:
        load_source = slot_num.pop()
    if len(slot_num) > 0:
        alt_load_source = slot_num.pop()
    if load_source is not None:
        if alt_load_source is None:
            alt_load_source = load_source
        lpar_w.io_config.tagged_io = pvm_bp.TaggedIO.bld(
                                        adapter, load_src=load_source,
                                        console='HMC',
                                        alt_load_src=alt_load_source)
    else:
        LOG.error('Not found Load source for ' +
                  'VM %s' % lpar_w.name)
    lpar_w.desig_ipl_src = pvm_lpar.IPLSrc.B
    lpar_w.keylock_pos = pvm_bp.KeylockPos.NORMAL
    return lpar_w
