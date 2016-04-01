# Copyright 2016 IBM Corp.
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

"""Helper methods for the storage module."""
from concurrent import futures
from oslo_log import log as logging
from taskflow import engines as tf_eng
from taskflow.patterns import unordered_flow as tf_uf
from taskflow import task as tf_tsk
import threading
import time

from pypowervm import exceptions as exc
from pypowervm.i18n import _
from pypowervm.tasks import scsi_mapper as sm
from pypowervm.tasks import vfc_mapper as fm
from pypowervm.utils import transaction as tx
from pypowervm.wrappers import storage as stor
from pypowervm.wrappers import vios_file as vf

# Concurrent uploads
_UPLOAD_SEM = threading.Semaphore(3)

LOG = logging.getLogger(__name__)


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


def _image_lu_for_clone(ssp, clone_lu):
    """Given a Disk LU linked clone, find the Image LU to which it is linked.

    :param ssp: The SSP EntryWrapper to search.
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
            LOG.warning(
                _("Linked clone Logical Unit %(luname)s (UDID %(udid)s) has "
                  "no backing image LU.  It should probably be deleted."),
                {'luname': lu.name, 'udid': lu.udid})
            continue
        if cloned_from[2:] == image_udid:
            return True
    return False


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
                    dev.toxmlstring())
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
                    LOG.warning(_("Backing LU %(lu_name)s was not found in "
                                  "SSP %(ssp_name)s"), msg_args)
    return changes


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
                vwrap.adapter, parent_class=vwrap.__class__,
                parent_uuid=vwrap.uuid))
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
