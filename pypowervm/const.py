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

import six

# TODO(IBM): is anything else not cacheable?
UNCACHEABLE = ('/rest/api/web/', '/rest/api/pcm/',
               '/quick', '/search/', '?detail', '/jobs')
# TODO(IBM): invalidate SSP cache based on ClusterLULinkedClone jobs

DEFAULT_SCHEMA_VERSION = 'V1_0'
SCHEMA_VER120 = 'V1_2_0'
SCHEMA_VER = 'schemaVersion'
ATTR_SCHEMA = 'ksv'
DEFAULT_SCHEMA_ATTR = {SCHEMA_VER: DEFAULT_SCHEMA_VERSION}
ATTR_SCHEMA120 = {ATTR_SCHEMA: SCHEMA_VER120}

XAG_NONE = 'None'
API_BASE_PATH = '/rest/api/'
LOGON_PATH = API_BASE_PATH + 'web/Logon'
TYPE_TEMPLATE = 'application/vnd.ibm.powervm.%s+xml; type=%s'
LOGONREQUEST_TEMPLATE = six.u(
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' +
    '<LogonRequest xmlns="http://www.ibm.com/xmlns/systems/power/firmware/' +
    'web/mc/2012_10/" schemaVersion="V1_0">\n' +
    '    <UserID>%(userid)s</UserID>\n' +
    '    <Password>%(passwd)s</Password>\n' +
    '</LogonRequest>')

ATOM_NS = 'http://www.w3.org/2005/Atom'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
WEB_NS = 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'
UOM_NS = 'http://www.ibm.com/xmlns/systems/power/firmware/uom/mc/2012_10/'
UOM_BASE_NS = 'http://www.ibm.com/xmlns/systems/power/firmware/uom/mc'

UUID_REGEX = ('[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-' +
              '[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}')
