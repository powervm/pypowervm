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

import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.constants as c
from pypowervm.wrappers import job
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)


def crt_cluster_ssp(adapter, clust_name, ssp_name, repos_pv, first_node,
                    data_pv_list):
    """Creates a Cluster/SharedStoragePool via the ClusterCreate Job.

    The Job takes two parameters: clusterXml and sspXml.

    :param adapter: The pypowervm.adapter.Adapter for REST communication.
    :param clust_name: String name for the Cluster.
    :param ssp_name: String name for the SharedStoragePool.
    :param repos_pv: storage.PV representing the repository hdisk. The name and
                     udid properties must be specified.
    :param first_node: cluster.Node representing the initial VIOS in the
                       cluster. (Cluster creation must be done with a single
                       node; other nodes may be added later.)  The Node wrapper
                       must contain either
                       o mtms, lpar_id, AND hostname; or
                       o vios_uri
                       The indicated node must be able to see each disk.
    :param data_pv_list: Iterable of storage.PV instances to use as the data
                         volume(s) for the SharedStoragePool.
    """
    # Pull down the ClusterCreate Job template
    jresp = adapter.read(c.CLUSTER, suffix_type=c.SUFFIX_TYPE_DO,
                         suffix_parm='Create')
    jwrap = job.Job.wrap(jresp.entry)

    cluster = clust.Cluster(
        name=clust_name, repos_pv=repos_pv, node_list=[first_node])

    ssp = stor.SSP(name=ssp_name, data_pv_list=data_pv_list)

    # Job parameters are CDATA containing XML of above
    jparams = [
        jwrap.create_job_parameter(
            'clusterXml', cluster.toxmlstring(), cdata=True),
        jwrap.create_job_parameter(
            'sspXml', ssp.toxmlstring(), cdata=True)]
    jwrap.run_job(adapter, None, job_parms=jparams)
    return jwrap