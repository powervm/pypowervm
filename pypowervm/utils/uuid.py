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

"""Utilities around Universally-Unique Identifiers (UUIDs)."""

PVM_BYTE_MAPPING = {'8': '0', '9': '1', 'a': '2', 'b': '3',
                    'c': '4', 'd': '5', 'e': '6', 'f': '7'}


def convert_uuid_to_pvm(uuid):
    """Converts a standard UUID to PowerVM format

    PowerVM uuids always set the byte 0, bit 0 to 0.

    :param uuid: A standard format uuid string
    :returns: A PowerVM compliant uuid
    """
    try:
        pvm1 = PVM_BYTE_MAPPING[uuid[:1]].lower()
    except KeyError:
        pvm1 = uuid[:1]

    pvm_uuid = pvm1 + uuid[1:]
    return pvm_uuid
