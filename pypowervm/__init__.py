# Copyright 2014, 2015 IBM Corp.
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

from oslo_config import cfg

ibmpowervm_opts = [
    cfg.IntOpt('pypowervm_update_collision_retries',
               default=5,
               help='Number of retries if an update operation failed due to '
                    'collision'),
    cfg.IntOpt('pypowervm_job_request_timeout',
               default=1800,
               help='Default timeout in seconds for PowerVM Job requests.'),
]

CONF = cfg.CONF
CONF.register_opts(ibmpowervm_opts)
