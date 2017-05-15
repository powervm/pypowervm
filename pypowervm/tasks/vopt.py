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

from oslo_log import log as logging

from pypowervm import exceptions as pvm_ex
from pypowervm.i18n import _
from pypowervm.tasks import partition
from pypowervm.wrappers import storage as pvm_stg
from pypowervm.wrappers import virtual_io_server as pvm_vios


LOG = logging.getLogger(__name__)

_cur_vios_uuid = None
_cur_vg_uuid = None


def validate_vopt_repo_exists(
        adapter, vopt_media_volume_group='rootvg', vopt_media_rep_size=1):
    """Will ensure that the virtual optical media repository exists.

    Checks to make sure that at least one Virtual I/O Server has a virtual
    optical media repository.

    If the volume group on an I/O Server goes down (perhaps due to
    maintenance), the system will rescan to determine if there is another
    I/O Server that can host the request.

    The very first invocation may be expensive.  It may also be expensive
    to call if a Virtual I/O Server unexpectedly goes down.

    :param adapter: The pypowervm adapter.
    :param vopt_media_volume_group: (Optional, Default: rootvg) The volume
                                    group to use if the vopt media repo needs
                                    to be created.
    :param vopt_media_rep_size: (Optional, Default: 1) The size of the virtual
                                optical media (in GB) if the repo needs to be
                                created.
    :return vios_uuid: The VIOS uuid hosting the VG
    :return vg_uuid: The volume group uuid hosting the vopt.
    :raise NoMediaRepoVolumeGroupFound: Raised when there are no VIOSes that
                                        can support the virtual optical media.
    """
    # If our static variables were set, then we should validate that the
    # repo is still running.  Otherwise, we need to reset the variables
    # (as it could be down for maintenance).
    if _cur_vg_uuid is not None:
        vio_uuid = _cur_vios_uuid
        vg_uuid = _cur_vg_uuid
        try:
            vg_wrap = pvm_stg.VG.get(
                adapter, uuid=vg_uuid, parent_type=pvm_vios.VIOS,
                parent_uuid=vio_uuid)
            if vg_wrap is not None and len(vg_wrap.vmedia_repos) != 0:
                return vio_uuid, vg_uuid
        except Exception as exc:
            LOG.exception(exc)

        LOG.warning(_("An error occurred querying the virtual optical "
                      "media repository.  Attempting to re-establish "
                      "connection with a virtual optical media repository."))

    # Did not find the media repository.  Need a deeper query
    return _find_or_rebuild_vopt_repo(adapter, vopt_media_volume_group,
                                      vopt_media_rep_size)


def _find_or_rebuild_vopt_repo(adapter, vopt_media_volume_group,
                               vopt_media_rep_size):
    # If we're hitting this:
    # a) It's our first time booting up;
    # b) The previously-used Volume Group went offline (e.g. VIOS went down
    #    for maintenance); OR
    # c) The previously-used media repository disappeared.
    #
    # The next step is to create a Media Repository dynamically.
    found_vg, found_vios, conf_vg, conf_vios = _find_vopt_repo_data(
        adapter, vopt_media_volume_group)

    # If we didn't find a media repos OR an appropriate volume group, raise
    # the exception.  Since vopt_media_volume_group defaults to rootvg,
    # which is always present, this should only happen if:
    # a) No media repos exists on any VIOS we can see; AND
    # b) The user specified a non-rootvg vopt_media_volume_group; AND
    # c) The specified volume group did not exist on any VIOS.
    if found_vg is None and conf_vg is None:
        raise pvm_ex.NoMediaRepoVolumeGroupFound(
            vol_grp=vopt_media_volume_group)

    # If no media repos was found, create it.
    if found_vg is None:
        found_vg, found_vios = conf_vg, conf_vios
        vopt_repo = pvm_stg.VMediaRepos.bld(
            adapter, 'vopt', vopt_media_rep_size)
        found_vg.vmedia_repos = [vopt_repo]
        found_vg = found_vg.update()

    # At this point, we know that we've successfully found or created the
    # volume group.  Save to the static variables.
    global _cur_vg_uuid, _cur_vios_uuid
    _cur_vg_uuid = found_vg.uuid
    _cur_vios_uuid = found_vios.uuid
    return _cur_vios_uuid, _cur_vg_uuid


def _find_vopt_repo_data(adapter, vopt_media_volume_group):
    """Finds the vopt repo defaults.

    :param adapter: pypowervm adapter
    :param vopt_media_volume_group: The name of the volume group to use.
    :return found_vg: Returned if a volume group already exists with a media
                      repo within it.  Is that corresponding volume group.
    :return found_vios: Returned if a volume group already exists with a media
                        repo within it.  This is the VIOS wrapper.
    :return conf_vg: Returned if a volume group does not exist with a media
                     repo within it.  This is the volume group wrapper (as
                     defined by the vopt_media_volume_group) that the consumer
                     code should create that media repo within.
    :return conf_vios: Returned if a volume group does not exist with a media
                       repo within it.  This is the VIOS wrapper that is the
                       parent of the conf_vg
    """
    vios_wraps = partition.get_active_vioses(adapter)

    # First loop through the VIOSes and their VGs to see if a media repos
    # already exists.
    found_vg, found_vios = None, None

    # And in case we don't find the media repos, keep track of the VG on
    # which we should create it.
    conf_vg, conf_vios = None, None

    for vio_wrap in vios_wraps:
        vg_wraps = pvm_stg.VG.get(adapter, parent=vio_wrap)
        for vg_wrap in vg_wraps:
            if len(vg_wrap.vmedia_repos) != 0:
                found_vg, found_vios = vg_wrap, vio_wrap
                break
            # In case no media repos exists, save a pointer to the
            # CONFigured vopt_media_volume_group if we find it.
            if (conf_vg is None and not vio_wrap.is_mgmt_partition and
                    vg_wrap.name == vopt_media_volume_group):
                conf_vg, conf_vios = vg_wrap, vio_wrap

        # If we found it, don't keep looking
        if found_vg:
            break

    return found_vg, found_vios, conf_vg, conf_vios
