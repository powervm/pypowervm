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

"""Tests for properties of EntryWrapper/ElementWrapper subclasses."""

import testtools

import pypowervm.const as c
from pypowervm.wrappers import base_partition
from pypowervm.wrappers import cluster
from pypowervm.wrappers import http_error
from pypowervm.wrappers import job
from pypowervm.wrappers import logical_partition
from pypowervm.wrappers import managed_system
from pypowervm.wrappers import management_console
from pypowervm.wrappers import monitor
from pypowervm.wrappers import mtms
from pypowervm.wrappers import network
from pypowervm.wrappers import shared_proc_pool
from pypowervm.wrappers import storage
from pypowervm.wrappers import vios_file
from pypowervm.wrappers import virtual_io_server


class TestXAGs(testtools.TestCase):

    def verify_xags(self, wcls, expected_xags):
        """Verify extended attribute groups for properties of a wrapper class.

        :param wcls: The pypowervm.wrappers.entry_wrapper.Wrapper subclass to
                     test.
        :param expected_xags: A dict mapping wcls's property names to their
                              respective extended attribute group names.  Can
                              (should) only include those properties for which
                              an extended attribute group is registered.  (If
                              it contains any other properties, the value must
                              be None.)  Format is { prop_name: xag_name }
        """
        for prop in dir(wcls):
            actual = wcls.get_xag_for_prop(prop)
            expected = expected_xags.get(prop, None)
            self.assertEqual(expected, actual,
                             message="%s.%s" % (wcls.__name__, prop))

    def test_xags(self):
        """Verify xags associated with properties of wrapper classes."""
        # The following wrapper classes have no properties with xags
        for wcls in (base_partition.DedicatedProcessorConfiguration,
                     base_partition.IOAdapter,
                     base_partition.IOSlot,
                     base_partition.IOSlot.AssociatedIOSlot,
                     base_partition.PartitionCapabilities,
                     base_partition.PartitionIOConfiguration,
                     base_partition.PartitionMemoryConfiguration,
                     base_partition.PartitionProcessorConfiguration,
                     base_partition.PhysFCAdapter,
                     base_partition.PhysFCPort,
                     base_partition.SharedProcessorConfiguration,
                     base_partition.TaggedIO,
                     cluster.Cluster,
                     cluster.Node,
                     http_error.HttpError,
                     job.Job,
                     logical_partition.LPAR,
                     managed_system.ASIOConfig,
                     managed_system.IOSlot,
                     managed_system.System,
                     management_console.AuthorizedKey,
                     management_console.ConsoleNetworkInterfaces,
                     management_console.ManagementConsole,
                     management_console.NetworkInterfaces,
                     monitor.PcmPref,
                     mtms.MTMS,
                     network.CNA,
                     network.EthernetBackingDevice,
                     network.LoadGroup,
                     network.NetBridge,
                     network.SEA,
                     network.TrunkAdapter,
                     network.VNet,
                     network.VSwitch,
                     shared_proc_pool.SharedProcPool,
                     storage.LU,
                     storage.PV,
                     storage.SSP,
                     storage.VClientStorageAdapterElement,
                     storage.VDisk,
                     storage.VFCClientAdapter,
                     storage.VG,
                     storage.VMediaRepos,
                     storage.VOptMedia,
                     storage.VServerStorageAdapterElement,
                     vios_file.File,
                     virtual_io_server.LinkAggrIOAdapterChoice,
                     virtual_io_server.VFCMapping,
                     virtual_io_server.VSCSIMapping):
            self.verify_xags(wcls, {})

        # The following wrapper classes do have properties with xags
        self.verify_xags(virtual_io_server.VIOS, {
            'media_repository': c.XAG.VIO_STOR,
            'ip_addresses': c.XAG.VIO_NET,
            'vfc_mappings': c.XAG.VIO_FMAP,
            'scsi_mappings': c.XAG.VIO_SMAP,
            'seas': c.XAG.VIO_NET,
            'trunk_adapters': c.XAG.VIO_NET,
            'phys_vols': c.XAG.VIO_STOR,
            'io_adpts_for_link_agg': c.XAG.VIO_NET
        })
