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

from pypowervm import adapter as a
from pypowervm.wrappers import constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

FILE_ROOT = 'File'
FILE_NAME = 'Filename'
FILE_DATE_MOD = 'DateModified'
FILE_INET_MED_TYPE = 'InternetMediaType'
FILE_UUID = 'FileUUID'
FILE_EXP_SIZE = 'ExpectedFileSizeInBytes'
FILE_CUR_SIZE = 'CurrentFileSizeInBytes'
FILE_ENUM_TYPE = 'FileEnumType'
FILE_VIOS = 'TargetVirtualIOServerUUID'
FILE_TDEV_UDID = 'TargetDeviceUniqueDeviceID'

BROKERED_MEDIA_ISO = 'BROKERED_MEDIA_ISO'
BROKERED_DISK_IMAGE = 'BROKERED_DISK_IMAGE'

DEFAULT_MEDIA_TYPE = 'application/octet-stream'


def crt_file(f_name, f_type, v_uuid, sha_chksum=None, f_size=None,
             tdev_udid=None):
    """Creates an element that can be used for a File create action.

    :param f_name: The name for the file.
    :param f_type: The type of the file.  Typically one of the following:
                   'BROKERED_MEDIA_ISO' - virtual optical media
                   'BROKERED_DISK_IMAGE' - virtual disk
    :param v_uuid: The UUID for the Virtual I/O Server that the file will
                   reside on.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful
                       for integrity checks.
    :param f_size: (OPTIONAL) The size in bytes of the file to upload.  Can be
                   an int or a String (that represents an integer number).
                   Useful for integrity checks.
    :param tdev_udid: The device UDID that the file will back into.
    :returns: The Element that represents the newly created File.
    """
    # Metadata needs to be in a specific order.  These are required
    metadata = [
        a.Element(FILE_NAME, ns=c.WEB_NS, text=f_name),
        a.Element(FILE_INET_MED_TYPE, ns=c.WEB_NS, text=DEFAULT_MEDIA_TYPE)
    ]

    # Optional - should not be included in the Element if None.
    if sha_chksum:
        metadata.append(a.Element('SHA256', ns=c.WEB_NS, text=sha_chksum))

    if f_size:
        metadata.append(a.Element(FILE_EXP_SIZE, ns=c.WEB_NS,
                                  text=str(f_size)))

    # These are required
    metadata.append(a.Element(FILE_ENUM_TYPE, ns=c.WEB_NS,
                              text=f_type))
    metadata.append(a.Element(FILE_VIOS, ns=c.WEB_NS, text=v_uuid))

    # Optical media doesn't need to cite a target dev for file upload
    if tdev_udid:
        metadata.append(a.Element('TargetDeviceUniqueDeviceID', ns=c.WEB_NS,
                                  text=tdev_udid))

    # Metadata about the file done.  Add that to a root element.
    return a.Element('File', ns=c.WEB_NS, attrib=c.DEFAULT_SCHEMA_ATTR,
                     children=metadata)


class File(ewrap.EntryWrapper):
    """Wraps the File Metadata for files on the VIOS.

    The API supports passing a File up to devices on the Virtual I/O Server.
    This object wraps the metadata for the Files.
    """

    @property
    def file_name(self):
        return self.get_parm_value(FILE_NAME)

    @property
    def date_modified(self):
        return self.get_parm_value(FILE_DATE_MOD)

    @property
    def internet_media_type(self):
        """Typically 'application/octet-stream'."""
        return self.get_parm_value(FILE_INET_MED_TYPE)

    @property
    def file_uuid(self):
        """The file's UUID (different from the entries)."""
        return self.get_parm_value(FILE_UUID)

    @property
    def expected_file_size(self):
        return self.get_parm_value_int(FILE_EXP_SIZE)

    @property
    def current_file_size(self):
        return self.get_parm_value_int(FILE_CUR_SIZE)

    @property
    def enum_type(self):
        """The type of the file.

        BROKERED_MEDIA_ISO - virtual optical media
        BROKERED_DISK_IMAGE - virtual disk
        """
        return self.get_parm_value(FILE_ENUM_TYPE)

    @property
    def vios_uuid(self):
        return self.get_parm_value(FILE_VIOS)

    @property
    def tdev_udid(self):
        return self.get_parm_value(FILE_TDEV_UDID)
