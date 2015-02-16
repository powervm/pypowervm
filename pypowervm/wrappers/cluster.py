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

import logging

import pypowervm.util as u
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.managed_system as ms
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)

# Cluster Constants
CL_NAME = 'ClusterName'
CL_ID = 'ClusterID'
CL_REPOPVS = 'RepositoryDisk'  # Yes, really
CL_PV = c.PV
CL_SSP_LINK = 'ClusterSharedStoragePool'
CL_NODES = 'Node'  # Yes, really
CL_NODE = 'Node'

# Node Constants
N_HOSTNAME = 'HostName'
N_LPARID = 'PartitionID'
N_VIOS_LINK = c.VIOS
N_MTMS = 'MachineTypeModelAndSerialNumber'


class Cluster(ewrap.EntryWrapper):
    """A Cluster behind a SharedStoragePool."""

    @property
    def name(self):
        return self.get_parm_value(CL_NAME)

    @property
    def id(self):
        """The string ID according to VIOS, not a UUID or UDID."""
        return self.get_parm_value(CL_ID)

    @property
    def ssp_uri(self):
        """The URI of the SharedStoragePool associated with this Cluster."""
        return self.get_href(CL_SSP_LINK, one_result=True)

    @property
    def ssp_uuid(self):
        """The UUID of the SharedStoragePool associated with this Cluster."""
        uri = self.ssp_uri
        if uri is not None:
            return u.get_req_path_uuid(uri)

    @property
    def repos_pv(self):
        """Returns the (one) repository PV.

        Although the schema technically allows a collection of PVs under the
        RepositoryDisk element, a Cluster always has exactly one repository PV.
        """
        repos_elem = self._find_or_seed(CL_REPOPVS)
        pv_list = repos_elem.findall(CL_PV)
        # Check only relevant when building up a Cluster wrapper internally
        if pv_list and len(pv_list) == 1:
            return stor.PhysicalVolume(pv_list[0])
        return None

    @repos_pv.setter
    def repos_pv(self, pv):
        """Set the (single) PhysicalVolume member of RepositoryDisk.

        You cannot change the repository disk of a live Cluster.  This setter
        is useful only when constructing new Clusters.

        :param pv: The PhysicalVolume (NOT a list) to set.
        """
        self.replace_list(CL_REPOPVS, [pv])

    @property
    def nodes(self):
        """WrapperElemList of Node wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(CL_NODES),
                                     CL_NODE, Node)

    @nodes.setter
    def nodes(self, ns):
        self.replace_list(CL_NODES, ns)


class Node(ewrap.ElementWrapper):
    """A Node represents a VIOS member of a Cluster.

    A Cluster cannot simply contain VirtualIOServer links because it is
    likely that some of the Cluster's members are not managed by the same
    instance of the PowerVM REST server, which would then have no way to
    construct said links.  In such cases, the Node object supplies enough
    information about the VIOS that it could be found by a determined consumer.

    To add a new Node to a Cluster, only the hostname is required.
    n = Node()
    n.hostname = ...
    cluster.nodes.append(n)
    adapter.update(...)
    """

    @property
    def hostname(self):
        return self.get_parm_value(N_HOSTNAME)

    @hostname.setter
    def hostname(self, hn):
        self.set_parm_value(N_HOSTNAME, hn)

    @property
    def lpar_id(self):
        """Small integer partition ID, not UUID."""
        return self.get_parm_value(N_LPARID, converter=int)

    @property
    def mtms(self):
        """MTMS Element wrapper of the system hosting the Node (VIOS)."""
        return ms.MTMS(self._find(N_MTMS))

    @property
    def vios_uri(self):
        """The URI of the VIOS.

        This is only set if the VIOS is on this system!
        """
        return self.get_href(N_VIOS_LINK, one_result=True)

    @property
    def vios_uuid(self):
        """The UUID of the Node (VIOS).

        This is only set if the VIOS is on this system!
        """
        uri = self.vios_uri
        if uri is not None:
            return u.get_req_path_uuid(uri)
