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

        lua_xml = ('<XML_LIST><general><cmd_version>3</cmd_version><version>'
                   '2.0</version></general><reliableITL>false</reliableITL>'
                   '<deviceList><device><vendor>OTHER</vendor><deviceTag>'
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

        self.assertEqual(lua_xml, hdisk._lua_recovery_xml(all_itls, None))

    def test_process_lua_result_no_resp(self):
        result = {}
        status, dev_name, udid = hdisk._process_lua_result(result)
        self.assertIsNone(status)
        self.assertIsNone(dev_name)
        self.assertIsNone(udid)

    def test_process_lua_result_terse_resp(self):
        """Tests where valid XML is returned, but no device."""
        xml = ('<luaResult><version>2.0</version><deviceList></deviceList>'
               '</luaResult>')
        result = {'StdOut': xml}
        status, dev_name, udid = hdisk._process_lua_result(result)
        self.assertIsNone(status)
        self.assertIsNone(dev_name)
        self.assertIsNone(udid)

    def test_process_lua_result(self):
        xml = ('<luaResult><version>2.0</version><deviceList><device>'
               '<deviceTag>21</deviceTag><status>8</status><msg><msgLen>9'
               '</msgLen><msgText>test text</msgText></msg><pvName>hdisk10'
               '</pvName><uniqueID>fake_uid</uniqueID><udid>fake_udid'
               '</udid></device></deviceList></luaResult>')
        result = {'StdOut': xml}
        status, dev_name, udid = hdisk._process_lua_result(result)
        self.assertEqual('8', status)
        self.assertEqual('hdisk10', dev_name)
        self.assertEqual('fake_udid', udid)

        # Repeat with the input as the resultXML
        result = {'OutputXML': xml}
        status, dev_name, udid = hdisk._process_lua_result(result)
        self.assertEqual('8', status)
        self.assertEqual('hdisk10', dev_name)
        self.assertEqual('fake_udid', udid)

    @mock.patch('pypowervm.tasks.hdisk.LOG')
    def test_validate_lua_status(self, mock_log):
        """This tests the branches of validate_lua_status."""
        hdisk._log_lua_status(hdisk.LUAStatus.DEVICE_AVAILABLE,
                              'dev_name', 'message')
        self.assertEqual(1, mock_log.info.call_count)

        hdisk._log_lua_status(hdisk.LUAStatus.FOUND_ITL_ERR,
                              'dev_name', 'message')
        self.assertEqual(1, mock_log.warn.call_count)

        hdisk._log_lua_status(hdisk.LUAStatus.DEVICE_IN_USE,
                              'dev_name', 'message')
        self.assertEqual(2, mock_log.warn.call_count)

        hdisk._log_lua_status(hdisk.LUAStatus.FOUND_DEVICE_UNKNOWN_UDID,
                              'dev_name', 'message')
        self.assertEqual(3, mock_log.warn.call_count)

        hdisk._log_lua_status(hdisk.LUAStatus.INCORRECT_ITL,
                              'dev_name', 'message')
        self.assertEqual(4, mock_log.warn.call_count)

    @mock.patch('pypowervm.tasks.hdisk._process_lua_result')
    @mock.patch('pypowervm.wrappers.job.Job')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_lua_recovery(self, mock_adapter, mock_job, mock_lua_result):
        itls = [hdisk.ITL('AABBCCDDEEFF0011', '00:11:22:33:44:55:66:EE', 238)]

        mock_lua_result.return_value = ('OK', 'hdisk1', 'udid')

        status, devname, udid = hdisk.lua_recovery(mock_adapter,
                                                   'vios_uuid', itls)

        # Validate value unpack
        self.assertEqual('OK', status)
        self.assertEqual('hdisk1', devname)
        self.assertEqual('udid', udid)

        # Validate method invocations
        self.assertEqual(1, mock_adapter.read.call_count)
        self.assertEqual(1, mock_lua_result.call_count)

    @mock.patch('pypowervm.tasks.hdisk._lua_recovery_xml')
    @mock.patch('pypowervm.tasks.hdisk._process_lua_result')
    @mock.patch('pypowervm.wrappers.job.Job')
    @mock.patch('pypowervm.adapter.Adapter')
    def test_lua_recovery_dupe_itls(self, mock_adapter, mock_job,
                                    mock_lua_result, mock_lua_xml):
        itls = [hdisk.ITL('AABBCCDDEEFF0011', '00:11:22:33:44:55:66:EE', 238),
                hdisk.ITL('AABBCCDDEEFF0011', '00:11:22:33:44:55:66:EE', 238)]

        mock_lua_result.return_value = ('OK', 'hdisk1', 'udid')

        status, devname, udid = hdisk.lua_recovery(mock_adapter,
                                                   'vios_uuid', itls)

        # Validate value unpack
        self.assertEqual('OK', status)
        self.assertEqual('hdisk1', devname)
        self.assertEqual('udid', udid)

        # Validate method invocations
        self.assertEqual(1, mock_adapter.read.call_count)
        self.assertEqual(1, mock_lua_result.call_count)
        mock_lua_xml.assert_called_with({itls[0]}, mock_adapter,
                                        vendor='OTHER')

    @mock.patch('pypowervm.tasks.hdisk.lua_recovery')
    @mock.patch('pypowervm.utils.transaction.FeedTask')
    @mock.patch('pypowervm.tasks.storage.add_lpar_storage_scrub_tasks')
    @mock.patch('pypowervm.tasks.storage.find_stale_lpars')
    @mock.patch('pypowervm.wrappers.entry_wrapper.EntryWrapperGetter.get')
    def test_discover_hdisk(self, mock_ewget, mock_fsl, mock_alsst, mock_ftsk,
                            mock_luar):
        def set_luar_side_effect(_stat, _dev):
            """Set up the lua_recovery mock's side effect.

            The second return will always be the same - used to verify that we
            really called twice when appropriate.
            The first return will be (_stat, _dev, "udid"), per the params.
            """
            mock_luar.reset_mock()
            mock_luar.side_effect = [(_stat, _dev, 'udid'),
                                     ('ok_s', 'ok_h', 'ok_u')]
        stale_lpar_ids = [12, 34]
        # All of these should cause a scrub-and-retry
        retry_rets = [(None, None), (hdisk.LUAStatus.DEVICE_AVAILABLE, None),
                      (hdisk.LUAStatus.FOUND_DEVICE_UNKNOWN_UDID, 'hdisk456')]
        # These should *not* cause a scrub-and-retry
        no_retry_rets = [(hdisk.LUAStatus.DEVICE_AVAILABLE, 'hdisk456'),
                         (hdisk.LUAStatus.FOUND_ITL_ERR, 'hdisk456'),
                         (hdisk.LUAStatus.DEVICE_IN_USE, 'hdisk456')]
        mock_fsl.return_value = stale_lpar_ids
        for st, dev in retry_rets:
            set_luar_side_effect(st, dev)
            self.assertEqual(
                ('ok_s', 'ok_h', 'ok_u'), hdisk.discover_hdisk(
                    'adp', 'vuuid', ['itls']))
            self.assertEqual(1, mock_fsl.call_count)
            mock_ftsk.assert_called_with('scrub_vios_vuuid', mock.ANY)
            self.assertEqual(1, mock_alsst.call_count)
            mock_luar.assert_has_calls([
                mock.call('adp', 'vuuid', ['itls'], vendor=hdisk.LUAType.OTHER)
                for i in range(2)])
            mock_fsl.reset_mock()
            mock_alsst.reset_mock()
            mock_ftsk.reset_mock()

        for st, dev in no_retry_rets:
            set_luar_side_effect(st, dev)
            self.assertEqual(
                (st, dev, 'udid'), hdisk.discover_hdisk(
                    'adp', 'vuuid', ['itls']))
            self.assertEqual(0, mock_fsl.call_count)
            self.assertEqual(0, mock_ftsk.call_count)
            self.assertEqual(0, mock_alsst.call_count)
            self.assertEqual(1, mock_luar.call_count)
            mock_luar.assert_called_with('adp', 'vuuid', ['itls'],
                                         vendor=hdisk.LUAType.OTHER)

        # If no stale LPARs found, scrub-and-retry should not be triggered with
        # either set.
        mock_fsl.return_value = []
        for st, dev in retry_rets + no_retry_rets:
            set_luar_side_effect(st, dev)
            self.assertEqual(
                (st, dev, 'udid'), hdisk.discover_hdisk(
                    'adp', 'vuuid', ['itls']))
            # find_stale_lpars will be called for retry_rets, but not for
            # no_retry_rets
            self.assertLessEqual(mock_fsl.call_count, 1)
            self.assertEqual(0, mock_ftsk.call_count)
            self.assertEqual(0, mock_alsst.call_count)
            self.assertEqual(1, mock_luar.call_count)
            mock_luar.assert_called_with('adp', 'vuuid', ['itls'],
                                         vendor=hdisk.LUAType.OTHER)
            mock_fsl.reset_mock()

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

        def verify_run_job(vios_uuid, job_parms=None):
            self.assertEqual(1, len(job_parms))
            job_parm = (b'<web:JobParameter xmlns:web="http://www.ibm.com/'
                        b'xmlns/systems/power/firmware/web/mc/2012_10/" '
                        b'schemaVersion="V1_0"><web:ParameterName>devName'
                        b'</web:ParameterName><web:ParameterValue>dev_name'
                        b'</web:ParameterValue></web:JobParameter>')
            self.assertEqual(job_parm, job_parms[0].toxmlstring())

        mock_run_job.side_effect = verify_run_job

        hdisk._remove_hdisk_job(mock_adapter, 'dev_name', 'vios_uuid')
        # Validate method invocations
        self.assertEqual(1, mock_adapter.read.call_count)
        self.assertEqual(1, mock_run_job.call_count)
