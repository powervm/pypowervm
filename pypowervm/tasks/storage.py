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

import math
from oslo_concurrency import lockutils as lock
from oslo_log import log as logging

import pypowervm.const as c
import pypowervm.exceptions as exc
from pypowervm.i18n import _
from pypowervm.tasks import storage_helpers as sh
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
    vio_file = sh._create_file(
        adapter, d_name, file_type, v_uuid, f_size=f_size,
        tdev_udid=n_vdisk.udid, sha_chksum=sha_chksum)

    maybe_file = sh._upload_stream(vio_file, d_stream)
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
    vio_file = sh._create_file(
        adapter, f_name, vf.FileType.MEDIA_ISO, v_uuid, sha_chksum, f_size)
    f_uuid = sh._upload_stream(vio_file, d_stream)

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

    maybe_file = upload_lu(v_uuid, new_lu, d_stream, f_size,
                           sha_chksum=sha_chksum)
    return new_lu, maybe_file


def upload_lu(v_uuid, lu, d_stream, f_size, sha_chksum=None):
    """Uploads a data stream to an existing SSP Logical Unit.

    :param v_uuid: The UUID of the Virtual I/O Server through which to perform
                   the upload.
    :param lu: LU Wrapper representing the Logical Unit to which to upload the
               data.  The LU must already exist in the SSP.
    :param d_stream: The data stream (either a file handle or stream) to
                     upload.  Must have the 'read' method that returns a chunk
                     of bytes.
    :param f_size: The size (in bytes) of the stream to be uploaded.
    :param sha_chksum: (OPTIONAL) The SHA256 checksum for the file.  Useful for
                       integrity checks.
    :return: Normally the return value will be None, indicating that the image
             was uploaded without issue.  If for some reason the File metadata
             for the VIOS was not cleaned up, the return value is the LU
             EntryWrapper.  This is simply a marker to be later used to retry
             the cleanup.
    """
    # The file type.  If local API server, then we can use the coordinated
    # file path.  Otherwise standard upload.
    file_type = (vf.FileType.DISK_IMAGE_COORDINATED
                 if lu.adapter.traits.local_api
                 else vf.FileType.DISK_IMAGE)

    # Create the file, specifying the UDID from the new Logical Unit.
    # The File name matches the LU name.
    vio_file = sh._create_file(
        lu.adapter, lu.name, file_type, v_uuid, f_size=f_size,
        tdev_udid=lu.udid, sha_chksum=sha_chksum)

    return sh._upload_stream(vio_file, d_stream)


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
        changes += len(sh._rm_vdisks(vg_wrap, vdisks))
    if vopts:
        changes += len(sh._rm_vopts(vg_wrap, vopts))
    if changes:
        # Update the volume group to remove the storage, if necessary.
        vg_wrap = vg_wrap.update()
    return vg_wrap


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
    if sh._rm_lus(ssp_wrap, lus, del_unused_images=del_unused_images):
        # Flush changes
        ssp_wrap = ssp_wrap.update()
    return ssp_wrap


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
                 The feed/getter must use the VIO_SMAP and VIO_FMAP xags.
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
            ex_lpar_ids = {lwrap.id for lwrap in lpar.LPAR.get(
                vwrap.adapter, parent_type=sys.System,
                parent_uuid=vwrap.assoc_sys_uuid)}
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
        return sh._remove_lpar_maps(vwrap, lpar_id_set, stg_type)

    ftsk.add_functor_subtask(remove_chain, 'VSCSI',
                             provides='vscsi_removals_' + tag)
    ftsk.add_functor_subtask(remove_chain, 'VFC')
    ftsk.add_post_execute(sh._RemoveStorage(tag))


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
    ftsk.add_functor_subtask(sh._remove_orphan_maps, 'VSCSI', lpar_id=lpar_id,
                             provides='vscsi_removals_orphans')
    ftsk.add_functor_subtask(sh._remove_orphan_maps, 'VFC', lpar_id=lpar_id)
    ftsk.add_post_execute(sh._RemoveStorage('orphans'))


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
            return sh._remove_lpar_maps(
                vwrap, provided['stale_lpar_ids'], stg_type)
        self.add_functor_subtask(remove_chain, 'VSCSI',
                                 provides='vscsi_removals_bylparid')
        self.add_functor_subtask(remove_chain, 'VFC')
        self.add_functor_subtask(sh._remove_orphan_maps, 'VSCSI',
                                 provides='vscsi_removals_orphans')
        self.add_functor_subtask(sh._remove_orphan_maps, 'VFC')
        self.add_post_execute(sh._RemoveStorage('comprehensive'))


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

        self.add_functor_subtask(sh._remove_orphan_maps, 'VSCSI',
                                 lpar_id=lpar_id,
                                 provides='vscsi_removals_orphans_lpar_id_%d' %
                                 lpar_id)
        self.add_functor_subtask(sh._remove_orphan_maps, 'VFC',
                                 lpar_id=lpar_id)
        self.add_post_execute(
            sh._RemoveStorage('orphans_for_lpar_%d' % lpar_id))


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
        self.add_functor_subtask(sh._remove_portless_vfc_maps, lpar_id=lpar_id)
