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

COMMENT = "#"
SECTION = "SECTION:"
END_OF_SECTION = "END OF SECTION"


def load_xml_sections(file_name):
    """Loads a file that contains xml sections

    This method takes a file that contains xml sections and returns
    a dict of them.  It's useful for testing the generation of the sections.

    See ../data/lpar_sections.txt for an example of the file contents.

    :param file_name: The name of the file to load.
    """
    def _read_section(nm):
        buf = ""
        while True:
            ln = sect_file.readline()
            if ln is None or len(ln) == 0:
                raise Exception("Could not find end of section %s of file %s" %
                                (nm, file_name))

            if ln.startswith(END_OF_SECTION):
                return buf

            buf += ln.strip('\n')

        return buf

    sections = {}

    # First try to load the name as passed in.
    dirname = os.path.dirname(file_name)
    if dirname is None or dirname == '':
        dirname = os.path.dirname(os.path.dirname(__file__))
        file_name = os.path.join(dirname, "data", file_name)

    sect_file = open(file_name, "r")

    if sect_file is None:
        raise Exception("Could not load %s" % file_name)

    while True:
        line = sect_file.readline()
        if line is None or len(line) == 0:
            break

        if len(line.strip()) == 0:
            continue

        if line.startswith(COMMENT):
            continue

        if line.startswith(SECTION):
            # Get the name of the section
            name = line[len(SECTION):].strip()
            # Get the data
            data = _read_section(name)
            sections[name] = data
        else:
            sect_file.close()
            raise Exception("Unknown line in file %s: %s" %
                            (file_name, line))

    sect_file.close()

    return sections
