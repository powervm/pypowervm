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

import re

from pypowervm import const


def convert_uuid_to_pvm(uuid):
    """Converts a standard UUID to PowerVM format

    PowerVM uuids always set the byte 0, bit 0 to 0.

    :param uuid: A standard format uuid string
    :returns: A PowerVM compliant uuid
    """
    return "%x%s" % (int(uuid[0], 16) & 7, uuid[1:])


def id_or_uuid(an_id):
    """Sanitizes a short ID or string UUID, and indicates which was used.

    Use as:
        is_uuid, lpar_id = id_or_uuid(lpar_id)
        if is_uuid:  # lpar_id is a string UUID
        else:  # lpar_id is LPAR short ID of type int

    :param an_id: Short ID (may be string or int) or string UUID of, e.g., an
                  LPAR.
    :return: Boolean.  If True, the other return is a UUID string.  If False,
                       it is an integer.
    :return: The input ID, either converted to int, or in its original string
             form if a UUID.
    """
    if isinstance(an_id, str) and re.match(const.UUID_REGEX_WORD, an_id):
        is_uuid = True
        ret_id = an_id
    else:
        is_uuid = False
        ret_id = int(an_id)
    return is_uuid, ret_id
