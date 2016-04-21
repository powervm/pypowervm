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

import unittest

import mock

from pypowervm.tests.test_utils import pvmhttp
import pypowervm.wrappers.http_error as he

HTTPRESP_FILE = "fake_httperror.txt"

MSG = ('Unexpected error occurred while fetching Cluster/SSP '
       'information : 9999-99Z*2125D4A/1 : Unable to send com'
       'mand to VIOS at this moment. VIOS 1*9999-99Z*2125D4A '
       'is busy processing some other request. Please retry t'
       'he operation after sometime.')
MSG2 = ('Error occurred while querying for Adapter from VIOS vios1 with ID 2 '
        'in System 9119-MHE*1085B07 -  The system is currently too busy to '
        'complete the specified request. Please retry the operation at a '
        'later time. If the operation continues to fail, check the error log '
        'to see if the filesystem is full.')
REASON_CODE = 'Unknown internal error.'


class TestHttpError(unittest.TestCase):

    def setUp(self):
        super(TestHttpError, self).setUp()

        self.http_error = pvmhttp.load_pvm_resp(HTTPRESP_FILE)
        self.assertIsNotNone(self.http_error,
                             "Could not load %s " %
                             HTTPRESP_FILE)

    def test_wrap(self):
        wrap = he.HttpError.wrap(self.http_error.response.entry)
        self.assertEqual(wrap.message, MSG)
        self.assertEqual(wrap.status, 500)
        self.assertEqual(wrap.reason_code, REASON_CODE)

        self.assertTrue(wrap.is_vios_busy())
        # Ensure it's checking for 500 only.
        with mock.patch.object(wrap, '_get_val_int', return_value=555):
            self.assertFalse(wrap.is_vios_busy())
        # Ensure it's checking for 'VIOS' string.
        with mock.patch.object(wrap, '_get_val_str', return_value='other'):
            self.assertFalse(wrap.is_vios_busy())
        # Ensure it finds 'VIOS' but not the other string.
        with mock.patch.object(wrap, '_get_val_str', return_value='VIOS xxx'):
            self.assertFalse(wrap.is_vios_busy())

        # Ensure it finds 'HSCL' return code.
        msg_string = 'msg HSCL3205 msg'
        with mock.patch.object(wrap, '_get_val_str', return_value=msg_string):
            self.assertTrue(wrap.is_vios_busy())

        msg_string = 'msg VIOS0014 msg'
        with mock.patch.object(wrap, '_get_val_str', return_value=msg_string):
            self.assertTrue(wrap.is_vios_busy())

        # Ensure we find the new message
        with mock.patch.object(wrap, '_get_val_str', return_value=MSG2):
            self.assertTrue(wrap.is_vios_busy())
