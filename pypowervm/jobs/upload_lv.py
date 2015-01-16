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

import math

from pypowervm import adapter as a
from pypowervm import const as c
from pypowervm import exceptions as exc
from pypowervm import util
from pypowervm.wrappers import constants as wc
from pypowervm.wrappers import volume_group as vg

FILE_UUID = 'FileUUID'


def upload_new_vdisk(adapter, v_uuid,  vol_grp_uuid, d_stream,
                     d_name, d_size, sha_chksum=None):
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
    :param d_size: The size (in bytes) of the stream to be uploaded.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :returns f_uuid: The File UUID that was created.
    :returns n_vdisk: The new VirtualDisk wrapper that was created as part of
                      the operation.
    """
    # Get the existing volume group
    vol_grp_data = adapter.read(wc.VIOS, v_uuid, wc.VOL_GROUP, vol_grp_uuid)
    vol_grp = vg.VolumeGroup(vol_grp_data.entry)

    # Create the new virtual disk.  The size here is in GB.  We can use decimal
    # precision on the create call.  What the VIOS will then do is determine
    # the appropriate segment size (pp) and will provide a virtual disk that
    # is 'at least' that big.  Depends on the segment size set up on the
    # volume group how much over it could go.
    #
    # See note below...temporary workaround needed.
    gb_size = util.convert_bytes_to_gb(d_size)

    # TODO(IBM) Temporary - need to round up to the highest GB.  This should
    # be done by the platform in the future.
    gb_size = math.ceil(gb_size)
    new_vdisk = vg.VirtualDisk(vg.crt_virtual_disk_obj(d_name, gb_size))

    # Append it to the list.  Requires get then set.
    vdisks = vol_grp.get_virtual_disks()
    vdisks.append(new_vdisk)
    vol_grp.set_virtual_disks(vdisks)

    # Now perform an update on the adapter.
    resp = adapter.update(vol_grp._entry.element, vol_grp_data.headers['etag'],
                          wc.VIOS, v_uuid, wc.VOL_GROUP, vol_grp_uuid,
                          xag=None)
    vol_grp = vg.VolumeGroup(resp.entry)

    # The new Virtual Disk should be created.  Find the one we created.
    n_vdisk = None
    for vdisk in vol_grp.get_virtual_disks():
        if vdisk.get_name() == d_name:
            n_vdisk = vdisk
            break
    if not n_vdisk:
        # This should never occur since the update went through without error,
        # but adding just in case as we don't want to create the file meta
        # without a backing disk.
        raise exc.Error("Unable to locate new vDisk on file upload.")

    # Next, create the file, but specify the appropriate disk udid from the
    # Virtual Disk
    f_meta = _create_file(adapter, d_name, wc.BROKERED_DISK_IMAGE, v_uuid,
                          f_size=d_size, tdev_udid=n_vdisk.get_udid(),
                          sha_chksum=sha_chksum)

    # Finally, upload the file
    adapter.upload_file(f_meta, d_stream)

    f_uuid = f_meta.findtext(FILE_UUID)
    return f_uuid, n_vdisk


def upload_vopt(adapter, v_uuid, d_stream, f_name,
                f_size=None, sha_chksum=None):
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
    :returns: The file's UUID once uploaded.
    """
    # First step is to create the 'file' on the system.
    f_meta = _create_file(adapter, f_name, wc.BROKERED_MEDIA_ISO, v_uuid,
                          sha_chksum, f_size)

    # Next, upload the file
    adapter.upload_file(f_meta, d_stream)

    # Determine the UUID
    f_uuid = f_meta.findtext(FILE_UUID)

    return f_uuid


def _create_file(adapter, f_name, f_type, v_uuid, sha_chksum=None, f_size=None,
                 tdev_udid=None):
    """Creates a file on the VIOS, which is needed before the POST.

    :param adapter: The adapter to talk over the API.
    :param f_name: The name for the file.
    :param f_type: The type of the file.  Typically one of the following:
                   'BROKERED_MEDIA_ISO' - virtual optical media
                   'BROKERED_DISK_IMAGE' - virtual disk
    :param v_uuid: The UUID for the Virtual I/O Server that the file will
                   reside on.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful
                       for integrity checks.
    :param f_size: (OPTIONAL) The size of the file to upload.  Useful for
                   integrity checks.
    :param tdev_udid: The device UDID that the file will back into.
    :returns: The Element that represents the newly created File.
    """
    # Metadata needs to be in a specific order.  These are required
    metadata = [
        a.Element('Filename', ns=c.WEB_NS, text=f_name),
        a.Element('InternetMediaType', ns=c.WEB_NS,
                  text='application/octet-stream')
    ]

    # Optionals should not be included in the Element if None.
    if sha_chksum:
        metadata.append(a.Element('SHA256', ns=c.WEB_NS, text=sha_chksum))

    if f_size:
        metadata.append(a.Element('ExpectedFileSizeInBytes', ns=c.WEB_NS,
                                  text=str(f_size)))

    # These are required
    metadata.append(a.Element('FileEnumType', ns=c.WEB_NS,
                              text=f_type))
    metadata.append(a.Element('TargetVirtualIOServerUUID', ns=c.WEB_NS,
                              text=v_uuid))

    # Optical media doesn't need to cite a target dev for file upload
    if tdev_udid:
        metadata.append(a.Element('TargetDeviceUniqueDeviceID', ns=c.WEB_NS,
                                  text=tdev_udid))

    # Metadata about the file done.  Add that to a root element.
    fd = a.Element('File', ns=c.WEB_NS, attrib=wc.DEFAULT_SCHEMA_ATTR,
                   children=metadata)

    # Create the file.
    fmeta = adapter.create(fd, 'File', service='web')
    return fmeta.entry.element
