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
    vios_resp = adapter.read(pvm_vios.VIOS.schema_type, root_id=vios_uuid)
    vios_w = pvm_vios.VIOS.wrap(vios_resp)

    # Loop through the existing SCSI Mappings.  Seeing if we have one that
    # we can utilize.
    existing_scsi_mappings = vios_w.scsi_mappings
    for existing_scsi_map in existing_scsi_mappings:
        if _can_be_fused(existing_scsi_map, scsi_map, fuse_limit):
            new_elems = scsi_map.backing_storage_elems
            existing_scsi_map.backing_storage_elems.extend(new_elems)
            vios_w.update(adapter)
            return

    # If we got here, the SCSI mapping could not fuse with any existing.
    # Should just add it as a new mapping.
    existing_scsi_mappings.append(scsi_map)
    vios_w.update(adapter)


def _can_be_fused(existing_scsi_map, new_scsi_map, fuse_limit):
    """Determines if the existing map can absorb the content of the new map."""

    # Are they not going to the same client LPAR ID?
    exist_c_adpt = existing_scsi_map.client_adapter
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
    """
    vios_resp = adapter.read(pvm_vios.VIOS.schema_type, root_id=vios_uuid)
    vios_w = pvm_vios.VIOS.wrap(vios_resp)

    matching_map = None
    scsi_elem = None

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
                matching_map = existing_scsi_map
                scsi_elem = stor_elem
                break

    if matching_map is None:
        return

    # If last storage, remove the mapping altogether.  Else, just remove the
    # element.
    if len(matching_map.backing_storage_elems) == 1:
        existing_scsi_mappings.remove(matching_map)
    else:
        matching_map.backing_storage_elems.remove(scsi_elem)
    vios_w.update(adapter)


def remove_vopt_mapping(adapter, vios_uuid, media_name, client_lpar_id):
    """Will remove the mapping for VOpt media.

    This method will remove the mapping between the virtual optical media
    and the client partition.  It does not delete the virtual optical media.
    Will leave other elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      added to.
    :param media_name: The name of the virtual optical media to remove from
                       the SCSI bus.
    :param client_lpar_id: The LPAR identifier of the client VM.
    """

    # The search function for virtual optical
    def search_func(existing_elem):
        if not isinstance(existing_elem, pvm_stor.VOptMedia):
            return False
        return existing_elem.media_name == media_name

    return _remove_storage_elem(adapter, vios_uuid, client_lpar_id,
                                search_func)


def remove_vdisk_mapping(adapter, vios_uuid, disk_name, client_lpar_id):
    """Will remove the mapping for VDisk media.

    This method will remove the mapping between the virtual disk and the
    client partition.  It does not delete the virtual disk.  Will leave other
    elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios_uuid: The virtual I/O server UUID that the mapping should be
                      added to.
    :param disk_name: The name of the virtual disk to remove from the SCSI bus.
    :param client_lpar_id: The LPAR identifier of the client VM.
    """

    # The search function for virtual optical
    def search_func(existing_elem):
        if not isinstance(existing_elem, pvm_stor.VDisk):
            return False
        return existing_elem.name == disk_name

    return _remove_storage_elem(adapter, vios_uuid, client_lpar_id,
                                search_func)
