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

"""Utilities for batching together updates to Virtual I/O Servers."""

import copy

from pypowervm import util as pvm_util
from pypowervm.utils import retry as pvm_retry
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import virtual_io_server as pvm_vios


class _VioUpdateTracker(object):
    """An internal class to track changes for a given VIOS.

    This class is meant to track all of the changes that are needed for the
    storage mappings against a given VIOS.
    """

    def __init__(self, vios_uuid):
        """Initialize the Virtual I/O Server mapping tracker.

        :param vios_uuid: The Virtual I/O Server UUID
        """
        self.vios_uuid = vios_uuid
        self.vscsi_adds = []
        self.vscsi_removes = []
        self.vfc_adds = []
        self.vfc_removes = []

    def transform(self, vios_w):
        # TODO(thorst) Remove the vSCSIs

        # TODO(thorst) Remove the vFCs

        # TODO(thorst) Add the vSCSIs

        # TODO(thorst) Add the vFCs
        pass


class VioUpdateBatch(object):
    """Virtual I/O Server Storage Mapping Batch Update.

    Running storage mapping operations against the Virtual I/O Server is one
    of the most expensive operations that can be done against the PowerVM API.
    A typical LPAR create request may need to make several mapping requests.
    This could be due to multiple I/O servers, connecting multiple things (ex.
    vOpt, vDisk, vFC, etc...) or a multitude of other reasons.

    This class allows a user to batch together all of the mapping requests
    for a set of Virtual I/O Servers together.  The code will be intelligent
    enough to run the Virtual I/O Server updates in parallel.  Will handle a
    failure scenarios and run retries.
    """

    def __init__(self, adapter, host_uuid):
        """Initializes the class.

        :param adapter: The pypowervm adapter to communicate with the PowerVM
                        API.
        :param host_uuid: The host server's UUID.
        """
        self.adapter = adapter
        self.host_uuid = host_uuid
        self._refresh_vioses()
        self.update_trackers = {x.uuid: _VioUpdateTracker()
                                for x in self.vios_wraps}
        self._orig_vioses = copy.deepcopy(self.vios_wraps)

    def _refresh_vioses(self):
        """Internally refresh the Virtual I/O Server wrappers."""
        vios_resp = self.adapter.read(
            pvm_ms.System.schema_type, root_id=self.host_uuid,
            child_type=pvm_vios.VIOS.schema_type,
            xag=[pvm_vios.VIOS.xags.SCSI_MAPPING,
                 pvm_vios.VIOS.xags.FC_MAPPING])
        self.vios_wraps = pvm_vios.VIOS.wrap(vios_resp)

    def orig_vioses(self):
        """Returns the original VIOS wrapper objects.

        This should be used by the functions attempting to use the batcher.
        It should inspect the VIOSes and determine what mappings it needs
        to add/remove to the VIOS to support its new operation.
        """
        return self._orig_vioses

    def orig_vios_for_uuid(self, vios_uuid):
        """Returns the original VIOS wrapper for a given UUID.

        See orig_vioses.
        :param vios_uuid: The Virtual I/O Server UUID.
        :return: The original Virtual I/O Server for the given uuid.
        """
        for vios_w in self._orig_vioses:
            if vios_w.uuid == vios_uuid:
                return vios_w
        return None

    def add_vscsi_map(self, vios_uuid, mapping):
        """Indicates that a given vSCSI mapping should be added to a VIOS.

        :param vios_uuid: The UUID of the Virtual I/O Server that the mapping
                          should be added to.
        :param mapping: The vSCSI mapping that should be added to the Virtual
                        I/O Server.
        """
        self.update_trackers[vios_uuid].vscsi_adds.append(mapping)

    def remove_vscsi_map(self, vios_uuid, mapping):
        """Indicates that a given vSCSI mapping should be removed from a VIOS.

        :param vios_uuid: The UUID of the Virtual I/O Server that the mapping
                          should be removed from.
        :param mapping: The vSCSI mapping that should be removed from the
                        Virtual I/O Server.
        """
        self.update_trackers[vios_uuid].vscsi_removes.append(mapping)

    def add_vfc_map(self, vios_uuid, mapping):
        """Indicates that a given vFC mapping should be added to a VIOS.

        :param vios_uuid: The UUID of the Virtual I/O Server that the mapping
                          should be added to.
        :param mapping: The vFC mapping that should be added to the Virtual
                        I/O Server.
        """
        self.update_trackers[vios_uuid].vfc_adds.append(mapping)

    def remove_vfc_map(self, vios_uuid, mapping):
        """Indicates that a given vFC mapping should be removed from a VIOS.

        :param vios_uuid: The UUID of the Virtual I/O Server that the mapping
                          should be removed from.
        :param mapping: The vFC mapping that should be removed from the Virtual
                        I/O Server.
        """
        self.update_trackers[vios_uuid].vfc_removes.append(mapping)

    def _wrap_for_id(self, vios_uuid):
        for vios_w in self.vios_wraps:
            if vios_w.uuid == vios_uuid:
                return vios_w
        return None

    def execute_update(self):
        """Execute the updates against the Virtual I/O Servers."""

        def _rebuild_vioses(this_try, max_tries, *args, **kwargs):
            """Retry argmod to refresh the vios wrappers.

            This is so that etag mismatches trigger a fresh GET.
            """
            self._refresh_vioses()
            return args, kwargs

        @pvm_retry.retry(argmod_func=_rebuild_vioses)
        def execute():
            # This operation runs through all the VIOSes with the refreshed
            # wrappers.  It will add/remove any mappings that it needs to.
            # If the mappings had already been added/removed, then they will
            # be ignored.
            for vios_uuid in self.update_trackers.keys():
                self.update_trackers[vios_uuid].transform(
                    self._wrap_for_id(vios_uuid))

            # Now execute a parallel update to the VIOSes.
            pvm_util.parallel_update(self.vios_wraps)
