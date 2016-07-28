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


def set_vnic_back_devs(vnic_w, pports, sriov_adaps=None, vioses=None,
                       min_redundancy=1, max_redundancy=2, capacity=None):
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
                       [vios1, vios2], max_redundancy=4)

    ...we will create backing devices like:

    [(vios1, PPortE), (vios2, PPortB), (vios1, PPortD), (vios2, PPortC)]

    This method will strive to allocate as many backing devices as possible, to
    a maximum of min(max_redundancy, len(pports)).  As part of the algorithm,
    we will use sriov_adaps to filter out physical ports which are already
    saturated.  This could err either way due to out-of-band changes:
    - We may end up excluding a port which has had some capacity freed up since
      sriov_adaps was retrieved, possibly resulting in a lower redundancy than
      may otherwise have been possible; or
    - We may attempt to include a port which has become saturated since
      sriov_adaps was retrieved, resulting in an error from the REST server.

    As a result of the above, and of the max_redundancy param, it is not
    guaranteed that all pports or all vioses will be used.  However, the caller
    may force all specified pports to be used (or the method will raise) by
    specifying parameters such that:
        min_redundancy == len(pports) <= max_redundancy

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
    :param sriov_adaps: Pre-fetched list of all iocard.SRIOVAdapter wrappers on
                        the host.  If not specified, the data will be fetched
                        from the server.
    :param vioses: List of VIOS wrappers to consider for distribution of vNIC
                   servers.  Not all listed VIOSes will necessarily be used.
                   If not specified, the feed of all active (including RMC)
                   VIOSes will be fetched from the server.  If specified, the
                   list will be filtered to include only active (including RMC)
                   VIOSes (according to the wrappers - the server is not re-
                   checked).
    :param min_redundancy: Minimum number of backing devices to assign.  If the
                           method can't allocate at least this many VFs,
                           InsufficientSRIOVCapacity will be raised.
    :param max_redundancy: Maximum number of backing devices to assign.
                           Ignored if greater than len(pports).
    :param capacity: (float) Minimum capacity to assign to each backing device.
                     Must be between 0.0 and 1.0, and must be a multiple of the
                     min_granularity of *all* of the pports.  (Capacity may be
                     assigned to each individual backing device after the fact
                     to achieve more control; but in that case, the consumer is
                     responsible for validating sufficient available capacity.)
    :raise NoRunningSharedSriovAdapters: If no SR-IOV adapters in Sriov mode
                                         and Running state can be found.
    :raise NotEnoughActiveVioses: If no active (including RMC) VIOSes can be
                                  found.
    :raise InsufficientSRIOVCapacity: If the method was not able to allocate
                                      enough VFs to satisfy min_redundancy.
    """
    # An Adapter to work with
    adap = vnic_w.adapter
    if adap is None:
        raise ValueError('Developer error: Must build vnic_w with an Adapter.')

    sriov_adaps = _get_good_sriovs(adap, sriov_adaps)

    # Ensure we have VIOSes
    vioses = tpar.get_active_vioses(adap, xag=[], vios_wraps=vioses,
                                    find_min=1)
    # Try not to end up lopsided on one VIOS
    random.shuffle(vioses)

    # Get the subset of backing ports corresponding to the specified location
    # codes which have enough space for new VFs.
    pport_wraps = _get_good_pport_list(sriov_adaps, pports, capacity,
                                       min_redundancy)

    # At this point, we've validated enough that we won't raise.  Start by
    # clearing any existing backing devices.
    vnic_w.back_devs = []

    # Ideal number of backing devs to assign.  Can't be more than the number of
    # ports we have to work with.  Must be at least min_redundancy.  If those
    # conditions are satisfied, use max_redundancy.
    backdev_goal = max(min_redundancy, min(max_redundancy, len(pport_wraps)))

    card_use = {}
    for pport in pport_wraps:
        said = pport.sriov_adap_id
        if said not in card_use:
            card_use[said] = {'num_used': 0, 'ports_left': 0}
        card_use[said]['ports_left'] += 1
    vio_idx = 0
    while pport_wraps and len(vnic_w.back_devs) < backdev_goal:
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


def _get_good_sriovs(adap, sriov_adaps=None):
    """(Retrieve and) filter SR-IOV adapters to those Running in Sriov mode.

    :param adap: pypowervm.adapter.Adapter for REST API communication.  Only
                 required if sriov_adaps is None.
    :param sriov_adaps: List of SRIOVAdapter wrappers to filter by mode/state.
                        If unspecified, the Managed System will be retrieved
                        from the server and its SR-IOV Adapters used.
    :return: List of SR-IOV adapters in Running state and in Sriov mode.
    :raise NoRunningSharedSriovAdapters: If no SR-IOV adapters can be found in
                                         Sriov mode and Running state.
    """
    if sriov_adaps is None:
        sriov_adaps = ms.System.get(adap)[0].asio_config.sriov_adapters
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


def _get_good_pport_list(sriov_adaps, pports, capacity, min_returns):
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
    :param min_returns: The minimum acceptable number of ports to return.  If
                        the filtered list has fewer than this number of ports,
                        InsufficientSRIOVCapacity is raised.
    :raise InsufficientSRIOVCapacity: If the final list contains fewer than
                                      min_returns ports.
    :return: A filtered list of SRIOV*PPort wrappers.
    """
    pport_wraps = []
    for sriov in sriov_adaps:
        for pport in sriov.phys_ports:
            # Is it in the candidate list?
            if pport.loc_code not in pports:
                continue
            # Does it have space?
            des_cap = pport.min_granularity
            if capacity is not None:
                # Must be at least min_granularity.
                des_cap = max(des_cap, capacity)
            if pport.allocated_capacity + des_cap > 1.0:
                continue
            pp2add = copy.deepcopy(pport)
            pport_wraps.append(pp2add)

    if len(pport_wraps) < min_returns:
        raise ex.InsufficientSRIOVCapacity(min_vfs=min_returns,
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
