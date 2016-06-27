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
from pypowervm.wrappers import base_partition as pvm_bp
from pypowervm.wrappers import storage as pvm_stg
from pypowervm.wrappers import virtual_io_server as pvm_vios


LOG = logging.getLogger(__name__)

_cur_vios_uuid = None
_cur_vg_uuid = None


def validate_vopt_repo_exists(
        adapter, vopt_media_volume_group='rootvg', vopt_media_rep_size=1):
    """Will ensure that the virtual optical media repository exists.

    This method will connect to one of the Virtual I/O Servers on the
    system and ensure that there is a root_vg that the optical media (which
    is temporary) exists.

    If the volume group on an I/O Server goes down (perhaps due to
    maintenance), the system will rescan to determine if there is another
    I/O Server that can host the request.

    The very first invocation may be expensive.  It may also be expensive
    to call if a Virtual I/O Server unexpectantly goes down.

    If there are no Virtual I/O Servers that can support the media, then
    an exception will be thrown.

    :param adapter: The pypowervm adapter.
    :param vopt_media_volume_group: (Optional, Default: rootvg) The volume
                                    group to use if the vopt media repo needs
                                    to be created.
    :param vopt_media_rep_size: (Optional, Default: 1) The size of the virtual
                                optical media (in GB) if the repo needs to be
                                created.
    :return vios_uuid: The VIOS uuid hosting the VG
    :return vg_uuid: The volume group uuid hosting the vopt.
    """
    global _cur_vg_uuid, _cur_vios_uuid

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

        LOG.info(_("An error occurred querying the virtual optical "
                   "media repository.  Attempting to re-establish "
                   "connection with a virtual optical media repository"))

    # If we're hitting this:
    # a) It's our first time booting up;
    # b) The previously-used Volume Group went offline (e.g. VIOS went down
    #    for maintenance); OR
    # c) The previously-used media repository disappeared.
    #
    # The next step is to create a vOpt dynamically.
    vio_wraps = _get_vioses(adapter)

    # First loop through the VIOSes and their VGs to see if a media repos
    # already exists.
    found_vg = None
    found_vios = None

    # And in case we don't find the media repos, keep track of the VG on
    # which we should create it.
    conf_vg = None
    conf_vios = None

    for vio_wrap in vio_wraps:
        # If the RMC state is not active, skip over to ensure we don't
        # timeout
        if vio_wrap.rmc_state != pvm_bp.RMCState.ACTIVE:
            continue

        try:
            vg_wraps = pvm_stg.VG.get(adapter, parent=vio_wrap)
            for vg_wrap in vg_wraps:
                if len(vg_wrap.vmedia_repos) != 0:
                    found_vg = vg_wrap
                    found_vios = vio_wrap
                    break
                # In case no media repos exists, save a pointer to the
                # CONFigured vopt_media_volume_group if we find it.
                if (conf_vg is None and vg_wrap.name ==
                        vopt_media_volume_group):
                    conf_vg = vg_wrap
                    conf_vios = vio_wrap

        except Exception:
            LOG.warning(_('Unable to read volume groups for Virtual I/O '
                          'Server %s'), vio_wrap.name)

        # If we found it, don't keep looking
        if found_vg:
            break

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
        found_vg = conf_vg
        found_vios = conf_vios
        vopt_repo = pvm_stg.VMediaRepos.bld(
            adapter, 'vopt', str(vopt_media_rep_size))
        found_vg.vmedia_repos = [vopt_repo]
        found_vg = found_vg.update()

    # At this point, we know that we've successfully found or created the
    # volume group.  Save to the static class variables.
    _cur_vg_uuid = found_vg.uuid
    _cur_vios_uuid = found_vios.uuid
    return _cur_vios_uuid, _cur_vg_uuid


def _get_vioses(adapter):
    """Returns the VIOS Wraps."""
    vio_wraps = pvm_vios.VIOS.get(adapter)
    # The mgmt partition should be the first element.
    vio_wraps.sort(key=lambda x: x.is_mgmt_partition, reverse=True)
    return vio_wraps
