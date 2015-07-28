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

from taskflow import engines as tf_eng
from taskflow.patterns import unordered_flow as tf_uf
from taskflow import task as tf_task

from pypowervm.tasks import scsi_mapper
from pypowervm.tasks import vfc_mapper
from pypowervm.utils import retry as pvm_retry
from pypowervm.wrappers import managed_system as pvm_ms
from pypowervm.wrappers import virtual_io_server as pvm_vios


class _VioUpdateTracker(tf_task.Task):
    """An internal class to track changes for a given VIOS.

    This class is meant to track all of the changes that are needed for the
    storage mappings against a given VIOS.
    """

    def __init__(self, vios_w):
        """Initialize the Virtual I/O Server mapping tracker.

        :param vios_w: The Virtual I/O Server wrapper
        """
        super(_VioUpdateTracker, self).__init__(
            name='update_vios_%s' % vios_w.uuid, requires=['updated_list'])
        self.vios_w = vios_w
        self.vscsi_adds = []
        self.vscsi_removes = []
        self.vfc_adds = []
        self.vfc_removes = []

    def check_vscsi_mapping(self, vscsi_mapping):
        """Checks to see if a given vSCSI mapping already exists.

        The challenge here is that we can't just do an 'equals' between the
        two mappings.  A mapping from the 'bld' method (ex. for creates) will
        not have the complete data.  Therefore they're not truly equal.

        :param vscsi_mapping: The mapping to verify for.
        :return: The corresponding vSCSI mapping within the mappings on the
                 VIOS.  If one does not exist, None is returned.
        """
        if vscsi_mapping.backing_storage is not None:
            matches = scsi_mapper.find_maps(
                self.vios_w.scsi_mappings, xxx,
                stg_elem=vscsi_mapping.backing_storage)
            if len(matches) > 0:
                return matches[0]
        return None

    def check_vfc_mapping(self, vfc_mapping, remove=False):
        """Checks to see if a given vFC mapping already exists.

        The challenge here is that we can't just do an 'equals' between the
        two mappings.  A mapping from the 'bld' method (ex. for creates) will
        not have the complete data.  Therefore they're not truly equal.

        :param vfc_mapping: The mapping to verify for.
        :return: The corresponding vFC mapping within the mappings on the
                 VIOS.  If one does not exist, None is returned.
        """
        if vfc_mapping.client_adapter is not None:
            matches = vfc_mapper.find_maps(
                self.vios_w.vfc_mappings, xxx,
                client_adpt=vfc_mapping.client_adapter)
            if len(matches) > 0:
                return matches[0]
        return None

    def execute(self, updated_list):
        def _rebuild_vios(this_try, max_tries, *args, **kwargs):
            """Retry argmod to refresh the vios wrapper.

            This is so that etag mismatches trigger a fresh GET.
            """
            self.vios_w = self.vios_w.refresh()
            return args, kwargs

        @pvm_retry.retry(argmod_func=_rebuild_vios)
        def _update():
            # Remove the vSCSIs.  Remember that the context is that this could
            # be a retry.  So only remove if you can find it.
            for vscsi_rm in self.vscsi_removes:
                inline_map = self.check_vscsi_mapping(vscsi_rm)
                if inline_map:
                    self.vios_w.scsi_mappings.remove(inline_map)

            # Remove the vFCs.  Only remove if it contains it (due to retry
            # context)
            for vfc_rm in self.vfc_removes:
                inline_map = self.check_vfc_mapping(vfc_rm)
                if inline_map:
                    self.vios_w.vfc_mappings.remove(inline_map)

            # Add the vSCSI and the vFC mappings.  However, the context is
            # such that this is a retry.  Keep in mind that it may already
            # be in the list.  If it is, do NOT add it, as that would be a
            # duplicate entry.
            for vscsi_add in self.vscsi_adds:
                if not self.check_vscsi_mapping(vscsi_add):
                    self.vios_w.scsi_mappings.add(vscsi_add)

            for vfc_add in self.vfc_adds:
                if not self.check_vfc_mapping(vfc_add):
                    self.vios_w.vfc_mappings.add(vfc_add)

            # Do the update
            updated_list.append(self.vios_w.update())

        # Run the update.  Will auto retry the individual wrapper if needed.
        _update()


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

        vios_resp = self.adapter.read(
            pvm_ms.System.schema_type, root_id=self.host_uuid,
            child_type=pvm_vios.VIOS.schema_type,
            xag=[pvm_vios.VIOS.xags.SCSI_MAPPING,
                 pvm_vios.VIOS.xags.FC_MAPPING])
        self.vios_wraps = pvm_vios.VIOS.wrap(vios_resp)

        self.update_trackers = {x.uuid: _VioUpdateTracker(x)
                                for x in self.vios_wraps}

    def orig_vioses(self):
        """Returns the original VIOS wrapper objects.

        This should be used by the functions attempting to use the batcher.
        It should inspect the VIOSes and determine what mappings it needs
        to add/remove to the VIOS to support its new operation.
        """
        return self.vios_wraps

    def orig_vios_for_uuid(self, vios_uuid):
        """Returns the original VIOS wrapper for a given UUID.

        See orig_vioses.
        :param vios_uuid: The Virtual I/O Server UUID.
        :return: The original Virtual I/O Server for the given uuid.
        """
        for vios_w in self.vios_wraps:
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

    def execute_update(self):
        """Execute the updates against the Virtual I/O Servers.

        :return: The list of VIOS wrappers
        """
        unordered_flow = tf_uf.Flow("parallel_updates")
        unordered_flow.add(self.update_trackers.values())

        # The response list
        update_list = []

        # Run the updates in parallel
        tf_engine = tf_eng.load(
            unordered_flow, engine='parallel', max_workers=4,
            store=dict(updated_list=update_list))
        tf_engine.run()

        return update_list
