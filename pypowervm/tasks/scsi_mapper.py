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

from pypowervm.wrappers import storage as pvm_stor
from pypowervm.wrappers import virtual_io_server as pvm_vios


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

    # Loop through the existing SCSI Mappings.  Seeing if we have one that
    # we can utilize.
    existing_scsi_mappings = vios_w.scsi_mappings
    for existing_scsi_map in existing_scsi_mappings:
        if _can_be_fused(existing_scsi_map, scsi_map, fuse_limit):
            new_elems = scsi_map.backing_storage_elems
            existing_scsi_map.backing_storage_elems.extend(new_elems)
            vios_w.update(adapter, xag=[pvm_vios.XAGEnum.VIOS_SCSI_MAPPING])
            return

    # If we got here, the SCSI mapping could not fuse with any existing.
    # Should just add it as a new mapping.
    existing_scsi_mappings.append(scsi_map)
    vios_w.update(adapter, xag=[pvm_vios.XAGEnum.VIOS_SCSI_MAPPING])


def _can_be_fused(existing_scsi_map, new_scsi_map, fuse_limit):
    """Determines if the existing map can absorb the content of the new map."""
    # If there is no client adapter, then it can't match.
    exist_c_adpt = existing_scsi_map.client_adapter
    if exist_c_adpt is None:
        return False

    # Are they not going to the same client LPAR ID?
    new_c_adpt = new_scsi_map.client_adapter
    if exist_c_adpt.lpar_id != new_c_adpt.lpar_id:
        return False

    # Did we reach a fusion limit?
    existing_count = len(existing_scsi_map.backing_storage_elems)
    new_count = len(new_scsi_map.backing_storage_elems)
    if (existing_count + new_count) > fuse_limit:
        return False

    return True


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

    matching_map = None
    scsi_elem = None

    # The first element is the SCSI map, the second is the scsi element within
    # the map to remove.
    matching_pairs = []

    # Loop through the existing SCSI Mappings.  Try to find the matching map.
    existing_scsi_mappings = vios_w.scsi_mappings
    for existing_scsi_map in existing_scsi_mappings:
        # No client, continue on.
        if existing_scsi_map.client_adapter is None:
            continue

        # If to a different VM, continue on.
        if existing_scsi_map.client_adapter.lpar_id != client_lpar_id:
            continue

        # Loop through and query the search function to see if we have the
        # correct one.
        for stor_elem in existing_scsi_map.backing_storage_elems:
            if search_func(stor_elem):
                # Found a match!
                matching_pairs.append((existing_scsi_map, stor_elem))

    if len(matching_pairs) == 0:
        return []

    # For each matching element, we need to determine if it is the last in
    # the map (and if so, we remove the map).  If not, we just remove that
    # element from the map.
    resp_list = []
    for matching_map, scsi_elem in matching_pairs:
        if len(matching_map.backing_storage_elems) == 1:
            existing_scsi_mappings.remove(matching_map)
        else:
            matching_map.backing_storage_elems.remove(scsi_elem)
        resp_list.append(scsi_elem)

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

    return _remove_storage_elem(adapter, vios_uuid, client_lpar_id,
                                _remove_search_func(pvm_stor.VOptMedia,
                                                    name_prop='media_name',
                                                    names=[media_name]))


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


def remove_vscsi_mapping(adapter, vios_uuid, client_lpar_id, backing_dev):
    """Will remove the vscsi mapping.

    This method will remove the vscsi mapping between the virtual disk and the
    client partition.  It does not delete the device.  Will leave other
    elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param host_uui: The pypowervm UUID of the host.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      removed from.
    :param backing_dev: The physical port name or volume name to be removed.
    :return: A list of the backing vscsi objects that were removed.
    """

    return _remove_storage_elem(adapter, vios_uuid, client_lpar_id,
                                _remove_search_func(pvm_stor.PV,
                                                    name_prop='name',
                                                    names=[backing_dev]))