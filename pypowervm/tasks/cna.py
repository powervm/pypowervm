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

"""Tasks around ClientNetworkAdapter."""

import pypowervm.exceptions as exc
from pypowervm.i18n import _
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as ms
from pypowervm.wrappers import network


def crt_cna(adapter, host_uuid, lpar_uuid, pvid,
            vswitch=network.VSW_DEFAULT_VSWITCH, crt_vswitch=False,
            slot_num=None, mac_addr=None, addl_vlans=None):
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
    :param crt_vswitch: A boolean to indicate that if the vSwitch can not be
                        found, the system should attempt to create one (with
                        the default parameters - ex: Veb mode).
    :param slot_num: Optional slot number to use for the CNA.  If not
                     specified, will utilize the next available slot on the
                     LPAR.
    :param mac_addr: The optional mac address.  If not specified, one will be
                     auto generated.
    :param addl_vlans: Optional list of (up to 18) additional VLANs.  Can be
                       a list of Ints or Strings (that parse down to ints).
    :return: The CNA Wrapper that was created.
    """
    # Join the additional VLANs
    addl_tagged_vlans = None
    if addl_vlans is not None:
        addl_tagged_vlans = " ".join(addl_vlans)

    # Sanitize the pvid
    pvid = str(pvid)

    # Find the appropriate virtual switch.
    vswitch_w = None
    vswitch_resp = adapter.read(ms.System.schema_type, root_id=host_uuid,
                                child_type=network.VSwitch.schema_type)
    vswitch_wraps = network.VSwitch.wrap(vswitch_resp)
    for vs_w in vswitch_wraps:
        if vs_w.name == vswitch:
            vswitch_w = vs_w
            break

    if vswitch_w is None:
        if crt_vswitch:
            vswitch_w = network.VSwitch.bld(adapter, vswitch)
            vswitch_w = vswitch_w.create(parent_type=ms.System,
                                         parent_uuid=host_uuid)
        else:
            raise exc.Error(_('Unable to find the Virtual Switch %s on the '
                              'system.') % vswitch)

    # Find the virtual network.  Ensures that the system is ready for this.
    if adapter.traits.vnet_aware:
        _find_or_create_vnet(adapter, host_uuid, pvid, vswitch_w)

    # Build and create the CNA
    net_adpt = network.CNA.bld(
        adapter, pvid, vswitch_w.related_href, slot_num=slot_num,
        mac_addr=mac_addr, addl_tagged_vlans=addl_tagged_vlans)
    return net_adpt.create(parent_type=lpar.LPAR, parent_uuid=lpar_uuid)


def _find_or_create_vnet(adapter, host_uuid, vlan, vswitch):
    # Read the existing virtual networks.  Try to locate...
    vnet_feed_resp = adapter.read(ms.System.schema_type, host_uuid,
                                  network.VNet.schema_type)
    vnets = network.VNet.wrap(vnet_feed_resp)
    for vnet in vnets:
        if vlan == str(vnet.vlan) and vnet.vswitch_id == vswitch.switch_id:
            return vnet

    # Must not have found it.  Lets try to create it.
    name = '%(vswitch)s-%(vlan)s' % {'vswitch': vswitch.name,
                                     'vlan': str(vlan)}
    # VLAN 1 is not allowed to be tagged.  All others are.  VLAN 1 would be
    # used for 'Flat' networks most likely.
    tagged = (vlan != '1')
    vnet = network.VNet.bld(adapter, name, vlan, vswitch.related_href, tagged)
    return vnet.create(parent_type=ms.System, parent_uuid=host_uuid)
