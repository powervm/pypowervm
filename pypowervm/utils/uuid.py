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

    PowerVM enforces the following UUID rules:
    - Bit 0 must be zero.
    - Bits 1-47 cannot all be zero.
    - The next 4 bits (48-51) are the generation method which must be 4 (0100).
    - The next 12 bits (52-63) cannot all be zero.
    - The next 2 bits (64-65) are the Variant which must be 2 (10).
    - The last 62 bits (66-127) cannot all be zero.

    :param uuid: A standard format uuid string
    :returns: A PowerVM compliant uuid
    """
    # Bit 0 must be zero.
    reta = ("%x%s" % (int(uuid[0], 16) & 7, uuid[1:])).split('-')
    # Now the first 48 bits (xxxxxxxx-xxxx) can't all be zeroes
    if reta[0] == '00000000' and reta[1] == '0000':
        reta[1] = '0001'
    # The next 4 bits (48-51) are the generation method which must be 4 (0100).
    reta[2] = '4' + reta[2][1:]
    # The next 12 bits (52-63) cannot all be zero, so this chunk can't be 4000.
    if reta[2] == '4000':
        reta[2] = '4001'
    # The next 2 bits (64-65) are the Variant which must be 2 (10).
    reta[3] = "%x%s" % (((int(reta[3][0], 16) | 4) & 7), reta[3][1:])
    # The last 62 bits (66-127) cannot all be zero, so the last two chunks
    # can't be 4000-000000000000
    if reta[3] == '4000' and reta[4] == '000000000000':
        reta[4] = '000000000001'
    return '-'.join(reta)


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
