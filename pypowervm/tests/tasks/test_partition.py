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

"""Tests for pypowervm.tasks.partition."""

import mock
import testtools

import pypowervm.const as c
import pypowervm.exceptions as ex
import pypowervm.tasks.partition as tpar
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as fx
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.base_partition as bp
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.virtual_io_server as vios


LPAR_FEED_WITH_MGMT = 'lpar.txt'
VIO_FEED_WITH_MGMT = 'fake_vios_feed.txt'
LPAR_FEED_NO_MGMT = 'lpar_ibmi.txt'
VIO_FEED_NO_MGMT = 'fake_vios_feed2.txt'


def mock_vios(name, state, rmc_state, is_mgmt=False, uptime=3601):
    ret = mock.Mock()
    ret.configure_mock(name=name, state=state, rmc_state=rmc_state,
                       is_mgmt_partition=is_mgmt, uptime=uptime)
    return ret


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
        self.adpt.read.side_effect = [self.nomgmt_vio, self.mgmt_lpar]

        mgmt_w = tpar.get_mgmt_partition(self.adpt)
        self.assertTrue(mgmt_w.is_mgmt_partition)
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', mgmt_w.uuid)
        self.assertIsInstance(mgmt_w, lpar.LPAR)
        self.assertEqual(2, self.adpt.read.call_count)

    def test_get_mgmt_vio(self):
        "Happy path where the LPAR is the mgmt VM is a VIOS."
        self.adpt.read.side_effect = [self.mgmt_vio, self.nomgmt_lpar]

        mgmt_w = tpar.get_mgmt_partition(self.adpt)
        self.assertTrue(mgmt_w.is_mgmt_partition)
        self.assertEqual('7DBBE705-E4C4-4458-8223-3EBE07015CA9', mgmt_w.uuid)
        self.assertIsInstance(mgmt_w, vios.VIOS)
        self.assertEqual(1, self.adpt.read.call_count)

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
        mock_lp_search.reset_mock()
        mock_lp_search.return_value = []
        mock_vio_search.return_value = [vios.VIOS.wrap(self.mgmt_vio)[0]]
        mock_my_id.return_value = 2
        my_w = tpar.get_this_partition(self.adpt)
        self.assertEqual(2, my_w.id)
        self.assertEqual('1300C76F-9814-4A4D-B1F0-5B69352A7DEA', my_w.uuid)
        mock_lp_search.assert_not_called()
        mock_vio_search.assert_called_with(self.adpt, id=2)

        # Bad path - no hits
        mock_lp_search.return_value = []
        mock_vio_search.return_value = []
        self.assertRaises(ex.ThisPartitionNotFoundException,
                          tpar.get_this_partition, self.adpt)

    def test_has_physical_io(self):
        """test partition has physical io."""
        part_w = mock.Mock(io_config=mock.Mock(
            io_slots=[mock.Mock(description='1 Gigabit Ethernet (UTP) 4 '
                                'Port Adapter PCIE  Short')]))
        self.assertTrue(tpar.has_physical_io(part_w))

        part_w = mock.Mock(io_config=mock.Mock(
            io_slots=[mock.Mock(description='test Graphics 3.0 test')]))
        self.assertFalse(tpar.has_physical_io(part_w))

        part_w = mock.Mock(io_config=mock.Mock(
            io_slots=[mock.Mock(description='My 3D Controller test')]))
        self.assertFalse(tpar.has_physical_io(part_w))

        part_w = mock.Mock(io_config=mock.Mock(io_slots=[]))
        self.assertFalse(tpar.has_physical_io(part_w))


class TestVios(twrap.TestWrapper):
    file = 'fake_vios_feed2.txt'
    wrapper_class_to_test = vios.VIOS

    def setUp(self):
        super(TestVios, self).setUp()
        sleep_p = mock.patch('time.sleep')
        self.mock_sleep = sleep_p.start()
        self.addCleanup(sleep_p.stop)
        vioget_p = mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
        self.mock_vios_get = vioget_p.start()
        self.addCleanup(vioget_p.stop)

    def test_get_active_vioses(self):
        self.mock_vios_get.return_value = self.entries
        vioses = tpar.get_active_vioses(self.adpt)
        self.assertEqual(1, len(vioses))
        self.mock_vios_get.assert_called_once_with(self.adpt, xag=())
        vio = vioses[0]
        self.assertEqual(bp.LPARState.RUNNING, vio.state)
        self.assertEqual(bp.RMCState.ACTIVE, vio.rmc_state)
        self.mock_vios_get.assert_called_once_with(self.adpt, xag=())

        self.mock_vios_get.reset_mock()

        # Test with actual xag.  find_min equal to the number found - works.
        vioses = tpar.get_active_vioses(self.adpt, xag='xaglist', find_min=1)
        self.assertEqual(1, len(vioses))
        vio = vioses[0]
        self.assertEqual(bp.LPARState.RUNNING, vio.state)
        self.assertEqual(bp.RMCState.ACTIVE, vio.rmc_state)
        self.mock_vios_get.assert_called_once_with(self.adpt, xag='xaglist')

        # Violates find_min
        self.assertRaises(ex.NotEnoughActiveVioses, tpar.get_active_vioses,
                          self.adpt, find_min=2)

    def test_get_active_vioses_w_vios_wraps(self):
        mock_vios1 = mock_vios('vios1', 'running', 'active')
        mock_vios2 = mock_vios('vios2', 'running', 'inactive')
        mock_vios3 = mock_vios('mgmt', 'running', 'inactive', is_mgmt=True)
        vios_wraps = [mock_vios1, mock_vios2, mock_vios3]

        vioses = tpar.get_active_vioses(self.adpt, vios_wraps=vios_wraps)
        self.assertEqual(2, len(vioses))
        self.mock_vios_get.assert_not_called()

        # The first should be the mgmt partition
        vio = vioses[0]
        self.assertEqual(bp.LPARState.RUNNING, vio.state)
        self.assertEqual(bp.RMCState.INACTIVE, vio.rmc_state)

        # The second should be the active one
        vio = vioses[1]
        self.assertEqual(bp.LPARState.RUNNING, vio.state)
        self.assertEqual(bp.RMCState.ACTIVE, vio.rmc_state)
        self.mock_vios_get.assert_not_called()

    def test_get_physical_wwpns(self):
        self.mock_vios_get.return_value = self.entries
        expected = {'21000024FF649104'}
        result = set(tpar.get_physical_wwpns(self.adpt))
        self.assertSetEqual(expected, result)

    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    @mock.patch('pypowervm.utils.transaction.FeedTask')
    def test_build_active_vio_feed_task(self, mock_feed_task,
                                        mock_get_active_vioses):
        mock_get_active_vioses.return_value = ['vios1', 'vios2']
        mock_feed_task.return_value = 'mock_feed'
        self.assertEqual('mock_feed', tpar.build_active_vio_feed_task('adpt'))
        mock_get_active_vioses.assert_called_once_with(
            'adpt', xag=(c.XAG.VIO_STOR, c.XAG.VIO_SMAP, c.XAG.VIO_FMAP),
            find_min=1)

    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    def test_build_tx_feed_task_w_empty_feed(self, mock_get_active_vioses):
        mock_get_active_vioses.return_value = []
        self.assertRaises(
            ex.FeedTaskEmptyFeed, tpar.build_active_vio_feed_task,
            mock.MagicMock())

    def _mk_mock_vioses(self):
        # No
        mock_vios1 = mock_vios('vios1', bp.LPARState.NOT_ACTIVATED,
                               bp.RMCState.INACTIVE)
        # No
        mock_vios2 = mock_vios('vios2', bp.LPARState.RUNNING,
                               bp.RMCState.BUSY)
        # Yes
        mock_vios3 = mock_vios('vios3', bp.LPARState.RUNNING,
                               bp.RMCState.UNKNOWN)
        # No
        mock_vios4 = mock_vios('vios4', bp.LPARState.UNKNOWN,
                               bp.RMCState.ACTIVE)
        # No
        mock_vios5 = mock_vios('vios5', bp.LPARState.RUNNING,
                               bp.RMCState.ACTIVE)
        # Yes
        mock_vios6 = mock_vios('vios6', bp.LPARState.RUNNING,
                               bp.RMCState.INACTIVE)

        # No
        mock_vios7 = mock_vios('vios7', bp.LPARState.RUNNING,
                               bp.RMCState.INACTIVE, is_mgmt=True)

        return [mock_vios1, mock_vios2, mock_vios3, mock_vios4, mock_vios5,
                mock_vios6, mock_vios7]

    @mock.patch('pypowervm.tasks.partition.LOG.warning')
    def test_timeout_short(self, mock_warn):
        """Short timeout because relevant VIOSes have been up a while."""

        self.mock_vios_get.return_value = self._mk_mock_vioses()

        tpar.validate_vios_ready('adap')
        # We slept 120s, (24 x 5s) because all VIOSes have been up >1h
        self.assertEqual(24, self.mock_sleep.call_count)
        self.mock_sleep.assert_called_with(5)
        # We wound up with rmc_down_vioses
        mock_warn.assert_called_once_with(mock.ANY, {'time': 120,
                                                     'vioses': 'vios3, vios6'})
        # We didn't raise - because some VIOSes were okay.

    @mock.patch('pypowervm.tasks.partition.LOG.warning')
    def test_rmc_down_vioses(self, mock_warn):
        """Time out waiting for up/inactive partitions, but succeed."""

        vioses = self._mk_mock_vioses()
        # This one booted "recently"
        vioses[5].uptime = 3559
        self.mock_vios_get.return_value = vioses

        tpar.validate_vios_ready('adap')
        # We slept 600s, (120 x 5s) because one VIOS booted "recently"
        self.assertEqual(120, self.mock_sleep.call_count)
        self.mock_sleep.assert_called_with(5)
        # We wound up with rmc_down_vioses
        mock_warn.assert_called_once_with(mock.ANY, {'time': 600,
                                                     'vioses': 'vios3, vios6'})
        # We didn't raise - because some VIOSes were okay.

    @mock.patch('pypowervm.tasks.partition.LOG.warning')
    def test_no_vioses(self, mock_warn):
        """In the (highly unusual) case of no VIOSes, no warning, but raise."""
        self.mock_vios_get.return_value = []
        self.assertRaises(ex.ViosNotAvailable, tpar.validate_vios_ready, 'adp')
        mock_warn.assert_not_called()

    @mock.patch('pypowervm.tasks.partition.LOG.warning')
    def test_max_wait_on_exception(self, mock_warn):
        """VIOS.get raises repeatedly until max_wait_time is exceeded."""
        self.mock_vios_get.side_effect = ValueError('foo')
        self.assertRaises(ex.ViosNotAvailable, tpar.validate_vios_ready, 'adp',
                          10)
        self.assertEqual(mock_warn.call_count, 3)

    @mock.patch('pypowervm.tasks.partition.LOG.warning')
    def test_exception_and_good_path(self, mock_warn):
        """VIOS.get raises, then succeeds with some halfsies, then succeeds."""
        vios1_good = mock_vios('vios1', bp.LPARState.RUNNING,
                               bp.RMCState.BUSY)
        vios2_bad = mock_vios('vios2', bp.LPARState.RUNNING,
                              bp.RMCState.UNKNOWN)
        vios2_good = mock_vios('vios2', bp.LPARState.RUNNING,
                               bp.RMCState.ACTIVE)
        self.mock_vios_get.side_effect = (ValueError('foo'),
                                          [vios1_good, vios2_bad],
                                          [vios1_good, vios2_good])
        tpar.validate_vios_ready('adap')
        self.assertEqual(3, self.mock_vios_get.call_count)
        self.assertEqual(2, self.mock_sleep.call_count)
        mock_warn.assert_called_once_with(mock.ANY)

    @mock.patch('pypowervm.tasks.partition.get_mgmt_partition')
    @mock.patch('pypowervm.wrappers.logical_partition.LPAR.get')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
    def test_get_partitions(self, mock_vio_get, mock_lpar_get, mock_mgmt_get):
        adpt = mock.Mock()

        # Test with the MGMT as a VIOS
        mgmt = mock.Mock(uuid='1')
        vioses = [mock.Mock(uuid='2'), mgmt]
        lpars = [mock.Mock(uuid='3'), mock.Mock(uuid='4')]

        mock_mgmt_get.return_value = mgmt
        mock_vio_get.return_value = vioses
        mock_lpar_get.return_value = lpars

        # Basic case
        self.assertEqual(vioses + lpars, tpar.get_partitions(adpt))

        # Different permutations
        self.assertEqual(lpars + [mgmt], tpar.get_partitions(
            adpt, vioses=False, mgmt=True))
        self.assertEqual(vioses, tpar.get_partitions(
            adpt, lpars=False, mgmt=True))

        # Now test with the MGMT as a LPAR
        vioses = [mock.Mock(uuid='2')]
        lpars = [mock.Mock(uuid='3'), mock.Mock(uuid='4'), mgmt]

        mock_vio_get.return_value = vioses
        mock_lpar_get.return_value = lpars

        # Basic case
        self.assertEqual(vioses + lpars, tpar.get_partitions(adpt))

        # Different permutations
        self.assertEqual(lpars, tpar.get_partitions(
            adpt, vioses=False, mgmt=True))
        self.assertEqual(vioses + [mgmt], tpar.get_partitions(
            adpt, lpars=False, mgmt=True))
