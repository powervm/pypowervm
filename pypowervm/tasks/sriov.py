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

"""Complex tasks around SR-IOV cards/ports, VFs, and vNICs."""

import copy
from oslo_concurrency import lockutils as lock
from oslo_log import log as logging
import random
import six

import pypowervm.exceptions as ex
from pypowervm.i18n import _
import pypowervm.tasks.partition as tpar
import pypowervm.utils.transaction as tx
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.managed_system as ms

LOG = logging.getLogger(__name__)

# Take read_lock on operations that create/delete VFs (including VNIC).  This
# is a read_lock so we don't serialize all VF creation globally.
# Take write_lock on operations that modify properties of physical ports and
# rely on knowing the usage counts thereon (e.g. changing port labels).
PPORT_MOD_LOCK = lock.ReaderWriterLock()


def set_vnic_back_devs(vnic_w, pports, sys_w=None, vioses=None, redundancy=1,
                       capacity=None, check_port_status=False):
    """Set a vNIC's backing devices over given SRIOV physical ports and VIOSes.

    Assign the backing devices to a iocard.VNIC wrapper using an anti-affinity
    algorithm.  That is, the method attempts to distribute the backing devices
    across as diverse a range of physical SRIOV adapters and VIOSes as
    possible, using the least-saturated ports first.  For example, given:

    vios1, vios2

    SRIOVAdapter1
        PPortA (50% allocated)
        PPortB (20%)
        PPortC (45%)
    SRIOVAdapter2
        PPortD (10%)
        PPortE (2%)
        PPortF (11%)

    set_vnic_back_devs(vnic, [PPortA, PPortB, PPortC, PPortD, PPortE, PPortF],
                       [vios1, vios2], redundancy=4)

    ...we will create backing devices like:

    [(vios1, PPortE), (vios2, PPortB), (vios1, PPortD), (vios2, PPortC)]

    As part of the algorithm, we will use sriov_adaps to filter out physical
    ports which are already saturated.  This could err either way due to
    out-of-band changes:
    - We may end up excluding a port which has had some capacity freed up since
      sriov_adaps was retrieved; or
    - We may attempt to include a port which has become saturated since
      sriov_adaps was retrieved, resulting in an error from the REST server.

    This method acts on the vNIC-related capabilities on the system and VIOSes:
    - If the system is not vNIC capable, the method will fail.
    - If none of the active VIOSes are vNIC capable, the method will fail.
    - If redundancy > 1,
        - the system must be vNIC failover capable, and
        - at least one active VIOS must be vNIC failover capable.
    - If any VIOSes are vNIC failover capable, failover-incapable VIOSes will
      be ignored.

    :param vnic_w: iocard.VNIC wrapper, as created via VNIC.bld().  If
                   vnic_w.back_devs is nonempty, it is cleared and replaced.
                   This parameter is modified by the method (there is no return
                   value).  If this method raises an exception, vnic_w is
                   guaranteed to be unchanged.
    :param pports: List of physical location code strings (corresponding to the
                   loc_code @property of iocard.SRIOV*PPort) for all SRIOV
                   physical ports to be considered as backing devices for the
                   vNIC.  This does not mean that all of these ports will be
                   used.
    :param sys_w: Pre-fetched pypowervm.wrappers.managed_system.System wrapper.
                  If not specified, it will be fetched from the server.
    :param vioses: List of VIOS wrappers to consider for distribution of vNIC
                   servers.  Not all listed VIOSes will necessarily be used.
                   If not specified, the feed of all active (including RMC)
                   VIOSes will be fetched from the server.  If specified, the
                   list will be filtered to include only active (including RMC)
                   VIOSes (according to the wrappers - the server is not re-
                   checked).  The list is also filtered to remove VIOSes which
                   are not vNIC capable; and, if min_redundancy > 1, to remove
                   VIOSes which are not vNIC failover capable.
    :param redundancy: Number of backing devices to assign.  If the method
                       can't allocate this many VFs after filtering the pports
                       list, InsufficientSRIOVCapacity will be raised.  Note
                       that at most one VF is created on each physical port.
    :param capacity: (float) Minimum capacity to assign to each backing device.
                     Must be between 0.0 and 1.0, and must be a multiple of the
                     min_granularity of *all* of the pports.  (Capacity may be
                     assigned to each individual backing device after the fact
                     to achieve more control; but in that case, the consumer is
                     responsible for validating sufficient available capacity.)
    :param check_port_status: If True, only ports with link-up status will be
                              considered for allocation.  If False (the
                              default), link-down ports may be used.
    :raise NoRunningSharedSriovAdapters: If no SR-IOV adapters in Sriov mode
                                         and Running state can be found.
    :raise NotEnoughActiveVioses: If no active (including RMC) VIOSes can be
                                  found.
    :raise InsufficientSRIOVCapacity: If the method was not able to allocate
                                      enough VFs to satisfy the specified
                                      redundancy.
    :raise SystemNotVNICCapable: If the managed system is not vNIC capable.
    :raise NoVNICCapableVIOSes: If there are no vNIC-capable VIOSes.
    :raise VNICFailoverNotSupportedSys: If redundancy > 1, and the system is
                                        not vNIC failover capable.
    :raise VNICFailoverNotSupportedVIOS: If redundancy > 1, and there are no
                                         vNIC failover-capable VIOSes.
    """
    # An Adapter to work with
    adap = vnic_w.adapter
    if adap is None:
        raise ValueError('Developer error: Must build vnic_w with an Adapter.')

    # Check vNIC capability on the system
    sys_w = _check_sys_vnic_capabilities(adap, sys_w, redundancy)

    # Filter SR-IOV adapters
    sriov_adaps = _get_good_sriovs(sys_w.asio_config.sriov_adapters)

    # Get VIOSes which are a) active, b) vNIC capable, and c) vNIC failover
    # capable, if necessary.
    vioses = _check_and_filter_vioses(adap, vioses, redundancy)

    # Try not to end up lopsided on one VIOS
    random.shuffle(vioses)

    # Get the subset of backing ports corresponding to the specified location
    # codes which have enough space for new VFs.
    pport_wraps = _get_good_pport_list(sriov_adaps, pports, capacity,
                                       redundancy, check_port_status)

    # At this point, we've validated enough that we won't raise.  Start by
    # clearing any existing backing devices.
    vnic_w.back_devs = []

    card_use = {}
    for pport in pport_wraps:
        said = pport.sriov_adap_id
        if said not in card_use:
            card_use[said] = {'num_used': 0, 'ports_left': 0}
        card_use[said]['ports_left'] += 1
    vio_idx = 0
    while pport_wraps and len(vnic_w.back_devs) < redundancy:
        # Always rotate VIOSes
        vio = vioses[vio_idx]
        vio_idx = (vio_idx + 1) % len(vioses)
        # Select the least-saturated port from among the least-used adapters.
        least_uses = min([cud['num_used'] for cud in card_use.values()])
        pp2use = min([pport for pport in pport_wraps if
                      card_use[pport.sriov_adap_id]['num_used'] == least_uses],
                     key=lambda pp: pp.allocated_capacity)
        said = pp2use.sriov_adap_id
        # Register a hit on the chosen port's card
        card_use[said]['num_used'] += 1
        # And take off a port
        card_use[said]['ports_left'] -= 1
        # If that was the last port, remove this card from consideration
        if card_use[said]['ports_left'] == 0:
            del card_use[said]
        # Create and add the backing device
        vnic_w.back_devs.append(card.VNICBackDev.bld(
            adap, vio.uuid, said, pp2use.port_id, capacity=capacity))
        # Remove the port we just used from subsequent consideration.
        pport_wraps.remove(pp2use)


def _check_sys_vnic_capabilities(adap, sys_w, redundancy):
    """Validate vNIC capabilities on the Managed System.

    :param adap: pypowervm Adapter.
    :param sys_w: pypowervm.wrappers.managed_system.System wrapper.  If None,
                  it is retrieved from the host.
    :param redundancy: If greater than 1, this method will verify that the
                       System is vNIC failover-capable.  Otherwise, this check
                       is skipped.
    :return: The System wrapper.
    :raise SystemNotVNICCapable: If the System is not vNIC capable.
    :raise VNICFailoverNotSupportedSys: If min_redundancy > 1 and the System is
                                        not vNIC failover capable.
    """
    if sys_w is None:
        sys_w = ms.System.get(adap)[0]

    if not sys_w.get_capability('vnic_capable'):
        raise ex.SystemNotVNICCapable()
    if redundancy > 1 and not sys_w.get_capability('vnic_failover_capable'):
        raise ex.VNICFailoverNotSupportedSys(red=redundancy)

    return sys_w


def _check_and_filter_vioses(adap, vioses, redundancy):
    """Return active VIOSes with appropriate vNIC capabilities.

    Remove all VIOSes which are not active or not vNIC capable.  If
    min_redundancy > 1, failover is required, so remove VIOSes that are not
    also vNIC failover capable.  Error if no VIOSes remain.

    :param adap: pypowervm Adapter.
    :param vioses: List of pypowervm.wrappers.virtual_io_server.VIOS to check.
                   If None, all active VIOSes are retrieved from the server.
    :param redundancy: If greater than 1, the return list will include only
                       vNIC failover-capable VIOSes.  Otherwise, if any VIOSes
                       are vNIC failover-capable, non-failover-capable VIOSes
                       are excluded.
    :return: The filtered list of VIOS wrappers.
    :raise NotEnoughActiveVioses: If no active (including RMC) VIOSes can be
                                  found.
    :raise NoVNICCapableVIOSes: If none of the vioses are vNIC capable.
    :raise VNICFailoverNotSupportedVIOS: If redundancy > 1 and none of the
                                         vioses is vNIC failover capable.
    """
    # This raises if none are found
    vioses = tpar.get_active_vioses(adap, xag=[], vios_wraps=vioses,
                                    find_min=1)
    # Filter by vNIC capability
    vioses = [vios for vios in vioses if vios.vnic_capable]
    if not vioses:
        raise ex.NoVNICCapableVIOSes()

    # Filter by failover capability, if needed.
    # If any are failover-capable, use just those, regardless of redundancy.
    failover_only = [vios for vios in vioses if vios.vnic_failover_capable]
    if redundancy > 1 or any(failover_only):
        vioses = failover_only

    # At this point, if the list is empty, it's because no failover capability.
    if not vioses:
        raise ex.VNICFailoverNotSupportedVIOS(red=redundancy)

    return vioses


def _get_good_sriovs(sriov_adaps):
    """(Retrieve and) filter SR-IOV adapters to those Running in Sriov mode.

    :param sriov_adaps: List of SRIOVAdapter wrappers to filter by mode/state.
    :return: List of SR-IOV adapters in Running state and in Sriov mode.
    :raise NoRunningSharedSriovAdapters: If no SR-IOV adapters can be found in
                                         Sriov mode and Running state.
    """
    # Filter SRIOV adapters to those in the correct mode/state
    good_adaps = [sriov for sriov in sriov_adaps if
                  sriov.mode == card.SRIOVAdapterMode.SRIOV and
                  sriov.state == card.SRIOVAdapterState.RUNNING]
    if not good_adaps:
        raise ex.NoRunningSharedSriovAdapters(
            sriov_loc_mode_state='\n'.join([' | '.join([
                sriov.phys_loc_code, sriov.mode,
                sriov.state or '-']) for sriov in sriov_adaps]))

    LOG.debug('Found running/shared SR-IOV adapter(s): %s',
              str([sriov.phys_loc_code for sriov in good_adaps]))

    return good_adaps


def _get_good_pport_list(sriov_adaps, pports, capacity, redundancy,
                         check_link_status):
    """Get a list of SRIOV*PPort filtered by capacity and specified pports.

    Builds a list of pypowervm.wrappers.iocard.SRIOV*PPort from sriov_adaps
    such that:
    - Only ports whose location codes are listed in the pports param are
      considered.
    - Only ports with sufficient remaining capacity (per the capacity param, if
      specified; otherwise the port's min_granularity) are considered.

    :param sriov_adaps: A list of SRIOVAdapter wrappers whose mode is Sriov and
                        whose state is Running.
    :param pports: A list of string physical location codes of the physical
                   ports to consider.
    :param capacity: (float) Minimum capacity which must be available on each
                     backing device.  Must be between 0.0 and 1.0, and must be
                     a multiple of the min_granularity of *all* of the pports.
                     If None, available port capacity is validated using each
                     port's min_granularity.
    :param redundancy: The desired redundancy level (number of ports to
                       return).required.  If the filtered list has fewer than
                       this number of ports, InsufficientSRIOVCapacity is
                       raised.
    :param check_link_status: If True, ports with link-down status will not be
                              returned.  If False, link status is not checked.
    :raise InsufficientSRIOVCapacity: If the final list contains fewer than
                                      'redundancy' ports.
    :return: A filtered list of SRIOV*PPort wrappers.
    """
    def port_ok(port):
        pok = True
        # Is it in the candidate list?
        if port.loc_code not in pports:
            pok = False
        # Is the link state up
        if check_link_status and not port.link_status:
            pok = False
        # Does it have available logical ports?
        if port.cfg_lps >= port.cfg_max_lps:
            pok = False
        # Does it have capacity?
        des_cap = port.min_granularity
        if capacity is not None:
            # Must be at least min_granularity.
            des_cap = max(des_cap, capacity)
        if port.allocated_capacity + des_cap > 1.0:
            pok = False
        return pok

    pport_wraps = []
    for sriov in sriov_adaps:
        for pport in sriov.phys_ports:
            if port_ok(pport):
                pp2add = copy.deepcopy(pport)
                pport_wraps.append(pp2add)

    if len(pport_wraps) < redundancy:
        raise ex.InsufficientSRIOVCapacity(red=redundancy,
                                           found_vfs=len(pport_wraps))
    LOG.debug('Filtered list of physical ports: %s' %
              str([pport.loc_code for pport in pport_wraps]))
    return pport_wraps


def get_lpar_vnics(adapter):
    """Return a dict mapping LPAR wrappers to their VNIC feeds.

    :param adapter: The pypowervm.adapter.Adapter for REST API communication.
    :return: A dict of the form { LPAR: [VNIC, ...] }, where the keys are
             pypowervm.wrappers.logical_partition.LPAR and the values are lists
             of the pypowervm.wrappers.iocard.VNIC they own.
    """
    return {lpar: card.VNIC.get(adapter, parent=lpar) for lpar in
            tpar.get_partitions(adapter, lpars=True, vioses=False)}


def _vnics_using_pport(pport, lpar2vnics):
    """Determine (and warn about) usage of SRIOV physical port by VNICs.

    Ascertain whether an SRIOV physical port is being used as a backing device
    for any VNICs.  The method returns a list of warning messages for each such
    usage found.

    :param pport: pypowervm.wrappers.iocard.SRIOV*PPort wrapper to check.
    :param lpar2vnics: Dict of {LPAR: [VNIC, ...]} gleaned from get_lpar_vnics
    :return: A list of warning messages for found usages of the physical port.
             If no usages were found, the empty list is returned.
    """
    warnings = []
    for lpar, vnics in six.iteritems(lpar2vnics):
        for vnic in vnics:
            if any([backdev for backdev in vnic.back_devs if
                    backdev.sriov_adap_id == pport.sriov_adap_id and
                    backdev.pport_id == pport.port_id]):
                warnings.append(
                    _("SR-IOV Physical Port at location %(loc_code)s is "
                      "backing a vNIC belonging to LPAR %(lpar_name)s (LPAR "
                      "UUID: %(lpar_uuid)s; vNIC UUID: %(vnic_uuid)s).") %
                    {'loc_code': pport.loc_code, 'lpar_name': lpar.name,
                     'lpar_uuid': lpar.uuid, 'vnic_uuid': vnic.uuid})
    return warnings


def _vet_port_usage(sys_w, label_index):
    """Look for relabeled ports which are in use by vNICs.

    :param sys_w: pypowervm.wrappers.managed_system.System wrapper for the
                  host.
    :param label_index: Dict of { port_loc_code: port_label_before } mapping
                        the physical location code of each physical port to the
                        value of its label before changes were made.
    :return: A list of translated messages warning of relabeled ports which are
             in use by vNICs.
    """
    warnings = []
    lpar2vnics = None
    for sriovadap in sys_w.asio_config.sriov_adapters:
        for pport in sriovadap.phys_ports:
            # If the port is unused, it's fine
            if pport.cfg_lps == 0:
                continue
            # If the original port label was unset, no harm setting it.
            if not label_index[pport.loc_code]:
                continue
            # If the port label is unchanged, it's fine
            if pport.label == label_index[pport.loc_code]:
                continue
            # Now we have to check all the VNICs on all the LPARs.  Lazy-load
            # this, because it's expensive.
            if lpar2vnics is None:
                lpar2vnics = get_lpar_vnics(sys_w.adapter)
            warnings += _vnics_using_pport(pport, lpar2vnics)
    return warnings


@tx.entry_transaction
def safe_update_pports(sys_w, callback_func, force=False):
    """Retrying entry transaction for safe updates to SR-IOV physical ports.

    Usage:
        def changes(sys_w):
            for sriov in sys_w.asio_config.sriov_adapters:
                ...
                sriov.phys_ports[n].pport.label = some_new_label
                ...
                update_needed = True
                ...
            return update_needed

        sys_w = safe_update_pports(System.getter(adap), changes, force=maybe)

    The consumer passes a callback method which makes changes to the labels of
    the physical ports of the ManagedSystem's SR-IOV adapters.

    If the callback returns a False value (indicating that no update is
    necessary), safe_update_pports immediately returns the sys_w.

    If the callback returns a True value, safe_update_pports first checks
    whether any of the changed ports are in use by vNICs (see "Why vNICs?"
    below).

    If the force option is not True, and any uses were found, this method
    raises an exception whose text includes details about the found usages.
    Otherwise, the found usages are logged as warnings.

    Assuming no exception is raised, safe_update_pports attempts to update the
    sys_w wrapper with the REST server.  (The caller does *not* do the update.)
    If an etag mismatch is encountered, safe_update_pports refreshes the sys_w
    wrapper and retries, according to the semantics of entry_transaction.

    Why vNICs?
    Care must be taken when changing port labels on the fly because those
    labels are used by LPM to ensure that the LPAR on the target system gets
    equivalent connectivity.  Direct-attached VFs - either those belonging to
    VIOSes (e.g. for SEA) or to LPARs - mean the partition is not migratable,
    so the labels can be changed with impunity.  And the only way a VF is
    migratable is if it belongs to a vNIC on a migratable LPAR.

    :param sys_w: pypowervm.wrappers.managed_system.System wrapper or getter
                  thereof.
    :param callback_func: Method executing the actual changes on the sys_w.
                          The method must accept sys_w (a System wrapper) as
                          its only argument.  Its return value will be
                          interpreted as a boolean to determine whether to
                          perform the update() (True) or not (False).
    :param force: If False (the default) and any of the updated physical ports
                  are found to be in use by vNICs, the method will raise.  If
                  True, warnings are logged for each such usage, but the method
                  will succeed.
    :return: The (possibly-updated) sys_w.
    :raise CantUpdatePPortsInUse: If any of the relabeled physical ports are in
                                  use by vNICs *and* the force option is False.
    """
    with PPORT_MOD_LOCK.write_lock():
        # Build an index of port:label for comparison after setting
        label_index = {pport.loc_code: pport.label for sriovadap in
                       sys_w.asio_config.sriov_adapters for pport in
                       sriovadap.phys_ports}

        # Let caller make the pport changes.
        if not callback_func(sys_w):
            # No update needed.
            # sys_w may be what was passed in, or the result of the getter.
            return sys_w

        # If return is True, caller wants us to update().  For each port that
        # changed, check its usage
        warnings = _vet_port_usage(sys_w, label_index)
        if warnings and not force:
            raise ex.CantUpdatePPortsInUse(warnings=warnings)
        # We're going to do the update.  Log any found usages.
        if warnings:
            LOG.warning(_("Making changes to the following SR-IOV physical "
                          "port labels even though they are in use by vNICs:"))
            for warning in warnings:
                LOG.warning(warning)
        return sys_w.update()


def find_pports_for_portlabel(portlabel, adapter, msys=None):
    """Find SR-IOV physical ports based on the port label.

    :param portlabel: portlabel of the SR-IOV physical ports to find.
    :param adapter: The pypowervm adapter API interface.
    :param msys: pypowervm.wrappers.managed_system.System wrapper.If not
                 specified, it will be retrieved from the server.
    :return: List of SRIOVEthPPort or SRIOVConvPPort wrappers for the specified
             port label, or the empty list if no such port exists.
    """
    # Physical ports for the given physical network
    if msys is None:
        msys = ms.System.get(adapter)[0]
    pports = []
    for sriov in msys.asio_config.sriov_adapters:
        for pport_w in sriov.phys_ports:
            if (pport_w.label or 'default') == portlabel:
                pports.append(pport_w)
    return pports


def find_pport(sys_w, physloc):
    """Find an SR-IOV physical port based on its location code.

    :param sys_w: pypowervm.wrappers.managed_system.System wrapper of the host.
    :param physloc: Physical location code string (per SRIOV*PPort.loc_code) of
                    the SR-IOV physical port to find.
    :return: SRIOVEthPPort or SRIOVConvPPort wrapper with the specified
             location code, or None if no such port exists in sys_w.
    """
    for sriov in sys_w.asio_config.sriov_adapters:
        for pport in sriov.phys_ports:
            if pport.loc_code == physloc:
                return pport
    return None
