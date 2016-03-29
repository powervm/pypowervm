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
import time
import uuid

import pypowervm.const as c
import pypowervm.exceptions as ex
from pypowervm.i18n import _
import pypowervm.tasks.storage as tsk_stg
import pypowervm.util as u
import pypowervm.wrappers.cluster as clust
from pypowervm.wrappers import job
import pypowervm.wrappers.storage as stor

LOG = logging.getLogger(__name__)


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


def _find_lu(ssp, lu_name, lu_type, whole_name=True, find_all=False):
    """Find a specified lu by name and type.

    :param ssp: SSP wrapper to search for the LU.
    :param lu_name: The name of the LU to find.
    :param lu_type: The type of the LU to find.
    :param whole_name: (Optional) If True (the default), the lu_name must
                       match exactly.  If False, match any name containing
                       lu_name as a substring.
    :param find_all: (Optional) If False (the default), the first matching
                     LU is returned, or None if none were found.  If True,
                     the return is always a list, containing zero or more
                     matching LUs.
    :return: If find_all=False, the wrapper of the first matching LU, or
             None if not found.  If find_all=True, a list of zero or more
             matching LU wrappers.
    """
    matches = []
    for lu in ssp.logical_units:
        if lu.lu_type != lu_type:
            continue
        if lu_name not in lu.name:
            continue
        if not whole_name or lu.name == lu_name:
            matches.append(lu)
    if find_all:
        return matches
    return matches[0] if matches else None


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


def _upload_conflict(lus, luname, mkr_luname):
    """Detect an upload conflict with another host (our thread should bail).

    :param lus: List of LUs to be considered (i.e. whose names contain the name
                of the LU we intend to upload).
    :param luname: The name of the LU we intend to upload.
    :param mkr_luname: The name of the marker LU we use to signify our upload
                       is in progress.
    :return: True if we find a winning conflict and should abandon our upload;
             False otherwise.
    """
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


def _stream_upload(ssp, luname, vios_uuid, stream_func, b_size):
    """Create the image LU and upload its contents.

    :param ssp: SSP EntryWrapper of the SharedStoragePool on which the image LU
                is to be hosted.
    :param luname: The name of the image LU.  Note that the name may be
                   shortened to satisfy length restrictions.
    :param vios_uuid: The UUID of the Virtual I/O Server through which the
                      upload should be performed, if necessary.
    :param stream_func: A method providing the data stream to upload.  The
                        method accepts no parameters.  It must return a file-
                        handle-like object (one with a read(bytes) method).
                        This method is only invoked if the image actually needs
                        to be uploaded.
    :param b_size: Integer size, in bytes, of the image provided by
                   stream_func's return value.
    :return: If the method is successful, a tuple of (ssp, img_lu) is returned,
             where ssp is the updated SSP EntryWrapper; and img_lu is the LU
             ElementWrapper representing the newly-created and -uploaded image
             LU.  If the method detects a race condition with another thread,
             None is returned, and the caller should rediscover the already-
             uploaded image LU.
    """
    strm = stream_func()
    try:
        return tsk_stg.upload_new_lu2(vios_uuid, ssp, strm, luname,
                                      b_size)[:2]
    except ex.DuplicateLUNameError:
        # The crt_lu part of upload_new_lu2 is an @entry_transaction.
        # If another process (on this host or another) got through all of the
        # above at the same time as this one, and it hits crt_lu first, our
        # crt_lu will 412, reload the SSP, and redrive.  At that point, it will
        # find the LU we're trying to create, and raise this exception.
        LOG.debug('Race condition: the LU was created elsewhere.')
        # Loop immediately and let the next iteration catch the LU.
        return None
    except Exception as exc:
        LOG.exception(exc)
        # It's possible the LU creation succeeded, but the upload
        # failed.  If so, we need to remove the LU so it doesn't block
        # others attempting to use the same one.
        lu = _find_lu(ssp, luname, stor.LUType.IMAGE)
        if lu:
            LOG.exception(_('Removing failed LU %s.'), luname)
            tsk_stg.rm_ssp_storage(ssp, [lu])
        raise exc


def get_or_upload_image_lu(ssp, luname, vios_uuid, stream_func, b_size):
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

    :param ssp: SSP EntryWrapper of the SharedStoragePool on which the image LU
                is to be hosted.
    :param luname: The name of the image LU.  Note that the name may be
                   shortened to satisfy length restrictions.
    :param vios_uuid: The UUID of the Virtual I/O Server through which the
                      upload should be performed, if necessary.
    :param stream_func: A method providing the data stream to upload.  The
                        method accepts no parameters.  It must return a file-
                        handle-like object (one with a read(bytes) method).
                        This method is only invoked if the image actually needs
                        to be uploaded.
    :param b_size: Integer size, in bytes, of the image provided by
                   stream_func's return value.
    :return: SSP EntryWrapper representing the (possibly updated) Shared
             Storage Pool.
    :return: LU ElementWrapper representing the image LU.
    """
    sleep_s = 3
    # Marker (upload-in-progress) LU name prefixed with 'partxxxxxxxx'
    prefix = 'part%s' % uuid.uuid4().hex[:8]
    # Ensure the marker LU name won't be too long
    luname = u.sanitize_file_name_for_api(
        luname, max_len=c.MaxLen.FILENAME_DEFAULT - len(prefix))
    mkr_luname = prefix + luname
    imgtyp = stor.LUType.IMAGE
    first = True
    while True:
        # Refresh the SSP data.  (Yes, even the first time.  A 304 costs
        # virtually nothing.)
        ssp = ssp.refresh()
        # Look for all LUs containing the right name.
        lus = _find_lu(ssp, luname, imgtyp, whole_name=False, find_all=True)
        # Does the LU already exist in its final, uploaded form?  If so,
        # then only that LU will exist, with an exact name match.
        if len(lus) == 1 and lus[0].name == luname:
            LOG.info(_('Using already-uploaded image LU %s.'), luname)
            return ssp, lus[0]

        # Is there an upload in progress?
        if _upload_in_progress(lus, luname, first):
            first = False
            time.sleep(sleep_s)
            continue

        # No upload in progress (at least as of when we grabbed the SSP).
        LOG.info(_('Creating marker LU %s'), mkr_luname)
        ssp, mkrlu = tsk_stg.crt_lu(ssp, mkr_luname, 0.001, typ=imgtyp)

        # We must remove the marker LU if
        # a) anything fails beyond this point; or
        # b) we succeessfully upload the image LU.
        try:
            # Now things get funky. If another process (possibly on another
            # host) hit the above line at the same time, there could be
            # multiple marker LUs out there.  We all use the next chunk to
            # decide which one of us gets to do the upload.
            lus = _find_lu(ssp, luname, imgtyp, whole_name=False,
                           find_all=True)

            # Did someone else race us here, and win?
            if _upload_conflict(lus, luname, mkr_luname):
                time.sleep(sleep_s)
                continue

            # Okay, we won.  Do the actual upload.
            LOG.info(_('Uploading to image LU %(lu)s (marker %(mkr)s).'),
                     {'lu': luname, 'mkr': mkr_luname})
            ret = _stream_upload(ssp, luname, vios_uuid, stream_func, b_size)
            if ret is None:
                # Discovered a race condition - another host beat us to the
                # upload.  Let the next iteration rediscover that image LU.
                continue
            # Otherwise, the return was a tuple of (ssp, img_lu) - return it.
            return ret

        finally:
            # Signal completion, or clean up, by removing the marker LU.
            tsk_stg.rm_ssp_storage(ssp, [mkrlu])
