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


from pypowervm.wrappers import storage as pvm_stor_w


def udid_to_scsi_mapping(vios_w, udid, ignore_empty_client=True):
    """Finds the SCSI mapping (if any) for a given volume udid.

    This is a helper method that will parse through a given VIOS wrapper
    (that has the Storage and SCSI mapping XAGs) and will find the client
    SCSI mapping for a given volume udid.

    :param vios_w: The Virtual I/O Server wrapper.  Should have the Storage
                   and SCSI mapping XAG associated with it.
    :param udid: The volume's udid.
    :param ignore_empty_client: (Optional, Default: True) If set to true, any
                                SCSI mappings that have a client adapter of
                                None will be ignored.
    :return: The SCSI mapping (or None)
    """
    for scsi_map in vios_w.scsi_mappings:
        # If there is not a client adapter, it isn't attached fully.
        if not scsi_map.client_adapter:
            continue

        # No backing storage, then ignore.
        if not scsi_map.backing_storage:
            continue

        if not isinstance(scsi_map.backing_storage, pvm_stor_w.PV):
            continue

        if scsi_map.backing_storage.udid == udid:
            return scsi_map

    return None


def c_wwpn_to_vfc_mapping(vios_w, c_wwpn):
    """Finds the vFC mapping (if any) for a given client WWPN.

    This is a helper method that will parse through a given VIOS wrapper
    (that has the VFC Mapping XAG) and will find the client vFC mapping for
    that WWPN.

    :param vios_w: The Virtual I/O Server wrapper.  Should have the VFC
                   mapping XAG associated with it.
    :param c_wwpn: One of the clients WWPNs.
    :return: The vFC mapping (or None)
    """
    for vfc_map in vios_w.vfc_mappings:
        # If there is not a client adapter, it isn't properly attached.
        if not vfc_map.client_adapter:
            continue

        if c_wwpn in vfc_map.client_adapter.wwpns:
            return vfc_map

    return None
