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
from oslo_concurrency import lockutils

from pypowervm import exceptions as exc
from pypowervm.i18n import _
from pypowervm.tasks import partition
from pypowervm.wrappers import logical_partition as lpar
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import network as pvm_net

VLAN_LOCK = "reserve_vlan"


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
    vswitch_w = pvm_net.VSwitch.search(adapter, parent_type=pvm_ms.System,
                                       parent_uuid=host_uuid, one_result=True,
                                       name=vs_name)

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


@lockutils.synchronized(VLAN_LOCK)
def assign_free_vlan(adapter, host_uuid, vswitch_w, cna, ensure_enabled=False):
    """Assigns a free vlan to a given cna. Also ensure the CNA is enabled.

    :param adapter: The adapter to read the vnet information from
    :param host_uuid: The host UUID that the CNA is on
    :param vswitch_w: The vswitch wrapper to find the free vlan on.
    :param cna: The CNA wrapper to be updated with a new vlan.
    :param ensure_enabled: (Optional, Default: False) If true, enable the CNA
                           before updating.
    :return: The updated CNA.
    """

    vlan = _find_free_vlan(adapter, host_uuid, vswitch_w)
    cna.pvid = vlan
    if ensure_enabled:
        cna.enabled = True
    cna = cna.update()
    return cna


@lockutils.synchronized(VLAN_LOCK)
def crt_trunk_with_free_vlan(
        adapter, host_uuid, src_io_host_uuids, vs_name,
        crt_vswitch=True, dev_name=None, ovs_bridge=None, ovs_ext_ids=None,
        configured_mtu=None):
    """Creates a trunk adapter(s) with a free VLAN on the system.

    :param adapter: The pypowervm adapter to perform the update through.
    :param host_uuid: The host UUID that the CNA will be put on.
    :param src_io_host_uuids: The list of UUIDs of the LPARs that will host the
                              Trunk Adapters.  At least one UUID is required.
                              Multiple will be supported, and the Trunk
                              Priority will increment per adapter (in the order
                              that the I/O hosts are specified).
    :param pvid: The port VLAN ID.
    :param vs_name: The name of the PowerVM Hypervisor Virtual Switch to create
                    the p2p connection on.  This is required because it is not
                    recommended to create it on the default (ETHERNET0) virtual
                    switch.
    :param crt_vswitch: (Optional, Default: True) A boolean to indicate that
                        if the vSwitch can not be found, the system should
                        attempt to create one (with the default parameters -
                        ex: Veb mode).
    :param dev_name: (Optional, Default: None) The device name.  Only valid
                     if the src_io_host_uuids is a single entity and the
                     uuid matches the mgmt lpar UUID.  Otherwise leave as
                     None.  If set, the name of the trunk adapter created on
                     the mgmt lpar will be set to this value.
    :param ovs_bridge: (Optional, Default: None) If hosting through mgmt
                       partition, this attribute specifies which Open vSwitch
                       to connect to.
    :param ovs_ext_ids: (Optional, Default: None) Comma-delimited list of
                        key=value pairs that get set as external-id metadata
                        attributes on the OVS port. Only valid if ovs_bridge
                        is set.
    :param configured_mtu: (Optional, Default: None) Sets the MTU on the
                           adapter. May only be valid if adapter is being
                           created against mgmt partition.
    :return: The CNA Wrapper that was created.
    :return: The TrunkAdapters that were created.  Match the order that the
             src_io_host_uuids were passed in.
    """
    # Make sure we have the appropriate vSwitch
    vswitch_w = _find_or_create_vswitch(adapter, host_uuid, vs_name,
                                        crt_vswitch)

    # Find the free VLAN
    vlan = _find_free_vlan(adapter, host_uuid, vswitch_w)

    # Need to get the VIOS uuids to determine if the src_io_host_uuid is a VIOS
    iohost_wraps = partition.get_partitions(
        adapter, lpars=False, vioses=True, mgmt=True)
    io_uuid_to_wrap = {w.uuid: w for w in iohost_wraps
                       if w.uuid in src_io_host_uuids}

    # Now create the corresponding Trunk
    trunk_adpts = []
    trunk_pri = 1
    for io_uuid in src_io_host_uuids:
        trunk_adpt = pvm_net.CNA.bld(
            adapter, vlan, vswitch_w.related_href, trunk_pri=trunk_pri,
            dev_name=dev_name, ovs_bridge=ovs_bridge,
            ovs_ext_ids=ovs_ext_ids, configured_mtu=configured_mtu)
        trunk_adpts.append(trunk_adpt.create(parent=io_uuid_to_wrap[io_uuid]))
        trunk_pri += 1
    return trunk_adpts


def crt_p2p_cna(adapter, host_uuid, lpar_uuid, src_io_host_uuids, vs_name,
                crt_vswitch=True, mac_addr=None, slot_num=None, dev_name=None,
                ovs_bridge=None, ovs_ext_ids=None, configured_mtu=None):
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
    :param slot_num: (Optional, Default: None) The slot number to use for the
                     CNA. If not specified, will utilize the next available
                     slot on the LPAR.
    :param dev_name: (Optional, Default: None) The device name.  Only valid
                     if the src_io_host_uuids is a single entity and the
                     uuid matches the mgmt lpar UUID.  Otherwise leave as
                     None.  If set, the trunk adapter created on the mgmt lpar
                     will be set to this value.
    :param ovs_bridge: (Optional, Default: None) If hosting through mgmt
                       partition, this attribute specifies which Open vSwitch
                       to connect to.
    :param ovs_ext_ids: (Optional, Default: None) Comma-delimited list of
                        key=value pairs that get set as external-id metadata
                        attributes on the OVS port. Only valid if ovs_bridge
                        is set.
    :param configured_mtu: (Optional, Default: None) Sets the MTU on the
                           adapter. May only be valid if adapter is being
                           created against mgmt partition.
    :return: The CNA Wrapper that was created.
    :return: The TrunkAdapters that were created.  Match the order that the
             src_io_host_uuids were passed in.
    """

    trunk_adpts = crt_trunk_with_free_vlan(
        adapter, host_uuid, src_io_host_uuids, vs_name,
        crt_vswitch=crt_vswitch, dev_name=dev_name, ovs_bridge=ovs_bridge,
        ovs_ext_ids=ovs_ext_ids, configured_mtu=configured_mtu)

    # Darn lack of re-entrant locks
    with lockutils.lock(VLAN_LOCK):
        vswitch_w = _find_or_create_vswitch(adapter, host_uuid, vs_name,
                                            crt_vswitch)
        client_adpt = pvm_net.CNA.bld(
            adapter, trunk_adpts[0].pvid, vswitch_w.related_href,
            slot_num=slot_num, mac_addr=mac_addr)
        client_adpt = client_adpt.create(parent_type=lpar.LPAR,
                                         parent_uuid=lpar_uuid)

    return client_adpt, trunk_adpts


def find_trunks(adapter, cna_w):
    """Returns the Trunk Adapters associated with the CNA.

    :param adapter: The pypowervm adapter to perform the search with.
    :param cna_w: The Client Network Adapter to find the Trunk Adapters for.
    :return: A list of Trunk Adapters (sorted by Trunk Priority) that host
             the Client Network Adapter.
    """
    # VIOS and Management Partitions can host Trunk Adapters.
    host_wraps = partition.get_partitions(
        adapter, lpars=False, vioses=True, mgmt=True)

    # Find the corresponding trunk adapters.
    trunk_list = []
    for host_wrap in host_wraps:
        trunk = _find_trunk_on_lpar(adapter, host_wrap, cna_w)
        if trunk:
            trunk_list.append(trunk)

    # Sort by the trunk priority
    trunk_list.sort(key=lambda x: x.trunk_pri)
    return trunk_list


def _find_trunk_on_lpar(adapter, parent_wrap, client_vea):

    cna_wraps = pvm_net.CNA.get(adapter, parent=parent_wrap)
    for cna in cna_wraps:
        if (cna.is_trunk and cna.pvid == client_vea.pvid and
                cna.vswitch_id == client_vea.vswitch_id):
            return cna
    return None


def _find_all_trunks_on_lpar(adapter, parent_wrap, vswitch_id=None):
    """Returns all trunk adapters on a given vswitch.

    :param adapter: The pypowervm adapter to perform the search with.
    :param vswitch_id: The id of the vswitch to search for orphaned trunks
                       on.
    :return: A list of trunk adapters that are associated with the given
             vswitch_id.
    """
    cna_wraps = pvm_net.CNA.get(adapter, parent=parent_wrap)
    trunk_list = []
    for cna in cna_wraps:
        if (cna.is_trunk and (vswitch_id is None
                              or cna.vswitch_id == vswitch_id)):
            trunk_list.append(cna)
    return trunk_list


def _find_cna_wraps(adapter, vswitch_id=None):
    """Returns all CNAs.

    :param adapter: The pypowervm adapter to perform the search with.
    :param vswitch_id: This param is optional. If specified, the method will
                       only return CNAs associated with the given vswitch.
    :return: A list of CNAs that are optionally associated with the given
             vswitch_id.
    """
    # All lpars should be searched, including VIOSes
    lpar_wraps = partition.get_partitions(adapter)

    cna_wraps = []
    filtered_cna_wraps = []
    for lpar_wrap in lpar_wraps:
        cna_wraps.extend(pvm_net.CNA.get(adapter, parent=lpar_wrap))

    # If a vswitch_id is passed in then filter to only cnas on that vswitch
    if (vswitch_id):
        for cna in cna_wraps:
            if(cna.vswitch_id == vswitch_id):
                filtered_cna_wraps.append(cna)
        cna_wraps = filtered_cna_wraps
    return cna_wraps


def find_cnas_on_trunk(trunk_w, cna_wraps=None):
    """Returns the CNAs associated with the Trunk Adapter.

    :param trunk_w: The Trunk Adapter to find the Client Network Adapters for.
    :param cna_wraps: Optional param for passing in the list of CNA wraps
                      to search.  If the list is none, queries will be done
                      to build the list.
    :return: A list of Client Network Adapters that are hosted by the Trunk
             Adapter.
    """
    adapter = trunk_w.adapter

    # Find all the CNAs on the system
    if cna_wraps is None:
        cna_wraps = _find_cna_wraps(adapter)

    # Search the CNA wraps for matching CNAs
    cna_list = []
    for cna in cna_wraps:
        if ((not cna.uuid == trunk_w.uuid) and cna.pvid == trunk_w.pvid and
                cna.vswitch_id == trunk_w.vswitch_id):
            cna_list.append(cna)

    return cna_list


def find_orphaned_trunks(adapter, vswitch_name):
    """Returns all orphaned trunk adapters on a given vswitch.

    An orphaned trunk is a trunk adapter that does not have any associated
    CNAs.

    :param adapter: The pypowervm adapter to perform the search with.
    :param vswitch_name: The name of the vswitch to search for orphaned trunks
                         on.
    :return: A list of trunk adapters that do not have any associated CNAs
    """
    vswitch = pvm_net.VSwitch.search(
        adapter, parent_type=pvm_ms.System, one_result=True,
        name=vswitch_name)

    # May occur if the system does not host the vswitch passed in.
    if vswitch is None:
        return []
    vswitch_id = vswitch.switch_id

    # VIOS and Management Partitions can host Trunk Adapters.
    host_wraps = partition.get_partitions(
        adapter, lpars=False, vioses=True, mgmt=True)

    # Get all the CNA wraps on the vswitch
    cna_wraps = _find_cna_wraps(adapter, vswitch_id=vswitch_id)

    # Find all trunk adapters on the vswitch.
    trunk_list = []
    for host_wrap in host_wraps:
        trunks = _find_all_trunks_on_lpar(adapter, parent_wrap=host_wrap,
                                          vswitch_id=vswitch_id)
        trunk_list.extend(trunks)

    # Check if the trunk adapters are orphans
    orphaned_trunk_list = []
    for trunk in trunk_list:
        if not find_cnas_on_trunk(trunk, cna_wraps=cna_wraps):
            orphaned_trunk_list.append(trunk)

    return orphaned_trunk_list
