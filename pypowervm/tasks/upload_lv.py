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

import logging
import math

import pypowervm.exceptions as exc
from pypowervm import util
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf
import pypowervm.wrappers.virtual_io_server as vios

FILE_UUID = 'FileUUID'

# Setup logging
LOG = logging.getLogger(__name__)


def upload_new_vdisk(adapter, v_uuid,  vol_grp_uuid, d_stream,
                     d_name, f_size, d_size=None, sha_chksum=None):
    """Creates a new Virtual Disk and uploads a data stream to it.

    :param adapter: The adapter to talk over the API.
    :param v_uuid: The Virtual I/O Server UUID that will host the disk.
    :param vol_grp_uuid: The volume group that will host the Virtual Disk's
                         UUID.
    :param d_stream: The data stream (either a file handle or stream) to
                     upload.  Must have the 'read' method that returns a chunk
                     of bytes.
    :param d_name: The name that should be given to the disk on the Virtual
                   I/O Server that will contain the file.
    :param f_size: The size (in bytes) of the stream to be uploaded.
    :param d_size: (OPTIONAL) The size of the file.  Not required if it should
                   match the file.  Must be at least as large as the file.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :return: The first return value is the virtual disk that the file is
             uploaded into.
    :return: Normally the second return value will be None, indicating that the
             disk and image were uploaded without issue.  If for some reason
             the File metadata for the VIOS was not cleaned up, the return
             value is the File UUID.  This is simply a metadata marker to be
             later used as input to the 'upload_cleanup' method.
    """
    # Get the existing volume group
    vol_grp_data = adapter.read(vios.VIOS.schema_type, v_uuid,
                                stor.VG.schema_type, vol_grp_uuid)
    vol_grp = stor.VG.wrap(vol_grp_data.entry)

    # Create the new virtual disk.  The size here is in GB.  We can use decimal
    # precision on the create call.  What the VIOS will then do is determine
    # the appropriate segment size (pp) and will provide a virtual disk that
    # is 'at least' that big.  Depends on the segment size set up on the
    # volume group how much over it could go.
    #
    # See note below...temporary workaround needed.
    if d_size is None or d_size < f_size:
        d_size = f_size
    gb_size = util.convert_bytes_to_gb(d_size)

    # TODO(IBM) Temporary - need to round up to the highest GB.  This should
    # be done by the platform in the future.
    gb_size = math.ceil(gb_size)
    new_vdisk = stor.VDisk.bld(d_name, gb_size)

    # Append it to the list.
    vol_grp.virtual_disks.append(new_vdisk)

    # Now perform an update on the adapter.
    vol_grp = vol_grp.update(adapter)

    # The new Virtual Disk should be created.  Find the one we created.
    n_vdisk = None
    for vdisk in vol_grp.virtual_disks:
        if vdisk.name == d_name:
            n_vdisk = vdisk
            break
    if not n_vdisk:
        # This should never occur since the update went through without error,
        # but adding just in case as we don't want to create the file meta
        # without a backing disk.
        raise exc.Error("Unable to locate new vDisk on file upload.")

    # Next, create the file, but specify the appropriate disk udid from the
    # Virtual Disk
    vio_file = _create_file(
        adapter, d_name, vf.FTypeEnum.BROKERED_DISK_IMAGE, v_uuid,
        f_size=f_size, tdev_udid=n_vdisk.udid, sha_chksum=sha_chksum)
    try:
        # Upload the file
        adapter.upload_file(vio_file.element, d_stream)
    finally:
        try:
            # Cleanup after the upload
            upload_cleanup(adapter, vio_file.uuid)
        except Exception:
            LOG.exception('Unable to cleanup after file upload.'
                          ' File uuid: %s' % vio_file.uuid)
            return n_vdisk, vio_file.uuid
    return n_vdisk, None


def upload_vopt(adapter, v_uuid, d_stream, f_name, f_size=None,
                sha_chksum=None):
    """Upload a file/stream into a virtual media repository on the VIOS.

    :param adapter: The adapter to talk over the API.
    :param v_uuid: The Virtual I/O Server UUID that will host the file.
    :param d_stream: The data stream (either a file handle or stream) to
                     upload.  Must have the 'read' method that returns a chunk
                     of bytes.
    :param f_name: The name that should be given to the file.
    :param f_size: (OPTIONAL) The size in bytes of the file to upload.  Useful
                   for integrity checks.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :return: Normally this method will return None, indicating that the disk
             and image were uploaded without issue.  If for some reason the
             File metadata for the VIOS was not cleaned up, the return value
             is the File UUID.  This is simply a metadata marker to be later
             used as input to the 'upload_cleanup' method.
    """
    # First step is to create the 'file' on the system.
    vio_file = _create_file(
        adapter, f_name, vf.FTypeEnum.BROKERED_MEDIA_ISO, v_uuid,
        sha_chksum, f_size)
    try:
        # Next, upload the file
        adapter.upload_file(vio_file.element, d_stream)
    finally:
        try:
            # Cleanup after the upload
            upload_cleanup(adapter, vio_file.uuid)
        except Exception:
            LOG.exception('Unable to cleanup after file upload.'
                          ' File uuid: %s' % vio_file.uuid)
            return vio_file.uuid
    return None


def upload_cleanup(adapter, f_uuid):
    """Cleanup after a file upload.

    When files are uploaded to either VIOS or the PowerVM management
    platform, they create artifacts on the platform.  These artifacts
    must be cleaned up because there is a 100 file limit.  When the file UUID
    is cleaned, two things can happend:

    1) if the file is targeted to the PowerVM management platform, then both
    the file and the metadata artifacts are cleaned up.

    2) if the file is a VIOS file, then just the PowerVM management platform
    artifacts are cleaned up.

    It's safe to cleanup VIOS file artifacts directly after uploading, as it
    will not affect the VIOS entity.

    :param adapter: The adapter to talk over the API.
    :param f_uuid: The file UUID to clean up.
    :returns: The response from the delete operation.
    """
    return adapter.delete(vf.File.schema_type, root_id=f_uuid, service='web')


def _create_file(adapter, f_name, f_type, v_uuid, sha_chksum=None, f_size=None,
                 tdev_udid=None):
    """Creates a file on the VIOS, which is needed before the POST.

    :param adapter: The adapter to talk over the API.
    :param f_name: The name for the file.
    :param f_type: The type of the file, from vios_file.FTypeEnum.
    :param v_uuid: The UUID for the Virtual I/O Server that the file will
                   reside on.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful
                       for integrity checks.
    :param f_size: (OPTIONAL) The size of the file to upload.  Useful for
                   integrity checks.
    :param tdev_udid: The device UDID that the file will back into.
    :returns: The File Wrapper
    """
    fd = vf.File.bld(f_name, f_type, v_uuid, sha_chksum=sha_chksum,
                     f_size=f_size, tdev_udid=tdev_udid)

    # Create the file.
    resp = adapter.create(fd.element, vf.File.schema_type, service='web')
    return vf.File.wrap(resp)
