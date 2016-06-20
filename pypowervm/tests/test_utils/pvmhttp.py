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

import ast
import os

import pypowervm.adapter as adp

EOL = "\n"

COMMENT = "#"
INFO = "INFO{"
HEADERS = "HEADERS{"
BODY = "BODY{"
END_OF_SECTION = "END OF SECTION}"


class PVMFile(object):
    def __init__(self, file_name=None):
        self.comment = None
        self.path = None
        self.reason = None
        self.status = None
        self.headers = None
        self.body = None

        if file_name is not None:
            self.load_file(file_name)

    def load_file(self, file_name):
        """Load a REST response file."""
        # If given a pathed filename, use it
        dirname = os.path.dirname(file_name)
        if not dirname:
            dirname = os.path.dirname(os.path.dirname(__file__))
            file_name = os.path.join(dirname, "data", file_name)

        resp_file = open(file_name, "r")

        if resp_file is None:
            raise Exception("Could not load %s" % file_name)

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
                info = ast.literal_eval(buf)
                self.comment = info['comment']
                self.path = info['path']
                self.reason = info['reason']
                self.status = info['status']
            elif line.startswith(HEADERS):
                self.headers = ast.literal_eval(buf)
            elif line.startswith(BODY):
                self.body = buf

        resp_file.close()


class PVMResp(PVMFile):

    """Class to encapsulate the text serialization of a response."""

    def __init__(self, file_name=None, pvmfile=None, adapter=None):
        """Initialize this PVMResp by loading a file or pulling a PVMFile.

        :param file_name: Name of a file to load.
        :param pvmfile: An existing PVMFile instance.  This PVMResp will use
                        its attributes.  If both file_name and pvmfile are
                        specified, the file will be reloaded into the passed-in
                        PVMFile.  This is probably not what you intended.
        :param adapter: A pypowervm.adapter.Adapter, used for traits, etc.
        """
        super(PVMResp, self).__init__()
        # Legacy no-arg constructor - allow caller to set fields manually
        if pvmfile is None and file_name is None:
            return
        if pvmfile is None:
            self.load_file(file_name)
        else:
            # Use pvmfile
            if file_name is not None:
                pvmfile.load_file(file_name)
            # Copy in attrs from pvmfile
            self.comment = pvmfile.comment
            self.path = pvmfile.path
            self.reason = pvmfile.reason
            self.status = pvmfile.status
            self.headers = pvmfile.headers
            self.body = pvmfile.body

        self.response = adp.Response(reqmethod=None, reqpath=None,
                                     status=self.status, reason=self.reason,
                                     headers=self.headers, body=self.body)
        self.response.adapter = adapter
        self.response._unmarshal_atom()

    def get_response(self):
        return self.response

    def refresh(self):
        """Do the query and get the response."""

        print("Connecting.")
        adap = adp.Adapter()

        print("Reading path:  " + self.path)
        self.response = adap.read(self.path)

        print("Received " + str(self.response))

    def save(self, file_name):

        everything = {
            'comment': self.comment,
            'path': self.path,
            'reason': self.response.reason,
            'status': self.response.status,
        }

        with open(file_name, 'wb') as df:
            df.write("####################################################")
            df.write(EOL)
            df.write("# THIS IS AN AUTOMATICALLY GENERATED FILE")
            df.write(EOL)
            df.write("# DO NOT EDIT. ANY EDITS WILL BE LOST ON NEXT UPDATE")
            df.write(EOL)
            df.write("#")
            df.write(EOL)
            df.write("# To update file, run: create_httpresp.py -refresh ")
            df.write(os.path.basename(file_name))
            df.write(EOL)
            df.write("#")
            df.write(EOL)
            df.write("####################################################")
            df.write(EOL)

            df.write(INFO + EOL)
            df.write(str(everything))
            df.write(EOL)
            df.write(END_OF_SECTION)
            df.write(EOL)
            df.write(HEADERS + EOL)
            df.write(str(self.response.headers))
            df.write(EOL)
            df.write(END_OF_SECTION)
            df.write(EOL)
            df.write(BODY + EOL)
            df.write(self.response.body)
            df.write(EOL)
            df.write(END_OF_SECTION)
            df.write(EOL)


def load_pvm_resp(file_name, adapter=None):
    return PVMResp(file_name, adapter=adapter)


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
