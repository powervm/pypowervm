# Copyright 2015, 2016 IBM Corp.
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

"""Identify behavioral traits specific to a PowerVM server type/version."""

import weakref


class APITraits(object):
    """Represents capabilities inherent to the backing API server.

    For instance, depending on a schema version, or the backing REST server,
    there may be different code paths that the user needs to go through.

    A key example of this would be the VirtualNetworks.  The HMC requires
    that Virtual Networks be the driver of code paths for various code paths.
    However, in other API servers, the Virtual Networks are simply realized
    based off the VLANs/virtual switches that adapters are currently tied
    to.

    This class encapsulates the various traits so that tasks and users do not
    have to inspect the header data directly to determine how the API should
    behave.
    """

    def __init__(self, session):
        # Avoid circular references to the session by using a weak reference.
        # Circular references prevent garabage collection.
        self._sess_ref = weakref.ref(session)
        self._is_hmc = session.mc_type == 'HMC'

    @property
    def session(self):
        # Get the session through the weak reference
        return self._sess_ref()

    @property
    def vnet_aware(self):
        """Indicates whether Virtual Networks are pre-reqs to Network changes.

        Some APIs (such as modifying the SEA or creating a Client Network
        Adapter) require that the VirtualNetwork (or VNet wrapper) be
        pre-created for the operation.  This is typically done when working
        against an HMC.

        This trait will return True if the Virtual Networks need to be
        passed in on NetworkBridge or Client Network Adapter creation, or
        False if the API should directly work with VLANs and Virtual Switches.
        """
        return self._is_hmc

    @property
    def has_lpar_profiles(self):
        """Indicates whether the platform manager supports LPAR profiles.

        This trait will return True if LPAR profiles are supported.
        """
        return self._is_hmc

    @property
    def local_api(self):
        """Indicates whether or not the PowerVM API Server is running locally.

        The PowerVM API server in some deployments may be running co-located
        with the pypowervm API.  In those cases, certain optimizations may be
        available (like uploading from a file instead of a pipe).

        This trait is a coarse check to determine, for certain, if the API
        is co-located on the same server.
        """
        # If the file auth is set to true, we must be colocated.  All other
        # routes could be error prone and lead to significant branches of
        # complexity.
        return self.session.use_file_auth

    @property
    def dynamic_pvid(self):
        """Indicates whether a CNA can dynamically modify its PVID."""
        return not self._is_hmc

    @property
    def rmdev_job_available(self):
        """Indicates whether or not the Job API supports RMDev."""
        return not self._is_hmc

    @property
    def has_high_slot(self):
        """Does the API support UseNextAvailableHighSlotID?"""
        return not self._is_hmc

    @property
    def vea_as_ibmi_console(self):
        """Indicates whether the console type of IBMi VM is vea.

        IBMi depends on the trait to determine the console type. If the host is
        not managed by HMC, the console type of an IBMi VM deployed on the host
        shall be the slot number of its first virtual ethernet adapter.
        Otherwise, the Console type shall be "HMC".
        """
        return not self._is_hmc
