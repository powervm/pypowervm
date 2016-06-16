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
                     to achieve more control.)
    :raise InsufficientSRIOVCapacity: If the method was not able to allocate
                                      enough VFs to satisfy min_redundancy.  If
                                      this exception is raised, the passed-in
                                      vnic_w is unchanged.
    """
    # TODO(IBM): Implement
    raise NotImplementedError()
