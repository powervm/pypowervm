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

import mock
import testtools

import pypowervm.entities as ent
from pypowervm.tasks import migration as mig
import pypowervm.tests.tasks.util as tju
import pypowervm.tests.test_fixtures as fx
from pypowervm.wrappers import job
from pypowervm.wrappers import virtual_io_server as pvm_vios

MIGRATION_VIOS_FEED = 'fakemigration.txt'


class TestMigration(testtools.TestCase):
    """Unit Tests for Migration."""

    def setUp(self):
        super(TestMigration, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        mock_resp = mock.MagicMock()
        mock_resp.entry = ent.Entry(
            {}, ent.Element('Dummy', self.adpt), self.adpt)
        self.adpt.read.return_value = mock_resp
        self.lpar_w = mock.MagicMock()
        self.lpar_w.adapter = self.adpt
        self.lpar_w.uuid = '1234'
        self.lpar_w.id = 63
        self.lpar_w.name = 'test-lp1'

    def _get_parm_checker(self, exp_uuid, exp_job_parms, exp_timeout=None):
        # Utility method to return a dynamic parameter checker for tests

        # Build the expected job parameter strings
        exp_job_parms_str = [job.Job.create_job_parameter(k, v).toxmlstring()
                             for k, v in exp_job_parms]

        def parm_checker(uuid, job_parms=None, timeout=None):
            # Check simple parms
            self.assertEqual(exp_uuid, uuid)
            self.assertEqual(exp_timeout, timeout)

            # Check the expected and actual number of job parms are equal
            self.assertEqual(len(exp_job_parms_str), len(job_parms))

            # Ensure each parameter is in the list of expected.
            for parm in job_parms:
                self.assertIn(parm.toxmlstring(), exp_job_parms_str)

        # We return our custom checker
        return parm_checker

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_migration(self, mock_run_job):

        # Test simple call
        mock_run_job.side_effect = self._get_parm_checker(
            '1234', [(mig.TGT_MGD_SYS, 'abc')], exp_timeout=1800)
        mig.migrate_lpar(self.lpar_w, 'abc')
        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='Migrate',
                                               suffix_type='do')
        # Test all parms
        self.adpt.read.reset_mock()
        parm_list = [(mig.TGT_MGD_SYS, 'abc'),
                     (mig.TGT_RMT_HMC, 'host'),
                     (mig.TGT_RMT_HMC_USR, 'usr'),
                     (mig.VFC_MAPPINGS, '1/1/1'),
                     (mig.VSCSI_MAPPINGS, '2/2/2'),
                     (mig.DEST_MSP, 'vios1'),
                     (mig.SRC_MSP, 'vios2')]
        mock_run_job.side_effect = self._get_parm_checker(
            '1234', parm_list, exp_timeout=1800)
        mig.migrate_lpar(self.lpar_w, 'abc',
                         tgt_mgmt_svr='host', tgt_mgmt_usr='usr',
                         virtual_fc_mappings='1/1/1',
                         virtual_scsi_mappings='2/2/2',
                         dest_msp_name='vios1', source_msp_name='vios2')
        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='Migrate',
                                               suffix_type='do')
        # Test simple validation call
        self.adpt.read.reset_mock()
        mock_run_job.side_effect = self._get_parm_checker(
            '1234', [(mig.TGT_MGD_SYS, 'abc')], exp_timeout=1800)
        mock_run_job.reset_mock()
        mig.migrate_lpar(self.lpar_w, 'abc', validate_only=True)
        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='MigrateValidate',
                                               suffix_type='do')

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_migration_recover(self, mock_run_job):
        # Test simple call
        mig.migrate_recover(self.lpar_w)
        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='MigrateRecover',
                                               suffix_type='do')
        mock_run_job.assert_called_once_with(
            '1234', job_parms=[], timeout=1800)

        # Test simple call with force
        self.adpt.read.reset_mock()
        mock_run_job.reset_mock()
        mock_run_job.side_effect = self._get_parm_checker(
            '1234', [('Force', 'true')], exp_timeout=1800)
        mig.migrate_recover(self.lpar_w, force=True)

        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='MigrateRecover',
                                               suffix_type='do')

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_migration_abort(self, mock_run_job):
        # Test simple call
        mig.migrate_abort(self.lpar_w)
        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='MigrateAbort',
                                               suffix_type='do')
        mock_run_job.assert_called_once_with(
            '1234', job_parms=None, timeout=1800)

    def test_generate_mappings_to_migrate(self):
        vios_wraps = pvm_vios.VIOS.wrap(tju.load_file(MIGRATION_VIOS_FEED))
        # Test VFC Mapping strings
        vfc_mapping = mig.generate_mappings_to_migrate(self.lpar_w, vios_wraps)
        vfc_out = ['63//test-lp1//94//fcs1', '63//test-lp1//93//fcs1',
                   '63//test-lp1//92//fcs1', '63//test-lp1//85//fcs0',
                   '63//test-lp1//94//fcs0', '63//test-lp1//1//86']
        scsi_out = ['19//test-lp1//43//fcs1', '19//test-lp1//2//41',
                    '19//test-lp1//23//fcs0']
        self.assertEqual(vfc_out, vfc_mapping)
        # Test VSCSI Mappings
        self.lpar_w.id = 19
        scsi_map = mig.generate_mappings_to_migrate(self.lpar_w, vios_wraps)
        self.assertEqual(scsi_out, scsi_map)
        self.lpar_w.id = 99
        no_map = mig.generate_mappings_to_migrate(self.lpar_w, vios_wraps)
        self.assertEqual(0, len(no_map))
