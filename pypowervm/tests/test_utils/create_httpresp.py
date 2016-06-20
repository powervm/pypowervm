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
import sys

import pypowervm.adapter as adp
from pypowervm.tests.test_utils import pvmhttp


def refresh_response(file_to_refresh):
    """Reload the file and redo the query."""
    print("Loading original file: ", file_to_refresh)
    new_http = pvmhttp.load_pvm_resp(file_to_refresh)
    if new_http is None or new_http.refresh() is False:
            print("Unable to refresh ", file_to_refresh)
            return 1

    print("Saving refreshed file: ", file_to_refresh)
    new_http.save(file_to_refresh)
    return 0


def usage():
    print("create_httpresp -path path -output out_file [-comment comment]")
    print("    Note: out_file can be a full path or a file in the same "
          "location as create_httpresp.py")

    print('Ex: create_httpresp -path ManagedSystem/<uuid>/LogicalPartition '
          ' -output fakelpar.txt -comment "Created by jsmith"')
    print()
    print('create_httpresp -refresh response_file')
    print('Update a previously created response file by '
          'redoing the same request')

    exit(-1)


def main(argv):

    new_response = pvmhttp.PVMResp()
    output_file = None
    file_to_refresh = None

    aindex = 0
    while aindex < len(argv):
        if argv[aindex] == '-path':
            aindex += 1
            new_response.path = argv[aindex]
        elif argv[aindex] == '-comment':
            aindex += 1
            new_response.comment = argv[aindex]
        elif argv[aindex] == '-output':
            aindex += 1
            output_file = argv[aindex]
        elif argv[aindex] == '-refresh':
            aindex += 1
            file_to_refresh = argv[aindex]
        else:
            print("Unknown argument ", argv[aindex])
            usage()

        aindex += 1

    if file_to_refresh:
        rc = refresh_response(file_to_refresh)
        exit(rc)

    if new_response.path is None or output_file is None:
        usage()

    print("Connecting.")
    adap = adp.Adapter()
    print("Reading path:  ", new_response.path)
    new_response.response = adap.read(new_response.path)

    print("Received ", new_response.response)

    orig_file_name = output_file

    dirname = os.path.dirname(output_file)
    if dirname is None or dirname == '':
        dirname = os.path.dirname(__file__)
        output_file = os.path.join(dirname, output_file)

    new_response.save(output_file)

    print("Response has been saved in ", output_file)
    print("Use the pvmhttp.load_pvm_resp('%s') method "
          "to load it in your testcase " % orig_file_name)

    print("You can have the %s file rebuilt by running: "
          "create_httpresp -refresh %s" %
          (orig_file_name, orig_file_name))


if __name__ == '__main__':
    main(sys.argv[1:])
