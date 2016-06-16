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
import itertools
from oslo_log import log as logging
import random

import pypowervm.exceptions as ex
import pypowervm.tasks.partition as tpar
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.managed_system as ms

LOG = logging.getLogger(__name__)


def set_vnic_back_devs(vnic_w, pports, sriov_adaps=None, vioses=None,
                       min_redundancy=1, max_redundancy=2, capacity=None):
    """Set a vNIC's backing devices over given SRIOV physical ports and VIOSes.

    Assign the backing devices to a iocard.VNIC wrapper using an anti-affinity
    algorithm.  That is, the method attempts to distribute the backing devices
    across as diverse a range of physical SRIOV adapters and VIOSes as
    possible.  For example given:

    vios1, vios2

    SRIOVAdapter1
        PPortA
        PPortB
    SRIOVAdapter2
        PPortC
        PPortD

    set_vnic_back_devs(vnic, [PPortA, PPortB, PPortC, PPortC], [vios1, vios2])

    ...we will create backing devices like:

    [(vios1, PPortA), (vios2, PPortB), (vios1, PPortC), (vios2, PPortD)]

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
    may force all specified pports to be used by specifying parameters such
    that:  min_redundancy == len(pports) <= max_redundancy

    :param vnic_w: iocard.VNIC wrapper, as created via VNIC.bld().  If
                   vnic_w.back_devs is nonempty, it is cleared and replaced.
                   This parameter is modified by the method (there is no return
                   value).
    :param pports: List of physical location code strings (corresponding to the
                   loc_code @property of iocard.SRIOV*PPort) for all SRIOV
                   physical ports to be considered as backing devices for the
                   vNIC.  This does not mean that all of these ports will be
                   used.
    :param sriov_adaps: Pre-fetched list of all iocard.SRIOVAdapter wrappers on
                        the host.  If not specified, the feed will be fetched
                        from the server.
    :param vioses: List of VIOS wrappers to consider for distribution of vNIC
                   servers.  Not all listed VIOSes will necessarily be used.
                   If not specified, the feed of all active (including RMC)
                   VIOSes will be fetched from the server.
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
                                      enough VFs to satisfy min_redundancy.  If
                                      this exception is raised, the passed-in
                                      vnic_w is unchanged.
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

    # Get the list of backing ports corresponding to the specified location
    # codes, ordered least-full first.
    pport_wraps = _get_good_pport_list(sriov_adaps, pports, capacity,
                                       min_redundancy)

    # Ideal number of backing devs to assign.  Can't be more than the number of
    # ports we have to work with.  Must be at least min_redundancy.  If those
    # conditions are satisfied, use max_redundancy.
    backdev_goal = max(min_redundancy, min(max_redundancy, len(pport_wraps)))

    # card_use[sriov_adap_id] = [num_uses_this_vnic, num_ports_remaining]
    card_use = {}
    for pport in pport_wraps:
        said = pport.sriov_adap_id
        if said not in card_use:
            card_use[said] = [0, 0]
        card_use[said][1] += 1
    sriov_adap_ids = list(card_use.keys())
    vio_idx = 0
    while pport_wraps and len(vnic_w.back_devs) < backdev_goal:
        # Always rotate VIOSes
        vio = vioses[vio_idx]
        vio_idx = (vio_idx + 1) % len(vioses)
        # Sort the adapters in order of least-used (for this vNIC)
        sriov_adap_ids.sort(key=lambda aid: card_use[aid][0])
        # If multiple adapters are least-used, consider all and only those.
        # Have to do this loop/break because the iterable consumes the values.
        for key_grp in itertools.groupby(
                sriov_adap_ids, key=lambda aid: card_use[aid][0]):
            adap_cands = list(key_grp[1])
            break
        # Get all the ports on just those cards, and use the emptiest one
        pp2use = sorted([pport for sriov_adap_id in adap_cands for pport in
                         pport_wraps if pport.sriov_adap_id == sriov_adap_id],
                        key=lambda pp: pp.allocated_capacity)[0]
        said = pp2use.sriov_adap_id
        # Register a hit on the chosen port's card
        card_use[said][0] += 1
        # And take off a port
        card_use[said][1] -= 1
        # If that was the last port, remove this card from consideration
        if card_use[said][1] == 0:
            sriov_adap_ids.remove(said)
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
    - The wrapper has an invisible (to REST) sriov_adap_id attribute indicating
      its parent SRIOV adapter ID.
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
    :return: A filtered, ordered list of SRIOV*PPort wrappers.
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
            # Back-pointer to the adapter ID
            pp2add.sriov_adap_id = sriov.sriov_adap_id
            pport_wraps.append(pp2add)

    if len(pport_wraps) < min_returns:
        raise ex.InsufficientSRIOVCapacity(min_vfs=min_returns,
                                           found_vfs=len(pport_wraps))
    LOG.debug('Filtered, ordered list of physical ports: %s' %
              str([pport.loc_code for pport in pport_wraps]))
    return pport_wraps
