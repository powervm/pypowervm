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

"""Manage mappings of virtual storage devices from VIOS to LPAR."""

import logging

from oslo_concurrency import lockutils as lock

import time

from pypowervm.i18n import _
from pypowervm.utils import retry as pvm_retry
from pypowervm.wrappers import storage as pvm_stor
from pypowervm.wrappers import virtual_io_server as pvm_vios

LOG = logging.getLogger(__name__)


def _delay(attempt, max_attempts, *args, **kwds):
    LOG.warn(_('Retrying modification of SCSI Mapping.'))
    time.sleep(1)


@lock.synchronized('vscsi_mapping')
@pvm_retry.retry(delay_func=_delay)
def add_vscsi_mapping(host_uuid, vios, lpar_uuid, storage_elem,
                      fuse_limit=32):
    """Will add a vSCSI mapping to a Virtual I/O Server.

    This method is used to connect a storage element (either a vDisk, vOpt,
    PV or LU) that resides on a Virtual I/O Server to a Virtual Machine.

    This is achieved using a 'vSCSI Mapping'.  The invoker does not need to
    interact with the mapping.

    A given mapping is essentially a 'vSCSI bus', which can host multiple
    storage elements.  This method has a fuse limit which throttles the number
    of devices on a given vSCSI bus.  The throttle should be lower if the
    storage elements are high I/O, and higher otherwise.

    :param host_uuid: The UUID of the host system.
    :param vios: The virtual I/O server to which the mapping should be
                 added.  This may be the VIOS's UUID string OR an existing VIOS
                 EntryWrapper.  If the latter, it must have been retrieved
                 using the SCSI_MAPPING extended attribute group.
    :param lpar_uuid: The UUID of the LPAR that will have the connected
                      storage.
    :param storage_elem: The storage element (either a vDisk, vOpt, LU or PV)
                         that is to be connected.
    :param fuse_limit: (Optional) The max number of devices to allow on one
                       scsi bus before creating a second SCSI bus.
    """
    adapter = storage_elem.adapter
    # If the 'vios' param is a string UUID, retrieve the VIOS wrapper.
    if not isinstance(vios, pvm_vios.VIOS):
        vios = pvm_vios.VIOS.wrap(
            adapter.read(pvm_vios.VIOS.schema_type, root_id=vios,
                         xag=[pvm_vios.VIOS.xags.SCSI_MAPPING]))

    # Get the client lpar href
    lpar_href = pvm_vios.VSCSIMapping.crt_related_href(adapter, host_uuid,
                                                       lpar_uuid)

    # Separate out the mappings into the applicable ones for this client.
    separated_mappings = _separate_mappings(vios, lpar_href)

    # Used if we need to clone an existing mapping
    clonable_map = None

    # What we need to figure out is, within the existing mappings, can we
    # reuse the existing client and server adapter (which we can only do if
    # below the fuse limit), or if we need to create a new adapter pair.
    for mapping_list in separated_mappings.values():
        if len(mapping_list) < fuse_limit:
            # Swap in the first maps client/server adapters into the existing
            # map.  We call the semi-private methods as this is not something
            # that an 'update' would do...this is part of the 'create' flow.
            clonable_map = mapping_list[0]
            break

    # If we have a clonable map, we can replicate that.  Otherwise we need
    # to build from scratch.
    if clonable_map is not None:
        scsi_map = pvm_vios.VSCSIMapping.bld_from_existing(clonable_map,
                                                           storage_elem)
    else:
        scsi_map = pvm_vios.VSCSIMapping.bld(adapter, host_uuid, lpar_uuid,
                                             storage_elem)

    # Add the mapping.  It may have been updated to have a different client
    # and server adapter.  It may be the original (which creates a new client
    # and server pair).
    vios.scsi_mappings.append(scsi_map)
    vios.update(xag=[pvm_vios.VIOS.xags.SCSI_MAPPING])


def _separate_mappings(vios_w, client_href):
    """Separates out the systems existing mappings into silos.

    :param vios_w: The pypowervm wrapper for the VIOS.
    :param client_href: The client to separate the mappings for.
    :return: A dictionary where the key is the server adapter (which is
             bound to the client).  The value is the list mappings that use
             the server adapter.
    """
    # The key is server_adapter.udid, the value is the list of applicable
    # mappings to the server adapter.
    resp = {}

    existing_mappings = vios_w.scsi_mappings
    for existing_map in existing_mappings:
        if existing_map.client_lpar_href == client_href:
            # Valid map to consider
            key = existing_map.server_adapter.udid
            if resp.get(key) is None:
                resp[key] = []
            resp[key].append(existing_map)

    return resp


@lock.synchronized('vscsi_mapping')
@pvm_retry.retry(delay_func=_delay)
def _remove_storage_elem(adapter, vios, client_lpar_id, match_func):
    """Removes the storage element from a SCSI bus and clears out bus.

    Will remove the vSCSI Mappings from the VIOS if the match_func indicates
    that the mapping is a match.  The match_func is only invoked if the
    client_lpar_id matches.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the SCSI_MAPPING extended attribute group.
    :param client_lpar_id: The integer short ID (not UUID) of the client VM.
    :param match_func: Matching function suitable for passing to find_maps.
                       See that method's match_func parameter.
    :return: The list of the storage elements that were removed from the maps.
    """
    # If the 'vios' param is a string UUID, retrieve the VIOS wrapper.
    if not isinstance(vios, pvm_vios.VIOS):
        vios = pvm_vios.VIOS.wrap(
            adapter.read(pvm_vios.VIOS.schema_type, root_id=vios,
                         xag=[pvm_vios.VIOS.xags.SCSI_MAPPING]))

    # Find the maps that need to be removed
    existing_scsi_mappings = vios.scsi_mappings
    matching_maps = find_maps(
        existing_scsi_mappings, client_lpar_id, match_func)
    if len(matching_maps) == 0:
        return []

    # Remove each invalid map.
    resp_list = []
    for matching_map in matching_maps:
        existing_scsi_mappings.remove(matching_map)
        resp_list.append(matching_map.backing_storage)

    # Update the VIOS
    vios.update(xag=[pvm_vios.VIOS.xags.SCSI_MAPPING])

    # return the list of removed elements
    return resp_list


def gen_match_func(wcls, name_prop='name', names=None, prefixes=None):
    """Generate a matching function for find_maps' match_func param.

    :param wcls: The Wrapper class of the object being matched.
    :param name_prop: The property of the Wrapper class on which to match.
    :param names: (Optional) A list of names to match.  If names and prefixes
                  are both None or empty, all inputs of the specified wcls will
                  be matched.
    :param prefixes: (Optional) A list of prefixes that can be specified
                     to serve as identifiers for potential matches.  Ignored
                     if names is specified.  If names and prefixes are both
                     None or empty, all inputs of the specified wcls will be
                     matched.
    :return: A callable matching function suitable for passing to the
             match_func parameter of the find_maps method.
    """
    def match_func(existing_elem):
        if not isinstance(existing_elem, wcls):
            return False
        if names:
            return getattr(existing_elem, name_prop) in names
        elif prefixes:
            for prefix in prefixes:
                if getattr(existing_elem, name_prop).startswith(prefix):
                    return True
        # Neither names nor prefixes specified - hit everything
        return True
    return match_func


def find_maps(mapping_list, client_lpar_id, match_func):
    """Filter a list of scsi mappings by LPAR ID and a matching function.

    :param mapping_list: The mappings to filter.  Iterable of VSCSIMapping.
    :param client_lpar_id: Integer short ID (not UUID) of the LPAR on the
                           client side of the mapping.
    :param match_func: Callable with the following specification:
        def match_func(storage_elem)
            param storage_elem: A backing storage element wrapper (VOpt, VDisk,
                                PV, or LU) to be analyzed.
            return: True if the storage_elem's mapping should be included;
                    False otherwise.
    :return: A list comprising the subset of the input mapping_list whose
             client LPAR IDs match client_lpar_id and whose backing storage
             elements satisfy match_func.
    """
    matching_maps = []
    for existing_scsi_map in mapping_list:
        # No client, continue on.
        if existing_scsi_map.client_adapter is None:
            continue

        # If to a different VM, continue on.  client_lpar_id was converted
        # to a str above.
        if existing_scsi_map.client_adapter.lpar_id != int(client_lpar_id):
            continue

        if match_func(existing_scsi_map.backing_storage):
            # Found a match!
            matching_maps.append(existing_scsi_map)
    return matching_maps


def remove_vopt_mapping(adapter, vios, client_lpar_id, media_name=None):
    """Will remove the mapping for VOpt media.

    This method will remove the mapping between the virtual optical media
    and the client partition.  It does not delete the virtual optical media.
    Will leave other elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the SCSI_MAPPING extended attribute group.
    :param client_lpar_id: The integer short ID (not UUID) of the client VM.
    :param media_name: (Optional) The name of the virtual optical media to
                       remove from the SCSI bus.  If None, will remove all
                       virtual optical media from this client lpar.
    :return: A list of the backing VOpt media that was removed.
    """
    names = [media_name] if media_name else None
    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.VOptMedia, name_prop='media_name', names=names))


def remove_vdisk_mapping(adapter, vios, client_lpar_id, disk_names=None,
                         disk_prefixes=None):
    """Will remove the mapping for VDisk media.

    This method will remove the mapping between the virtual disk and the
    client partition.  It does not delete the virtual disk.  Will leave other
    elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the SCSI_MAPPING extended attribute group.
    :param client_lpar_id: The integer short ID (not UUID) of the client VM.
    :param disk_names: (Optional) A list of names of the virtual disk to remove
                       from the SCSI bus.  If None, all virtual disks will be
                       removed from the LPAR.
    :param disk_prefixes: (Optional) A list of prefixes that can be specified
                          to serve as identifiers for potential disks.  Ignored
                          if the disk_name is specified.
    :return: A list of the backing VDisk objects that were removed.
    """

    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.VDisk, names=disk_names, prefixes=disk_prefixes))


def remove_lu_mapping(adapter, vios, client_lpar_id, disk_names=None,
                      disk_prefixes=None):
    """Remove mappings for one or more SSP LUs associated with an LPAR.

    This method will remove the mapping between the Logical Unit and the
    client partition.  It does not delete the LU.  Will leave other elements on
    the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the SCSI_MAPPING extended attribute group.
    :param client_lpar_id: The integer short ID (not UUID) of the client VM.
    :param disk_names: (Optional) A list of names of the LUs to remove from
                       the SCSI bus.  If None, all LUs asssociated with the
                       LPAR will be removed.
    :param disk_prefixes: (Optional) A list of prefixes that can be specified
                          to serve as identifiers for potential disks.  Ignored
                          if the disk_name is specified.
    :return: A list of LU EntryWrappers representing the mappings that were
             removed.
    """

    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.LU, names=disk_names, prefixes=disk_prefixes))


def remove_pv_mapping(adapter, vios, client_lpar_id, backing_dev):
    """Will remove the PV mapping.

    This method will remove the pv mapping. It does not delete the device.
    Will leave other elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the SCSI_MAPPING extended attribute group.
    :param client_lpar_id: The integer short ID (not UUID) of the client VM.
    :param backing_dev: The physical volume name to be removed.
    :return: A list of the backing physical device objects that were removed.
    """

    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.PV, names=[backing_dev]))
