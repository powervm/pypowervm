# Copyright 2014, 2016 IBM Corp.
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

"""Create, remove, map, unmap, and populate virtual storage objects."""

import contextlib
import math
import os
import tempfile
import threading
import time

from concurrent import futures
from oslo_concurrency import lockutils as lock
from oslo_log import log as logging
from taskflow import engines as tf_eng
from taskflow.patterns import unordered_flow as tf_uf
from taskflow import task as tf_tsk

from pypowervm import const as c
from pypowervm import exceptions as exc
from pypowervm.helpers import vios_busy
from pypowervm.i18n import _
from pypowervm.tasks import scsi_mapper as sm
from pypowervm.tasks import vfc_mapper as fm
from pypowervm import util
from pypowervm.utils import retry
from pypowervm.utils import transaction as tx
from pypowervm.wrappers import logical_partition as lpar
from pypowervm.wrappers import managed_system as sys
from pypowervm.wrappers import storage as stor
from pypowervm.wrappers import vios_file as vf
from pypowervm.wrappers import virtual_io_server as vios

FILE_UUID = 'FileUUID'

# Setup logging
LOG = logging.getLogger(__name__)

_LOCK_VOL_GRP = 'vol_grp_lock'

# Concurrent uploads
_UPLOAD_SEM = threading.Semaphore(3)


class UploadType(object):
    """Used in conjunction with the upload_xx methods.

    Indicates how the invoker will pass in the handle to the data.
    """

    # The data stream (either a file handle or stream) to upload.  Must have
    # the 'read' method that returns a chunk of bytes.
    IO_STREAM = 'stream'

    # A parameter-less function that builds an IO_STREAM.
    IO_STREAM_BUILDER = 'stream_builder'

    # DEPRECATED: Known issues combining threads and greenlets may cause hangs.
    #
    # A method function that will be invoked to stream the data into the
    # virtual disk. Only one parameter is passed in, and that is the path to
    # the file to stream the data into.
    FUNC = 'delegate_function'


def _delete_vio_file(vio_file):
    """Try to delete a File artifact.

    :param vio_file: pypowervm.wrappers.vios_file.File object, retrieved from
                     the server, representing the File object to delete.
    :return: If the deletion is successful (or the File was already gone), the
             method returns None.  Otherwise, the vio_file parameter is
             returned.
    """
    # Try to delete the file.
    try:
        vio_file.adapter.delete(vio_file.schema_type, root_id=vio_file.uuid,
                                service='web')
    except exc.HttpNotFound:
        # Already gone - ignore
        pass
    except exc.Error:
        LOG.exception(_("Failed to delete vio_file with UUID %s.  It must be "
                        "manually deleted."), vio_file.uuid)
        return vio_file
    return None


def crt_copy_vdisk(adapter, v_uuid, vol_grp_uuid, src, f_size, d_name,
                   d_size=None, file_format=None):
    """Create a new virtual disk that contains all the data of the src given.

    :param adapter: The adapter to talk over the API.
    :param v_uuid: The UUID of the Virtual I/O Server that will host the new
                   VDisk.
    :param vol_grp_uuid: The UUID of the volume group that will host the new
                         VDisk.
    :param src: UDID of virtual disk to copy data from
    :param f_size: The size (in bytes) of the src disk.
    :param d_name: The name that should be given to the disk on the Virtual
                   I/O Server that will contain the file.
    :param d_size: (Optional) The desired size of the new VDisk in bytes.  If
                   omitted or smaller than f_size, it will be set to match
                   f_size.
    :param file_format: (Optional) File format of src VDisk.  See
                        stor.FileFormatType enumeration for valid formats.
    :return: The virtual disk that the file is uploaded into.
    """
    # Create the new virtual disk.  The size here is in GB.  We can use decimal
    # precision on the create call.  What the VIOS will then do is determine
    # the appropriate segment size (pp) and will provide a virtual disk that
    # is 'at least' that big.  Depends on the segment size set up on the
    # volume group how much over it could go.
    if d_size is None or d_size < f_size:
        d_size = f_size
    gb_size = util.convert_bytes_to_gb(d_size)

    # The REST API requires that we round up to the highest GB.
    gb_size = math.ceil(gb_size)
    return crt_vdisk(adapter, v_uuid, vol_grp_uuid, d_name, gb_size,
                     base_image=src, file_format=file_format)


def _clean_out_bad_upload(adapter, vol_grp_uuid, v_uuid, n_vdisk, vio_file):
    """Cleans out a bad vDisk after a failed upload."""
    # Keeps sonar happy.
    vol_grp = stor.VG.get(adapter, vol_grp_uuid, parent_type=vios.VIOS,
                          parent_uuid=v_uuid)
    rm_vg_storage(vol_grp, vdisks=[n_vdisk])

    _delete_vio_file(vio_file)


def upload_new_vdisk(adapter, v_uuid, vol_grp_uuid, io_handle, d_name, f_size,
                     d_size=None, sha_chksum=None,
                     upload_type=UploadType.IO_STREAM, file_format=None):
    """Uploads a new virtual disk.

    :param adapter: The adapter to talk over the API.
    :param v_uuid: The Virtual I/O Server UUID that will host the disk.
    :param vol_grp_uuid: The volume group that will host the Virtual Disk's
                         UUID.
    :param io_handle: The I/O handle (as defined by the upload_type)
    :param d_name: The name that should be given to the disk on the Virtual
                   I/O Server that will contain the file.
    :param f_size: The size (in bytes) of the stream to be uploaded.
    :param d_size: (Optional) The desired size of the new VDisk in bytes.  If
                   omitted or smaller than f_size, it will be set to match
                   f_size.
    :param sha_chksum: (Optional) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :param upload_type: (Optional, Default: IO_STREAM) Defines the way in
                        which the vdisk should be uploaded.  Refer to the
                        UploadType enumeration for valid upload mechanisms.
    :param file_format: (Optional) Format of file coming from io_handle.  See
                        stor.FileFormatType enumeration for valid formats.
    :return: The first return value is the virtual disk that the file is
             uploaded into.
    :return: Normally the second return value will be None, indicating that the
             disk and image were uploaded without issue.  If for some reason
             the File metadata for the VIOS was not cleaned up, the return
             value is the File EntryWrapper.  This is simply a metadata marker
             to be later used to retry the cleanup.
    """
    # Create the new virtual disk.  The size here is in GB.  We can use decimal
    # precision on the create call.  What the VIOS will then do is determine
    # the appropriate segment size (pp) and will provide a virtual disk that
    # is 'at least' that big.  Depends on the segment size set up on the
    # volume group how much over it could go.
    if d_size is None or d_size < f_size:
        d_size = f_size
    gb_size = util.convert_bytes_to_gb(d_size)

    # The REST API requires that we round up to the highest GB.
    gb_size = math.ceil(gb_size)
    n_vdisk = crt_vdisk(adapter, v_uuid, vol_grp_uuid, d_name, gb_size,
                        file_format=file_format)

    # Next, create the file, but specify the appropriate disk udid from the
    # Virtual Disk
    vio_file = _create_file(
        adapter, d_name, vf.FileType.DISK_IMAGE, v_uuid, f_size=f_size,
        tdev_udid=n_vdisk.udid, sha_chksum=sha_chksum)

    try:
        # Run the upload
        maybe_file = _upload_stream(vio_file, io_handle, upload_type)
    except Exception:
        _clean_out_bad_upload(adapter, vol_grp_uuid, v_uuid, n_vdisk, vio_file)

        # Re-raise the original exception
        raise
    return n_vdisk, maybe_file


def upload_vopt(adapter, v_uuid, d_stream, f_name, f_size=None,
                sha_chksum=None):
    """Upload a file/stream into a virtual media repository on the VIOS.

    :param adapter: The adapter to talk over the API.
    :param v_uuid: The Virtual I/O Server UUID that will host the file.
    :param d_stream: A file path or data stream (must have 'read' method) to
                     upload.
    :param f_name: The name that should be given to the file.
    :param f_size: (OPTIONAL) The size in bytes of the file to upload.  Useful
                   for integrity checks.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :return: The vOpt loaded into the media repository.  This is a reference,
             for use in scsi mappings.
    :return: Normally this method will return None, indicating that the disk
             and image were uploaded without issue.  If for some reason the
             File metadata for the VIOS was not cleaned up, the return value
             is the File EntryWrapper.  This is simply a marker to be later
             used to retry the cleanup.
    """
    # First step is to create the 'file' on the system.
    vio_file = _create_file(
        adapter, f_name, vf.FileType.MEDIA_ISO, v_uuid, sha_chksum, f_size)

    if isinstance(d_stream, str):
        f_wrap = _upload_file(vio_file, d_stream)
    else:
        f_wrap = _upload_stream(vio_file, d_stream, UploadType.IO_STREAM)

    # Simply return a reference to this.
    reference = stor.VOptMedia.bld_ref(adapter, f_name)

    return reference, f_wrap


def upload_new_lu(v_uuid, ssp, io_handle, lu_name, f_size, d_size=None,
                  sha_chksum=None, return_ssp=False,
                  upload_type=UploadType.IO_STREAM):
    """Creates a new SSP Logical Unit and uploads an image to it.

    Note: return spec varies based on the return_ssp parameter:

        # Default/legacy behavior
        new_lu, maybe_file = upload_new_lu(..., return_ssp=False)

        # With return_ssp=True
        ssp, new_lu, maybe_file = upload_new_lu(..., return_ssp=True)

    :param v_uuid: The UUID of the Virtual I/O Server through which to perform
                   the upload.  (Note that the new LU will be visible from any
                   VIOS in the Shared Storage Pool's Cluster.)
    :param ssp: SSP EntryWrapper representing the Shared Storage Pool on which
                to create the new Logical Unit.
    :param io_handle: The I/O handle (as defined by the upload_type)
    :param lu_name: The name that should be given to the new LU.
    :param f_size: The size (in bytes) of the stream to be uploaded.
    :param d_size: (OPTIONAL) The size of the LU (in bytes).  Not required if
                   it should match the file.  Must be at least as large as the
                   file.
    :param sha_chksum: (Optional) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :param return_ssp: (Optional) If True, the return value of the method is a
                       three-member tuple whose third value is the updated SSP
                       EntryWrapper.  If False (the default), the method
                       returns a two-member tuple.
    :param upload_type: (Optional, Default: IO_STREAM) Defines the way in
                        which the LU should be uploaded.  Refer to the
                        UploadType enumeration for valid upload mechanisms.
    :return: If the return_ssp parameter is True, the first return value is the
             updated SSP EntryWrapper, containing the newly-created and
             -uploaded LU.  If return_ssp is False, this return value is absent
             - only the below two values are returned.
    :return: An LU EntryWrapper corresponding to the Logical Unit into which
             the file was uploaded.
    :return: Normally None, indicating that the LU was created and the image
             was uploaded without issue.  If for some reason the File metadata
             for the VIOS was not cleaned up, the return value is the File
             EntryWrapper.  This is simply a marker to be later used to retry
             the cleanup.
    """
    # Create the new Logical Unit.  The LU size needs to be in decimal GB.
    if d_size is None or d_size < f_size:
        d_size = f_size
    gb_size = util.convert_bytes_to_gb(d_size, dp=2)

    ssp, new_lu = crt_lu(ssp, lu_name, gb_size, typ=stor.LUType.IMAGE)

    maybe_file = upload_lu(v_uuid, new_lu, io_handle, f_size,
                           sha_chksum=sha_chksum, upload_type=upload_type)

    return (ssp, new_lu, maybe_file) if return_ssp else (new_lu, maybe_file)


def upload_lu(v_uuid, lu, io_handle, f_size, sha_chksum=None,
              upload_type=UploadType.IO_STREAM):
    """Uploads a data stream to an existing SSP Logical Unit.

    :param v_uuid: The UUID of the Virtual I/O Server through which to perform
                   the upload.
    :param lu: LU Wrapper representing the Logical Unit to which to upload the
               data.  The LU must already exist in the SSP.
    :param io_handle: The I/O handle (as defined by the upload_type)
    :param f_size: The size (in bytes) of the stream to be uploaded.
    :param sha_chksum: (Optional) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :param upload_type: (Optional, Default: IO_STREAM) Defines the way in
                        which the LU should be uploaded.  Refer to the
                        UploadType enumeration for valid upload mechanisms.
    :return: Normally the return value will be None, indicating that the image
             was uploaded without issue.  If for some reason the File metadata
             for the VIOS was not cleaned up, the return value is the LU
             EntryWrapper.  This is simply a marker to be later used to retry
             the cleanup.
    """
    # Create the file, specifying the UDID from the new Logical Unit.
    # The File name matches the LU name.
    vio_file = _create_file(
        lu.adapter, lu.name, vf.FileType.DISK_IMAGE, v_uuid, f_size=f_size,
        tdev_udid=lu.udid, sha_chksum=sha_chksum)

    return _upload_stream(vio_file, io_handle, upload_type)


def _upload_file(vio_file, path):
    """Upload a file by its path

    :param vio_file: The File EntryWrapper representing the metadata for the
                     file.
    :param path: The path as a string to the file to be uploaded.
    :return: Returns None if file upload is successful. Otherwise returns the
             File EntryWrapper if the File metadata was not cleaned up.
    """
    f_wrap = None
    i = 0
    while True:
        try:
            with open(path, 'rb') as d_stream:
                f_wrap = _upload_stream(vio_file, d_stream,
                                        UploadType.IO_STREAM)
            break
        except Exception:
            if i < 3:
                LOG.warning(_("Encountered an issue while uploading. "
                              "Will retry."))
            else:
                raise
            i += 1
    return f_wrap


def _upload_stream(vio_file, io_handle, upload_type):
    """Upload a file stream and clean up the metadata afterward.

    When files are uploaded to either VIOS or the PowerVM management
    platform, they create artifacts on the platform.  These artifacts
    must be cleaned up because there is a 100 file limit.  When the file UUID
    is cleaned, two things can happen:

    1) if the file is targeted to the PowerVM management platform, then both
    the file and the metadata artifacts are cleaned up.

    2) if the file is a VIOS file, then just the PowerVM management platform
    artifacts are cleaned up.

    It's safe to cleanup VIOS file artifacts directly after uploading, as it
    will not affect the VIOS entity.

    :param vio_file: The File EntryWrapper representing the metadata for the
                     file.
    :param io_handle: The I/O handle (as defined by the upload_type)
    :param upload_type: Defines the way in which the element should be
                        uploaded.  Refer to the UploadType enumeration for
                        valid upload mechanisms.
    :return: Normally this method will return None, indicating that the disk
             and image were uploaded without issue.  If for some reason the
             File metadata for the VIOS was not cleaned up, the return value
             is the File EntryWrapper.  This is simply a marker to be later
             used to retry the cleanup.
    """
    # If the io_handle is a function that opens a stream we are to read from,
    # open that stream.
    if upload_type == UploadType.IO_STREAM_BUILDER:
        io_handle, upload_type = io_handle(), UploadType.IO_STREAM

    try:
        # Acquire the upload semaphore
        _UPLOAD_SEM.acquire()

        start = time.time()
        # Upload the file directly to the REST API server.
        _upload_stream_api(vio_file, io_handle, upload_type)
        LOG.debug("Upload took %.2fs", time.time() - start)
    finally:
        # Must release the semaphore
        _UPLOAD_SEM.release()

        # Allow the exception to be raised up...if there was one.
        ret_vio = _delete_vio_file(vio_file)
    return ret_vio


@contextlib.contextmanager
def _rest_api_pipe(file_writer):
    """A piping context manager to allow "local" uploads from a remote user.

    Usage:
        with _rest_api_pipe(file_writer) as read_stream:
            upload(read_stream)

    :param file_writer: A method in the spirit of:
                        def file_writer(file_path):
                            with open(file_path, 'w') as out_stream:
                                while ...:
                                    out_stream.write(...)
    """
    fifo_reader, file_path, temp_dir = None, None, None
    try:
        # Make the file path
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, 'REST_API_Pipe')
        os.mkfifo(file_path)
        # Spawn the writer thread
        with futures.ThreadPoolExecutor(1) as th_pool:
            writer_f = th_pool.submit(file_writer, file_path)
            # Create a readable stream on the FIFO pipe.
            fifo_reader = util.retry_io_command(open, file_path, 'r')

            # Let the caller consume the pipe contents
            yield fifo_reader

            # Make sure the writer is finished.  This will also raise any
            # exception the writer caused.
            writer_f.result()
    finally:
        # Close and clean up the FIFO, carefully.  Any step could have raised.
        if fifo_reader:
            util.retry_io_command(fifo_reader.close)
        if file_path:
            os.remove(file_path)
        if temp_dir:
            os.rmdir(temp_dir)


def _upload_stream_api(vio_file, io_handle, upload_type):
    # If using a FUNCtion-based upload remotely, we have to make that function
    # (which is passed in as io_handle) think it's writing to a local file.  We
    # spoof this with _RestApiPipe, which uses a fifo (named pipe) that it
    # populates from d_stream in a separate thread.
    if upload_type == UploadType.FUNC:
        with _rest_api_pipe(io_handle) as in_stream:
            vio_file.adapter.upload_file(vio_file.element, in_stream)
    else:
        # We don't want to use the VIOS retry mechanism here.
        helpers = vio_file.adapter.helpers
        try:
            helpers.remove(vios_busy.vios_busy_retry_helper)
        except ValueError:
            pass
        # io_handle is already an open, readable stream
        vio_file.adapter.upload_file(vio_file.element, io_handle,
                                     helpers=helpers)


def _create_file(adapter, f_name, f_type, v_uuid, sha_chksum=None, f_size=None,
                 tdev_udid=None):
    """Creates a file on the VIOS, which is needed before the POST.

    :param adapter: The adapter to talk over the API.
    :param f_name: The name for the file.
    :param f_type: The type of the file, from vios_file.FileType.
    :param v_uuid: The UUID for the Virtual I/O Server that the file will
                   reside on.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful
                       for integrity checks.
    :param f_size: (OPTIONAL) The size of the file to upload.  Useful for
                   integrity checks.
    :param tdev_udid: The device UDID that the file will back into.
    :returns: The File Wrapper
    """
    return vf.File.bld(adapter, f_name, f_type, v_uuid, sha_chksum=sha_chksum,
                       f_size=f_size, tdev_udid=tdev_udid).create()


def default_tier_for_ssp(ssp):
    """Find the default Tier for the given Shared Storage Pool.

    :param ssp: The SSP EntryWrapper whose default Tier is to be retrieved.
    :return: Tier EntryWrapper representing ssp's default Tier.
    :raise NoDefaultTierFoundOnSSP: If no default Tier is found on the
                                    specified Shared Storage Pool.
    """
    tier = stor.Tier.search(ssp.adapter, parent=ssp, is_default=True,
                            one_result=True)
    if tier is None:
        raise exc.NoDefaultTierFoundOnSSP(ssp_name=ssp.name)
    return tier


def crt_lu_linked_clone(ssp, cluster, src_lu, new_lu_name, lu_size_gb=0):
    """Create a new LU as a linked clone to a backing image LU.

    :deprecated: Use crt_lu instead.
    :param ssp: The SSP EntryWrapper representing the SharedStoragePool on
                which to create the new LU.
    :param cluster: The Cluster EntryWrapper representing the Cluster against
                    which to invoke the LULinkedClone Job.
    :param src_lu: The LU ElementWrapper or LUEnt EntryWrapper representing the
                   link source.
    :param new_lu_name: The name to be given to the new LU.
    :param lu_size_gb: The size of the new LU in GB with decimal precision.  If
                       this is not specified or is smaller than the size of the
                       image_lu, the size of the image_lu is used.
    :return: The updated SSP EntryWrapper containing the newly-created LU.
    :return: The newly created and linked LU.
    """
    import warnings
    warnings.warn(_("The crt_lu_linked_clone method is deprecated!  Please "
                    "use the crt_lu method (clone=src_lu, size=lu_size_gb)."),
                  DeprecationWarning)
    # Create the LU.  No locking needed on this method, as the crt_lu handles
    # the locking.
    ssp, dst_lu = crt_lu(ssp, new_lu_name, lu_size_gb, thin=True,
                         typ=stor.LUType.DISK, clone=src_lu)

    return ssp, dst_lu


def _image_lu_for_clone(lus, clone_lu):
    """Given a Disk LU linked clone, find the Image LU to which it is linked.

    :param lus: List of LUs (LU or LUEnt) to search.
    :param clone_lu: The LU EntryWrapper representing the Disk LU linked clone
                     whose backing Image LU is to be found.
    :return: The LU EntryWrapper representing the Image LU backing the
             clone_lu.  None if no such Image LU can be found.
    """
    # Check if the clone never happened
    if clone_lu.cloned_from_udid is None:
        return None
    # When comparing udid/cloned_from_udid, disregard the 2-digit 'type' prefix
    image_udid = clone_lu.cloned_from_udid[2:]
    for lu in lus:
        if lu.lu_type != stor.LUType.IMAGE:
            continue
        if lu.udid[2:] == image_udid:
            return lu
    return None


def _image_lu_in_use(lus, image_lu):
    """Determine whether an Image LU still has any Disk LU linked clones.

    :param lus: List of all the LUs in the SSP/Tier.  They must have UDIDs
                (i.e. must have been retrieved from the server, not created
                locally).
    :param image_lu: LU EntryWrapper representing the Image LU.
    :return: True if the SSP contains any Disk LU linked clones backed by the
             image_lu; False otherwise.
    """
    # When comparing udid/cloned_from_udid, disregard the 2-digit 'type' prefix
    image_udid = image_lu.udid[2:]
    for lu in lus:
        if lu.lu_type != stor.LUType.DISK:
            continue
        cloned_from = lu.cloned_from_udid
        if cloned_from is None:
            LOG.warning(
                _("Disk Logical Unit %(luname)s has no backing image LU.  "
                  "(UDID: %(udid)s) "), {'luname': lu.name, 'udid': lu.udid})
            continue
        if cloned_from[2:] == image_udid:
            return True
    return False


def find_vg(adapter, vg_name, vios_name=None):
    """Returns the VIOS and VG wrappers for the volume group.

    :param adapter: pypowervm.adapter.Adapter for REST communication.
    :param vg_name: Name of the volume group to find.
    :param vios_name: The name of the VIOS on which to search for the volume
                      group.  If not specified, all VIOSes are searched.
    :return vios_wrap: The VIOS wrapper representing the Virtual I/O Server on
                       which the volume group was found.
    :return vg_wrap: The VG wrapper representing the volume group.
    :raise VIOSNotFound: If vios_name was specified and no such VIOS exists.
    :raise VGNotFound: If no volume group of the specified vg_name could be
                       found.
    """
    if vios_name:
        # Search for the VIOS by name if specified.
        vios_wraps = vios.VIOS.search(adapter, name=vios_name)
        if not vios_wraps:
            raise exc.VIOSNotFound(vios_name=vios_name)
    else:
        # Get all VIOSes.
        vios_wraps = vios.VIOS.get(adapter)

    # Loop through each VIOS's VGs to find the one with the appropriate name.
    for vios_wrap in vios_wraps:
        # Search the feed for the volume group
        for vg_wrap in stor.VG.get(adapter, parent=vios_wrap):
            LOG.debug('Volume group: %s', vg_wrap.name)
            if vg_name == vg_wrap.name:
                return vios_wrap, vg_wrap

    raise exc.VGNotFound(vg_name=vg_name)


@lock.synchronized(_LOCK_VOL_GRP)
def crt_vdisk(adapter, v_uuid, vol_grp_uuid, d_name, d_size_gb,
              base_image=None, file_format=None):
    """Creates a new Virtual Disk in the specified volume group.

    :param adapter: The pypowervm.adapter.Adapter through which to request the
                    change.
    :param v_uuid: The UUID of the Virtual I/O Server that will host the disk.
    :param vol_grp_uuid: The volume group that will host the new Virtual Disk.
    :param d_name: The name that should be given to the disk on the Virtual
                   I/O Server that will contain the file.
    :param d_size_gb: The size of the disk in GB.
    :param base_image: (Optional) The UDID of a VDisk to copy data from.
    :param file_format: (Optional) File format of the new VirtualDisk.  See
                        stor.FileFormatType enumeration for valid formats.
    :return: VDisk ElementWrapper representing the new VirtualDisk from the
             server response (i.e. UDID will be populated).
    :raise exc.Error: If the server response from attempting to add the VDisk
                      does not contain the new VDisk.
    """
    # Get the existing volume group
    vol_grp_data = adapter.read(vios.VIOS.schema_type, v_uuid,
                                stor.VG.schema_type, vol_grp_uuid)
    vol_grp = stor.VG.wrap(vol_grp_data.entry)

    new_vdisk = stor.VDisk.bld(adapter, d_name, d_size_gb,
                               base_image=base_image, file_format=file_format)

    # Append it to the list.
    vol_grp.virtual_disks.append(new_vdisk)

    # Now perform an update on the adapter.
    vol_grp = vol_grp.update()

    # The new Virtual Disk should be created.  Find the one we created.
    for vdisk in vol_grp.virtual_disks:
        # Vdisk name can be either disk_name or /path/to/disk_name
        if vdisk.name.split('/')[-1] == d_name.split('/')[-1]:
            return vdisk
    # This should never occur since the update went through without error,
    # but adding just in case as we don't want to create the file meta
    # without a backing disk.
    raise exc.Error(_("Unable to locate new vDisk on file upload."))


@lock.synchronized(_LOCK_VOL_GRP)
@retry.retry(argmod_func=retry.refresh_wrapper, tries=60,
             delay_func=retry.STEPPED_RANDOM_DELAY)
def rm_vg_storage(vg_wrap, vdisks=None, vopts=None):
    """Remove storage elements from a volume group.

    Changes are flushed back to the REST server.

    :param vg_wrap: VG wrapper representing the Volume Group to update.
    :param vdisks: Iterable of VDisk wrappers representing the Virtual Disks to
                   delete.  Ignored if None or empty.
    :param vopts: Iterable of VOptMedia wrappers representing Virtual Optical
                  devices to delete.  Ignored if None or empty.
    :return: The (possibly) updated vg_wrap.
    """
    changes = 0
    if vdisks:
        changes += len(_rm_vdisks(vg_wrap, vdisks))
    if vopts:
        changes += len(_rm_vopts(vg_wrap, vopts))
    if changes:
        # Update the volume group to remove the storage, if necessary.
        vg_wrap = vg_wrap.update()
    return vg_wrap


def _rm_dev_by_udid(dev, devlist):
    """Use UDID matching to remove a device from a list.

    Use this method in favor of devlist.remove(dev) when the dev originates
    from somewhere other than the devlist, and may have some non-matching
    properties which would cause normal equality comparison to fail.

    For example, use this method when using a VSCSI mapping's backing_storage
    to decide which LogicalUnit to remove from the list of SSP.logical_units.

    Note: This method relies on UDIDs being present in both dev and the
    corresponding item in devlist.

    :param dev: The EntryWrapper representing the device to remove.  May be
                VDisk, VOpt, PV, or LU.
    :param devlist: The list from which to remove the device.
    :return: The device removed, as it existed in the devlist.  None if the
             device was not found by UDID.
    """
    if not dev.udid:
        LOG.warning(_("Ignoring device because it lacks a UDID:\n%s"),
                    dev.toxmlstring(pretty=True))
        return None

    matches = [realdev for realdev in devlist if realdev.udid == dev.udid]
    if len(matches) == 0:
        LOG.warning(_("Device %s not found in list."), dev.name)
        return None
    if len(matches) > 1:
        raise exc.FoundDevMultipleTimes(devname=dev.name, count=len(matches))

    LOG.debug("Removing %s from devlist.", dev.name)
    match = matches[0]
    devlist.remove(match)
    return match


def _rm_vdisks(vg_wrap, vdisks):
    """Delete some number of virtual disks from a volume group wrapper.

    The wrapper is not updated back to the REST server.

    :param vg_wrap: VG wrapper representing the Volume Group to update.
    :param vdisks: Iterable of VDisk wrappers representing the Virtual Disks to
                   delete.
    :return: The number of disks removed from vg_wrap.  The consumer may use
             this to decide whether to run vg_wrap.update() or not.
    """
    existing_vds = vg_wrap.virtual_disks
    changes = []
    for removal in vdisks:
        # Can't just call direct on remove, because attribs are off.
        removed = _rm_dev_by_udid(removal, existing_vds)

        if removed is not None:
            LOG.info(_('Deleting virtual disk %(vdisk)s from volume group '
                       '%(vg)s'), {'vdisk': removed.name, 'vg': vg_wrap.name})
            changes.append(removed)

    return changes


def _rm_vopts(vg_wrap, vopts):
    """Delete some number of virtual optical media from a volume group wrapper.

    The wrapper is not updated back to the REST server.

    :param vg_wrap: VG wrapper representing the Volume Group to update.
    :param vopts: Iterable of VOptMedia wrappers representing the devices to
                  delete.
    :return: The number of VOptMedia removed from vg_wrap.  The consumer may
             use this to decide whether to run vg_wrap.update() or not.
    """
    vg_om = vg_wrap.vmedia_repos[0].optical_media
    changes = []
    for vopt in vopts:
        try:
            vg_om.remove(vopt)
            LOG.info(_('Deleting virtual optical device %(vopt)s from volume '
                       'group %(vg)s'), {'vopt': vopt.name,
                                         'vg': vg_wrap.name})
            changes.append(vopt)
        except ValueError:
            # It's okay if the vopt was already absent.
            pass

    return changes


def crt_lu(tier_or_ssp, name, size, thin=None, typ=None, clone=None):
    """Create a Logical Unit on the specified Tier.

    :param tier_or_ssp: Tier or SSP EntryWrapper denoting the Tier or Shared
                        Storage Pool on which to create the LU.  If an SSP is
                        supplied, the LU is created on the default Tier.
    :param name: Name for the new Logical Unit.
    :param size: LU size in GB with decimal precision.
    :param thin: Provision the new LU as Thin (True) or Thick (False).  If
                 unspecified, use the server default.
    :param typ: The type of LU to create, one of the LUType values.  If
                unspecified, use the server default.
    :param clone: If the new LU is to be a linked clone, this param is a
                  LU(Ent) wrapper representing the backing image LU.
    :return: If the tier_or_ssp argument is an SSP, the updated SSP wrapper
             (containing the new LU and with a new etag) is returned.
             Otherwise, the first return value is the Tier.
    :return: LU ElementWrapper representing the Logical Unit just created.
    """
    is_ssp = isinstance(tier_or_ssp, stor.SSP)
    tier = default_tier_for_ssp(tier_or_ssp) if is_ssp else tier_or_ssp

    lu = stor.LUEnt.bld(tier_or_ssp.adapter, name, size, thin=thin, typ=typ,
                        clone=clone)
    lu = lu.create(parent=tier)

    if is_ssp:
        # Refresh the SSP to pick up the new LU and etag
        tier_or_ssp = tier_or_ssp.refresh()

    return tier_or_ssp, lu


def _rm_lus(all_lus, lus_to_rm, del_unused_images=True):
    changes = []
    backing_images = set()

    for lu in lus_to_rm:
        # Is it a linked clone?  (We only care if del_unused_images.)
        if del_unused_images and lu.lu_type == stor.LUType.DISK:
            # Note: This can add None to the set
            backing_images.add(_image_lu_for_clone(all_lus, lu))
        msgargs = {'lu_name': lu.name, 'lu_udid': lu.udid}
        removed = _rm_dev_by_udid(lu, all_lus)
        if removed:
            LOG.debug(_("Removing LU %(lu_name)s (UDID %(lu_udid)s)"), msgargs)
            changes.append(removed)
        else:
            # It's okay if the LU was already absent.
            LOG.info(_("LU %(lu_name)s was not found - it may have been "
                       "deleted out of band.  (UDID: %(lu_udid)s)"), msgargs)

    # Now remove any unused backing images.  This set will be empty if
    # del_unused_images=False
    for back_img in backing_images:
        # Ignore None, which could have appeared if a clone existed with no
        # backing image.
        if back_img is None:
            continue
        msgargs = {'lu_name': back_img.name, 'lu_udid': back_img.udid}
        # Only remove backing images that are not in use.
        if _image_lu_in_use(all_lus, back_img):
            LOG.debug("Not removing Image LU %(lu_name)s because it is still "
                      "in use.  (UDID: %(lu_udid)s)", msgargs)
        else:
            removed = _rm_dev_by_udid(back_img, all_lus)
            if removed:
                LOG.info(_("Removing Image LU %(lu_name)s because it is no "
                           "longer in use.  (UDID: %(lu_udid)s)"), msgargs)
                changes.append(removed)
            else:
                # This would be wildly unexpected
                LOG.warning(_("Backing LU %(lu_name)s was not found.  "
                              "(UDID: %(lu_udid)s)"), msgargs)
    return changes


def rm_tier_storage(lus_to_rm, tier=None, lufeed=None, del_unused_images=True):
    """Remove Logical Units from a Shared Storage Pool Tier.

    :param lus_to_rm: Iterable of LU ElementWrappers or LUEnt EntryWrappers
                      representing the LogicalUnits to delete.
    :param tier: Tier EntryWrapper representing the SSP Tier on which the
                 lus_to_rm (and their backing images) reside. Either tier or
                 lufeed is required.  If both are specified, tier is ignored.
    :param lufeed: Pre-fetched list of LUEnt (i.e. result of a GET of
                   Tier/{uuid}/LogicalUnit) where we expect to find the
                   lus_to_rm (and their backing images).  Either tier or lufeed
                   is required.  If both are specified, tier is ignored.
    :param del_unused_images: If True, and a removed Disk LU was the last one
                              linked to its backing Image LU, the backing Image
                              LU is also removed.
    :raise ValueError: - If neither tier nor lufeed was supplied.
                       - If lufeed was supplied but doesn't contain LUEnt
                         EntryWrappers (e.g. the caller provided
                         SSP.logical_units).
    """
    if all(param is None for param in (tier, lufeed)):
        raise ValueError(_("Developer error: Either tier or lufeed is "
                           "required."))
    if lufeed is None:
        lufeed = stor.LUEnt.get(tier.adapter, parent=tier)
    elif any(not isinstance(lu, stor.LUEnt) for lu in lufeed):
        raise ValueError(_("Developer error: The lufeed parameter must "
                           "comprise LUEnt EntryWrappers."))

    # Figure out which LUs to delete and delete them; _rm_lus returns a list of
    # LUEnt, so they can be removed directly.
    for dlu in _rm_lus(lufeed, lus_to_rm, del_unused_images=del_unused_images):
        msg_args = dict(lu_name=dlu.name, lu_udid=dlu.udid)
        LOG.info(_("Deleting LU %(lu_name)s (UDID: %(lu_udid)s)"), msg_args)
        try:
            dlu.delete()
        except exc.HttpError as he:
            LOG.warning(he)
            LOG.warning(_("Ignoring HttpError for LU %(lu_name)s may have "
                          "been deleted out of band.  (UDID: %(lu_udid)s)"),
                        msg_args)


@tx.entry_transaction
def rm_ssp_storage(ssp_wrap, lus, del_unused_images=True):
    """Remove some number of LogicalUnits from a SharedStoragePool.

    The changes are flushed back to the REST server.

    :param ssp_wrap: SSP EntryWrapper representing the SharedStoragePool to
    modify.
    :param lus: Iterable of LU ElementWrappers or LUEnt EntryWrappers
                representing the LogicalUnits to delete.
    :param del_unused_images: If True, and a removed Disk LU was the last one
                              linked to its backing Image LU, the backing Image
                              LU is also removed.
    :return: The (possibly) modified SSP wrapper.
    """
    if _rm_lus(ssp_wrap.logical_units, lus,
               del_unused_images=del_unused_images):
        # Flush changes
        ssp_wrap = ssp_wrap.update()
    return ssp_wrap


def _remove_orphan_maps(vwrap, type_str, lpar_id=None):
    """Remove orphan storage mappings (no client adapter) from a list.

    This works for both VSCSI and VFC mappings.

    :param vwrap: VIOS wrapper containing the mappings to inspect.  If type_str
                  is 'VFC', the VIOS wrapper must have been retrieved with the
                  VIO_FMAP extended attribute group; if type_str is 'VSCSI',
                  the VIO_SMAP extended attribute group must have been used.
    :param type_str: The type of mapping being removed.  Must be either 'VFC'
                     or 'VSCSI'.
    :param lpar_id: (Optional) Only orphan mappings associated with the
                    specified LPAR ID will be removed.  If None (the default),
                    all LPARs' mappings will be considered.
    :return: The list of mappings removed.  May be empty.
    """
    # This will raise KeyError if type_str isn't one of 'VFC' or 'VSCSI'
    maps = dict(VSCSI=vwrap.scsi_mappings, VFC=vwrap.vfc_mappings)[type_str]
    msgargs = dict(vios_name=vwrap.name, stg_type=type_str)
    # Make a list of orphans first (since we can't remove while iterating).
    # If requested, limit candidates to those matching the specified LPAR ID.
    removals = [mp for mp in maps if mp.client_adapter is None and (
        lpar_id is None or mp.server_adapter.lpar_id == lpar_id)]
    for rm_map in removals:
        maps.remove(rm_map)
    if removals:
        LOG.warning(_("Removing %(num_maps)d orphan %(stg_type)s mappings "
                      "from VIOS %(vios_name)s."),
                    dict(msgargs, num_maps=len(removals)))
    else:
        LOG.debug("No orphan %(stg_type)s mappings found on VIOS "
                  "%(vios_name)s.", msgargs)
    return removals


def _remove_portless_vfc_maps(vwrap, lpar_id=None):
    """Remove non-logged-in VFC mappings (no Port) from a list.

    :param vwrap: VIOS wrapper containing the mappings to inspect.  Must have
                  been retrieved with the VIO_FMAP extended attribute group.
    :param lpar_id: (Optional) Only port-less mappings associated with the
                    specified LPAR ID will be removed.  If None (the default),
                    all LPARs' mappings will be considered.
    :return: The list of mappings removed.  May be empty.
    """
    # Make a list of removals first (since we can't remove while iterating).
    # If requested, limit candidates to those matching the specified LPAR ID.
    removals = [mp for mp in vwrap.vfc_mappings if mp.backing_port is None and
                (lpar_id is None or mp.server_adapter.lpar_id == lpar_id)]
    for rm_map in removals:
        vwrap.vfc_mappings.remove(rm_map)
    if removals:
        LOG.warning(_("Removing %(num_maps)d port-less VFC mappings from "
                      "VIOS %(vios_name)s."),
                    dict(num_maps=len(removals), vios_name=vwrap.name))
    else:
        LOG.debug("No port-less VFC mappings found on VIOS %(vios_name)s.",
                  dict(vios_name=vwrap.name))
    return removals


def _remove_lpar_maps(vwrap, lpar_ids, type_str):
    """Remove VFC or VSCSI mappings for the specified LPAR IDs.

    :param vwrap: VIOS EntryWrapper containing the mappings to scrub.
    :param lpar_ids: Iterable of short IDs (not UUIDs) of the LPARs whose
                     mappings are to be removed.
    :param type_str: The type of mapping being removed.  Must be either 'VFC'
                     or 'VSCSI'.
    :return: The list of mappings removed.
    """
    # This will raise KeyError if a bogus type_str is passed in
    rm_maps = dict(VSCSI=sm.remove_maps, VFC=fm.remove_maps)[type_str]
    msgargs = dict(stg_type=type_str, vios_name=vwrap.name)
    removals = []
    for lpar_id in lpar_ids:
        msgargs['lpar_id'] = lpar_id
        _removals = rm_maps(vwrap, lpar_id)
        if _removals:
            LOG.warning(_("Removing %(num_maps)d %(stg_type)s mappings "
                          "associated with LPAR ID %(lpar_id)d from VIOS "
                          "%(vios_name)s."),
                        dict(msgargs, num_maps=len(_removals)))
            removals.extend(_removals)
        else:
            LOG.debug("No %(stg_type)s mappings found for LPAR ID "
                      "%(lpar_id)d on VIOS %(vios_name)s.", msgargs)
    return removals


class _RemoveStorage(tf_tsk.Task):
    def __init__(self, tag):
        """Initialize the storage removal Task.

        :param tag: Added to the Task name to make it unique within a Flow.
        """
        super(_RemoveStorage, self).__init__('rm_storage_%s' % tag)

    def execute(self, wrapper_task_rets):
        """Remove the storage elements associated with the deleted mappings.

        We remove storage elements for each VIOS, but only those we can be sure
        belong ONLY to that VIOS.  That is, we do not remove SSP Logical Units
        because they may be mapped from some other VIOS in the cluster - one we
        don't even know about.
        """
        # Accumulate removal tasks
        rmtasks = []
        for vuuid, rets in wrapper_task_rets.items():
            vwrap = rets['wrapper']
            # VFC mappings don't have storage we can get to, so ignore those.

            # We may get removals from more than one subtask.  All will have
            # the 'vscsi_removals_' prefix.  There may be some overlap, but
            # the removal methods will ignore duplicates.
            vscsi_rms = []
            for vrk in (k for k in rets if k.startswith('vscsi_removals_')):
                vscsi_rms.extend(rets[vrk])

            # We can short out of this VIOS if no vscsi mappings were removed
            # from it.
            if not vscsi_rms:
                continue

            # Index remaining VSCSI mappings to isolate still-in-use storage.
            smindex = sm.index_mappings(vwrap.scsi_mappings)

            # Figure out which storage elements need to be removed.
            # o Some VSCSI mappings may not have backing storage.
            # o Ignore any storage elements that are still in use (still have
            # mappings associated with them).
            stg_els_to_remove = [
                rmap.backing_storage for rmap in vscsi_rms if
                rmap.backing_storage is not None and
                rmap.backing_storage.udid not in smindex['by-storage-udid']]

            # If there's nothing left, we're done with this VIOS
            if not stg_els_to_remove:
                continue

            # Extract lists of each type of storage
            vopts_to_rm = []
            vdisks_to_rm = []
            for stg in stg_els_to_remove:
                if isinstance(stg, (stor.LU, stor.PV)):
                    LOG.warning(
                        _("Not removing storage %(stg_name)s of type "
                          "%(stg_type)s because it cannot be determined "
                          "whether it is still in use.  Manual verification "
                          "and cleanup may be necessary."),
                        {'stg_name': stg.name, 'stg_type': stg.schema_type})
                elif isinstance(stg, stor.VOptMedia):
                    vopts_to_rm.append(stg)
                elif isinstance(stg, stor.VDisk):
                    vdisks_to_rm.append(stg)
                else:
                    LOG.warning(
                        _("Storage scrub ignoring storage element "
                          "%(stg_name)s because it is of unexpected type "
                          "%(stg_type)s."),
                        {'stg_name': stg.name, 'stg_type': stg.schema_type})

            # Any storage to be deleted?
            if not any((vopts_to_rm, vdisks_to_rm)):
                continue

            # If we get here, we have storage that needs to be deleted from one
            # or more volume groups.  We don't have a way of knowing which ones
            # without REST calls, so get all VGs for this VIOS and delete from
            # all of them.  POST will only be done on VGs which actually need
            # updating.
            vgftsk = tx.FeedTask('scrub_vg_vios_%s' % vuuid, stor.VG.getter(
                vwrap.adapter, parent=vwrap))
            if vdisks_to_rm:
                vgftsk.add_functor_subtask(
                    _rm_vdisks, vdisks_to_rm, logspec=(LOG.warning, _(
                        "Scrubbing the following %(vdcount)d Virtual Disks "
                        "from VIOS %(vios)s: %(vdlist)s"), {
                            'vdcount': len(vdisks_to_rm), 'vios': vwrap.name,
                            'vdlist': ["%s (%s)" % (vd.name, vd.udid) for vd
                                       in vdisks_to_rm]}))
            if vopts_to_rm:
                vgftsk.add_functor_subtask(
                    _rm_vopts, vopts_to_rm, logspec=(LOG.warning, _(
                        "Scrubbing the following %(vocount)d Virtual Opticals "
                        "from VIOS %(vios)s: %(volist)s"), {
                            'vocount': len(vopts_to_rm), 'vios': vwrap.name,
                            'volist': ["%s (%s)" % (vo.name, vo.udid) for vo
                                       in vopts_to_rm]}))
            rmtasks.append(vgftsk)

        # We only created removal Tasks if we found something to remove.
        if rmtasks:
            # Execute any storage removals in parallel, max 8 threads.
            tf_eng.run(
                tf_uf.Flow('remove_storage').add(*rmtasks), engine='parallel',
                executor=tx.ContextThreadPoolExecutor(max(8, len(rmtasks))))


def add_lpar_storage_scrub_tasks(lpar_ids, ftsk, lpars_exist=False,
                                 remove_storage=True):
    """Delete storage mappings and elements associated with an LPAR ID.

    This should typically be used to clean leftovers from an LPAR that has been
    deleted, since stale storage artifacts can cause conflicts with a new LPAR
    recycling that ID.

    This operates by inspecting mappings first, since we have no other way to
    associate a mapping-less storage element with an LPAR ID.

    Storage elements are deleted if their only mappings are to the LPAR ID
    being scrubbed (and remove_storage=True).

    This method only adds subtasks/post-execs to the passed-in FeedTask.  The
    caller is responsible for executing that FeedTask in an appropriate Flow or
    other context.

    :param lpar_ids: List of integer short IDs (not UUIDs) of the LPAR whose
                     storage artifacts are to be scrubbed.
    :param ftsk: FeedTask to which the scrubbing actions should be added, for
                 execution by the caller.  The FeedTask must be built for all
                 the VIOSes from which mappings and storage should be scrubbed.
                 The feed/getter must use the VIO_SMAP and VIO_FMAP xags.
    :param lpars_exist: (Optional) If set to False (the default), storage
                        artifacts associated with an extant LPAR will be
                        ignored (NOT scrubbed).  Otherwise, we will scrub
                        whether the LPAR exists or not. Thus, set to True only
                        if intentionally removing mappings associated with
                        extant LPARs.
    :param remove_storage: If True (the default), storage elements associated
                           with stale mappings are removed, assuming it can be
                           verified that they were only in use by this LPAR.
                           If False, no storage removal is attempted.
    """
    tag = '_'.join((str(lpar_id) for lpar_id in lpar_ids))

    def remove_chain(vwrap, stg_type):
        """_remove_lpar_maps with an additional check for existing LPARs."""
        lpar_id_set = set(lpar_ids)
        if not lpars_exist:
            # Restrict scrubbing to LPARs that don't exist on the system.
            ex_lpar_ids = {lwrap.id for lwrap in lpar.LPAR.get(
                vwrap.adapter, parent_type=sys.System,
                parent_uuid=vwrap.assoc_sys_uuid)}
            ex_lpar_ids.update(vioswrap.id for vioswrap in vios.VIOS.get(
                vwrap.adapter, parent_type=sys.System,
                parent_uuid=vwrap.assoc_sys_uuid))
            # The list of IDs of the LPARs whose mappings (and storage) are to
            # be preserved (not scrubbed) is the intersection of
            # {the IDs we we were asked to scrub}
            # and
            # {the IDs of all the LPARs on the system}
            lpar_ids_to_preserve = lpar_id_set & ex_lpar_ids
            if lpar_ids_to_preserve:
                LOG.warning(_("Skipping scrub of %(stg_type)s mappings from "
                              "VIOS %(vios_name)s for the following LPAR IDs "
                              "because those LPARs exist: %(lpar_ids)s"),
                            dict(stg_type=stg_type, vios_name=vwrap.name,
                                 lpar_ids=list(lpar_ids_to_preserve)))
                lpar_id_set -= lpar_ids_to_preserve
        return _remove_lpar_maps(vwrap, lpar_id_set, stg_type)

    ftsk.add_functor_subtask(remove_chain, 'VSCSI',
                             provides='vscsi_removals_' + tag)
    ftsk.add_functor_subtask(remove_chain, 'VFC')
    if remove_storage:
        ftsk.add_post_execute(_RemoveStorage(tag))


def add_orphan_storage_scrub_tasks(ftsk, lpar_id=None):
    """Delete orphan mappings (no client adapter) and their storage elements.

    :param ftsk: FeedTask to which the scrubbing actions should be added, for
                 execution by the caller.  The FeedTask must be built for all
                 the VIOSes from which mappings and storage should be scrubbed.
                 The feed/getter must use the VIO_SMAP and VIO_FMAP xags.
    :param lpar_id: (Optional) Only orphan mappings associated with the
                    specified LPAR ID will be removed.  If None (the default),
                    all LPARs' mappings will be considered.
    """
    ftsk.add_functor_subtask(_remove_orphan_maps, 'VSCSI', lpar_id=lpar_id,
                             provides='vscsi_removals_orphans')
    ftsk.add_functor_subtask(_remove_orphan_maps, 'VFC', lpar_id=lpar_id)
    ftsk.add_post_execute(_RemoveStorage('orphans'))


def find_stale_lpars(vios_w):
    """Find orphan LPAR IDs in a Virtual I/O Server's VSCSI/VFC mappings.

    This method collates all client LPAR IDs from the VSCSI/VFC mappings of the
    specified VIOS wrapper and compares to the list of LPAR IDs on that VIOS's
    host, returning the list of any IDs which exist in the former but not the
    latter.

    :param vios_w: VIOS EntryWrapper.  To be effective, this must have been
                   retrieved with the VIO_SMAP and VIO_FMAP extended
                   attribute groups.
    :return: List of LPAR IDs (integer short IDs, not UUIDs) which don't exist
             on the system.  The list is guaranteed to contain no duplicates.
    """
    ex_lpar_ids = {lwrap.id for lwrap in lpar.LPAR.get(
        vios_w.adapter, parent_type=sys.System,
        parent_uuid=vios_w.assoc_sys_uuid)}
    vios_ids = {vioswrap.id for vioswrap in vios.VIOS.get(
        vios_w.adapter, parent_type=sys.System,
        parent_uuid=vios_w.assoc_sys_uuid)}
    ex_lpar_ids.update(vios_ids)
    map_lpar_ids = {smp.server_adapter.lpar_id for smp in
                    (list(vios_w.scsi_mappings) + list(vios_w.vfc_mappings))}
    return list(map_lpar_ids - ex_lpar_ids)


class ComprehensiveScrub(tx.FeedTask):
    """Scrub all the stale/orphan mappings/storage we can find.

    A FeedTask which does the following:

    For all VIOSes (on the host):
        For each stale LPAR
            Scrub mappings & storage
        Scrub all orphan mappings (those without client adapters)
    """
    def __init__(self, adapter, host_uuid=None):
        """Create the FeedTask to scrub stale/orphan mappings/storage.

        :param adapter: A pypowervm.adapter.Adapter for REST API communication.
        :param host_uuid: (Optional) If specified, limit to VIOSes on this one
                          host.  Otherwise, scrub across all VIOSes known to
                          the adapter.
        """
        getter_kwargs = {'xag': [c.XAG.VIO_FMAP, c.XAG.VIO_SMAP]}
        if host_uuid is not None:
            getter_kwargs = dict(getter_kwargs, parent_class=sys.System,
                                 parent_uuid=host_uuid)
        super(ComprehensiveScrub, self).__init__(
            'comprehensive_scrub', vios.VIOS.getter(adapter, **getter_kwargs))

        self.add_functor_subtask(find_stale_lpars, provides='stale_lpar_ids',
                                 flag_update=False)

        # Wrap _remove_lpar_maps to get the stale LPAR IDs from the above
        # find_stale_lpars Subtask.
        def remove_chain(vwrap, stg_type, provided):
            return _remove_lpar_maps(
                vwrap, provided['stale_lpar_ids'], stg_type)
        self.add_functor_subtask(remove_chain, 'VSCSI',
                                 provides='vscsi_removals_bylparid')
        self.add_functor_subtask(remove_chain, 'VFC')
        self.add_functor_subtask(_remove_orphan_maps, 'VSCSI',
                                 provides='vscsi_removals_orphans')
        self.add_functor_subtask(_remove_orphan_maps, 'VFC')
        self.add_post_execute(_RemoveStorage('comprehensive'))


class ScrubOrphanStorageForLpar(tx.FeedTask):
    """Scrub orphan mappings and their storage for one specific LPAR."""
    def __init__(self, adapter, lpar_id, host_uuid=None):
        """Create the FeedTask to scrub orphan mappings/storage by LPAR ID.

        :param adapter: A pypowervm.adapter.Adapter for REST API communication.
        :param lpar_id: The integer short ID (not UUID) of the LPAR to be
                        examined and scrubbed of orphan mappings and their
                        storage.
        :param host_uuid: (Optional) If specified, limit to VIOSes on this one
                          host.  Otherwise, scrub across all VIOSes known to
                          the adapter.
        """
        getter_kwargs = {'xag': [c.XAG.VIO_FMAP, c.XAG.VIO_SMAP]}
        if host_uuid is not None:
            getter_kwargs = dict(getter_kwargs, parent_class=sys.System,
                                 parent_uuid=host_uuid)
        super(ScrubOrphanStorageForLpar, self).__init__(
            'scrub_orphans_for_lpar_%d' % lpar_id, vios.VIOS.getter(
                adapter, **getter_kwargs))

        self.add_functor_subtask(_remove_orphan_maps, 'VSCSI', lpar_id=lpar_id,
                                 provides='vscsi_removals_orphans_lpar_id_%d' %
                                 lpar_id)
        self.add_functor_subtask(_remove_orphan_maps, 'VFC', lpar_id=lpar_id)
        self.add_post_execute(_RemoveStorage('orphans_for_lpar_%d' % lpar_id))


class ScrubPortlessVFCMaps(tx.FeedTask):
    """Scrub virtual fibre channel mappings which have no backing port."""
    def __init__(self, adapter, lpar_id=None, host_uuid=None):
        """Create the FeedTask to scrub VFC mappings with no backing port.

        :param adapter: A pypowervm.adapter.Adapter for REST API communication.
        :param lpar_id: (Optional) The integer short ID (not UUID) of the LPAR
                        to be examined and scrubbed of portless VFC mappings.
                        If unspecified, all LPARs' mappings will be examined.
        :param host_uuid: (Optional) If specified, limit to VIOSes on this one
                          host.  Otherwise, scrub across all VIOSes known to
                          the adapter.
        """
        getter_kwargs = {'xag': [c.XAG.VIO_FMAP]}
        if host_uuid is not None:
            getter_kwargs = dict(getter_kwargs, parent_class=sys.System,
                                 parent_uuid=host_uuid)
        name = 'scrub_portless_vfc_maps_for_' + ('all_lpars' if lpar_id is None
                                                 else 'lpar_%d' % lpar_id)
        super(ScrubPortlessVFCMaps, self).__init__(
            name, vios.VIOS.getter(adapter, **getter_kwargs))
        self.add_functor_subtask(_remove_portless_vfc_maps, lpar_id=lpar_id)
