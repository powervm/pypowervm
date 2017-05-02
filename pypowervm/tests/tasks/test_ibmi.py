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


import fixtures
import mock
import testtools

from pypowervm import exceptions as pvm_exc
from pypowervm.tasks import ibmi
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as pvm_fx
import pypowervm.wrappers.base_partition as pvm_bp
from pypowervm.wrappers import virtual_io_server as pvm_vios

VIOS_FEED = 'fake_vios_feed.txt'


class TestIBMi(testtools.TestCase):
    """Unit Tests for IBMi changes."""

    def setUp(self, traits_type):
        super(TestIBMi, self).setUp()
        self.traits = traits_type
        self.apt = self.useFixture(pvm_fx.AdapterFx(
            traits=self.traits)).adpt
        self.vio_feed = pvm_vios.VIOS.wrap(
            tju.load_file(VIOS_FEED, self.apt))
        self.vioslist = [self.vio_feed[0], self.vio_feed[1]]

    @staticmethod
    def _validate_settings(self, boot_type, traits_type, entry):
        self.assertEqual('b', entry.desig_ipl_src)
        self.assertEqual('normal', entry.keylock_pos)

        if traits_type == pvm_fx.LocalPVMTraits:
            self.assertEqual('HMC', entry.io_config.tagged_io.console)
        else:
            self.assertEqual('HMC', entry.io_config.tagged_io.console)
        if boot_type == 'npiv':
            self.assertEqual('3', entry.io_config.tagged_io.load_src)
            self.assertEqual('4', entry.io_config.tagged_io.alt_load_src)
        else:
            self.assertEqual('2', entry.io_config.tagged_io.load_src)
            self.assertEqual('2', entry.io_config.tagged_io.alt_load_src)

    def _validate_ibmi_settings(self, mock_viosw):
        mock_viosw.return_value = self.vioslist
        mock_lparw = mock.MagicMock()
        mock_lparw.id = 22

        # Test update load source with npiv boot
        boot_type = 'npiv'
        entry = ibmi.update_ibmi_settings(self.apt, mock_lparw, boot_type)
        self._validate_settings(self, boot_type, self.traits, entry)

        # Test update load source with vscsi boot
        boot_type = 'vscsi'
        entry = ibmi.update_ibmi_settings(self.apt, mock_lparw, boot_type)
        self._validate_settings(self, boot_type, self.traits, entry)

        # Test bad path if load source is not found
        mock_lparw.reset_mock()
        mock_lparw.id = 220
        boot_type = 'vscsi'
        self.assertRaises(pvm_exc.IBMiLoadSourceNotFound,
                          ibmi.update_ibmi_settings, self.apt, mock_lparw,
                          boot_type)


class TestIBMiWithHMC(TestIBMi):
    """Unit Tests for IBMi changes for HMC."""

    def setUp(self):
        super(TestIBMiWithHMC, self).setUp(pvm_fx.RemoteHMCTraits)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.wrap')
    def test_update_ibmi_settings(self, mock_viosw):
        self._validate_ibmi_settings(mock_viosw)


class TestIBMiWithPVM(TestIBMi):
    """Unit Tests for IBMi changes for PVM."""

    def setUp(self):
        super(TestIBMiWithPVM, self).setUp(pvm_fx.LocalPVMTraits)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.wrap')
    def test_update_ibmi_settings(self, mock_viosw):
        self._validate_ibmi_settings(mock_viosw)

    @mock.patch('pypowervm.wrappers.virtual_io_server.VIOS.wrap')
    @mock.patch('pypowervm.wrappers.virtual_io_server.VStorageMapping.'
                'client_adapter', new_callable=mock.PropertyMock,
                return_value=None)
    def test_update_ibmi_settings_w_stale_adapters(self, mock_c_adap,
                                                   mock_viosw):
        mock_lparw = mock.MagicMock()
        mock_lparw.id = 22
        self.assertRaises(pvm_exc.IBMiLoadSourceNotFound,
                          ibmi.update_ibmi_settings, self.apt,
                          mock_lparw, 'vscsi')


class TestPanelFunction(testtools.TestCase):
    def setUp(self):
        super(TestPanelFunction, self).setUp()

        self.adpt = self.useFixture(pvm_fx.AdapterFx()).adpt

        # Make it easier to validate job params: create_job_parameter returns a
        # simple 'name=value' string.
        mock_crt_jparm = self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.job.Job.create_job_parameter')).mock
        mock_crt_jparm.side_effect = (
            lambda name, value, cdata=False: '%s=%s' % (name, value))

        # Patch Job.wrap to return a mocked Job wrapper
        mock_job = mock.Mock()
        self.useFixture(fixtures.MockPatch(
            'pypowervm.wrappers.job.Job.wrap')).mock.return_value = mock_job
        self.run_job = mock_job.run_job

    def mock_partition(self, env=pvm_bp.LPARType.OS400,
                       rmc_state=pvm_bp.RMCState.ACTIVE):
        """Returns a mocked partition with the specified properties."""
        return mock.Mock(adapter=self.adpt, env=env, rmc_state=rmc_state)

    def test_ops(self):
        mock_part = self.mock_partition()
        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.CONSOLESERVICE)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=consoleservice'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.IOPDUMP)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=iopdump'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.IOPRESET)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=iopreset'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.REMOTEDSTON)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=remotedston'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.REMOTEDSTOFF)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=remotedstoff'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.RETRYDUMP)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=retrydump'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.DSTON)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=dston'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.DUMPRESTART)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=dumprestart'],
            synchronous=True, timeout=1800)
        self.run_job.reset_mock()

        ibmi.start_panel_job(mock_part,
                             ibmi.IBMiPanelOperations.DUMPRESTART,
                             synchronous=False, timeout=100)
        self.run_job.assert_called_once_with(
            mock_part.uuid, job_parms=['operation=dumprestart'],
            synchronous=False, timeout=100)
        self.run_job.reset_mock()

        self.assertRaises(pvm_exc.InvalidIBMiPanelFunctionOperation,
                          ibmi.start_panel_job, mock_part, 'NotRight')

        self.assertRaises(pvm_exc.InvalidIBMiPanelFunctionOperation,
                          ibmi.start_panel_job, mock_part, None)

    def test_exceptions(self):
        mock_part = self.mock_partition(env=pvm_bp.LPARType.AIXLINUX)
        self.assertRaises(pvm_exc.PartitionIsNotIBMi, ibmi.start_panel_job,
                          mock_part, ibmi.IBMiPanelOperations.REMOTEDSTON)

        self.assertRaises(pvm_exc.PanelFunctionRequiresPartition,
                          ibmi.start_panel_job, None,
                          ibmi.IBMiPanelOperations.REMOTEDSTON)
