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

"""Tasks related to objects that will appear as hard disks to VMs."""

from pypowervm.tasks.hdisk import _fc
from pypowervm.tasks.hdisk import _iscsi

LUAType = _fc.LUAType
LUAStatus = _fc.LUAStatus
normalize_lun = _fc.normalize_lun
ITL = _fc.ITL
good_discovery = _fc.good_discovery
build_itls = _fc.build_itls
discover_hdisk = _fc.discover_hdisk
lua_recovery = _fc.lua_recovery
remove_hdisk = _fc.remove_hdisk
get_pg83_via_job = _fc.get_pg83_via_job
discover_iscsi = _iscsi.discover_iscsi
discover_iscsi_initiator = _iscsi.discover_iscsi_initiator
remove_iscsi = _iscsi.remove_iscsi
