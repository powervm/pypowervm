# Copyright 2016 IBM Corp.
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


from pypowervm import util


def udid_to_scsi_mapping(vios_w, udid, lpar_w, stg_class=None,
                         ignore_orphan=True):
    """Finds the SCSI mapping (if any) for a given backing storage udid.

    This is a helper method that will parse through a given VIOS wrapper
    (retrieved with pypowervm.const.XAG.VIO_SMAP) and will find the client
    SCSI mapping for a given backing storage element (LU, PV, LV, VOpt).

    :param vios_w: The Virtual I/O Server wrapper.  Should have the Storage
                   and SCSI mapping XAG associated with it.
    :param udid: The volume's udid.
    :param lpar_w: LPAR EntryWrapper representing the client LPAR whose mapping
                   is to be found.
    :param stg_class: (Optional, Default: None) A storage EntryWrapper class -
                      VOptMedia, VDisk, LU, LUEnt, or PV - indicating the type
                      of the mapping's backing storage.  If None (the default),
                      any backing storage type is matched.
    :param ignore_orphan: (Optional, Default: True) If set to True, any orphan
                          SCSI mappings (those with no client adapter) will be
                          ignored.
    :return: The first matching SCSI mapping (or None).
    """
    for scsi_map in vios_w.scsi_mappings:
        # No backing storage, then ignore.
        if not scsi_map.backing_storage:
            continue

        # If there is not a client adapter, it isn't attached fully.
        if not scsi_map.client_adapter and ignore_orphan:
            continue

        if (stg_class is not None and scsi_map.backing_storage.schema_type !=
                stg_class.schema_type):
            continue

        if scsi_map.backing_storage.udid == udid:
            return scsi_map

    return None


def c_wwpn_to_vfc_mapping(vios_w, c_wwpn):
    """Finds the vFC mapping (if any) for a given client WWPN.

    This is a helper method that will parse through a given VIOS wrapper
    (retrieved with pypowervm.const.XAG.VIO_FMAP) and will find the client vFC
    mapping for that WWPN.

    :param vios_w: The Virtual I/O Server wrapper.  Should have
                   pypowervm.const.XAG.VIO_FMAP associated with it.
    :param c_wwpn: One of the client's WWPNs.
    :return: The vFC mapping (or None)
    """
    wwpn = util.sanitize_wwpn_for_api(c_wwpn)
    for vfc_map in vios_w.vfc_mappings:
        # If there is not a client adapter, it isn't properly attached.
        if not vfc_map.client_adapter:
            continue

        if wwpn in vfc_map.client_adapter.wwpns:
            return vfc_map

    return None
