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

"""Tasks specific to partitions (LPARs and VIOSes)."""

import pypowervm.exceptions as ex
import pypowervm.util as u
import pypowervm.wrappers.logical_partition as lpar


def get_mgmt_partition(adapter):
    """Get the LPAR wrapper representing the PowerVM management partition.

    :param adapter: The pypowervm.adapter.Adapter through which to query the
                    REST API.
    :return: pypowervm.wrappers.logical_partition.LPAR wrapper representing the
             management partition.
    :raise ManagementPartitionNotFoundException: if we don't find exactly one
                                                 management partition.
    """
    wraps = lpar.LPAR.search(adapter, is_mgmt_partition=True)
    if len(wraps) != 1:
        raise ex.ManagementPartitionNotFoundException(count=len(wraps))
    return wraps[0]


def get_this_partition(adapter):
    """Get the LPAR wrapper representing the node on which this method runs.

    :param adapter: The pypowervm.adapter.Adapter through which to query the
                    REST API.
    :return: pypowervm.wrappers.logical_partition.LPAR wrapper representing the
             local partition.
    :raise LocalPartitionNotFoundException: if we don't find exactly one LPAR
                                            with the local VM's short ID.
    """
    myid = u.my_partition_id()
    wraps = lpar.LPAR.search(adapter, id=myid)
    if len(wraps) != 1:
        raise ex.ThisPartitionNotFoundException(lpar_id=myid, count=len(wraps))
    return wraps[0]
