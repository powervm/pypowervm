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

import pypowervm.adapter as adp

EOL = "\n"

COMMENT = "#"
INFO = "INFO{"
HEADERS = "HEADERS{"
BODY = "BODY{"
END_OF_SECTION = "END OF SECTION}"


class PVMResp(object):

    """Class to encapsulate the text serialization of a response."""

    def __init__(self):
        self.comment = None
        self.host = None
        self.user = None
        self.pw = None
        self.path = None
        self.response = None

    def get_response(self):
        return self.response

    def refresh(self):
        """Do the query and get the response."""

        print("Connecting to " + self.host)
        conn = adp.Session(self.host, self.user, self.pw, certpath=None)
        if conn is None:
            print("Could not get connection to " + self.host)
            return False

        oper = adp.Adapter(conn)
        if oper is None:
            print("Could not create a Adapter")
            return False

        print("Reading path:  " + self.path)
        self.response = oper.read(self.path)

        print("Received " + self.response)

    def save(self, file_name):

        everything = {
            'comment': self.comment,
            'host': self.host,
            'user': self.user,
            'pw': self.pw,
            'path': self.path,
            'reason': self.response.reason,
            'status': self.response.status,
        }

        disk_file = file(file_name, 'wb')
        disk_file.write("####################################################")
        disk_file.write(EOL)
        disk_file.write("# THIS IS AN AUTOMATICALLY GENERATED FILE")
        disk_file.write(EOL)
        disk_file.write("# DO NOT EDIT. ANY EDITS WILL BE LOST ON NEXT UPDATE")
        disk_file.write(EOL)
        disk_file.write("#")
        disk_file.write(EOL)
        disk_file.write("# To update file, run: create_httpresp.py -refresh ")
        disk_file.write(os.path.basename(file_name))
        disk_file.write(EOL)
        disk_file.write("#")
        disk_file.write(EOL)
        disk_file.write("####################################################")
        disk_file.write(EOL)

        disk_file.write(INFO + EOL)
        disk_file.write(str(everything))
        disk_file.write(EOL)
        disk_file.write(END_OF_SECTION)
        disk_file.write(EOL)
        disk_file.write(HEADERS + EOL)
        disk_file.write(str(self.response.headers))
        disk_file.write(EOL)
        disk_file.write(END_OF_SECTION)
        disk_file.write(EOL)
        disk_file.write(BODY + EOL)
        disk_file.write(self.response.body)
        disk_file.write(EOL)
        disk_file.write(END_OF_SECTION)
        disk_file.write(EOL)
        disk_file.close()


def load_pvm_resp(file_name):
    new_resp = PVMResp()

    """First try to load the name as passed in."""
    dirname = os.path.dirname(file_name)
    if dirname is None or dirname == '':
        dirname = os.path.dirname(os.path.dirname(__file__))
        file_name = os.path.join(dirname, "data", file_name)

    resp_file = open(file_name, "r")

    if resp_file is None:
        raise Exception("Could not load %s" % file_name)

    status = None
    reason = None
    headers = None
    body = None

    while True:
        line = resp_file.readline()
        if line is None or len(line) == 0:
            break

        if len(line.strip()) == 0:
            continue

        if line.startswith(COMMENT):
            continue

        if line.startswith(INFO):
            section = INFO
        elif line.startswith(HEADERS):
            section = HEADERS
        elif line.startswith(BODY):
            section = BODY
        else:
            resp_file.close()
            raise Exception("Unknown line in file %s: %s" %
                            (file_name, line))

        buf = _read_section(section, file_name, resp_file)

        if line.startswith(INFO):
            info = eval(buf)
            new_resp.comment = info['comment']
            new_resp.host = info['host']
            new_resp.user = info['user']
            new_resp.pw = info['pw']
            new_resp.path = info['path']
            reason = info['reason']
            status = info['status']
        elif line.startswith(HEADERS):
            headers = eval(buf)
        elif line.startswith(BODY):
            body = buf

    resp_file.close()

    new_resp.response = adp.Response(reqmethod=None, reqpath=None,
                                     status=status, reason=reason,
                                     headers=headers, body=body)
    new_resp.response._unmarshal_atom()

    return new_resp


def _read_section(section, file_name, resp_file):

    buf = ""
    while True:
        line = resp_file.readline()
        if line is None or len(line) == 0:
            raise Exception("Could not find end of section %s of file %s" %
                            (section, file_name))

        if line.startswith(END_OF_SECTION):
            return buf

        buf += EOL + line
