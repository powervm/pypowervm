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

"""Tasks around Cluster/SharedStoragePool."""

from oslo_log import log as logging
from random import randint
import time
import uuid

import pypowervm.const as c
from pypowervm.i18n import _
import pypowervm.tasks.storage as tsk_stg
import pypowervm.util as u
import pypowervm.wrappers.cluster as clust
from pypowervm.wrappers import job
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)

IMGTYP = stor.LUType.IMAGE
MKRSZ = 0.001
SLEEP_U_MIN = 30
SLEEP_U_MAX = 60


def crt_cluster_ssp(clust_name, ssp_name, repos_pv, first_node, data_pv_list):
    """Creates a Cluster/SharedStoragePool via the ClusterCreate Job.

    The Job takes two parameters: clusterXml and sspXml.

    :param clust_name: String name for the Cluster.
    :param ssp_name: String name for the SharedStoragePool.
    :param repos_pv: storage.PV representing the repository hdisk. The name and
                     udid properties must be specified.
    :param first_node: cluster.Node representing the initial VIOS in the
                       cluster. (Cluster creation must be done with a single
                       node; other nodes may be added later.)  The Node wrapper
                       must contain either
                       - mtms, lpar_id, AND hostname; or
                       - vios_uri
                       The indicated node must be able to see each disk.
    :param data_pv_list: Iterable of storage.PV instances to use as the data
                         volume(s) for the SharedStoragePool.
    """
    adapter = repos_pv.adapter
    # Pull down the ClusterCreate Job template
    jresp = adapter.read(clust.Cluster.schema_type,
                         suffix_type=c.SUFFIX_TYPE_DO, suffix_parm='Create')
    jwrap = job.Job.wrap(jresp.entry)

    cluster = clust.Cluster.bld(adapter, clust_name, repos_pv, first_node)

    ssp = stor.SSP.bld(adapter, ssp_name, data_pv_list)

    # Job parameters are CDATA containing XML of above
    jparams = [
        jwrap.create_job_parameter(
            'clusterXml', cluster.toxmlstring(), cdata=True),
        jwrap.create_job_parameter(
            'sspXml', ssp.toxmlstring(), cdata=True)]
    jwrap.run_job(None, job_parms=jparams)
    return jwrap


def _find_lus(tier, luname):
    """Finds image LUs whose name contains the specified luname.

    :param tier: Tier EntryWrapper representing the Tier to search.
    :param luname: The LU name substring to search for.
    :return: All LUs in the tier a) of type image; and b) whose names contain
             luname.
    """
    lufeed = stor.LUEnt.search(tier.adapter, parent=tier, lu_type=IMGTYP)
    return [lu for lu in lufeed if luname in lu.name]


def _upload_in_progress(lus, luname, first):
    """Detect whether another host has an upload is in progress.

    :param lus: List of LUs to be considered (i.e. whose names contain the name
                of the LU we intend to upload).
    :param luname: The name of the LU we intend to upload.
    :param first: Boolean indicating whether this is this the first time we
                  detected an upload in progress.  Should be True the first
                  and until the first time this method returns True.
                  Thereafter, should be False.
    :return: True if another host has an upload in progress; False otherwise.
    """
    mkr_lus = [lu for lu in lus
               if lu.name != luname and lu.name.endswith(luname)]
    if mkr_lus:
        # Info the first time; debug thereafter to avoid flooding the log.
        if first:
            LOG.info(_('Waiting for in-progress upload(s) to complete.  '
                       'Marker LU(s): %s'),
                     str([lu.name for lu in mkr_lus]))
        else:
            LOG.debug('Waiting for in-progress upload(s) to complete. '
                      'Marker LU(s): %s',
                      str([lu.name for lu in mkr_lus]))
        return True

    return False


def _upload_conflict(tier, luname, mkr_luname):
    """Detect an upload conflict with another host (our thread should bail).

    :param tier: Tier EntryWrapper representing the Tier to search.
    :param luname: The name of the LU we intend to upload.
    :param mkr_luname: The name of the marker LU we use to signify our upload
                       is in progress.
    :return: True if we find a winning conflict and should abandon our upload;
             False otherwise.
    """
    # Refetch the feed.  We must do this in case one or more other threads
    # created their marker LU since our last feed GET.
    lus = _find_lus(tier, luname)

    # First, if someone else already started the upload, we clean up
    # and wait for that one.
    if any([lu for lu in lus if lu.name == luname]):
        LOG.info(_('Abdicating in favor of in-progress upload.'))
        return True

    # The lus list should be all markers at this point.  If there's
    # more than one (ours), then the first (by alpha sort) wins.
    if len(lus) > 1:
        lus.sort(key=lambda l: l.name)
        winner = lus[0].name
        if winner != mkr_luname:
            # We lose.  Delete our LU and let the winner proceed
            LOG.info(_('Abdicating upload in favor of marker %s.'),
                     winner)
            # Remove just our LU - other losers take care of theirs
            return True

    return False


def get_or_upload_image_lu(tier, luname, vios_uuid, io_handle, b_size,
                           upload_type=tsk_stg.UploadType.IO_STREAM_BUILDER):
    """Ensures our SSP has an LU containing the specified image.

    If an LU of type IMAGE with the specified luname already exists in our SSP,
    return it.  Otherwise, create it, prime it with the image contents provided
    via stream_func, and return it.

    This method assumes that consumers employ a naming convention such that an
    LU with a given name represents the same data (size and content) no matter
    where/when it's created/uploaded - for example, by including the image's
    MD5 checksum in the name.

    This method is designed to coordinate the upload of a particular image LU
    across multiple hosts which use the same SSP, but otherwise can not
    communicate with each other.

    :param tier: Tier EntryWrapper of the Shared Storage Pool Tier on which the
                 image LU is to be hosted.
    :param luname: The name of the image LU.  Note that the name may be
                   shortened to satisfy length restrictions.
    :param vios_uuid: The UUID of the Virtual I/O Server through which the
                      upload should be performed, if necessary.
    :param io_handle: The I/O handle (as defined by the upload_type).  This is
                      only used if the image_lu needs to be uploaded.
    :param b_size: Integer size, in bytes, of the image provided by
                   stream_func's return value.
    :param upload_type: (Optional, Default: IO_STREAM_BUILDER) Defines the way
                        in which the LU should be uploaded.  Refer to the
                        UploadType enumeration for valid upload mechanisms.
                        It defaults to IO_STREAM_BUILDER for legacy reasons.
    :return: LUEnt EntryWrapper representing the image LU.
    """
    # Marker (upload-in-progress) LU name prefixed with 'partxxxxxxxx'
    prefix = 'part%s' % uuid.uuid4().hex[:8]
    # Ensure the marker LU name won't be too long
    luname = u.sanitize_file_name_for_api(
        luname, max_len=c.MaxLen.FILENAME_DEFAULT - len(prefix))
    mkr_luname = prefix + luname
    first = True
    while True:
        # (Re)fetch the list of image LUs whose name *contains* luname.
        lus = _find_lus(tier, luname)

        # Does the LU already exist in its final, uploaded form?  If so, then
        # only that LU will exist, with an exact name match.
        if len(lus) == 1 and lus[0].name == luname:
            LOG.info(_('Using already-uploaded image LU %s.'), luname)
            return lus[0]

        # Is there an upload in progress?
        if _upload_in_progress(lus, luname, first):
            first = False
            _sleep_for_upload()
            continue

        # No upload in progress (at least as of when we grabbed the feed).
        LOG.info(_('Creating marker LU %s'), mkr_luname)
        tier, mkrlu = tsk_stg.crt_lu(tier, mkr_luname, MKRSZ, typ=IMGTYP)

        # We must remove the marker LU if
        # a) anything fails beyond this point; or
        # b) we successfully upload the image LU.
        try:
            # If another process (possibly on another host) created a marker LU
            # at the same time, there could be multiple marker LUs out there.
            # We all use _upload_conflict to decide which one of us gets to do
            # the upload.
            if _upload_conflict(tier, luname, mkr_luname):
                _sleep_for_upload()
                continue

            # Okay, we won.  Do the actual upload.
            LOG.info(_('Uploading to image LU %(lu)s (marker %(mkr)s).'),
                     {'lu': luname, 'mkr': mkr_luname})
            # Create the new Logical Unit.  The LU size needs to be decimal GB.
            tier, new_lu = tsk_stg.crt_lu(
                tier, luname, u.convert_bytes_to_gb(b_size, dp=2), typ=IMGTYP)
            try:
                tsk_stg.upload_lu(vios_uuid, new_lu, io_handle, b_size,
                                  upload_type=upload_type)
            except Exception as exc:
                LOG.exception(exc)
                # We need to remove the LU so it doesn't block others
                # attempting to use the same one.
                LOG.exception(_('Removing failed LU %s.'), luname)
                new_lu.delete()
                raise
            return new_lu
        finally:
            # Signal completion, or clean up, by removing the marker LU.
            mkrlu.delete()


def _sleep_for_upload():
    """Sleeps if a conflict was found during the SSP upload."""
    time.sleep(randint(SLEEP_U_MIN, SLEEP_U_MAX))
