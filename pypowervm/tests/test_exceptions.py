# Copyright 2014, 2015 IBM Corp.
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

import os
import unittest

import six

import pypowervm.exceptions as pvmex

msg_params = {
    "backing_dev": "backing_dev_param",
    "cpu_size": 678,
    "element": "element_param",
    "element_type": "element_type_param",
    "error": "error_param",
    "file_name": "file_name_param",
    "image_volume": "image_volume_param",
    "lpar_name": "lpar_name_param",
    "min_vios": "min_vios_param",
    "name": "name_param",
    "operation_name": "operation_name_param",
    "reason": "reason_param",
    "seconds": 147,
    "valid_values": "valid_values_param",
    "vios_state": "vios_state_param",
    "volume": "volume_param",
    "access_file": "testfile",
}

os.environ['LANG'] = 'en_US'

class2msg = {
    pvmex.NotFound:
    "Element not found: element_type_param element_param",
    pvmex.LPARNotFound:
    "LPAR not found: lpar_name_param",
    pvmex.JobRequestFailed:
    "The 'operation_name_param' operation failed. error_param",
    pvmex.JobRequestTimedOut:
    "The 'operation_name_param' operation failed. "
    "Failed to complete the task in 147 seconds.",
    pvmex.AuthFileReadError:
    "OS denied access to file testfile.",
    pvmex.AuthFileAccessError:
    "OS encountered an I/O error attempting to read file testfile: "
    "error_param",
    pvmex.MigrationFailed:
    "The migration task failed. error_param"
}


class TestExceptions(unittest.TestCase):
    """Test coverage for the pypowervm.exceptions module."""

    def raise_helper(self, e):
        raise e

    def fmt_helper(self, eclass, expected_message):
        e = eclass(**msg_params)
        self.assertRaises(eclass, self.raise_helper, e)
        try:
            raise e
        except eclass as e1:
            self.assertEqual(e1.args[0], expected_message)

    def test_Error(self):
        e = pvmex.Error("test")
        self.assertRaises(pvmex.Error, self.raise_helper, e)
        try:
            raise e
        except pvmex.Error as e1:
            self.assertEqual(e1.args[0], "test")

    def test_fmterrors(self):
        for e, s in six.iteritems(class2msg):
            try:
                self.fmt_helper(e, s)
            except ValueError:
                self.fail(s)

    def test_bogusformatparams(self):
        class Bogus(pvmex.AbstractMsgFmtError):
            msg_fmt = "This has a %(bogus)s format parameter."

        self.assertRaises(KeyError, Bogus, **msg_params)

if __name__ == "__main__":
    unittest.main()
