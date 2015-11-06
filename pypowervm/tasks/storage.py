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

import math
import threading
import time

from concurrent import futures
from oslo_concurrency import lockutils as lock
from oslo_log import log as logging
import taskflow.engines as tf_eng
from taskflow.patterns import unordered_flow as tf_uf
import taskflow.task as tf_tsk

import pypowervm.const as c
import pypowervm.exceptions as exc
from pypowervm.i18n import _
from pypowervm.tasks import scsi_mapper as sm
from pypowervm.tasks import vfc_mapper as fm
from pypowervm import util
from pypowervm.utils import retry
from pypowervm.utils import transaction as tx
from pypowervm.wrappers import job
import pypowervm.wrappers.logical_partition as lpar
import pypowervm.wrappers.managed_system as sys
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.vios_file as vf
import pypowervm.wrappers.virtual_io_server as vios

FILE_UUID = 'FileUUID'

# Setup logging
LOG = logging.getLogger(__name__)

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
        cloned_from = lu.cloned_from_udid
        if cloned_from is None:
            LOG.warn(_("Linked clone Logical Unit %(luname)s (UDID %(udid)s) "
                       "has no backing image LU.  It should probably be "
                       "deleted."), {'luname': lu.name, 'udid': lu.udid})
            continue
        if cloned_from[2:] == image_udid:
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


@lock.synchronized(_LOCK_VOL_GRP)
@retry.retry(argmod_func=retry.refresh_wrapper)
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
        LOG.warn(_("Ignoring device because it lacks a UDID:\n%s"),
                 dev.toxmlstring())
        return None

    matches = [realdev for realdev in devlist if realdev.udid == dev.udid]
    if len(matches) == 0:
        LOG.warn(_("Device %s not found in list."), dev.name)
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


@tx.entry_transaction
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


def _rm_lus(ssp_wrap, lus, del_unused_images=True):
    ssp_lus = ssp_wrap.logical_units
    changes = []
    backing_images = set()

    for lu in lus:
        # Is it a linked clone?  (We only care if del_unused_images.)
        if del_unused_images and lu.lu_type == stor.LUType.DISK:
            # Note: This can add None to the set
            backing_images.add(_image_lu_for_clone(ssp_wrap, lu))
        msg_args = dict(lu_name=lu.name, ssp_name=ssp_wrap.name)
        removed = _rm_dev_by_udid(lu, ssp_lus)
        if removed:
            LOG.info(_("Removing LU %(lu_name)s from SSP %(ssp_name)s"),
                     msg_args)
            changes.append(lu)
        else:
            # It's okay if the LU was already absent.
            LOG.info(_("LU %(lu_name)s was not found in SSP %(ssp_name)s"),
                     msg_args)

    # Now remove any unused backing images.  This set will be empty if
    # del_unused_images=False
    for backing_image in backing_images:
        # Ignore None, which could have appeared in the unusual event that a
        # clone existed with no backing image.
        if backing_image is not None:
            msg_args = dict(lu_name=backing_image.name, ssp_name=ssp_wrap.name)
            # Only remove backing images that are not in use.
            if _image_lu_in_use(ssp_wrap, backing_image):
                LOG.debug("Not removing Image LU %(lu_name)s from SSP "
                          "%(ssp_name)s because it is still in use." %
                          msg_args)
            else:
                removed = _rm_dev_by_udid(backing_image, ssp_lus)
                if removed:
                    LOG.info(_("Removing Image LU %(lu_name)s from SSP "
                               "%(ssp_name)s because it is no longer in use."),
                             msg_args)
                    changes.append(backing_image)
                else:
                    # This would be wildly unexpected
                    LOG.warn(_("Backing LU %(lu_name)s was not found in SSP "
                               "%(ssp_name)s"), msg_args)
    return changes


@tx.entry_transaction
def rm_ssp_storage(ssp_wrap, lus, del_unused_images=True):
    """Remove some number of LogicalUnits from a SharedStoragePool.

    The changes are flushed back to the REST server.

    :param ssp_wrap: SSP EntryWrapper representing the SharedStoragePool to
    modify.
    :param lus: Iterable of LU EntryWrappers representing the LogicalUnits to
                delete.
    :param del_unused_images: If True, and a removed Disk LU was the last one
                              linked to its backing Image LU, the backing Image
                              LU is also removed.
    :return: The (possibly) modified SSP wrapper.
    """
    if _rm_lus(ssp_wrap, lus, del_unused_images=del_unused_images):
        # Flush changes
        ssp_wrap = ssp_wrap.update()
    return ssp_wrap


def _remove_orphan_maps(vwrap, type_str, lpar_id=None):
    """Remove orphan storage mappings (no client adapter) from a list.

    This works for both VSCSI and VFC mappings.

    :param vwrap: VIOS wrapper containing the mappings to inspect.  If type_str
                  is 'VFC', the VIOS wrapper must have been retrieved with the
                  FC_MAPPING extended attribute group; if type_str is 'VSCSI',
                  the SCSI_MAPPING extended attribute group must have been
                  used.
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
        LOG.warn(_("Removing %(num_maps)d orphan %(stg_type)s mappings from "
                   "VIOS %(vios_name)s."),
                 dict(msgargs, num_maps=len(removals)))
    else:
        LOG.debug("No orphan $(stg_type)s mappings found on VIOS "
                  "%(vios_name)s.", msgargs)
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
            LOG.warn(_("Removing %(num_maps)d %(stg_type)s mappings "
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
                    LOG.warn(_("Not removing storage %(stg_name)s of type "
                               "%(stg_type)s because it cannot be determined "
                               "whether it is still in use.  Manual "
                               "verification and cleanup may be necessary."),
                             {'stg_name': stg.name,
                              'stg_type': stg.schema_type})
                elif isinstance(stg, stor.VOptMedia):
                    vopts_to_rm.append(stg)
                elif isinstance(stg, stor.VDisk):
                    vdisks_to_rm.append(stg)
                else:
                    LOG.warn(_("Storage scrub ignoring storage element "
                               "%(stg_name)s because it is of unexpected type "
                               "%(stg_type)s."),
                             {'stg_name': stg.name,
                              'stg_type': stg.schema_type})

            # Any storage to be deleted?
            if not any((vopts_to_rm, vdisks_to_rm)):
                continue

            # If we get here, we have storage that needs to be deleted from one
            # or more volume groups.  We don't have a way of knowing which ones
            # without REST calls, so get all VGs for this VIOS and delete from
            # all of them.  POST will only be done on VGs which actually need
            # updating.
            vgftsk = tx.FeedTask('scrub_vg_vios_%s' % vuuid, stor.VG.getter(
                vwrap.adapter, parent_class=vwrap.__class__,
                parent_uuid=vwrap.uuid))
            if vdisks_to_rm:
                vgftsk.add_functor_subtask(
                    _rm_vdisks, vdisks_to_rm, logspec=(LOG.warn, _(
                        "Scrubbing the following %(vdcount)d Virtual Disks "
                        "from VIOS %(vios)s: %(vdlist)s"), {
                        'vdcount': len(vdisks_to_rm), 'vios': vwrap.name,
                        'vdlist': ["%s (%s)" % (vd.name, vd.udid) for vd
                                   in vdisks_to_rm]}))
            if vopts_to_rm:
                vgftsk.add_functor_subtask(
                    _rm_vopts, vopts_to_rm, logspec=(LOG.warn, _(
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


def add_lpar_storage_scrub_tasks(lpar_ids, ftsk, lpars_exist=False):
    """Delete storage mappings and elements associated with an LPAR ID.

    This should typically be used to clean leftovers from an LPAR that has been
    deleted, since stale storage artifacts can cause conflicts with a new LPAR
    recycling that ID.

    This operates by inspecting mappings first, since we have no other way to
    associate a mapping-less storage element with an LPAR ID.

    Storage elements are deleted if their only mappings are to the LPAR ID
    being scrubbed.

    This method only adds subtasks/post-execs to the passed-in FeedTask.  The
    caller is responsible for executing that FeedTask in an appropriate Flow or
    other context.

    :param lpar_ids: List of integer short IDs (not UUIDs) of the LPAR whose
                     storage artifacts are to be scrubbed.
    :param ftsk: FeedTask to which the scrubbing actions should be added, for
                 execution by the caller.  The FeedTask must be built for all
                 the VIOSes from which mappings and storage should be scrubbed.
                 The feed/getter must use the SCSI_MAPPING and FC_MAPPING xags.
    :param lpars_exist: (Optional) If set to False (the default), storage
                        artifacts associated with an extant LPAR will be
                        ignored (NOT scrubbed).  Otherwise, we will scrub
                        whether the LPAR exists or not. Thus, set to True only
                        if intentionally removing mappings associated with
                        extant LPARs.
    """
    tag = '_'.join((str(lpar_id) for lpar_id in lpar_ids))

    def remove_chain(vwrap, stg_type):
        """_remove_lpar_maps with an additional check for existing LPARs."""
        lpar_id_set = set(lpar_ids)
        if not lpars_exist:
            # Restrict scrubbing to LPARs that don't exist on the system.
            ex_lpar_ids = {lwrap.id for lwrap in lpar.LPAR.wrap(
                vwrap.adapter.read(sys.System.schema_type,
                                   root_id=vwrap.assoc_sys_uuid,
                                   child_type=lpar.LPAR.schema_type))}
            # The list of IDs of the LPARs whose mappings (and storage) are to
            # be preserved (not scrubbed) is the intersection of
            # {the IDs we we were asked to scrub}
            # and
            # {the IDs of all the LPARs on the system}
            lpar_ids_to_preserve = lpar_id_set & ex_lpar_ids
            if lpar_ids_to_preserve:
                LOG.warn(_("Skipping scrub of %(stg_type)s mappings from VIOS "
                           "%(vios_name)s for the following LPAR IDs because "
                           "those LPARs exist: %(lpar_ids)s"),
                         dict(stg_type=stg_type, vios_name=vwrap.name,
                              lpar_ids=list(lpar_ids_to_preserve)))
                lpar_id_set -= lpar_ids_to_preserve
        return _remove_lpar_maps(vwrap, lpar_id_set, stg_type)

    ftsk.add_functor_subtask(remove_chain, 'VSCSI',
                             provides='vscsi_removals_' + tag)
    ftsk.add_functor_subtask(remove_chain, 'VFC')
    ftsk.add_post_execute(_RemoveStorage(tag))


def add_orphan_storage_scrub_tasks(ftsk, lpar_id=None):
    """Delete orphan mappings (no client adapter) and their storage elements.

    :param ftsk: FeedTask to which the scrubbing actions should be added, for
                 execution by the caller.  The FeedTask must be built for all
                 the VIOSes from which mappings and storage should be scrubbed.
                 The feed/getter must use the SCSI_MAPPING and FC_MAPPING xags.
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
                   retrieved with the SCSI_MAPPING and FC_MAPPING extended
                   attribute groups.
    :return: List of LPAR IDs (integer short IDs, not UUIDs) which don't exist
             on the system.  The list is guaranteed to contain no duplicates.
    """
    ex_lpar_ids = {lwrap.id for lwrap in lpar.LPAR.wrap(vios_w.adapter.read(
        sys.System.schema_type, root_id=vios_w.assoc_sys_uuid,
        child_type=lpar.LPAR.schema_type))}
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
        getter_kwargs = {'xag': [vios.VIOS.xags.FC_MAPPING,
                                 vios.VIOS.xags.SCSI_MAPPING]}
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
        getter_kwargs = {'xag': [vios.VIOS.xags.FC_MAPPING,
                                 vios.VIOS.xags.SCSI_MAPPING]}
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
