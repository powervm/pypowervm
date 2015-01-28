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

import datetime as dt
import hashlib
import logging
import re
import socket
import ssl
try:
    import urlparse
except ImportError:
    from urllib.parse import urlparse

from oslo.utils import units
from pyasn1.codec.der import decoder as der_decoder
from pyasn1_modules import rfc2459

from pypowervm import const

# Set up logging
LOG = logging.getLogger(__name__)


def sanitize_path(path):
    # trim trailing '/' from path, if present
    if path.endswith('/'):
        path = path[:-1]
    return path


def determine_paths(resp):
    paths = []
    if resp.feed:
        links = resp.feed.properties.get('links')
    else:
        links = resp.entry.properties.get('links')
    if links:
        self_links = links.get('SELF')
        if self_links:
            for lnk in self_links:
                paths.append(urlparse.urlparse(lnk).path)
    if not paths:
        if resp.reqmethod == 'PUT':
            # a PUT's reqpath will be the feed, to which we need to add
            # the new entry id (which didn't exist before the PUT)
            paths = [resp.reqpath + '/' + resp.entry.properties['id']]
        else:
            paths = [resp.reqpath]
    return paths


def get_max_age(path, use_events, schema_version):
    if any(p in path for p in ['Cluster', 'SharedStoragePool']):
        # no event support
        # TODO(IBM): update when event support is added
        return 15
    if not use_events or schema_version.startswith('V1_0'):
        # bad event support
        # attempt to return the same values used by PowerVC 1.2.0 feed caches
        # TODO(IBM): make these config options
        if re.search('/LogicalPartition$', path):
            return 30
        if re.search('/VirtualIOServer$', path):
            return 90
        if re.search('/SharedProcessorPool$', path):
            return 600
        if re.search('/ManagedSystem/%s$' % const.UUID_REGEX, path):
            return 30
        else:
            # TODO(IBM): can we trust the cache longer than 0
            # for anything else?
            return 0
    else:
        # TODO(IBM): consider extending as we grow more confident in events
        return 600


# TODO(IBM): fix (for MITM attacks) or remove (if using loopback only)
def validate_certificate(host, port, certpath, certext):
    hostname = re.sub('[:.]', '_', host)
    cert_file = '%s%s%s' % (certpath, hostname, certext)
    try:
        with open(cert_file, 'r') as f:
            # Retrieve previously trusted certificate
            trusted_cert = ssl.PEM_cert_to_DER_cert(f.read())
    except Exception:
        # found no trusted certificate
        return False
    # Read current certificate from host
    conn = None
    try:
        # workaround for http://bugs.python.org/issue11811
        # should go back to using get_server_certificate when fixed
        # (Issue is resolved as of python 3.3.  Workaround still needed for
        # python 2.7 support.)
        #   rawcert = ssl.get_server_certificate((host, port))
        #   current_cert = ssl.PEM_cert_to_DER_cert(rawcert)
        conn = socket.create_connection((host, port))
        sock = ssl.wrap_socket(conn)
        current_cert = sock.getpeercert(True)
    except Exception:
        # couldn't get certificate from host
        return False
    finally:
        if conn is not None:
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
    # Verify certificate finger prints are the same
    if not (hashlib.sha1(trusted_cert).digest() ==
            hashlib.sha1(current_cert).digest()):
        return False
    # check certificate expiration
    try:
        cert = der_decoder.decode(current_cert,
                                  asn1Spec=rfc2459.Certificate())[0]
        tbs = cert.getComponentByName('tbsCertificate')
        validity = tbs.getComponentByName('validity')
        not_after = validity.getComponentByName('notAfter').getComponent()
        not_after = dt.datetime.strptime(str(not_after), '%y%m%d%H%M%SZ')
        if dt.datetime.utcnow() >= not_after:
            LOG.warn('certificate has expired')
            return False
    except Exception:
        LOG.exception('error parsing cert for expiration check')
        return False
    return True


def get_req_path_uuid(path):
    """Extract request target uuid of sanitized path."""
    if '/' in path:
        target_id = path.rsplit('/', 1)[1]
        uuid_match = re.match(const.UUID_REGEX, target_id)
        if uuid_match:
            return uuid_match.group(0).lower()
    return None


# TODO(IBM): Use urlparse.parse_qs()
def get_uuid_xag_from_path(path):
    if '/' in path:
        (feed_path, uuid) = path.rsplit('/', 1)
        match_str = '(' + const.UUID_REGEX + ')' + '(.*)'
        matched_uuid = re.match(match_str, uuid)
        if matched_uuid:
            (uuid, parms) = matched_uuid.group(1, 2)
            xag_search = re.search('([&?]group=)(.*)', parms)
            if xag_search:
                xag_str = xag_search.group(2)
                if '&' in xag_str:
                    xag_str = xag_str.split('&')[0]
            else:
                xag_str = ''
            return uuid.lower(), xag_str
    return None, None


def convert_bytes_to_gb(bytes_, low_value=.0001):
    """Converts an integer of bytes to a decimal representation of gigabytes.

    If the value is too low, will return the 'low_value'.  This is useful
    for converting a small number of bytes (ex. 50) into gigabytes.  Rounding
    may be required.

    :param bytes_: The integer number of bytes.
    :param low_value: The minimum value that should be returned.
    :returns: The decimal value.
    """
    gb_size = bytes_ / float(units.Gi)
    if gb_size < low_value:
        return low_value
    return gb_size


def sanitize_mac_for_api(mac):
    """Converts a generalized mac address to one for the API.

    Takes any standard mac (case-insensitive, with or without colons) and
    formats it to uppercase and removes colons.  This is the format for
    the API.
    :param mac: The input mac.
    :returns: The sanitized mac.
    """
    return mac.replace(':', '').upper()


def find_equivalent(elem, find_list):
    """Returns the element from the list that is equal to the one passed in.

    For remove operations and what not, the exact object may need to be
    provided.  This method will find the functionally equivalent element
    from the list.

    :param elem: The original element.
    :param find_list: The list to search through.
    :returns: An element from the that is functionally equivalent (based on
              __eq__).  If it does not exist, None is returned.
    """
    for find_elem in find_list:
        if find_elem == elem:
            return find_elem
    return None
