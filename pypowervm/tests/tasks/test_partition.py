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

"""Tests for pypowervm.tasks.partition."""

import mock
import testtools

import pypowervm.exceptions as ex
import pypowervm.tasks.partition as tpar
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as fx
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.virtual_io_server as vios

LPAR_FEED_WITH_MGMT = 'lpar.txt'
VIO_FEED_WITH_MGMT = 'fake_vios_feed.txt'
LPAR_FEED_NO_MGMT = 'lpar_ibmi.txt'
VIO_FEED_NO_MGMT = 'fake_vios_feed2.txt'


class TestPartition(testtools.TestCase):

    def setUp(self):
        super(TestPartition, self).setUp()
        self.adpt = self.useFixture(
            fx.AdapterFx(traits=fx.RemotePVMTraits)).adpt
        self.mgmt_vio = tju.load_file(VIO_FEED_WITH_MGMT, self.adpt)
        self.mgmt_lpar = tju.load_file(LPAR_FEED_WITH_MGMT, self.adpt)
        self.nomgmt_vio = tju.load_file(VIO_FEED_NO_MGMT, self.adpt)
        self.nomgmt_lpar = tju.load_file(LPAR_FEED_NO_MGMT, self.adpt)

    def test_get_mgmt_lpar(self):
        "Happy path where the LPAR is the mgmt VM is a LPAR."
        self.adpt.read.side_effect = [self.mgmt_lpar, self.nomgmt_vio]

        mgmt_w = tpar.get_mgmt_partition(self.adpt)
        self.assertTrue(mgmt_w.is_mgmt_partition)
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', mgmt_w.uuid)
        self.assertIsInstance(mgmt_w, lpar.LPAR)

    def test_get_mgmt_vio(self):
        "Happy path where the LPAR is the mgmt VM is a VIOS."
        self.adpt.read.side_effect = [self.nomgmt_lpar, self.mgmt_vio]

        mgmt_w = tpar.get_mgmt_partition(self.adpt)
        self.assertTrue(mgmt_w.is_mgmt_partition)
        self.assertEqual('7DBBE705-E4C4-4458-8223-3EBE07015CA9', mgmt_w.uuid)
        self.assertIsInstance(mgmt_w, vios.VIOS)

    def test_get_mgmt_multiple(self):
        """Failure path with multiple mgmt VMs."""
        self.adpt.read.side_effect = [self.mgmt_lpar, self.mgmt_vio]

        self.assertRaises(ex.ManagementPartitionNotFoundException,
                          tpar.get_mgmt_partition, self.adpt)

    def test_get_mgmt_none(self):
        """Failure path with no mgmt VMs."""
        self.adpt.read.side_effect = [self.nomgmt_lpar, self.nomgmt_vio]

        self.assertRaises(ex.ManagementPartitionNotFoundException,
                          tpar.get_mgmt_partition, self.adpt)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.search')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR.search')
    @mock.patch('pypowervm.util.my_partition_id')
    def test_get_me(self, mock_my_id, mock_lp_search, mock_vio_search):
        """Test get_this_partition()."""
        # Good path - one hit on LPAR
        mock_lp_search.return_value = [lpar.LPAR.wrap(self.mgmt_lpar)[0]]
        mock_vio_search.return_value = []
        mock_my_id.return_value = 9
        my_w = tpar.get_this_partition(self.adpt)
        self.assertEqual(9, my_w.id)
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', my_w.uuid)
        mock_lp_search.assert_called_with(self.adpt, id=9)
        mock_vio_search.assert_called_with(self.adpt, id=9)

        # Good path - one hit on VIOS
        mock_lp_search.return_value = []
        mock_vio_search.return_value = [vios.VIOS.wrap(self.mgmt_vio)[0]]
        mock_my_id.return_value = 2
        my_w = tpar.get_this_partition(self.adpt)
        self.assertEqual(2, my_w.id)
        self.assertEqual('1300C76F-9814-4A4D-B1F0-5B69352A7DEA', my_w.uuid)
        mock_lp_search.assert_called_with(self.adpt, id=2)
        mock_vio_search.assert_called_with(self.adpt, id=2)

        # Bad path - multiple hits
        mock_lp_search.return_value = lpar.LPAR.wrap(self.mgmt_lpar)
        self.assertRaises(ex.ThisPartitionNotFoundException,
                          tpar.get_this_partition, self.adpt)

        # Bad path - no hits
        mock_lp_search.return_value = []
        mock_vio_search.return_value = []
        self.assertRaises(ex.ThisPartitionNotFoundException,
                          tpar.get_this_partition, self.adpt)
