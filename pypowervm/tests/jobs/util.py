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

import os

from pypowervm.tests.wrappers.util import pvmhttp


def load_file(file_name):
    """Helper method to load the responses from a given location."""
    data_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(data_dir, 'data')
    file_path = os.path.join(data_dir, file_name)
    return pvmhttp.load_pvm_resp(file_path).get_response()
