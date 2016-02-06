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
from pypowervm.wrappers import logical_partition as lpar
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import network as pvm_net
from pypowervm.wrappers import virtual_io_server as pvm_vios


def crt_cna(adapter, host_uuid, lpar_uuid, pvid,
            vswitch=pvm_net.VSW_DEFAULT_VSWITCH, crt_vswitch=False,
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
    vswitch_w = _find_or_create_vswitch(adapter, host_uuid, vswitch,
                                        crt_vswitch)

    # Find the virtual network.  Ensures that the system is ready for this.
    if adapter.traits.vnet_aware:
        _find_or_create_vnet(adapter, host_uuid, pvid, vswitch_w)

    # Build and create the CNA
    net_adpt = pvm_net.CNA.bld(
        adapter, pvid, vswitch_w.related_href, slot_num=slot_num,
        mac_addr=mac_addr, addl_tagged_vlans=addl_tagged_vlans)
    return net_adpt.create(parent_type=lpar.LPAR, parent_uuid=lpar_uuid)


def _find_or_create_vnet(adapter, host_uuid, vlan, vswitch):
    # Read the existing virtual networks.  Try to locate...
    vnet_feed_resp = adapter.read(pvm_ms.System.schema_type, host_uuid,
                                  pvm_net.VNet.schema_type)
    vnets = pvm_net.VNet.wrap(vnet_feed_resp)
    for vnet in vnets:
        if vlan == str(vnet.vlan) and vnet.vswitch_id == vswitch.switch_id:
            return vnet

    # Must not have found it.  Lets try to create it.
    name = '%(vswitch)s-%(vlan)s' % {'vswitch': vswitch.name,
                                     'vlan': str(vlan)}
    # VLAN 1 is not allowed to be tagged.  All others are.  VLAN 1 would be
    # used for 'Flat' networks most likely.
    tagged = (vlan != '1')
    vnet = pvm_net.VNet.bld(adapter, name, vlan, vswitch.related_href, tagged)
    return vnet.create(parent_type=pvm_ms.System, parent_uuid=host_uuid)


def _find_or_create_vswitch(adapter, host_uuid, vs_name, crt_vswitch):
    """Finds (or creates) the appropriate virtual switch.

    :param adapter: The pypowervm adapter to perform the update through.
    :param host_uuid: The host UUID that the CNA will be put on.
    :param vs_name: The name of the virtual switch that this CNA will be
                    attached to.
    :param crt_vswitch: A boolean to indicate that if the vSwitch can not be
                        found, the system should attempt to create one (with
                        the default parameters - ex: Veb mode).
    """
    # TODO(IBM): Change this over to .search()
    vswitch_w = None
    vswitch_wraps = pvm_net.VSwitch.get(adapter, parent_type=pvm_ms.System,
                                        parent_uuid=host_uuid)
    for vs_w in vswitch_wraps:
        if vs_w.name == vs_name:
            vswitch_w = vs_w
            break

    if vswitch_w is None:
        if crt_vswitch:
            vswitch_w = pvm_net.VSwitch.bld(adapter, vs_name)
            vswitch_w = vswitch_w.create(parent_type=pvm_ms.System,
                                         parent_uuid=host_uuid)
        else:
            raise exc.Error(_('Unable to find the Virtual Switch %s on the '
                              'system.') % vs_name)
    return vswitch_w


def _find_free_vlan(adapter, host_uuid, vswitch_w):
    """Finds a free VLAN on the vswitch specified."""

    # A Virtual Network (VNet) will exist for every PowerVM vSwitch / VLAN
    # combination in the system.  Getting the feed is a quick way to determine
    # which VLANs are in use.
    vnet_resp_feed = adapter.read(pvm_ms.System.schema_type,
                                  root_id=host_uuid,
                                  child_type=pvm_net.VNet.schema_type)
    vnets = pvm_net.VNet.wrap(vnet_resp_feed)

    # Use that feed to get the VLANs in use, but only get the ones in use for
    # the vSwitch passed in.
    used_vids = [x.vlan for x in vnets
                 if x.associated_switch_uri == vswitch_w.related_href]

    # Walk through the VLAN range, and as soon as one is found that is not in
    # use, return it to the user.
    for x in range(1, 4094):
        if x not in used_vids:
            return x

    raise exc.Error(_('Unable to find a valid VLAN for Virtual Switch %s.') %
                    vswitch_w.name)


def crt_p2p_cna(adapter, host_uuid, lpar_uuid, src_io_host_uuids, vs_name,
                crt_vswitch=True, mac_addr=None):
    """Creates a 'point-to-point' Client Network Adapter.

    A point to point connection is one that has a VLAN that is shared only
    between the lpar and the appropriate trunk adapter(s).  The system will
    determine what a free VLAN is on the virtual switch and use that for the
    point to point connection.

    The method will return the Client Network Adapter and the corresponding
    Trunk Adapter that it has created.  There may be multiple Trunk Adapters
    created if multiple src_io_host_uuids are passed in.  The Trunk Adapters
    can be created against the Virtual I/O Servers or the NovaLink partition.

    Nothing prevents the system from allowing another Client Network Adapter
    from being created and attaching to the connection.  The point-to-point
    connection is only guaranteed at the point in time at which it was created.

    NOTE: See the note in src_io_host_uuids.  Currently this API will only
    support the NovaLink partition.  Others will be added.  This parameter is
    there for future facing compatibility.

    :param adapter: The pypowervm adapter to perform the update through.
    :param host_uuid: The host UUID that the CNA will be put on.
    :param lpar_uuid: The lpar UUID to update.
    :param src_io_host_uuids: The list of UUIDs of the LPARs that will host the
                              Trunk Adapters.  At least one UUID is required.
                              Multiple will be supported, and the Trunk
                              Priority will increment per adapter (in the order
                              that the I/O hosts are specified).
    :param pvid: The primary VLAN ID.
    :param vs_name: The name of the PowerVM Hypervisor Virtual Switch to create
                    the p2p connection on.  This is required because it is not
                    recommended to create it on the default (ETHERNET0) virtual
                    switch.
    :param crt_vswitch: (Optional, Default: True) A boolean to indicate that
                        if the vSwitch can not be found, the system should
                        attempt to create one (with the default parameters -
                        ex: Veb mode).
    :param mac_addr: (Optional, Default: None) The mac address.  If not
                     specified, one will be auto generated.
    :return: The CNA Wrapper that was created.
    :return: The TrunkAdapters that were created.  Match the order that the
             src_io_host_uuids were passed in.
    """
    # Make sure we have the appropriate vSwitch
    vswitch_w = _find_or_create_vswitch(adapter, host_uuid, vs_name,
                                        crt_vswitch)

    # Find the free VLAN
    vlan = _find_free_vlan(adapter, host_uuid, vswitch_w)

    # Build and create the CNA
    client_adpt = pvm_net.CNA.bld(
        adapter, vlan, vswitch_w.related_href, mac_addr=mac_addr)
    client_adpt = client_adpt.create(parent_type=lpar.LPAR,
                                     parent_uuid=lpar_uuid)

    # Need to get the VIOS uuids to determine if the src_io_host_uuid is a VIOS
    vios_wraps = pvm_vios.VIOS.get(adapter)
    vios_uuids = [x.uuid for x in vios_wraps]

    # Now create the corresponding Trunk
    trunk_adpts = []
    trunk_pri = 1
    for src_io_host_uuid in src_io_host_uuids:
        lpar_type = (pvm_vios.VIOS if src_io_host_uuid in vios_uuids
                     else lpar.LPAR)
        trunk_adpt = pvm_net.CNA.bld(
            adapter, vlan, vswitch_w.related_href, trunk_pri=trunk_pri)
        trunk_adpts.append(trunk_adpt.create(parent_type=lpar_type,
                                             parent_uuid=src_io_host_uuid))
        trunk_pri += 1
    return client_adpt, trunk_adpts
