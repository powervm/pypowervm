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

from pypowervm import exceptions as exc
from pypowervm.i18n import _
from pypowervm.wrappers import client_network_adapter as cna
from pypowervm.wrappers import constants as c
from pypowervm.wrappers import network


def crt_cna(adapter, host_uuid, lpar_uuid, pvid,
            vswitch=network.VSW_DEFAULT_VSWITCH, slot_num=None, mac_addr=None,
            addl_vlans=None):
    """Puts a new ClientNetworkAdapter on a given LPAR.

    This will update the LPAR and put a new CNA on it.  If the LPAR is active
    can only perform if there is an active RMC connection.  If the LPAR is
    powered off, then it will update it offline.

    :param adapter: The pypowervm adapter to perform the update through.
    :param host_uuid: The host UUID that the CNA will be put on.
    :param lpar_uuid: The lpar UUID to update.
    :param pvid: The primary VLAN ID.
    :param vswitch: The name of the virtual switch that this CNA will be
                    attached to.
    :param slot_num: Optional slot number to use for the CNA.  If not
                     specified, will utilize the next available slot on the
                     LPAR.
    :param mac_addr: The optional mac address.  If not specified, one will be
                     auto generated.
    :param addl_vlans: Optional list of (up to 18) additional VLANs.  Can be
                       a list of Ints or Strings (that parse down to ints).
    """
    # Join the additional VLANs
    addl_tagged_vlans = None
    if addl_vlans is not None:
        addl_tagged_vlans = " ".join(addl_vlans)

    # Find the appropriate virtual switch.
    vswitch_href = None
    vswitch_resp = adapter.read(c.MGT_SYS, root_id=host_uuid,
                                child_type=network.VSW_ROOT)
    for vs_entry in vswitch_resp.feed.entries:
        vs_w = network.VirtualSwitch(vs_entry)
        if vs_w.get_name() == vswitch:
            vswitch_href = vs_w.get_href()

    if vswitch_href is None:
        raise exc.Error(_('Unable to find the Virtual Switch %s on the '
                          'system.')
                        % vswitch)

    net_adpt = cna.crt_cna(pvid, vswitch_href, slot_num, mac_addr,
                           addl_tagged_vlans)
    resp = adapter.create(net_adpt, c.MGT_SYS, root_id=host_uuid,
                          child_type=cna.VADPT_ROOT)
    return resp.entry
