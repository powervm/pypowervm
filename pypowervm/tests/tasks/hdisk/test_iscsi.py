# Copyright 2015, 2017 IBM Corp.
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
from pypowervm import exceptions as pexc
from pypowervm.tasks.hdisk import _iscsi as iscsi
import pypowervm.tests.test_fixtures as fx
from pypowervm.wrappers import job


class TestIscsi(testtools.TestCase):

    def setUp(self):
        super(TestIscsi, self).setUp()
        entry = ent.Entry({}, ent.Element('Dummy', None), None)
        self.mock_job = job.Job(entry)
        self.adpt = self.useFixture(fx.AdapterFx()).adpt

    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    def test_add_parameter(self, mock_create):

        def create_param(name, value):
            return (name, value)

        mock_create.side_effect = create_param
        parm_array = []
        final_array = [("true", "True"), ("false", "False"), ("zero", "0"),
                       ("int", "1"), ("int list", "[0,1]"), ("str", "str"),
                       ("str list", "[str1,str2]")]
        iscsi._add_parameter(parm_array, "None", None)
        iscsi._add_parameter(parm_array, "true", True)
        iscsi._add_parameter(parm_array, "false", False)
        iscsi._add_parameter(parm_array, "zero", 0)
        iscsi._add_parameter(parm_array, "int", 1)
        iscsi._add_parameter(parm_array, "int list", [0, 1])
        iscsi._add_parameter(parm_array, "str", "str")
        iscsi._add_parameter(parm_array, "str list", ["str1", u'str2'])
        self.assertEqual(parm_array, final_array)

    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_discover_iscsi(self, mock_job_res, mock_job_p, mock_run_job,
                            mock_job_w):
        mock_job_w.return_value = self.mock_job
        mock_host_ip = '10.0.0.1:3290'
        mock_user = 'username'
        mock_pass = 'password'
        mock_iqn = 'fake_iqn'
        mock_uuid = 'uuid'
        mock_iface_name = 'iface_name'
        args = ['VirtualIOServer', mock_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': 'ISCSIDiscovery'}
        mock_job_res.return_value = {'DEV_OUTPUT': '["fake_iqn devName udid"]',
                                     'RETURN_CODE': '0'}
        device_name, udid = iscsi.discover_iscsi(
            self.adpt, mock_host_ip, mock_user, mock_pass, mock_iqn, mock_uuid,
            iface_name=mock_iface_name)

        self.adpt.read.assert_called_once_with(*args, **kwargs)
        self.assertEqual('devName', device_name)
        self.assertEqual('udid', udid)
        self.assertEqual(1, mock_run_job.call_count)
        mock_job_p.assert_has_calls([
            mock.call('hostIP', mock_host_ip), mock.call('user', mock_user),
            mock.call('password', mock_pass), mock.call('targetIQN', mock_iqn),
            mock.call('ifaceName', mock_iface_name),
            mock.call('multipath', str(False))], any_order=True)
        self.assertEqual(6, mock_job_p.call_count)

        # Test for lunid
        mock_job_p.reset_mock()
        mock_lunid = 2
        mock_job_res.return_value = {'DEV_OUTPUT': '["fake_iqn devName udid"]',
                                     'RETURN_CODE': '15'}
        device_name, udid = iscsi.discover_iscsi(
            self.adpt, mock_host_ip, mock_user, mock_pass, mock_iqn, mock_uuid,
            iface_name=mock_iface_name, lunid=mock_lunid)
        self.assertEqual(7, mock_job_p.call_count)
        mock_job_p.assert_any_call('targetLUN', str(mock_lunid))

        mock_job_res.return_value = {'DEV_OUTPUT': '["fake_iqn devName udid"]',
                                     'RETURN_CODE': '8'}
        self.assertRaises(pexc.ISCSIDiscoveryFailed, iscsi.discover_iscsi,
                          self.adpt, mock_host_ip, mock_user, mock_pass,
                          mock_iqn, mock_uuid, iface_name=mock_iface_name)

        # Check named args
        mock_job_p.reset_mock()
        mock_arg = mock.MagicMock()
        mock_job_res.return_value = {'DEV_OUTPUT': '["fake_iqn devName udid"]',
                                     'RETURN_CODE': '0'}

        device_name, udid = iscsi.discover_iscsi(
            self.adpt, mock_host_ip, mock_user, mock_pass, mock_iqn, mock_uuid,
            iface_name=mock_iface_name, lunid=mock_lunid, auth=mock_arg,
            discovery_auth=mock_arg, discovery_username=mock_arg,
            discovery_password=mock_arg, multipath=True)
        self.assertEqual('devName', device_name)
        self.assertEqual('udid', udid)

    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_discover_initiator(self, mock_job_res, mock_run_job, mock_job_w):
        mock_job_w.return_value = self.mock_job
        mock_uuid = 'uuid'
        args = ['VirtualIOServer', mock_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': ('ISCSIDiscovery')}
        mock_job_res.return_value = {'InitiatorName': 'fake_iqn',
                                     'RETURN_CODE': '0'}
        initiator = iscsi.discover_iscsi_initiator(self.adpt, mock_uuid)

        self.adpt.read.assert_called_once_with(*args, **kwargs)
        self.assertEqual('fake_iqn', initiator)
        self.assertEqual(1, mock_run_job.call_count)
        mock_job_res.return_value = {'InitiatorName': '',
                                     'RETURN_CODE': '8'}
        self.assertRaises(pexc.ISCSIDiscoveryFailed,
                          iscsi.discover_iscsi_initiator, self.adpt, mock_uuid)

    @mock.patch('pypowervm.wrappers.job.Job.create_job_parameter')
    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.wrappers.job.Job.get_job_results_as_dict')
    def test_remove_iscsi(self, mock_job_res, mock_run_job, mock_job_w,
                          mock_job_p):
        mock_job_w.return_value = self.mock_job
        mock_uuid = 'uuid'
        mock_iqn = 'fake_iqn'
        mock_parm = mock.MagicMock()
        mock_job_p.return_value = mock_parm
        args = ['VirtualIOServer', mock_uuid]
        kwargs = {'suffix_type': 'do', 'suffix_parm': ('ISCSIRemove')}
        mock_job_res.return_value = {'RETURN_CODE': '0'}
        iscsi.remove_iscsi(self.adpt, mock_iqn, mock_uuid)

        self.adpt.read.assert_called_once_with(*args, **kwargs)
        mock_run_job.assert_called_once_with(
            mock_uuid, job_parms=[mock_parm] * 2, timeout=120)
        mock_job_p.assert_any_call('targetIQN', mock_iqn)
        self.assertEqual(1, mock_run_job.call_count)

        # Test to check the ISCSIRemoveFailed
        mock_run_job.reset_mock()
        mock_job_res.return_value = {'RETURN_CODE': '2'}
        self.assertRaises(pexc.ISCSIRemoveFailed,
                          iscsi.remove_iscsi, self.adpt, mock_iqn, mock_uuid)

        # Test the Return Code 21
        mock_run_job.reset_mock()
        mock_job_res.return_value = {'RETURN_CODE': '21'}
        iscsi.remove_iscsi(self.adpt, mock_iqn, mock_uuid)
        mock_run_job.assert_called_once_with(
            mock_uuid, job_parms=[mock_parm] * 2, timeout=120)

        # Check named params
        mock_run_job.reset_mock()
        mock_arg = mock.MagicMock()
        iscsi.remove_iscsi(self.adpt, mock_iqn, mock_uuid, iface_name=mock_arg,
                           lun=mock_arg, portal=mock_arg, multipath=mock_arg)
        mock_run_job.assert_called_once_with(
            mock_uuid, job_parms=[mock_parm] * 5, timeout=120)
