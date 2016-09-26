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
import pypowervm.tests.tasks.util as u
import pypowervm.tests.test_fixtures as fx


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

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    def test_migration(self, mock_run_job):

        # Test simple call
        mock_run_job.side_effect = u.get_parm_checker(
            self, '1234', [(mig.TGT_MGD_SYS, 'abc')], exp_timeout=1800 * 4)
        mig.migrate_lpar(self.lpar_w, 'abc')
        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='Migrate',
                                               suffix_type='do')
        # Test all parms
        self.adpt.read.reset_mock()
        parm_list = [(mig.TGT_MGD_SYS, 'abc'),
                     (mig.TGT_RMT_HMC, 'host'),
                     (mig.TGT_RMT_HMC_USR, 'usr'),
                     (mig.DEST_MSP, 'vios1'),
                     (mig.SRC_MSP, 'vios2'),
                     (mig.SPP_ID, '5'),
                     (mig.OVS_OVERRIDE, '2'),
                     (mig.VLAN_BRIDGE_OVERRIDE, '2')]
        mapping_list = [(mig.VFC_MAPPINGS, ['1/1/1', '3/3/3//3']),
                        (mig.VSCSI_MAPPINGS, ['2/2/2']),
                        (mig.VLAN_MAPPINGS, ['001122334455/4',
                                             '001122334466/5/6 7'])]
        mock_run_job.side_effect = u.get_parm_checker(
            self, '1234', parm_list, exp_job_mappings=mapping_list,
            exp_timeout=1800 * 4)

        mig.migrate_lpar(self.lpar_w, 'abc',
                         tgt_mgmt_svr='host', tgt_mgmt_usr='usr',
                         virtual_fc_mappings=['1/1/1', '3/3/3//3'],
                         virtual_scsi_mappings=['2/2/2'],
                         vlan_mappings=['001122334455/4',
                                        '001122334466/5/6 7'],
                         dest_msp_name='vios1', source_msp_name='vios2',
                         spp_id='5', sdn_override=True,
                         vlan_check_override=True)
        self.adpt.read.assert_called_once_with('LogicalPartition', '1234',
                                               suffix_parm='Migrate',
                                               suffix_type='do')
        # Test simple validation call
        self.adpt.read.reset_mock()
        mock_run_job.side_effect = u.get_parm_checker(
            self, '1234', [(mig.TGT_MGD_SYS, 'abc')], exp_timeout=1800 * 4)
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
        mock_run_job.side_effect = u.get_parm_checker(
            self, '1234', [('Force', 'true')], exp_timeout=1800)
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
