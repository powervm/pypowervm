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

from pypowervm.tasks.hdisk import _npiv

LUAType = _npiv.LUAType
LUAStatus = _npiv.LUAStatus
normalize_lun = _npiv.normalize_lun
ITL = _npiv.ITL
good_discovery = _npiv.good_discovery
build_itls = _npiv.build_itls
discover_hdisk = _npiv.discover_hdisk
lua_recovery = _npiv.lua_recovery
remove_hdisk = _npiv.remove_hdisk
get_pg83_via_job = _npiv.get_pg83_via_job
