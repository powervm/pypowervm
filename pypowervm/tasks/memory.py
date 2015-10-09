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

import math

from oslo_log import log as logging

import pypowervm.const as c
from pypowervm.i18n import _
import pypowervm.log as lgc
from pypowervm.wrappers import base_partition as pvm_bp
from pypowervm.wrappers import job
from pypowervm.wrappers import managed_system as pvm_ms

LOG = logging.getLogger(__name__)


@lgc.logcall
def calculate_memory_overhead_on_host(adapter, host_uuid,
                                      reserved_mem_data={},
                                      lmb_size=None, default=512):
    """Calculate host memory overhead.

    A certain amount of additional memory, such as memory for firmware,
    is required from the host during the creation of an instance or while
    changing an instance's memory specifications. This method queries the
    host to get the reserved PHYP memory needed for an LPAR. The
    calculation is based off of the instance's max memory requested,
    network and I/O adapter configurations, and the host's HPT ratio.
    The job response contains a value for total memory required to create
    or change the LPAR, which is desired memory plus reserved PHYP memory.

    :param adapter: pypowervm adapter
    :param host_uuid: the UUID of the host
    :param reserve_mem_data: (Optional) dictionary with values for job params
        {'desired_mem': int,
         'max_mem': int,
         'lpar_env': 'AIX/Linux' OR 'OS400',
         'num_virt_eth_adapters': int,
         'num_vscsi_adapters': int,
         'num_vfc_adapters': int}
    :param lmb_size: (Optional) logical memory block size
    :param default: (Optional) default value to use for required memory
                    overhead value if there was an error with the job
    :return overhead: reserved host memory
    :return avail_mem: available host memory
    """
    # If desired memory and maximum memory are not known, this query is
    # part of calculating host stats, and specific configurations of an
    # instance is not known. This will use the config option for a default
    # maximum memory.
    desired_mem = reserved_mem_data.get('desired_mem', 512)
    max_mem = reserved_mem_data.get('max_mem', 32768)
    # If lmb size is given, round max mem up to be a multiple
    # of lmb size. If max_mem is 0, max_mem will be set to lmb size.
    if lmb_size is not None:
        max_mem = int(math.ceil((max_mem or 1) / float(lmb_size)) *
                      int(lmb_size))
    lpar_env = reserved_mem_data.get('lpar_env', pvm_bp.LPARType.AIXLINUX)
    num_virt_eth_adapter = reserved_mem_data.get('num_virt_eth_adapters', 2)
    num_vscsi_adapter = reserved_mem_data.get('num_vscsi_adapters', 1)
    num_vfc_adapter = reserved_mem_data.get('num_vfc_adapters', 1)
    job_wrapper = job.Job.wrap(adapter.read(pvm_ms.System.schema_type,
                                            host_uuid,
                                            suffix_type=c.SUFFIX_TYPE_DO,
                                            suffix_parm=('QueryReservedMemory'
                                                         'RequiredFor'
                                                         'Partition')))

    # Create job parameters
    job_parms = [job_wrapper.create_job_parameter(
        'LogicalPartitionEnvironment', lpar_env)]
    job_parms.append(job_wrapper.create_job_parameter(
        'DesiredMemory', str(desired_mem)))
    job_parms.append(job_wrapper.create_job_parameter(
        'MaximumMemory', str(max_mem)))
    job_parms.append(job_wrapper.create_job_parameter(
        'NumberOfVirtualEthernetAdapter', str(num_virt_eth_adapter)))
    job_parms.append(job_wrapper.create_job_parameter(
        'NumberOfVirtualSCSIAdapter', str(num_vscsi_adapter)))
    job_parms.append(job_wrapper.create_job_parameter(
        'NumberOfVirtualFibreChannelAdapter', str(num_vfc_adapter)))

    try:
        job_wrapper.run_job(host_uuid, job_parms=job_parms,
                            timeout=120)
        results = job_wrapper.get_job_results_as_dict()
    except Exception as error:
        LOG.error(_("Error obtaining host memory overhead for host "
                    "with UUID '%(host)s': %(error)s.") %
                  {'host': host_uuid, 'error': error})
        LOG.debug("Defaulting required memory overhead for host with UUID "
                  "'%s' to %d MB" % (host_uuid, default))
        return default, None
    required_mem = results.get('RequiredMemory')
    avail_mem = results.get('CurrentAvailableSystemMemory')
    if required_mem is not None:
        overhead = int(required_mem) - desired_mem
    else:
        overhead = default
    if avail_mem is not None:
        avail_mem = int(avail_mem)
    return overhead, avail_mem
