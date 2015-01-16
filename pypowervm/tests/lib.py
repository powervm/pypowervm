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

import six

datapath = os.path.join(os.path.dirname(__file__), "data")


def file2b(basename):
    """Reads a file into a byte string.

    :param basename: The base name (no path) of the file to consume.  The
        file is expected to reside in the data/ subdirectory of the path
        containing this library.
    :return: Python 2- and 3-compatible byte string of the input file's
        contents, unaltered and unprocessed.
    """
    with open(os.path.join(datapath, basename), "r") as fh:
        return six.b(fh.read())
