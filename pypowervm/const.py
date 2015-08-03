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

"""Pervasive, widely-used constants."""

import six

# TODO(IBM): is anything else not cacheable?
UNCACHEABLE = ('/rest/api/web/', '/rest/api/pcm/',
               '/quick', '/search/', '?detail', '/jobs')
# TODO(IBM): invalidate SSP cache based on ClusterLULinkedClone jobs

DEFAULT_SCHEMA_VERSION = 'V1_0'
SCHEMA_VER120 = 'V1_2_0'
SCHEMA_VER130 = 'V1_3_0'
SCHEMA_VER = 'schemaVersion'
ATTR_SCHEMA = 'ksv'
DEFAULT_SCHEMA_ATTR = {SCHEMA_VER: DEFAULT_SCHEMA_VERSION}
ATTR_SCHEMA120 = {ATTR_SCHEMA: SCHEMA_VER120}
ATTR_SCHEMA130 = {ATTR_SCHEMA: SCHEMA_VER130, SCHEMA_VER: SCHEMA_VER130}

API_BASE_PATH = '/rest/api/'
LOGON_PATH = API_BASE_PATH + 'web/Logon'
TYPE_TEMPLATE = 'application/vnd.ibm.powervm.%s+xml; type=%s'
# The following is interpolated *twice*.  The first time, we insert either the
# Password element or the GenerateX-API-SessionFile element after the UserID.
# We don't want to interpolate 'userid' until the second interpolation, which
# happens at runtime in the Session's login routine.
_LOGONREQUEST_TEMPLATE_TEMPLATE = six.u(
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' +
    '<LogonRequest xmlns="http://www.ibm.com/xmlns/systems/power/firmware/' +
    'web/mc/2012_10/" schemaVersion="V1_0">\n' +
    '    <UserID>%%(userid)s</UserID>\n' +
    '    %(pass_or_file)s\n' +
    '</LogonRequest>')
_PASS_TEMPLATE = '<Password>%(passwd)s</Password>'
_SESS_FILE = '<GenerateX-API-SessionFile>true</GenerateX-API-SessionFile>'
# LogonRequest template to be used for password-based authentication
LOGONREQUEST_TEMPLATE_PASS = _LOGONREQUEST_TEMPLATE_TEMPLATE % dict(
    pass_or_file=_PASS_TEMPLATE)
# LogonRequest template to be used for file-based authentication
LOGONREQUEST_TEMPLATE_FILE = _LOGONREQUEST_TEMPLATE_TEMPLATE % dict(
    pass_or_file=_SESS_FILE)

ATOM_NS = 'http://www.w3.org/2005/Atom'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
WEB_NS = 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'
PCM_NS = 'http://www.ibm.com/xmlns/systems/power/firmware/pcm/mc/2012_10/'
UOM_BASE_NS = 'http://www.ibm.com/xmlns/systems/power/firmware/uom/mc'
UOM_NS = UOM_BASE_NS + '/2012_10/'

# Match a UUID anywhere in the search string
UUID_REGEX = '%(x)s{8}-%(x)s{4}-%(x)s{4}-%(x)s{4}-%(x)s{12}' % {
    'x': '[A-Fa-f0-9]'}
# Entire search string must be a UUID and nothing more
UUID_REGEX_WORD = '^%s$' % UUID_REGEX

SUFFIX_TYPE_DO = 'do'
LINK = 'link'

PORT_DEFAULT_BY_PROTO = {
    'http': 12080,
    'https': 12443
}

SERVICE_BY_NS = {
    WEB_NS: 'web',
    UOM_NS: 'uom',
    PCM_NS: 'pcm'
}


class HTTPStatus(object):
    """Small subset of HTTP status codes as used by PowerVM."""
    OK_NO_CONTENT = 204
    NO_CHANGE = 304
    UNAUTHORIZED = 401
    ETAG_MISMATCH = 412
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


class MaxLen(object):
    """Maximum lengths for various PowerVM entities."""
    # FileName.Pattern
    FILENAME_DEFAULT = 79
    VOPT_NAME = 37
    VDISK_NAME = 15
