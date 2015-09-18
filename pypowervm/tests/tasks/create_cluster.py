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

# This script attempts to create a real cluster on a real system using the
# cluster_ssp module.  Execute from project root directory as:
# PYTHONPATH=. python pypowervm/tests/tasks/create_cluster.py

import six

import pypowervm.adapter as adp
import pypowervm.exceptions as ex
import pypowervm.tasks.cluster_ssp as cs
import pypowervm.wrappers.cluster as clust
import pypowervm.wrappers.storage as stor

# >>>Replace the following with real values>>>
HOST = '9.1.2.3'
USER = 'hscroot'
PASS = 'abc123'

NODE_HOSTNAME = 'vios1.example.com'
NODE_MTMS = '8247-22L*1234D0A'
NODE_LPARID = 2
NODE_URI = ('https://9.1.2.3:12443/rest/api/uom/VirtualIOServer/'
            '58C9EB1D-7213-4956-A011-77D43CC4ACCC')
REPOS_UDID = '01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDAwMg=='
REPOS_NAME = 'hdisk2'
DATA1_UDID = '01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDAwMw=='
DATA1_NAME = 'hdisk3'
DATA2_UDID = '01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDAwNA=='
DATA2_NAME = 'hdisk4'
DATA3_UDID = '01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDAwNQ=='
DATA3_NAME = 'hdisk5'
# <<<Replace the foregoing with real values<<<

sess = adp.Session(HOST, USER, PASS, certpath=None)
adap = adp.Adapter(sess)

# Option 1: MTMS, LPAR_ID, Hostname
node1 = clust.Node.bld(adap, hostname=NODE_HOSTNAME, mtms=NODE_MTMS,
                       lpar_id=NODE_LPARID)

# Option 2: URI
node2 = clust.Node.bld(adap, vios_uri=NODE_URI)

repos = stor.PV.bld(adap, udid=REPOS_UDID, name=REPOS_NAME)

data_pvs = [
    stor.PV.bld(adap, udid=udid, name=name) for udid, name in (
        (DATA1_UDID, DATA1_NAME),
        (DATA2_UDID, DATA2_NAME),
        (DATA3_UDID, DATA3_NAME))]
try:
    cs.crt_cluster_ssp('clust1', 'ssp1', repos, node1, data_pvs)
except ex.JobRequestFailed as e:
    print(six.text_type(e))

adap = None
