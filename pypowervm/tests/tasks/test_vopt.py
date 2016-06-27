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

import mock
import testtools

from pypowervm import exceptions as pvm_ex
from pypowervm.tasks import vopt
from pypowervm.tests import test_fixtures as pvm_fx


class TestVOpt(testtools.TestCase):
    """Tests the vopt file."""

    def setUp(self):
        super(TestVOpt, self).setUp()

        self.apt = self.useFixture(pvm_fx.AdapterFx()).adpt

        # Wipe out the static variables, so that the re-validate is called
        vopt._cur_vios_uuid = None
        vopt._cur_vg_uuid = None

    @mock.patch('pypowervm.wrappers.storage.VG.get')
    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    def test_validate_vopt_vg1(self, mock_vios_get, mock_vg_get):
        """One VIOS, rootvg found; locals are set."""
        # Init objects to test with
        mock_vg = mock.Mock()
        mock_vg.configure_mock(name='rootvg',
                               uuid='1e46bbfd-73b6-3c2a-aeab-a1d3f065e92f',
                               vmedia_repos=['repo'])
        mock_vg_get.return_value = [mock_vg]
        mock_vios = mock.Mock()
        mock_vios.configure_mock(name='the_vios', uuid='vios_uuid',
                                 rmc_state='active')
        mock_vios_get.return_value = [mock_vios]

        # Run
        vio_ret_uuid, vg_ret_uuid = vopt.validate_vopt_repo_exists(self.apt)
        self.assertEqual('vios_uuid', vio_ret_uuid)
        self.assertEqual('1e46bbfd-73b6-3c2a-aeab-a1d3f065e92f', vg_ret_uuid)

        # Validate
        self.assertEqual('1e46bbfd-73b6-3c2a-aeab-a1d3f065e92f',
                         vopt._cur_vg_uuid)
        self.assertEqual('vios_uuid', vopt._cur_vios_uuid)

    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    @mock.patch('pypowervm.wrappers.storage.VG.get')
    @mock.patch('pypowervm.wrappers.storage.VMediaRepos.bld')
    def test_validate_vopt_vg2(self, mock_vmr_bld, mock_vg_get, mock_vios_get):
        """Dual VIOS, multiple VGs, repos on non-rootvg."""
        vwrap1 = mock.Mock()
        vwrap1.configure_mock(name='vio1', rmc_state='active', uuid='vio_id1',
                              is_mgmt_partition=False)
        vwrap2 = mock.Mock()
        vwrap2.configure_mock(name='vio2', rmc_state='active', uuid='vio_id2',
                              is_mgmt_partition=False)
        mock_vios_get.return_value = [vwrap1, vwrap2]
        vg1 = mock.Mock()
        vg1.configure_mock(name='rootvg', vmedia_repos=[], uuid='vg1')
        vg2 = mock.Mock()
        vg2.configure_mock(name='other1vg', vmedia_repos=[], uuid='vg2')
        vg3 = mock.Mock()
        vg3.configure_mock(name='rootvg', vmedia_repos=[], uuid='vg3')
        vg4 = mock.Mock()
        vg4.configure_mock(name='other2vg', vmedia_repos=[1], uuid='vg4')

        # 1: Find the media repos on non-rootvg on the second VIOS
        mock_vg_get.side_effect = [[vg1, vg2], [vg3, vg4]]

        vio_ret_uuid, vg_ret_uuid = vopt.validate_vopt_repo_exists(self.apt)
        self.assertEqual('vio_id2', vio_ret_uuid)
        self.assertEqual('vg4', vg_ret_uuid)

        mock_vios_get.reset_mock()
        mock_vg_get.reset_mock()

        # 2: At this point, the statics are set.  If we validate again, and the
        # VG.get returns the right one, we should bail out early.
        mock_vg_get.side_effect = None
        mock_vg_get.return_value = vg4

        vio_ret_uuid, vg_ret_uuid = vopt.validate_vopt_repo_exists(self.apt)
        self.assertEqual('vio_id2', vio_ret_uuid)
        self.assertEqual('vg4', vg_ret_uuid)

        # Statics unchanged
        self.assertEqual('vg4', vopt._cur_vg_uuid)
        self.assertEqual('vio_id2', vopt._cur_vios_uuid)

        # We didn't have to query the VIOS
        mock_vios_get.assert_not_called()
        # We only did VG.get once
        self.assertEqual(1, mock_vg_get.call_count)

        mock_vg_get.reset_mock()

        # 3: Same again, but this time the repos is somewhere else.  We should
        # find it.
        vg4.vmedia_repos = []
        vg2.vmedia_repos = [1]
        # The first VG.get is looking for the already-set repos.  The second
        # will be the feed from the first VIOS.  There should be no third call,
        # since we should find the repos on VIOS 2.
        mock_vg_get.side_effect = [vg4, [vg1, vg2]]

        vio_ret_uuid, vg_ret_uuid = vopt.validate_vopt_repo_exists(self.apt)
        self.assertEqual('vio_id1', vio_ret_uuid)
        self.assertEqual('vg2', vg_ret_uuid)

        # And the static values
        self.assertEqual('vg2', vopt._cur_vg_uuid)
        self.assertEqual('vio_id1', vopt._cur_vios_uuid)

        mock_vg_get.reset_mock()
        mock_vios_get.reset_mock()

        # 4: No repository anywhere - need to create one.  The default VG name
        # (rootvg) exists in multiple places.  Ensure we create in the first
        # one, for efficiency.
        vg2.vmedia_repos = []
        mock_vg_get.side_effect = [vg1, [vg1, vg2], [vg3, vg4]]
        vg1.update.return_value = vg1

        vio_ret_uuid, vg_ret_uuid = vopt.validate_vopt_repo_exists(self.apt)
        self.assertEqual('vio_id1', vio_ret_uuid)
        self.assertEqual('vg1', vg_ret_uuid)

        self.assertEqual('vg1', vopt._cur_vg_uuid)
        self.assertEqual('vio_id1', vopt._cur_vios_uuid)
        self.assertEqual([mock_vmr_bld.return_value], vg1.vmedia_repos)

        mock_vg_get.reset_mock()
        mock_vios_get.reset_mock()
        vg1 = mock.MagicMock()

        # 5: No repos, need to create one.  But not on the mgmt partition.
        vwrap1.configure_mock(name='vio1', rmc_state='active', uuid='vio_id1',
                              is_mgmt_partition=True)
        vg3.vmedia_repos = []
        mock_vg_get.side_effect = [vg1, [vg1, vg2], [vg3, vg4]]
        vg3.update.return_value = vg3

        vio_ret_uuid, vg_ret_uuid = vopt.validate_vopt_repo_exists(self.apt)
        self.assertEqual('vio_id2', vio_ret_uuid)
        self.assertEqual('vg3', vg_ret_uuid)

        self.assertEqual('vg3', vopt._cur_vg_uuid)
        self.assertEqual('vio_id2', vopt._cur_vios_uuid)
        self.assertEqual([mock_vmr_bld.return_value], vg3.vmedia_repos)

        mock_vg_get.reset_mock()
        mock_vios_get.reset_mock()
        vg3 = mock.MagicMock()

        # 6: No repos, and a configured VG name that doesn't exist
        vwrap1.configure_mock(name='vio1', rmc_state='active', uuid='vio_id1',
                              is_mgmt_partition=False)
        vg4.vmedia_repos = []
        mock_vg_get.side_effect = [vg1, [vg1, vg2], [vg3, vg4]]

        self.assertRaises(pvm_ex.NoMediaRepoVolumeGroupFound,
                          vopt.validate_vopt_repo_exists, self.apt,
                          vopt_media_volume_group='mythicalvg')

        # 7: No repos - need to create.  Make sure conf setting is honored.
        vg1.vmedia_repos = []

        mock_vg_get.side_effect = [vg1, [vg1, vg2], [vg3, vg4]]
        vg4.update.return_value = vg4

        vio_ret_uuid, vg_ret_uuid = vopt.validate_vopt_repo_exists(
            self.apt, vopt_media_volume_group='other2vg')
        self.assertEqual('vio_id2', vio_ret_uuid)
        self.assertEqual('vg4', vg_ret_uuid)

        self.assertEqual('vg4', vopt._cur_vg_uuid)
        self.assertEqual('vio_id2', vopt._cur_vios_uuid)
        self.assertEqual([mock_vmr_bld.return_value], vg4.vmedia_repos)
        vg1.update.assert_not_called()
