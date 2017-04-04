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

"""EntryWrapper for File ('web' namespace)."""

import pypowervm.const as pc
import pypowervm.wrappers.entry_wrapper as ewrap

_FILE_NAME = 'Filename'
_FILE_DATE_MOD = 'DateModified'
_FILE_INET_MED_TYPE = 'InternetMediaType'
_FILE_UUID = 'FileUUID'
_FILE_EXP_SIZE = 'ExpectedFileSizeInBytes'
_FILE_CUR_SIZE = 'CurrentFileSizeInBytes'
_FILE_ENUM_TYPE = 'FileEnumType'
_FILE_VIOS = 'TargetVirtualIOServerUUID'
_FILE_TDEV_UDID = 'TargetDeviceUniqueDeviceID'
_FILE_ASSET_FILE = 'AssetFile'
_FILE_CHKSUM = 'SHA256'


_DEFAULT_MEDIA_TYPE = 'application/octet-stream'


class FileType(object):
    """Supported file types."""
    MEDIA_ISO = 'BROKERED_MEDIA_ISO'
    DISK_IMAGE = 'BROKERED_DISK_IMAGE'
    # Obsolete.  Behaves the same as DISK_IMAGE.
    DISK_IMAGE_COORDINATED = 'BROKERED_DISK_IMAGE'


@ewrap.EntryWrapper.pvm_type('File', ns=pc.WEB_NS)
class File(ewrap.EntryWrapper):
    """Wraps the File Metadata for files on the VIOS.

    The API supports passing a File up to devices on the Virtual I/O Server.
    This object wraps the metadata for the Files.
    """

    @classmethod
    def bld(cls, adapter, f_name, f_type, v_uuid, sha_chksum=None, f_size=None,
            tdev_udid=None):
        """Creates a fresh File wrapper that can be used for a create action.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param f_name: The name for the file.
        :param f_type: The type of the file.  One of the FileType values.
        :param v_uuid: The UUID for the Virtual I/O Server that the file will
                       reside on.
        :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful
                           for integrity checks.
        :param f_size: (OPTIONAL) The size in bytes of the file to upload.  Can
                       be an int or a String (that represents an integer
                       number).  Useful for integrity checks.
        :param tdev_udid: The device UDID that the file will back into.
        :returns: The newly created File wrapper.
        """
        # Metadata needs to be in a specific order.  These are required
        f = super(File, cls)._bld(adapter)
        f._file_name(f_name)
        f._internet_media_type(_DEFAULT_MEDIA_TYPE)

        # Optional - should not be included in the Element if None.
        if sha_chksum:
            f._chksum(sha_chksum)

        if f_size:
            f._expected_file_size(f_size)

        # These are required
        f._enum_type(f_type)
        f._vios_uuid(v_uuid)

        # Optical media doesn't need to cite a target dev for file upload
        if tdev_udid:
            f._tdev_udid(tdev_udid)

        return f

    @property
    def file_name(self):
        return self._get_val_str(_FILE_NAME)

    def _file_name(self, name):
        self.set_parm_value(_FILE_NAME, name)

    @property
    def date_modified(self):
        return self._get_val_str(_FILE_DATE_MOD)

    @property
    def internet_media_type(self):
        """Typically 'application/octet-stream'."""
        return self._get_val_str(_FILE_INET_MED_TYPE)

    def _internet_media_type(self, imt):
        self.set_parm_value(_FILE_INET_MED_TYPE, imt)

    @property
    def file_uuid(self):
        """The file's UUID (different from the entries)."""
        return self._get_val_str(_FILE_UUID)

    @property
    def expected_file_size(self):
        return self._get_val_int(_FILE_EXP_SIZE)

    def _expected_file_size(self, sz):
        self.set_parm_value(_FILE_EXP_SIZE, sz)

    @property
    def current_file_size(self):
        return self._get_val_int(_FILE_CUR_SIZE)

    @property
    def enum_type(self):
        """The type of the file.  One of the FileType values."""
        return self._get_val_str(_FILE_ENUM_TYPE)

    def _enum_type(self, et):
        self.set_parm_value(_FILE_ENUM_TYPE, et)

    def _chksum(self, sha):
        self.set_parm_value(_FILE_CHKSUM, sha)

    @property
    def vios_uuid(self):
        return self._get_val_str(_FILE_VIOS)

    def _vios_uuid(self, uuid):
        self.set_parm_value(_FILE_VIOS, uuid)

    @property
    def tdev_udid(self):
        return self._get_val_str(_FILE_TDEV_UDID)

    def _tdev_udid(self, udid):
        self.set_parm_value(_FILE_TDEV_UDID, udid)

    @property
    def asset_file(self):
        """Used to identify the asset file on upload.

        Only used in conjunction with DISK_IMAGE_COORDINATED.

        Provides the path to a file on the local system where data can be sent
        during an upload operation.  This is used for significant speed
        improvements as the REST API server does not need to be involved with
        the upload.
        """
        return self._get_val_str(_FILE_ASSET_FILE)
