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
import retrying

import pypowervm.const as c
import pypowervm.exceptions as ex
import pypowervm.tasks.partition as tpar
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.logical_partition as lpar

from pypowervm.wrappers import base_partition as pvm_bp
from pypowervm.wrappers import virtual_io_server as vios


class TestPartition(twrap.TestWrapper):
    file = 'lpar.txt'
    wrapper_class_to_test = lpar.LPAR

    def test_get_mgmt(self):
        """Test get_mgmt_partition()."""
        self.adpt.read.return_value = self.resp
        mgmt_w = tpar.get_mgmt_partition(self.adpt)
        self.assertTrue(mgmt_w.is_mgmt_partition)
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', mgmt_w.uuid)
        with mock.patch('pypowervm.wrappers.logical_partition.LPAR.'
                        'is_mgmt_partition', return_value=False):
            self.assertRaises(ex.ManagementPartitionNotFoundException,
                              tpar.get_mgmt_partition, self.adpt)

    @mock.patch('pypowervm.wrappers.logical_partition.LPAR.search')
    @mock.patch('pypowervm.util.my_partition_id')
    def test_get_me(self, mock_my_id, mock_search):
        """Test get_this_partition()."""
        # Good path - one hit
        mock_search.return_value = [self.dwrap]
        mock_my_id.return_value = 9
        my_w = tpar.get_this_partition(self.adpt)
        self.assertEqual(9, my_w.id)
        self.assertEqual('089FFB20-5D19-4A8C-BB80-13650627D985', my_w.uuid)
        mock_search.assert_called_with(self.adpt, id=9)

        # Bad path - multiple hits
        mock_search.return_value = self.entries
        self.assertRaises(ex.ThisPartitionNotFoundException,
                          tpar.get_this_partition, self.adpt)

        # Bad path - no hits
        mock_search.return_value = []
        self.assertRaises(ex.ThisPartitionNotFoundException,
                          tpar.get_this_partition, self.adpt)


class TestVios(twrap.TestWrapper):
    file = 'fake_vios_feed2.txt'
    wrapper_class_to_test = vios.VIOS

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
    def test_get_active_vioses(self, mock_vios_get):
        mock_vios_get.return_value = self.entries
        vioses = tpar.get_active_vioses(self.adpt)
        self.assertEqual(1, len(vioses))
        mock_vios_get.assert_called_once_with(self.adpt, xag=())
        vio = vioses[0]
        self.assertEqual(pvm_bp.LPARState.RUNNING, vio.state)
        self.assertEqual(pvm_bp.RMCState.ACTIVE, vio.rmc_state)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
    def test_get_active_vioses_w_vios_wraps(self, mock_get):
        mock_vios1 = mock.Mock(state='running', rmc_state='active')
        mock_vios2 = mock.Mock(state='running', rmc_state='inactive')
        vios_wraps = [mock_vios1, mock_vios2]

        vioses = tpar.get_active_vioses(self.adpt, vios_wraps=vios_wraps)
        self.assertEqual(1, len(vioses))
        mock_get.assert_not_called()
        vio = vioses[0]
        self.assertEqual(pvm_bp.LPARState.RUNNING, vio.state)
        self.assertEqual(pvm_bp.RMCState.ACTIVE, vio.rmc_state)
        self.assertEqual(0, mock_get.call_count)

    def test_get_inactive_running_vioses(self):
        # No
        mock_vios1 = mock.Mock(
            state=pvm_bp.LPARState.NOT_ACTIVATED,
            rmc_state=pvm_bp.RMCState.INACTIVE)
        # No
        mock_vios2 = mock.Mock(
            state=pvm_bp.LPARState.RUNNING,
            rmc_state=pvm_bp.RMCState.BUSY)
        # Yes
        mock_vios3 = mock.Mock(
            state=pvm_bp.LPARState.RUNNING,
            rmc_state=pvm_bp.RMCState.UNKNOWN)
        # No
        mock_vios4 = mock.Mock(
            state=pvm_bp.LPARState.UNKNOWN,
            rmc_state=pvm_bp.RMCState.ACTIVE)
        # No
        mock_vios5 = mock.Mock(
            state=pvm_bp.LPARState.RUNNING,
            rmc_state=pvm_bp.RMCState.ACTIVE)
        # Yes
        mock_vios6 = mock.Mock(
            state=pvm_bp.LPARState.RUNNING,
            rmc_state=pvm_bp.RMCState.INACTIVE)

        self.assertEqual(
            {mock_vios6, mock_vios3}, set(tpar._get_inactive_running_vioses(
                [mock_vios1, mock_vios2, mock_vios3, mock_vios4,
                 mock_vios5, mock_vios6])))

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
    def test_get_physical_wwpns(self, mock_vios_get):
        mock_vios_get.return_value = self.entries
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
            'adpt', xag=(c.XAG.VIO_STOR, c.XAG.VIO_SMAP, c.XAG.VIO_FMAP))

    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    def test_build_tx_feed_task_w_empty_feed(self, mock_get_active_vioses):
        mock_get_active_vioses.return_value = []
        self.assertRaises(
            ex.NoActiveVios, tpar.build_active_vio_feed_task, mock.MagicMock())

    @mock.patch('retrying.retry')
    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    @mock.patch('pypowervm.tasks.partition._get_inactive_running_vioses')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.get')
    def test_is_vios_ready(self, mock_get, mock_get_inactive_vioses,
                           mock_get_active_vioses, mock_retry):
        # Validates the retry method itself.
        def validate_retry(kwargs):
            self.assertIn('retry_on_result', kwargs)
            self.assertEqual(5000, kwargs['wait_fixed'])
            self.assertEqual(300000, kwargs['stop_max_delay'])

        # Used to simulate an eventual timeout.
        def retry_timeout(**kwargs):
            # First validate the retry.
            validate_retry(kwargs)

            def one_running_inactive_vio():
                mock_vios1 = mock.Mock()
                mock_vios1.configure_mock(name='vios1')
                return [mock_vios1]

            def wrapped(_poll_for_dev):
                self.assertIsNotNone(_poll_for_dev)
                return one_running_inactive_vio
            return wrapped

        # Validate that we will eventually timeout.
        mock_retry.side_effect = retry_timeout
        mock_get_active_vioses.return_value = [mock.Mock()]

        # Shouldn't raise an error because we have active vioses
        tpar.validate_vios_ready(self.adpt)

        # Should raise an exception now because we timed out and there
        # weren't any active VIOSes
        mock_get_active_vioses.return_value = []
        self.assertRaises(
            ex.ViosNotAvailable, tpar.validate_vios_ready, self.adpt)

        # Now test where we pass through to the actual method in the retry.
        def retry_passthrough(**kwargs):
            validate_retry(kwargs)

            def wrapped(_poll_for_dev):
                return _poll_for_dev
            return wrapped

        def get_active_vioses_side_effect(adap, **kwargs):
            self.assertIsNotNone(adap)
            return kwargs['vios_wraps']

        mock_retry.side_effect = retry_passthrough

        # First run should succeed because all VIOSes should be active and
        # running
        mock_get.return_value = ['vios1', 'vios2', 'vios3', 'vios4']
        mock_get_inactive_vioses.return_value = []
        mock_get_active_vioses.side_effect = get_active_vioses_side_effect
        tpar.validate_vios_ready(self.adpt)

        # Second run should fail because we raise an exception (which retries,
        # and then eventually times out with no active VIOSes)
        mock_get.reset_mock()
        mock_get.side_effect = Exception('testing error')
        mock_get_active_vioses.reset_mock()
        mock_get_active_vioses.return_value = []
        self.assertRaises(
            ex.ViosNotAvailable, tpar.validate_vios_ready, self.adpt)

        # Last run should succeed but raise a warning because there's
        # still inactive running VIOSes
        mock_vios1, mock_vios2 = mock.Mock(), mock.Mock()
        mock_vios1.configure_mock(name='vios1')
        mock_vios2.configure_mock(name='vios2')
        mock_get_inactive_vioses.return_value = [mock_vios1, mock_vios2]
        mock_get_active_vioses.reset_mock()
        mock_get_active_vioses.side_effect = ['vios1', 'vios2']
        tpar.validate_vios_ready(self.adpt)

        def retry_exception(**kwargs):
            validate_retry(kwargs)

            def wrapped(func):
                self.assertIsNotNone(func)
                return raise_exception

            def raise_exception():
                raise retrying.RetryError('test retry error')

            return wrapped

        mock_get_active_vioses.reset_mock()
        mock_retry.side_effect = retry_exception
        mock_get_active_vioses.side_effect = [[], ['vios1', 'vios2']]
        # Test failure when retry decorator fails out with no active VIOSes
        self.assertRaises(
            ex.ViosNotAvailable, tpar.validate_vios_ready, self.adpt)

        # Test success when retry decorator fails out with at least 1 active
        # VIOS
        tpar.validate_vios_ready(self.adpt)
