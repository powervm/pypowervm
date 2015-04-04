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

import copy
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
def add_vscsi_mapping(adapter, vios_uuid, scsi_map, fuse_limit=32):
    """Will add a vSCSI mapping to a Virtual I/O Server.

    This method takes in a vSCSI mapping for a Virtual I/O Server and performs
    the mapping.

    The extra intelligence that this method provides is that it will fuse
    common vSCSI mappings together.  The fusing looks at the source and target
    and will determine if they can re-utilize an existing scsi mapping.

    This reduces the number of server/client adapters that are required to the
    virtual machine.  However, there is a limit to how much fusing should be
    done before a new vSCSI mapping bus is used.  That can be defined by
    specifying the 'fuse_limit'.

    The fuse_limit should be set low if the scsi bus is going to be quite busy.
    If the traffic over the scsi bus is going to be low, a significantly
    higher limit can be used.  If you are unsure what the traffic will be, use
    the default.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      added to.
    :param scsi_map: The mapping to add.  As noted above, this may be fused
                     with another scsi mapping on the virtual I/O server.
    :param fuse_limit: (Optional) The max number of devices to allow on one
                       scsi bus before creating a second SCSI bus.
    """
    vios_resp = adapter.read(pvm_vios.VIOS.schema_type, root_id=vios_uuid,
                             xag=[pvm_vios.XAGEnum.VIOS_SCSI_MAPPING])
    vios_w = pvm_vios.VIOS.wrap(vios_resp)

    # Separate out the mappings into the applicable ones for this client.
    separated_mappings = _separate_mappings(vios_w, scsi_map.client_lpar_href)

    # What we need to figure out is, within the existing mappings, can we
    # reuse the existing client and server adapter (which we can only do if
    # below the fuse limit), or if we need to create a new adapter pair.
    for mapping_list in separated_mappings.values():
        if len(mapping_list) < fuse_limit:
            # Swap in the first maps client/server adapters into the existing
            # map.  We call the semi-private methods as this is not something
            # that an 'update' would do...this is part of the 'create' flow.
            c_map = mapping_list[0]
            scsi_map._client_adapter(copy.deepcopy(c_map.client_adapter))
            scsi_map._server_adapter(copy.deepcopy(c_map.server_adapter))
            break

    # Add the mapping.  It may have been updated to have a different client
    # and server adapter.  It may be the original (which creates a new client
    # and server pair).
    vios_w.scsi_mappings.append(scsi_map)
    vios_w.update(adapter, xag=[pvm_vios.XAGEnum.VIOS_SCSI_MAPPING])


def _separate_mappings(vios_w, client_href):
    """Separates out the systems existing mappings into silos.

    :param vios_w: The pypowervm wrapper for the VIOS.
    :param client_href: The client to separate the mappings for.
    :return: A dictionary where the key is the server adapter (which is
             bound to the client.  The value is the list mappings that use
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
def _remove_storage_elem(adapter, vios_uuid, client_lpar_id, search_func):
    """Removes the storage element from a SCSI bus and clears out bus.

    Will remove the SCSI element from the VIOSes vSCSI Mappings.  If it is
    the last storage element on the vSCSI mapping, will also remove the entire
    mapping.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      added to.
    :param client_lpar_id: The LPAR identifier of the client VM.
    :param search_func: The search function to use to query for the mapping.
                        One parameter for input.  Will be a storage element
                        (but the type could be anything - VDisk, VOpt, etc...)
                        If that element matches to your seed, then return True.
                        Otherwise return False.
    :return: The list of the storage elements that were removed from the maps.
    """
    vios_resp = adapter.read(pvm_vios.VIOS.schema_type, root_id=vios_uuid,
                             xag=[pvm_vios.XAGEnum.VIOS_SCSI_MAPPING])
    vios_w = pvm_vios.VIOS.wrap(vios_resp)

    # The maps that match that need to be removed
    matching_maps = []
    client_lpar_id = str(client_lpar_id)

    # Loop through the existing SCSI Mappings.  Try to find the matching map.
    existing_scsi_mappings = vios_w.scsi_mappings
    for existing_scsi_map in existing_scsi_mappings:
        # No client, continue on.
        if existing_scsi_map.client_adapter is None:
            continue

        # If to a different VM, continue on.
        if str(existing_scsi_map.client_adapter.lpar_id) != client_lpar_id:
            continue

        if search_func(existing_scsi_map.backing_storage):
            # Found a match!
            matching_maps.append(existing_scsi_map)

    if len(matching_maps) == 0:
        return []

    # For each matching element, we need to determine if it is the last in
    # the map (and if so, we remove the map).  If not, we just remove that
    # element from the map.
    resp_list = []

    for matching_map in matching_maps:
        existing_scsi_mappings.remove(matching_map)
        resp_list.append(matching_map.backing_storage)

    # Update the VIOS
    vios_w.update(adapter, xag=[pvm_vios.XAGEnum.VIOS_SCSI_MAPPING])

    # return the list of removed elements
    return resp_list


def _remove_search_func(wcls, name_prop='name', names=None, prefixes=None):
    """Generate a search function for _remove_storage_elem's search_func param.

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
    :return: A callable search function suitable for passing to the search_func
             parameter of the _remove_storage_elem method.
    """
    def search_func(existing_elem):
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
    return search_func


def remove_vopt_mapping(adapter, vios_uuid, client_lpar_id, media_name=None):
    """Will remove the mapping for VOpt media.

    This method will remove the mapping between the virtual optical media
    and the client partition.  It does not delete the virtual optical media.
    Will leave other elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      removed from.
    :param client_lpar_id: The LPAR identifier of the client VM.
    :param media_name: (Optional) The name of the virtual optical media to
                       remove from the SCSI bus.  If None, will remove all
                       virtual optical media from this client lpar.
    :return: A list of the backing VOpt media that was removed.
    """
    names = [media_name] if media_name else None
    return _remove_storage_elem(adapter, vios_uuid, client_lpar_id,
                                _remove_search_func(pvm_stor.VOptMedia,
                                                    name_prop='media_name',
                                                    names=names))


def remove_vdisk_mapping(adapter, vios_uuid, client_lpar_id, disk_names=None,
                         disk_prefixes=None):
    """Will remove the mapping for VDisk media.

    This method will remove the mapping between the virtual disk and the
    client partition.  It does not delete the virtual disk.  Will leave other
    elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      removed from.
    :param client_lpar_id: The LPAR identifier of the client VM.
    :param disk_names: (Optional) A list of names of the virtual disk to remove
                       from the SCSI bus.  If None, all virtual disks will be
                       removed from the LPAR.
    :param disk_prefixes: (Optional) A list of prefixes that can be specified
                          to serve as identifiers for potential disks.  Ignored
                          if the disk_name is specified.
    :return: A list of the backing VDisk objects that were removed.
    """

    return _remove_storage_elem(
        adapter, vios_uuid, client_lpar_id, _remove_search_func(
            pvm_stor.VDisk, names=disk_names, prefixes=disk_prefixes))


def remove_lu_mapping(adapter, vios_uuid, client_lpar_id, disk_names=None,
                      disk_prefixes=None):
    """Remove mappings for one or more SSP LUs associated with an LPAR.

    This method will remove the mapping between the Logical Unit and the
    client partition.  It does not delete the LU.  Will leave other elements on
    the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      removed from.
    :param client_lpar_id: The LPAR identifier of the client VM.
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
        adapter, vios_uuid, client_lpar_id, _remove_search_func(
            pvm_stor.LU, names=disk_names, prefixes=disk_prefixes))


def remove_pv_mapping(adapter, vios_uuid, client_lpar_id, backing_dev):
    """Will remove the PV mapping.

    This method will remove the pv mapping. It does not delete the device.
    Will leave other elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      removed from.
    :param client_lpar_id: The LPAR identifier of the client VM.
    :param backing_dev: The physical volume name to be removed.
    :return: A list of the backing physical device objects that were removed.
    """

    return _remove_storage_elem(adapter, vios_uuid, client_lpar_id,
                                _remove_search_func(pvm_stor.PV,
                                                    names=[backing_dev]))
