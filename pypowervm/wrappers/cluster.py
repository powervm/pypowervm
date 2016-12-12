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

"""EntryWrappers for Cluster and its subelements."""

from oslo_log import log as logging

import pypowervm.util as u
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.mtms as mtmwrap
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)

# Cluster Constants
_CL_NAME = 'ClusterName'
_CL_ID = 'ClusterID'
_CL_REPOPVS = 'RepositoryDisk'  # Yes, really
_CL_PV = stor.PHYS_VOL
_CL_SSP_LINK = 'ClusterSharedStoragePool'
_CL_NODES = 'Node'  # Yes, really
_CL_NODE = 'Node'
_CL_CAPABILITY = 'ClusterCapabilities'
_CL_EL_ORDER = (_CL_NAME, _CL_ID, _CL_REPOPVS, _CL_SSP_LINK, _CL_NODE,
                _CL_CAPABILITY)
# Node Constants
_N_HOSTNAME = 'HostName'
_N_LPARID = 'PartitionID'
_N_NAME = 'PartitionName'
_N_VIOS_LEVEL = 'VirtualIOServerLevel'
_N_VIOS_LINK = 'VirtualIOServer'
_N_IPADDR = 'IPAddress'
_N_STATE = 'State'
_N_EL_ORDER = (_N_HOSTNAME, _N_LPARID, _N_NAME, mtmwrap.MTMS_ROOT,
               _N_VIOS_LEVEL, _N_VIOS_LINK, _N_IPADDR, _N_STATE)


class NodeState(object):
    """Cluster node state, from NodeState.Enum."""
    UP = 'Up'
    DOWN = 'Down'
    UNKNOWN = 'Unknown'


@ewrap.EntryWrapper.pvm_type('Cluster', child_order=_CL_EL_ORDER)
class Cluster(ewrap.EntryWrapper):
    """A Cluster behind a SharedStoragePool."""

    search_keys = dict(name='ClusterName')

    @classmethod
    def bld(cls, adapter, name, repos_pv, first_node):
        """Create a fresh Cluster EntryWrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: String name for the Cluster.
        :param repos_pv: storage.PV representing the repository disk.
        :param first_node: Node wrapper representing the first VIOS
        to host the Cluster.  (The Cluster Create API only accepts a single
        node; others must be added later.)  The VIOS must be able to see each
        disk.
        """
        clust = cls._bld(adapter)
        clust.repos_pv = repos_pv
        clust.nodes = [first_node]
        clust._name(name)
        return clust

    @property
    def name(self):
        return self._get_val_str(_CL_NAME)

    def _name(self, newname):
        self.set_parm_value(_CL_NAME, newname)

    @property
    def id(self):
        """The string ID according to VIOS, not a UUID or UDID."""
        return self._get_val_str(_CL_ID)

    @property
    def ssp_uri(self):
        """The URI of the SharedStoragePool associated with this Cluster."""
        return self.get_href(_CL_SSP_LINK, one_result=True)

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
        repos_elem = self._find_or_seed(_CL_REPOPVS)
        pv_list = repos_elem.findall(_CL_PV)
        # Check only relevant when building up a Cluster wrapper internally
        if pv_list and len(pv_list) == 1:
            return stor.PV.wrap(pv_list[0])
        return None

    @repos_pv.setter
    def repos_pv(self, pv):
        """Set the (single) PV member of RepositoryDisk.

        You cannot change the repository disk of a live Cluster.  This setter
        is useful only when constructing new Clusters.

        :param pv: The PV (NOT a list) to set.
        """
        self.replace_list(_CL_REPOPVS, [pv])

    @property
    def nodes(self):
        """WrapperElemList of Node wrappers."""
        return ewrap.WrapperElemList(self._find_or_seed(_CL_NODES), Node)

    @nodes.setter
    def nodes(self, ns):
        self.replace_list(_CL_NODES, ns)


@ewrap.ElementWrapper.pvm_type('Node', has_metadata=True,
                               child_order=_N_EL_ORDER)
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

    @classmethod
    def bld(cls, adapter, hostname=None, lpar_id=None, mtms=None,
            vios_uri=None):
        """Create a fresh Node ElementWrapper.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param hostname: String hostname (or IP) of the Node.
        :param lpar_id: Integer LPAR ID of the Node.
        :param mtms: String OR mtms.MTMS wrapper representing the
                     Machine Type, Model, and Serial Number of the system
                     hosting the VIOS.  String format: 'MT-M*S'
                     e.g. '8247-22L*1234A0B'.
        :param vios_uri: String URI representing this Node.
        """
        node = cls._bld(adapter)
        if vios_uri:
            node._vios_uri(vios_uri)
        if lpar_id:
            node._lpar_id(lpar_id)
        if mtms:
            node._mtms(mtms)
        if hostname:
            node._hostname(hostname)
        return node

    @property
    def hostname(self):
        return self._get_val_str(_N_HOSTNAME)

    def _hostname(self, hn):
        self.set_parm_value(_N_HOSTNAME, hn)

    @property
    def lpar_id(self):
        """Small integer partition ID, not UUID."""
        return self._get_val_int(_N_LPARID)

    def _lpar_id(self, new_lpar_id):
        self.set_parm_value(_N_LPARID, str(new_lpar_id))

    @property
    def mtms(self):
        """MTMS Element wrapper of the system hosting the Node (VIOS)."""
        return mtmwrap.MTMS.wrap(self._find(mtmwrap.MTMS_ROOT))

    def _mtms(self, new_mtms):
        """Sets the MTMS of the Node.

        :param new_mtms: May be either a string of the form 'MT-M*S' or a
                         mtms.MTMS ElementWrapper.
        """
        if not isinstance(new_mtms, mtmwrap.MTMS):
            new_mtms = mtmwrap.MTMS.bld(self.adapter, new_mtms)
        self.inject(new_mtms.element)

    @property
    def vios_uri(self):
        """The URI of the VIOS.

        This is only set if the VIOS is on this system!
        """
        return self.get_href(_N_VIOS_LINK, one_result=True)

    def _vios_uri(self, new_uri):
        self.set_href(_N_VIOS_LINK, new_uri)

    @property
    def vios_uuid(self):
        """The UUID of the Node (VIOS).

        This is only set if the VIOS is on this system!
        """
        uri = self.vios_uri
        if uri is not None:
            return u.get_req_path_uuid(uri, preserve_case=True)

    @property
    def state(self):
        return self._get_val_str(_N_STATE)
