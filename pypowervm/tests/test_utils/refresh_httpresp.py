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

# Convenience program to call create_httpresp.py -refresh
#
# Run this standalone and it will list all the .txt files and
# prompt you to select which one you want to refresh.
#

import os
import tempfile

import six

from pypowervm.tests.test_utils import create_httpresp

defaultresp_path = os.path.join(tempfile.gettempdir(), 'defaultresp.txt')


def get_default_selection():
    """Retrieve the last response file updated."""
    try:
        if not os.path.exists(defaultresp_path):
            return None

        with open(defaultresp_path, 'r') as file_ptr:
            default_selection = file_ptr.readline()
            if default_selection is None:
                return None
            return default_selection.strip()
    except Exception:
        return None


def save_default_selection(default_line):
    """Save the selection so it can be set as the default next time."""
    try:

        with open(defaultresp_path, 'w') as file_ptr:
            file_ptr.write(default_line)
    except Exception as e:
        print("%s" % e)


def get_txt_file():
    error_message = None
    default_selection = get_default_selection()

    dirname = os.path.dirname(os.path.dirname(__file__))
    dirname = os.path.join(dirname, "data")
    directory_listing = os.listdir(dirname)
    txtfiles = [name
                for name in directory_listing
                if name.endswith('.txt')]
    txtfiles.sort()

    while True:
        if default_selection and default_selection not in txtfiles:
            default_selection = None  # The previous file was not found

        count = 1
        for name in txtfiles:
            if name == default_selection:
                fmt = '%d:*\t[%s]'
            else:
                fmt = '%d:\t%s'
            print(fmt % (count, name))
            count += 1

        print()
        if error_message:
            print(error_message)

        if default_selection:
            fmt = ('Enter index or name of file to refresh [Enter=%s]--> ' %
                   default_selection)
        else:
            fmt = 'Enter index or name of file to refresh--> '

        line = six.moves.input(fmt)

        line = line.strip()
        if line is None:
            return None

        if len(line) == 0 and default_selection:
            return default_selection

        print(line)

        if line in txtfiles:
            save_default_selection(line)
            return line  # The actual filename was entered

        try:
            line_index = int(line)
        except ValueError:
            error_message = 'Could not convert %s to an integer' % line
            continue

        if line_index < 1 or line_index > len(txtfiles):
            error_message = 'Index %d is out of range' % line_index
            continue

        save_default_selection(txtfiles[line_index - 1])
        return txtfiles[line_index - 1]

if __name__ == '__main__':
    txt_file = get_txt_file()

    print("Selected %s " % txt_file)

    create_httpresp.main(['-refresh', txt_file])
