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

"""Manage mappings of virtual storage devices from VIOS to LPAR."""

from oslo_concurrency import lockutils as lock
from oslo_log import log as logging

from pypowervm import const as c
from pypowervm.i18n import _
from pypowervm import util
from pypowervm.utils import retry as pvm_retry
from pypowervm.utils import uuid
from pypowervm.wrappers import storage as pvm_stor
from pypowervm.wrappers import virtual_io_server as pvm_vios

LOG = logging.getLogger(__name__)


def _argmod(this_try, max_tries, *args, **kwargs):
    """Retry argmod to change 'vios' arg from VIOS wrapper to a string UUID.

    This is so that etag mismatches trigger a fresh GET.
    """
    LOG.warning(_('Retrying modification of SCSI Mapping.'))
    argl = list(args)
    # Second argument is vios.
    if isinstance(argl[1], pvm_vios.VIOS):
        argl[1] = argl[1].uuid
    return argl, kwargs


@lock.synchronized('vscsi_mapping')
@pvm_retry.retry(tries=60, argmod_func=_argmod,
                 delay_func=pvm_retry.STEPPED_RANDOM_DELAY)
def add_vscsi_mapping(host_uuid, vios, lpar_uuid, storage_elem, fuse_limit=32,
                      lpar_slot_num=None, lua=None):
    """Will add a vSCSI mapping to a Virtual I/O Server.

    This method is used to connect a storage element (either a vDisk, vOpt,
    PV or LU) that resides on a Virtual I/O Server to a Virtual Machine.

    This is achieved using a 'vSCSI Mapping'.  The invoker does not need to
    interact with the mapping.

    A given mapping is essentially a 'vSCSI bus', which can host multiple
    storage elements.  This method has a fuse limit which throttles the number
    of devices on a given vSCSI bus.  The throttle should be lower if the
    storage elements are high I/O, and higher otherwise.

    :param host_uuid: The UUID of the host system.
    :param vios: The virtual I/O server to which the mapping should be
                 added.  This may be the VIOS's UUID string OR an existing VIOS
                 EntryWrapper.  If the latter, it must have been retrieved
                 using the VIO_SMAP extended attribute group.
    :param lpar_uuid: The UUID of the LPAR that will have the connected
                      storage.
    :param storage_elem: The storage element (either a vDisk, vOpt, LU or PV)
                         that is to be connected.
    :param fuse_limit: (Optional, Default: 32) The max number of devices to
                       allow on one scsi bus before creating a second SCSI bus.
    :param lpar_slot_num: (Optional, Default: None) The slot number for the
                          client LPAR to use in the mapping. If None, the next
                          available slot number is assigned by the server.
    :param lua: (Optional.  Default: None) Logical Unit Address to set on the
                TargetDevice.  If None, the LUA will be assigned by the server.
                Should be specified for all of the VSCSIMappings for a
                particular bus, or none of them.
    :return: The VIOS wrapper representing the updated Virtual I/O Server.
             This is current with respect to etag and SCSI mappings.
    """
    adapter = storage_elem.adapter

    # If the 'vios' param is a string UUID, retrieve the VIOS wrapper.
    if not isinstance(vios, pvm_vios.VIOS):
        vios_w = pvm_vios.VIOS.wrap(
            adapter.read(pvm_vios.VIOS.schema_type, root_id=vios,
                         xag=[c.XAG.VIO_SMAP]))
    else:
        vios_w = vios

    # If the storage element is already there, do nothing.
    if find_maps(vios_w.scsi_mappings, client_lpar_id=lpar_uuid,
                 stg_elem=storage_elem):
        LOG.info(_("Found existing mapping of %(stg_type)s storage element "
                   "%(stg_name)s from Virtual I/O Server %(vios_name)s to "
                   "client LPAR %(lpar_uuid)s."),
                 {'stg_type': storage_elem.schema_type,
                  'stg_name': storage_elem.name,
                  'vios_name': vios_w.name,
                  'lpar_uuid': lpar_uuid})
        return vios_w

    # Build the mapping.
    scsi_map = build_vscsi_mapping(host_uuid, vios_w, lpar_uuid, storage_elem,
                                   fuse_limit=fuse_limit,
                                   lpar_slot_num=lpar_slot_num, lua=lua)

    # Add the mapping.  It may have been updated to have a different client
    # and server adapter.  It may be the original (which creates a new client
    # and server pair).
    vios_w.scsi_mappings.append(scsi_map)

    LOG.info(_("Creating mapping of %(stg_type)s storage element %(stg_name)s "
               "from Virtual I/O Server %(vios_name)s to client LPAR "
               "%(lpar_uuid)s."),
             {'stg_type': storage_elem.schema_type,
              'stg_name': storage_elem.name,
              'vios_name': vios_w.name,
              'lpar_uuid': lpar_uuid})
    return vios_w.update()


def build_vscsi_mapping(host_uuid, vios_w, lpar_uuid, storage_elem,
                        fuse_limit=32, lpar_slot_num=None, lua=None,
                        target_name=None):
    """Will build a vSCSI mapping that can be added to a VIOS.

    This method is used to create a mapping element (for either a vDisk, vOpt,
    PV or LU) that connects a Virtual I/O Server to a LPAR.

    A given mapping is essentially a 'vSCSI bus', which can host multiple
    storage elements.  This method has a fuse limit which throttles the number
    of devices on a given vSCSI bus.  The throttle should be lower if the
    storage elements are high I/O, and higher otherwise.

    :param host_uuid: The UUID of the host system.
    :param vios_w: The virtual I/O server wrapper that the mapping is intended
                   to be attached to.  The method will call the update against
                   the API.  It will only update the in memory wrapper.
    :param lpar_uuid: The UUID of the LPAR that will have the connected
                      storage.
    :param storage_elem: The storage element (either a vDisk, vOpt, LU or PV)
                         that is to be connected.
    :param fuse_limit: (Optional, Default: 32) The max number of devices to
                       allow on one scsi bus before creating a second SCSI bus.
    :param lpar_slot_num: (Optional, Default: None) The slot number for the
                          client LPAR to use in the mapping. If None, the next
                          available slot number is assigned by the server.
    :param lua: (Optional.  Default: None) Logical Unit Address to set on the
                TargetDevice.  If None, the LUA will be assigned by the server.
                Should be specified for all of the VSCSIMappings for a
                particular bus, or none of them.
    :param target_name: (Optional, Default: None) The name of the Target
                        mapping. If None, the target_name will be assigned by
                        the server.
    :return: The SCSI mapping that can be added to the vios_w.  This does not
             do any updates to the wrapper itself.
    """
    adapter = storage_elem.adapter

    # Get the client lpar href
    lpar_href = pvm_vios.VSCSIMapping.crt_related_href(adapter, host_uuid,
                                                       lpar_uuid)

    # Separate out the mappings into the applicable ones for this client.
    separated_mappings = _separate_mappings(vios_w, lpar_href)

    # Used if we need to clone an existing mapping
    clonable_map = None

    # What we need to figure out is, within the existing mappings, can we
    # reuse the existing client and server adapter (which we can only do if
    # below the fuse limit), or if we need to create a new adapter pair.
    for mapping_list in separated_mappings.values():
        if len(mapping_list) < fuse_limit:
            # Swap in the first maps client/server adapters into the existing
            # map.  We call the semi-private methods as this is not something
            # that an 'update' would do...this is part of the 'create' flow.
            clonable_map = mapping_list[0]
            break

    # If we have a clonable map, we can replicate that.  Otherwise we need
    # to build from scratch.
    if clonable_map is not None:
        scsi_map = pvm_vios.VSCSIMapping.bld_from_existing(
            clonable_map, storage_elem, lpar_slot_num=lpar_slot_num, lua=lua,
            target_name=target_name)
    else:
        scsi_map = pvm_vios.VSCSIMapping.bld(
            adapter, host_uuid, lpar_uuid, storage_elem,
            lpar_slot_num=lpar_slot_num, lua=lua, target_name=target_name)
    return scsi_map


def _separate_mappings(vios_w, client_href):
    """Separates out the systems existing mappings into silos.

    :param vios_w: The pypowervm wrapper for the VIOS.
    :param client_href: The client to separate the mappings for.
    :return: A dictionary where the key is the server adapter (which is
             bound to the client).  The value is the list mappings that use
             the server adapter.
    """
    # The key is server_adapter.udid, the value is the list of applicable
    # mappings to the server adapter.
    resp = {}

    existing_mappings = vios_w.scsi_mappings
    for existing_map in existing_mappings:
        if (existing_map.client_lpar_href == client_href and
                # ignore orphaned mappings
                existing_map.client_adapter is not None):
            # Valid map to consider
            key = existing_map.server_adapter.udid
            if resp.get(key) is None:
                resp[key] = []
            resp[key].append(existing_map)

    return resp


def add_map(vios_w, scsi_mapping):
    """Will add the mapping to the VIOS wrapper, if not already included.

    This method has the logic in place to detect if the storage from the
    mapping is already part of a SCSI mapping.  If so, it will not re-add
    the mapping to the VIOS wrapper.

    The new mapping is added to the wrapper, but it is up to the invoker to
    call the update method on the wrapper.

    :param vios_w: The Virtual I/O Server wrapping to add the mapping to.
    :param scsi_mapping: The scsi mapping to include in the VIOS.
    :return: The scsi_mapping that was added.  None if the mapping was already
             on the vios_w.
    """
    # Check to see if the mapping is already in the system.
    lpar_uuid = util.get_req_path_uuid(scsi_mapping.client_lpar_href,
                                       preserve_case=True)
    existing_mappings = find_maps(vios_w.scsi_mappings,
                                  client_lpar_id=lpar_uuid,
                                  stg_elem=scsi_mapping.backing_storage)
    if len(existing_mappings) > 0:
        return None
    vios_w.scsi_mappings.append(scsi_mapping)
    return scsi_mapping


def remove_maps(vwrap, client_lpar_id, match_func=None, include_orphans=True):
    """Remove one or more SCSI mappings from a VIOS wrapper.

    The changes are not flushed back to the REST server.

    :param vwrap: VIOS EntryWrapper representing the Virtual I/O Server whose
                  SCSI mappings are to be updated.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param match_func: (Optional) Matching function suitable for passing to
                       find_maps.  See that method's match_func parameter.
                       Defaults to None (match only on client_lpar_id).
    :param include_orphans: (Optional) An "orphan" contains a server adapter
                            but no client adapter.  If this parameter is True,
                            mappings with no client adapter will be considered
                            for removal. If False, mappings with no client
                            adapter will be left alone, regardless of any other
                            criteria.  Default: True (remove orphans).
    :return: The list of removed mappings.
    """
    resp_list = []
    for matching_map in find_maps(
            vwrap.scsi_mappings, client_lpar_id=client_lpar_id,
            match_func=match_func, include_orphans=include_orphans):
        vwrap.scsi_mappings.remove(matching_map)
        resp_list.append(matching_map)
    return resp_list


def detach_storage(vwrap, client_lpar_id, match_func=None):
    """Detach the storage from all matching SCSI mappings.

    We do this by removing the Storage and TargetDevice child elements.  This
    method only updates the vwrap.  It does not POST back to the REST server.
    It does not lock.

    :param vwrap: VIOS EntryWrapper representing the Virtual I/O Server whose
                  SCSI mappings are to be updated.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param match_func: (Optional) Matching function suitable for passing to
                       find_maps.  See that method's match_func parameter.
                       Defaults to None (match only on client_lpar_id).
    :return: The list of SCSI mappings which were modified, in their original
             (storage-attached) form.
    """
    # Rather than modifying the matching mappings themselves, we remove them
    # and recreate them without storage.
    resp_list = []
    for match in find_maps(
            vwrap.scsi_mappings, client_lpar_id=client_lpar_id,
            match_func=match_func, include_orphans=True):
        vwrap.scsi_mappings.remove(match)
        resp_list.append(match)
        vwrap.scsi_mappings.append(
            pvm_vios.VSCSIMapping.bld_from_existing(match, None))
    return resp_list


@lock.synchronized('vscsi_mapping')
@pvm_retry.retry(tries=60, argmod_func=_argmod,
                 delay_func=pvm_retry.STEPPED_RANDOM_DELAY)
def _remove_storage_elem(adapter, vios, client_lpar_id, match_func):
    """Removes the storage element from a SCSI bus and clears out bus.

    Will remove the vSCSI Mappings from the VIOS if the match_func indicates
    that the mapping is a match.  The match_func is only invoked if the
    client_lpar_id matches.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the VIO_SMAP extended attribute group.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param match_func: Matching function suitable for passing to find_maps.
                       See that method's match_func parameter.
    :return: The VIOS wrapper representing the updated Virtual I/O Server.
             This is current with respect to etag and SCSI mappings.
    :return: The list of the storage elements that were removed from the maps.
    """
    # If the 'vios' param is a string UUID, retrieve the VIOS wrapper.
    if not isinstance(vios, pvm_vios.VIOS):
        vios = pvm_vios.VIOS.wrap(
            adapter.read(pvm_vios.VIOS.schema_type, root_id=vios,
                         xag=[c.XAG.VIO_SMAP]))

    resp_list = remove_maps(vios, client_lpar_id, match_func=match_func)

    # Update the VIOS, but only if we actually removed mappings
    if resp_list:
        vios = vios.update()

    # return the (possibly updated) VIOS and the list of removed backing
    # storage elements.
    return vios, [rmap.backing_storage for rmap in resp_list
                  if rmap.backing_storage is not None]


def gen_match_func(wcls, name_prop='name', names=None, prefixes=None,
                   udids=None):
    """Generate a matching function for find_maps' match_func param.

    :param wcls: The Wrapper class of the object being matched.
    :param name_prop: The property of the Wrapper class on which to match.
    :param names: (Optional) A list of names to match.  If names and prefixes
                  are both None or empty, all inputs of the specified wcls will
                  be matched.
    :param prefixes: (Optional) A list of prefixes that can be specified
                     to serve as identifiers for potential matches.  Ignored
                     if names is specified.  If names and prefixes are both
                     None or empty, all inputs of the specified wcls will be
                     matched.
    :param udids: (Optional) A list of UDIDs that can be specified to serve as
                  identifiers for potential matches.  Ignored if names or
                  prefixes are specified.  If all three are None or empty, all
                  inputs of the specified wcls will be matched.
    :return: A callable matching function suitable for passing to the
             match_func parameter of the find_maps method.
    """
    def match_func(existing_elem):
        if not isinstance(existing_elem, wcls):
            return False
        if names:
            return getattr(existing_elem, name_prop) in names
        if prefixes:
            for prefix in prefixes:
                if getattr(existing_elem, name_prop).startswith(prefix):
                    return True
            # prefixes specified, but none matched
            return False
        if udids:
            return existing_elem.udid in udids
        # No names, prefixes, or UDIDs specified - hit everything
        return True
    return match_func


def find_maps(mapping_list, client_lpar_id=None, match_func=None,
              stg_elem=None, include_orphans=False):
    """Filter a list of scsi mappings by LPAR ID/UUID and a matching function.

    :param mapping_list: The mappings to filter.  Iterable of VSCSIMapping.
    :param client_lpar_id: Integer short ID or string UUID of the LPAR on the
                           client side of the mapping.  Note that the UUID form
                           relies on the presence of the client_lpar_href
                           field.  Some mappings lack this field, and would
                           therefore be ignored. If client_lpar_id is not
                           passed it will return matching mappings for all
                           the lpar_ids.
    :param match_func: Callable with the following specification:

        def match_func(storage_elem)
            param storage_elem: A backing storage element wrapper (VOpt, VDisk,
                                PV, or LU) to be analyzed.  May be None (some
                                mappings have no backing storage).
            return: True if the storage_elem's mapping should be included;
                    False otherwise.

                       If neither match_func nor stg_elem is specified, the
                       default is to match everything - that is, find_maps will
                       return all mappings for the specified client_lpar_id.
                       It is illegal to specify both match_func and stg_elem.
    :param stg_elem: Match mappings associated with a specific storage element.
                     Effectively, this generates a default match_func which
                     matches on the type and name of the storage element.
                     If neither match_func nor stg_elem is specified, the
                     default is to match everything - that is, find_maps will
                     return all mappings for the specified client_lpar_id.
                     It is illegal to specify both match_func and stg_elem.
    :param include_orphans: An "orphan" contains a server adapter but no client
                            adapter.  If this parameter is True, mappings with
                            no client adapter will still be considered for
                            inclusion.  If False, mappings with no client
                            adapter will be skipped entirely, regardless of any
                            other criteria.
    :return: A list comprising the subset of the input mapping_list whose
             client LPAR IDs match client_lpar_id and whose backing storage
             elements satisfy match_func.
    :raise ValueError: If both match_func and stg_elem are specified.
    """
    if match_func and stg_elem:
        raise ValueError(_("Must not specify both match_func and stg_elem."))
    if not match_func:
        # Default no filter
        match_func = lambda x: True
    if stg_elem:
        # Match storage element on type and name
        match_func = lambda stg_el: (
            stg_el is not None and
            stg_el.schema_type == stg_elem.schema_type and
            stg_el.name == stg_elem.name)

    is_uuid = False
    client_id = None
    if client_lpar_id:
        is_uuid, client_id = uuid.id_or_uuid(client_lpar_id)
    matching_maps = []
    for existing_scsi_map in mapping_list:
        # No client, continue on unless including orphans.
        if not include_orphans and existing_scsi_map.client_adapter is None:
            continue

        # If to a different VM, continue on.
        href = existing_scsi_map.client_lpar_href
        if is_uuid and (not href or client_id != util.get_req_path_uuid(
                href, preserve_case=True)):
            continue
        elif (client_lpar_id and not is_uuid and
              # Use the server adapter in case this is an orphan.
              existing_scsi_map.server_adapter.lpar_id != client_id):
            continue

        if match_func(existing_scsi_map.backing_storage):
            # Found a match!
            matching_maps.append(existing_scsi_map)
    return matching_maps


def index_mappings(maps):
    """Create an index dict of SCSI mappings to facilitate reverse lookups.

    :param maps: Iterable of VSCSIMapping to index.
    :return: A dict of the form:
        { 'by-lpar-id': { str(lpar_id): [VSCSIMapping, ...], ... },
          'by-lpar-uuid': { lpar_uuid: [VSCSIMapping, ...], ... },
          'by-storage-udid': { storage_udid: [VSCSIMapping, ...], ... }
        }
        ...where:
        - lpar_id is the short integer ID (not UUID) of the LPAR, stringified.
        - lpar_uuid is the UUID of the LPAR.
        - storage_udid is the Unique Device Identifier (UDID) of the backing
            Storage element associated with the mapping.

        While the outermost dict is guaranteed to have all keys, the inner
        dicts may be empty.  However, if an inner dict has a member, its list
        of mappings is guaranteed to be nonempty.
    """
    ret = {'by-lpar-id': {}, 'by-lpar-uuid': {}, 'by-storage-udid': {}}

    def add(key, ident, smap):
        """Add a mapping to an index.

        :param key: The top-level key name ('by-lpar-uuid', etc.)
        :param ident: The lower-level key name (e.g. the lpar_uuid)
        :param smap: The mapping to add to the index.
        """
        ident = str(ident)
        if not ident:
            return
        if ident not in ret[key]:
            ret[key][ident] = []
        ret[key][ident].append(smap)

    for smap in maps:
        clhref = smap.client_lpar_href
        if clhref:
            add('by-lpar-uuid',
                util.get_req_path_uuid(clhref, preserve_case=True), smap)

        clid = None
        # Mapping may not have a client adapter, but will always have a server
        # adapter - so get the LPAR ID from the server adapter.
        if smap.server_adapter:
            clid = smap.server_adapter.lpar_id
        add('by-lpar-id', clid, smap)

        stg = smap.backing_storage
        if stg:
            add('by-storage-udid', stg.udid, smap)

    return ret


def remove_vopt_mapping(adapter, vios, client_lpar_id, media_name=None,
                        udid=None):
    """Will remove the mapping for VOpt media.

    This method will remove the mapping between the virtual optical media
    and the client partition.  It does not delete the virtual optical media.
    Will leave other elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the VIO_SMAP extended attribute group.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param media_name: (Optional) The name of the virtual optical media to
                       remove from the SCSI bus.  If both media_name and udid
                       are None, will remove all virtual optical media mappings
                       associated with the specified client_lpar_id
    :param udid: (Optional) The UDID of the virtual optical media to remove
                 from the SCSI bus.  Ignored if media_name is specified.  If
                 both media_name and udid are None, will remove all virtual
                 optical media mappings associated with the client_lpar_id.
    :return: The VIOS wrapper representing the updated Virtual I/O Server.
             This is current with respect to etag and SCSI mappings.
    :return: A list of the backing VOpt media that was removed.
    """
    names = [media_name] if media_name else None
    udids = [udid] if udid else None
    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.VOptMedia, name_prop='media_name', names=names,
            udids=udids))


def remove_vdisk_mapping(adapter, vios, client_lpar_id, disk_names=None,
                         disk_prefixes=None, udids=None):
    """Will remove the mapping for VDisk media.

    This method will remove the mapping between the virtual disk and the
    client partition.  It does not delete the virtual disk.  Will leave other
    elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the VIO_SMAP extended attribute group.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param disk_names: (Optional) A list of names of the virtual disk to remove
                       from the SCSI bus.  If disk_names, disk_prefixes, and
                       udids are all None/empty, will remove all virtual disk
                       mappings associated with the specified client_lpar_id.
    :param disk_prefixes: (Optional) A list of prefixes that can be specified
                          to serve as identifiers for potential disks.  Ignored
                          if disk_names is specified.  If disk_names,
                          disk_prefixes, and udids are all None/empty, will
                          remove all virtual disk mappings associated with the
                          specified client_lpar_id.
    :param udids: (Optional) A list of UDIDs of the virtual disks to remove
                  from the SCSI bus.  Ignored if disk_names or disk_prefixes
                  are specified.  If all three are None/empty, will remove all
                  virtual disk mappings associated with the specified
                  client_lpar_id.
    :return: The VIOS wrapper representing the updated Virtual I/O Server.
             This is current with respect to etag and SCSI mappings.
    :return: A list of the backing VDisk objects that were removed.
    """

    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.VDisk, names=disk_names, prefixes=disk_prefixes,
            udids=udids))


def remove_lu_mapping(adapter, vios, client_lpar_id, disk_names=None,
                      disk_prefixes=None, udids=None):
    """Remove mappings for one or more SSP LUs associated with an LPAR.

    This method will remove the mapping between the Logical Unit and the
    client partition.  It does not delete the LU.  Will leave other elements on
    the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the VIO_SMAP extended attribute group.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param disk_names: (Optional) A list of names of the LUs to remove from
                       the SCSI bus.  If disk_names, disk_prefixes, and
                       udids are all None/empty, will remove all logical unit
                       mappings associated with the specified client_lpar_id.
    :param disk_prefixes: (Optional) A list of prefixes that can be specified
                          to serve as identifiers for potential disks.  Ignored
                          if disk_names is specified.  If disk_names,
                          disk_prefixes, and udids are all None/empty, will
                          remove all logical unit mappings associated with the
                          specified client_lpar_id.
    :param udids: (Optional) A list of UDIDs of the logical units to remove
                  from the SCSI bus.  Ignored if disk_names or disk_prefixes
                  are specified.  If all three are None/empty, will remove all
                  logical unit mappings associated with the specified
                  client_lpar_id.
    :return: The VIOS wrapper representing the updated Virtual I/O Server.
             This is current with respect to etag and SCSI mappings.
    :return: A list of LU EntryWrappers representing the mappings that were
             removed.
    """

    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.LU, names=disk_names, prefixes=disk_prefixes,
            udids=udids))


def remove_pv_mapping(adapter, vios, client_lpar_id, backing_dev, udid=None):
    """Will remove the PV mapping.

    This method will remove the pv mapping. It does not delete the device.
    Will leave other elements on the vSCSI bus intact.

    :param adapter: The pypowervm adapter for API communication.
    :param vios: The virtual I/O server from which the mapping should be
                 removed.  This may be the VIOS's UUID string OR an existing
                 VIOS EntryWrapper.  If the latter, it must have been retrieved
                 using the VIO_SMAP extended attribute group.
    :param client_lpar_id: The integer short ID or string UUID of the client VM
    :param backing_dev: The physical volume name to be removed.  If both
                        backing_dev and udid are None, will remove all physical
                        volume mappings associated with the specfied
                        client_lpar_id.
    :param udid: (Optional) UDID of the physical volume to remove from the SCSI
                  bus.  Ignored if backing_dev is not None.  If backing_dev and
                  udid are both None, will remove all physical volume mappings
                  associated with the specified client_lpar_id.
    :return: The VIOS wrapper representing the updated Virtual I/O Server.
             This is current with respect to etag and SCSI mappings.
    :return: A list of the backing physical device objects that were removed.
    """
    names = [backing_dev] if backing_dev else None
    udids = [udid] if udid else None
    return _remove_storage_elem(
        adapter, vios, client_lpar_id, gen_match_func(
            pvm_stor.PV, names=names, udids=udids))
