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

import unittest

from pypowervm.tasks import hdisk
import pypowervm.tests.tasks.util as tju

VIOS_FEED = 'fake_vios_feed.txt'


class TestHDisk(unittest.TestCase):

    def setUp(self):
        super(TestHDisk, self).setUp()

    def test_itl(self):
        """Tests the ITL class."""
        itl = hdisk.ITL('AABBCCDDEEFF0011', '00:11:22:33:44:55:66:EE', 238)
        self.assertEqual('aabbccddeeff0011', itl.initiator)
        self.assertEqual('00112233445566ee', itl.target)
        self.assertEqual('ee000000000000', itl.lun)

    def test_build_itls(self):
        """Tests that the ITL combinations can be built out."""
        i_wwpns = ['0011223344556677', '0011223344556678']
        t_wwpns = ['1111223344556677', '1111223344556678', '1111223344556679']
        all_itls = hdisk.build_itls(i_wwpns, t_wwpns, 238)

        self.assertEqual(6, len(all_itls))

        combos = [hdisk.ITL(i_wwpns[0], t_wwpns[0], 238),
                  hdisk.ITL(i_wwpns[0], t_wwpns[1], 238),
                  hdisk.ITL(i_wwpns[0], t_wwpns[2], 238),
                  hdisk.ITL(i_wwpns[1], t_wwpns[0], 238),
                  hdisk.ITL(i_wwpns[1], t_wwpns[1], 238),
                  hdisk.ITL(i_wwpns[1], t_wwpns[2], 238)]
        self.assertListEqual(combos, all_itls)

    def test_lua_recovery_xml(self):
        """Validates that the LUA recovery XML is build properly."""
        i_wwpns = ['0011223344556677', '0011223344556678']
        t_wwpns = ['1111223344556677', '1111223344556678', '1111223344556679']
        all_itls = hdisk.build_itls(i_wwpns, t_wwpns, 238)

        LUA_XML = ('<XML_LIST><general><cmd_version>3</cmd_version><version>'
                   '2.0</version></general><reliableITL>false</reliableITL>'
                   '<deviceList><device><vendor>IBM</vendor><deviceTag>'
                   '1</deviceTag><itlList><number>6</number><itl>'
                   '<Iwwpn>0011223344556677</Iwwpn><Twwpn>1111223344556677'
                   '</Twwpn><lua>ee000000000000</lua></itl><itl><Iwwpn>'
                   '0011223344556677</Iwwpn><Twwpn>1111223344556678</Twwpn>'
                   '<lua>ee000000000000</lua></itl><itl><Iwwpn>'
                   '0011223344556677</Iwwpn><Twwpn>1111223344556679</Twwpn>'
                   '<lua>ee000000000000</lua></itl><itl><Iwwpn>'
                   '0011223344556678</Iwwpn><Twwpn>1111223344556677</Twwpn>'
                   '<lua>ee000000000000</lua></itl><itl><Iwwpn>'
                   '0011223344556678</Iwwpn><Twwpn>1111223344556678</Twwpn>'
                   '<lua>ee000000000000</lua></itl><itl><Iwwpn>'
                   '0011223344556678</Iwwpn><Twwpn>1111223344556679</Twwpn>'
                   '<lua>ee000000000000</lua></itl></itlList></device>'
                   '</deviceList></XML_LIST>')

        self.assertEqual(LUA_XML, hdisk._lua_recovery_xml(all_itls))

    @mock.patch('pypowervm.tasks.hdisk.LOG')
    def test_validate_lua_status(self, mock_log):
        """This tests the branches of validate_lua_status."""
        hdisk._validate_lua_status(hdisk.LUAStatus.DEVICE_AVAILABLE,
                                   'dev_name', 'udid', 'message')
        self.assertEqual(1, mock_log.info.call_count)

        hdisk._validate_lua_status(hdisk.LUAStatus.FOUND_ITL_ERR,
                                   'dev_name', 'udid', 'message')
        self.assertEqual(1, mock_log.warn.call_count)

        hdisk._validate_lua_status(hdisk.LUAStatus.DEVICE_IN_USE,
                                   'dev_name', 'udid', 'message')
        self.assertEqual(2, mock_log.warn.call_count)

        hdisk._validate_lua_status(hdisk.LUAStatus.FOUND_DEVICE_UNKNOWN_UDID,
                                   'dev_name', 'udid', 'message')
        self.assertEqual(3, mock_log.warn.call_count)

        hdisk._validate_lua_status(hdisk.LUAStatus.INCORRECT_ITL,
                                   'dev_name', 'udid', 'message')
        self.assertEqual(4, mock_log.warn.call_count)

    @mock.patch('pypowervm.tasks.hdisk._process_lua_result')
    @mock.patch('pypowervm.wrappers.job.Job')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_discover_hdisk(self, mock_adapter, mock_job, mock_lua_result):
        itls = [hdisk.ITL('AABBCCDDEEFF0011', '00:11:22:33:44:55:66:EE', 238)]

        mock_lua_result.return_value = ('OK', 'hdisk1', 'udid')

        status, devname, udid = hdisk.discover_hdisk(mock_adapter,
                                                     'vios_uuid', itls)

        # Validate value unpack
        self.assertEqual('OK', status)
        self.assertEqual('hdisk1', devname)
        self.assertEqual('udid', udid)

        # Validate method invocations
        self.assertEqual(1, mock_adapter.read.call_count)
        self.assertEqual(1, mock_lua_result.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.job_status')
    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_hdisk_classic(self, mock_adapter, mock_run_job,
                                  mock_job_status):
        mock_adapter.read.return_value = (tju.load_file(VIOS_FEED)
                                          .feed.entries[0])

        hdisk._remove_hdisk_classic(mock_adapter, 'host_name', 'dev_name',
                                    'vios_uuid')
        # Validate method invocations
        self.assertEqual(2, mock_adapter.read.call_count)
        self.assertEqual(1, mock_run_job.call_count)

    @mock.patch('pypowervm.wrappers.job.Job.run_job')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_remove_hdisk_job(self, mock_adapter, mock_run_job):
        mock_adapter.read.return_value = (tju.load_file(VIOS_FEED)
                                          .feed.entries[0])

        def verify_run_job(adapter, vios_uuid, job_parms=None):
            self.assertEqual(1, len(job_parms))
            job_parm = ('<web:JobParameter xmlns:web="http://www.ibm.com/xmlns'
                        '/systems/power/firmware/web/mc/2012_10/" '
                        'schemaVersion="V1_0"><web:ParameterName>devName'
                        '</web:ParameterName><web:ParameterValue>dev_name'
                        '</web:ParameterValue></web:JobParameter>')
            self.assertEqual(job_parm, job_parms[0].toxmlstring())

        mock_run_job.side_effect = verify_run_job

        hdisk._remove_hdisk_job(mock_adapter, 'host_name', 'dev_name',
                                'vios_uuid')
        # Validate method invocations
        self.assertEqual(1, mock_adapter.read.call_count)
        self.assertEqual(1, mock_run_job.call_count)
