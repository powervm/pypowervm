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

"""Create, remove, map, unmap, and populate virtual storage objects."""

import logging
import math
import threading
import time

from concurrent import futures
from oslo_concurrency import lockutils as lock

import pypowervm.const as c
import pypowervm.exceptions as exc
from pypowervm.i18n import _
from pypowervm import util
from pypowervm.wrappers import job
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf
import pypowervm.wrappers.virtual_io_server as vios

FILE_UUID = 'FileUUID'

# Setup logging
LOG = logging.getLogger(__name__)

_LOCK_SSP = 'ssp_op_lock'
_LOCK_VOL_GRP = 'vol_grp_lock'

# Concurrent uploads
_UPLOAD_SEM = threading.Semaphore(3)


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
    :param d_size: (OPTIONAL) The desired size of the new VDisk in bytes.  If
                     omitted or smaller than f_size, it will be set to match
                     f_size.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful for
                       integrity checks.
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
    #
    # See note below...temporary workaround needed.
    if d_size is None or d_size < f_size:
        d_size = f_size
    gb_size = util.convert_bytes_to_gb(d_size)

    # TODO(IBM) Temporary - need to round up to the highest GB.  This should
    # be done by the platform in the future.
    gb_size = math.ceil(gb_size)

    n_vdisk = crt_vdisk(adapter, v_uuid, vol_grp_uuid, d_name, gb_size)

    # The file type.  If local API server, then we can use the coordinated
    # file path.  Otherwise standard upload.
    file_type = (vf.FileType.DISK_IMAGE_COORDINATED if adapter.traits.local_api
                 else vf.FileType.DISK_IMAGE)

    # Next, create the file, but specify the appropriate disk udid from the
    # Virtual Disk
    vio_file = _create_file(
        adapter, d_name, file_type, v_uuid, f_size=f_size,
        tdev_udid=n_vdisk.udid, sha_chksum=sha_chksum)

    maybe_file = _upload_stream(vio_file, d_stream)
    return n_vdisk, maybe_file


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
    f_uuid = _upload_stream(vio_file, d_stream)

    # Simply return a reference to this.
    reference = stor.VOptMedia.bld_ref(adapter, f_name)

    return reference, f_uuid


def upload_new_lu(v_uuid,  ssp, d_stream, lu_name, f_size, d_size=None,
                  sha_chksum=None):
    """Creates a new SSP Logical Unit and uploads a data stream to it.

    :param v_uuid: The UUID of the Virtual I/O Server through which to perform
                   the upload.  (Note that the new LU will be visible from any
                   VIOS in the Shared Storage Pool's Cluster.)
    :param ssp: SSP EntryWrapper representing the Shared Storage Pool on which
                to create the new Logical Unit.
    :param d_stream: The data stream (either a file handle or stream) to
                     upload.  Must have the 'read' method that returns a chunk
                     of bytes.
    :param lu_name: The name that should be given to the new LU.
    :param f_size: The size (in bytes) of the stream to be uploaded.
    :param d_size: (OPTIONAL) The size of the LU (in bytes).  Not required if
                   it should match the file.  Must be at least as large as the
                   file.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :return: The first return value is an LU EntryWrapper corresponding to the
             Logical Unit into which the file was uploaded.
    :return: Normally the second return value will be None, indicating that the
             LU was created and the image was uploaded without issue.  If for
             some reason the File metadata for the VIOS was not cleaned up, the
             return value is the LU EntryWrapper.  This is simply a marker to
             be later used to retry the cleanup.
    """
    # Create the new Logical Unit.  The LU size needs to be in decimal GB.
    if d_size is None or d_size < f_size:
        d_size = f_size
    gb_size = util.convert_bytes_to_gb(d_size, dp=2)

    ssp, new_lu = crt_lu(ssp, lu_name, gb_size, typ=stor.LUType.IMAGE)

    # The file type.  If local API server, then we can use the coordinated
    # file path.  Otherwise standard upload.
    file_type = (vf.FileType.DISK_IMAGE_COORDINATED
                 if ssp.adapter.traits.local_api
                 else vf.FileType.DISK_IMAGE)

    # Create the file, specifying the UDID from the new Logical Unit.
    # The File name matches the LU name.
    vio_file = _create_file(
        ssp.adapter, lu_name, file_type, v_uuid, f_size=f_size,
        tdev_udid=new_lu.udid, sha_chksum=sha_chksum)

    maybe_file = _upload_stream(vio_file, d_stream)
    return new_lu, maybe_file


def _upload_stream(vio_file, d_stream):
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
    :return: Normally this method will return None, indicating that the disk
             and image were uploaded without issue.  If for some reason the
             File metadata for the VIOS was not cleaned up, the return value
             is the File EntryWrapper.  This is simply a marker to be later
             used to retry the cleanup.
    """
    try:
        # Acquire the upload semaphore
        _UPLOAD_SEM.acquire()

        if vio_file.enum_type == vf.FileType.DISK_IMAGE_COORDINATED:
            # This path offers low CPU overhead and higher throughput, but
            # can only be executed if running on the same system as the API.
            # It works by writing to a file 'pipe'.  This is harder to
            # coordinate.  But the vio_file's 'asset_file' tells us where
            # to write the stream to.

            # A reader to tell the API we have nothing to upload
            class EmptyReader(object):
                def read(self, size):
                    return None

            with futures.ThreadPoolExecutor(max_workers=2) as th:
                # The upload file is a blocking call (won't return until pipe
                # is fully written to), which is why we put it in another
                # thread.
                upload_f = th.submit(vio_file.adapter.upload_file,
                                     vio_file.element, EmptyReader())

                # Create a function that streams to the FIFO pipe
                out_stream = open(vio_file.asset_file, 'a+b', 0)

                def copy_func(in_stream, out_stream):
                    while True:
                        chunk = d_stream.read(65536)
                        if not chunk:
                            break
                        out_stream.write(chunk)

                        # Yield to other threads
                        time.sleep(0)

                    # The close indicates to the other side we are done.  Will
                    # force the upload_file to return.
                    out_stream.close()
                copy_f = th.submit(copy_func, d_stream, out_stream)

            try:
                # Make sure we call the results.  This is just to make sure it
                # doesn't have exceptions
                for io_future in futures.as_completed([upload_f, copy_f]):
                    io_future.result()
            finally:
                # If the upload failed, then make sure we close the stream.
                # This will ensure that if one of the threads fail, both fail.
                # Note that if it is already closed, this no-ops.
                out_stream.close()
        else:
            # Upload the file directly to the REST API server.
            vio_file.adapter.upload_file(vio_file.element, d_stream)
    finally:
        # Must release the semaphore
        _UPLOAD_SEM.release()

        try:
            # Cleanup after the upload
            vio_file.adapter.delete(vf.File.schema_type, root_id=vio_file.uuid,
                                    service='web')
        except Exception:
            LOG.exception(_('Unable to cleanup after file upload. '
                            'File uuid: %s') % vio_file.uuid)
            return vio_file
    return None


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


def crt_lu_linked_clone(ssp, cluster, src_lu, new_lu_name, lu_size_gb=0):
    """Create a new LU as a linked clone to a backing image LU.

    :param ssp: The SSP EntryWrapper representing the SharedStoragePool on
                which to create the new LU.
    :param cluster: The Cluster EntryWrapper representing the Cluster against
                    which to invoke the LULinkedClone Job.
    :param src_lu: The LU EntryWrapper representing the link source.
    :param new_lu_name: The name to be given to the new LU.
    :param lu_size_gb: The size of the new LU in GB with decimal precision.  If
                       this is not specified or is smaller than the size of the
                       image_lu, the size of the image_lu is used.
    :return: The updated SSP EntryWrapper containing the newly-created LU.
    :return: The newly created and linked LU.
    """
    # New LU must be at least as big as the backing LU.
    lu_size_gb = max(lu_size_gb, src_lu.capacity)

    # Create the LU.  No locking needed on this method, as the crt_lu handles
    # the locking.
    ssp, dst_lu = crt_lu(ssp, new_lu_name, lu_size_gb, thin=True,
                         typ=stor.LUType.DISK)

    # Run the job to link the new LU to the source
    jresp = ssp.adapter.read(cluster.schema_type, suffix_type=c.SUFFIX_TYPE_DO,
                             suffix_parm='LULinkedClone')
    jwrap = job.Job.wrap(jresp)

    jparams = [
        jwrap.create_job_parameter(
            'SourceUDID', src_lu.udid),
        jwrap.create_job_parameter(
            'DestinationUDID', dst_lu.udid)]
    jwrap.run_job(cluster.uuid, job_parms=jparams)

    return ssp, dst_lu


@lock.synchronized(_LOCK_SSP)
def remove_lu_linked_clone(ssp, disk_lu, del_unused_image=False,
                           update=True):
    """Remove a linked clone LU and maybe its backing Image LU.

    :param ssp: The SSP EntryWrapper representing the SharedStoragePool on
                which to operate.
    :param disk_lu: The LU EntryWrapper representing the Disk LU linked clone
                    to remove.
    :param del_unused_image: If True, and the removed Disk LU was the last one
                             linked to its backing Image LU, the backing Image
                             LU is also removed.
    :param update: If True, flush the change back through the adapter.  If
                   False, just update the ssp wrapper locally.  Use this to
                   optimize multiple concurrent removals.
    :return: The updated SSP EntryWrapper.
    """
    # Find the right image LU
    image_lu = _image_lu_for_clone(ssp, disk_lu)
    if image_lu is None:
        raise exc.BackingLUNotFoundError(lu_name=disk_lu.name,
                                         ssp_name=ssp.name)

    # Remove the disk_lu.  Don't flush the update yet.
    LOG.debug("Removing Disk LU %(lu_name)s from SSP %(ssp_name)s"
              % dict(lu_name=disk_lu.name, ssp_name=ssp.name))
    ssp, removed_lu = rm_lu(ssp, lu=disk_lu, update=False)

    # Remove the image LU if requested and it's no longer in use
    if del_unused_image:
        if _image_lu_in_use(ssp, image_lu):
            LOG.debug("Not removing Image LU %(lu_name)s from SSP "
                      "%(ssp_name)s because it is still in use."
                      % dict(lu_name=image_lu.name, ssp_name=ssp.name))
        else:
            LOG.debug("Removing Image LU %(lu_name)s from SSP %(ssp_name)s "
                      "because it is no longer in use."
                      % dict(lu_name=image_lu.name, ssp_name=ssp.name))
            ssp.logical_units.remove(image_lu)

    # Finally, push the update back to PowerVM if requested.
    if update:
        ssp = ssp.update()
    return ssp


def _image_lu_for_clone(ssp, clone_lu):
    """Given a Disk LU linked clone, find the Image LU to which it is linked.

    :param ssp: The SSP EntryWrapper to search.
    :param clone_lu: The LU EntryWrapper representing the Disk LU linked clone
                     whose backing Image LU is to be found.
    :return: The LU EntryWrapper representing the Image LU backing the
             clone_lu.  None if no such Image LU can be found.
    """
    # When comparing udid/cloned_from_udid, disregard the 2-digit 'type' prefix
    image_udid = clone_lu.cloned_from_udid[2:]
    for lu in ssp.logical_units:
        if lu.lu_type != stor.LUType.IMAGE:
            continue
        if lu.udid[2:] == image_udid:
            return lu
    return None


def _image_lu_in_use(ssp, image_lu):
    """Determine whether an Image LU still has any Disk LU linked clones.

    :param ssp: The SSP EntryWrapper to search.
    :param image_lu: LU EntryWrapper representing the Image LU.
    :return: True if the SSP contains any Disk LU linked clones backed by the
             image_lu; False otherwise.
    """
    # When comparing udid/cloned_from_udid, disregard the 2-digit 'type' prefix
    image_udid = image_lu.udid[2:]
    for lu in ssp.logical_units:
        if lu.lu_type != stor.LUType.DISK:
            continue
        if lu.cloned_from_udid[2:] == image_udid:
            return True
    return False


@lock.synchronized(_LOCK_VOL_GRP)
def crt_vdisk(adapter, v_uuid, vol_grp_uuid, d_name, d_size_gb):
    """Creates a new Virtual Disk in the specified volume group.

    :param adapter: The pypowervm.adapter.Adapter through which to request the
                     change.
    :param v_uuid: The UUID of the Virtual I/O Server that will host the disk.
    :param vol_grp_uuid: The volume group that will host the new Virtual Disk.
    :param d_name: The name that should be given to the disk on the Virtual
                   I/O Server that will contain the file.
    :param d_size_gb: The size of the disk in GB.
    :return: VDisk ElementWrapper representing the new VirtualDisk from the
             server response (i.e. UDID will be populated).
    :raise exc.Error: If the server response from attempting to add the VDisk
                      does not contain the new VDisk.
    """
    # Get the existing volume group
    vol_grp_data = adapter.read(vios.VIOS.schema_type, v_uuid,
                                stor.VG.schema_type, vol_grp_uuid)
    vol_grp = stor.VG.wrap(vol_grp_data.entry)

    new_vdisk = stor.VDisk.bld(adapter, d_name, d_size_gb)

    # Append it to the list.
    vol_grp.virtual_disks.append(new_vdisk)

    # Now perform an update on the adapter.
    vol_grp = vol_grp.update()

    # The new Virtual Disk should be created.  Find the one we created.
    for vdisk in vol_grp.virtual_disks:
        if vdisk.name == d_name:
            return vdisk
    # This should never occur since the update went through without error,
    # but adding just in case as we don't want to create the file meta
    # without a backing disk.
    raise exc.Error(_("Unable to locate new vDisk on file upload."))


@lock.synchronized(_LOCK_SSP)
def crt_lu(ssp, name, size, thin=None, typ=None):
    """Create a Logical Unit on the specified Shared Storage Pool.

    :param ssp: SSP EntryWrapper denoting the Shared Storage Pool on which to
                create the LU.
    :param name: Name for the new Logical Unit.
    :param size: LU size in GB with decimal precision.
    :param thin: Provision the new LU as Thin (True) or Thick (False).  If
                 unspecified, use the server default.
    :param typ: The type of LU to create, one of the LUType values.  If
                unspecified, use the server default.
    :return: The updated SSP wrapper.  (It will contain the new LU and have a
             new etag.)
    :return: LU ElementWrapper representing the Logical Unit just created.
    """
    # Refuse to add with duplicate name
    if name in [lu.name for lu in ssp.logical_units]:
        raise exc.DuplicateLUNameError(lu_name=name, ssp_name=ssp.name)

    lu = stor.LU.bld(ssp.adapter, name, size, thin=thin, typ=typ)
    ssp.logical_units.append(lu)
    ssp = ssp.update()
    newlu = None
    for lu in ssp.logical_units:
        if lu.name == name:
            newlu = lu
            break
    return ssp, newlu


def rm_lu(ssp, lu=None, udid=None, name=None, update=True):
    """Remove a LogicalUnit from a SharedStoragePool.

    This method allows the LU to be specified by wrapper, name, or UDID.

    :param ssp: SSP EntryWrapper denoting the Shared Storage Pool from which to
                remove the LU.
    :param lu: LU ElementWrapper indicating the LU to remove.  If specified,
               the name and udid parameters are ignored.
    :param udid: The UDID of the LU to remove.  If both name and udid are
                 specified, udid is used.
    :param name: The name of the LU to remove.  If both name and udid are
                 specified, udid is used.
    :param update: If True, flush the change back through the adapter.  If
                   False, just update the ssp wrapper locally.
    :return: The updated SSP wrapper.  (It will contain the modified LU list
             and have a new etag.)
    :return: LU ElementWrapper representing the Logical Unit removed.
    """
    lus = ssp.logical_units
    lu_to_rm = None
    if lu:
        try:
            lu_to_rm = lus[lus.index(lu)]
        except ValueError:
            raise exc.LUNotFoundError(lu_label=lu.name, ssp_name=ssp.name)
    else:
        for l in lus:
            # This should implicitly account for 'None'
            if l.udid == udid or l.name == name:
                lu_to_rm = l
                break
        if lu_to_rm is None:
            label = name or udid
            raise exc.LUNotFoundError(lu_label=label, ssp_name=ssp.name)
    lus.remove(lu_to_rm)

    if update:
        with lock.lock(_LOCK_SSP):
            ssp = ssp.update()
    return ssp, lu_to_rm
