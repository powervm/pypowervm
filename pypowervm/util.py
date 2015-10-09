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

"""Pervasive/commonly-used utilities."""

import datetime as dt
import hashlib
import math
import re
import socket
import ssl
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

from oslo_log import log as logging
from oslo_utils import units
from pyasn1.codec.der import decoder as der_decoder
from pyasn1_modules import rfc2459

from pypowervm import const
from pypowervm.i18n import _

# Set up logging
LOG = logging.getLogger(__name__)

XPATH_DELIM = '/'


def dice_href(href, include_scheme_netloc=False, include_query=True,
              include_fragment=True):
    """Parse, sanitize, and reassemble an href.

    :param href: A full link string of the form
                 '<scheme>://<netloc>/<path>;<params>?<query>#<fragment>'.
                 This method also works if the <scheme>://<netloc> is omitted,
                 (but obviously include_scheme_netloc has no effect).
    :param include_scheme_netloc: If True, the <scheme>://<netloc> portion is
                                  included in the returned string.  If False,
                                  it is stripped.
    :param include_query: If True, any ?<query> portion of the link will be
                          included in the return value.
    :param include_fragment: If True, any #<fragment> portion of the link will
                             be included in the return value.
    :return: A string representing the specified portion of the input link.
    """
    parsed = urlparse.urlparse(href)
    ret = ''
    if include_scheme_netloc:
        ret += parsed.scheme + '://' + parsed.netloc
    ret += parsed.path
    # trim trailing '/'s from path, if present
    while ret.endswith('/'):
        ret = ret[:-1]
    if include_query and parsed.query:
        ret += '?' + parsed.query
    if include_fragment and parsed.fragment:
        ret += '#' + parsed.fragment
    return ret


def check_and_apply_xag(path, xag):
    """Validate extended attribute groups and produce the correct path.

    If the existing path already has a group=* other than None, we use it.
    However, if there is a proposed xag - including [] - it must match the
    existing xag, or ValueError is raised.

    Otherwise, we construct the group=* query param according to the
    proposed xag list, as follows:

    If xag is None, use group=None.
    If xag is [] (the empty list), omit the group= query param entirely.
    Otherwise the group= value is a sorted, comma-separated string of the
    xag list.  E.g. for xag=['b', 'c', 'a'], yield 'group=a,b,c'.

    :param path: Input path or href, which may or may not contain a query
                 string, which may or may not contain a group=*.  (Multiple
                 group=* not handled.)  Values in the group=* must be
                 alpha sorted.
    :param xag: Iterable of proposed extended attribute values to be included
                in the query string of the resulting path.
    :return: path, with at most one group=* in the query string.  That
             group= query param's value will be alpha sorted.
    """
    parsed = urlparse.urlsplit(path)
    # parse_qs yields { 'key': ['value'], ... }
    qparms = urlparse.parse_qs(parsed.query) if parsed.query else {}
    path_xag = qparms.pop('group', ['None'])[0]
    if xag is None:
        arg_xag = 'None'
    else:
        # Ensure we have a mutable copy to sort
        xag = list(xag)
        xag.sort()
        arg_xag = ','.join(map(str, xag))  # may be ''

    if path_xag == 'None':
        # No existing xag.  (Treat existing 'group=None' as if not there.)
        # Use whatever was proposed (which may be implicit group=None or
        # may be nothing).
        path_xag = arg_xag
    elif arg_xag != 'None':
        # There was xag in the path already, as well as proposed xag (maybe
        # empty).  Previous xag must match proposed xag if specified
        # (including empty).
        if path_xag != arg_xag:
            raise ValueError(_("Proposed extended attribute group "
                               "'%(arg_xag)s' doesn't match existing "
                               "extended attribute group '%(path_xag)s'") %
                             dict(arg_xag=arg_xag, path_xag=path_xag))
    # else proposed xag is None, so use whatever was already in the path,

    # Whatever we decided on, add it back to the query params if nonempty.
    if path_xag != '':
        qparms['group'] = [path_xag]

    # Rebuild the querystring.  Honor multiples (e.g. foo=bar&foo=baz).
    # (We didn't expect/handle multiple group=*, but need to support it in
    # other keys.)
    qstr = '&'.join(['%s=%s' % (key, val)
                     for key, vals in qparms.items()
                     for val in vals])
    return urlparse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                qstr, parsed.fragment))


def extend_basepath(href, add):
    """Extends the base path of an href, accounting for querystring/fragment.

    For example, extend_basepath('http://server:1234/foo?a=b&c=d#frag', '/bar')
    => 'http://server:1234/foo/bar?a=b&c=d#frag'

    :param href: Path or href to augment.  Scheme, netloc, query string, and
                 fragment are allowed but not required.
    :param add: String to add onto the base path of the href.  Must not contain
                unescaped special characters such as '?', '&', '#'.
    :return: The augmented href.
    """
    parsed = urlparse.urlsplit(href)
    basepath = parsed.path + add
    return urlparse.urlunsplit((parsed.scheme, parsed.netloc, basepath,
                                parsed.query, parsed.fragment))


def is_instance_path(href):
    """Does the path or href represent an instance (end with UUID)?

    :param href: Path or href to check.  Scheme, netloc, query string, and
                 fragment are allowed but not required.
    :return: True if href's path ends with a UUID, indicating that it
             represents an instance (as opposed to a Feed or some special URI
             such as quick or search).
    """
    path = dice_href(href, include_scheme_netloc=False, include_query=False,
                     include_fragment=False)

    return re.match(const.UUID_REGEX_WORD, path.rsplit('/', 1)[1])


def determine_paths(resp):
    paths = []
    for lnk in resp.atom.links.get('SELF', []):
        paths.append(urlparse.urlparse(lnk).path)
    if not paths:
        if resp.reqmethod == 'PUT':
            # a PUT's reqpath will be the feed, to which we need to add
            # the new entry id (which didn't exist before the PUT)
            paths = [extend_basepath(resp.reqpath, '/' + resp.entry.uuid)]
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


def get_req_path_uuid(path, preserve_case=False, root=False):
    """Extract request target uuid of sanitized path.

    :param path: Path or URI from which to extract the UUID.
    :param preserve_case: If False, the returned UUID will be lowercased.  If
                          True, it will be returned as it exists in the path.
    :param root: If True, and path represents a CHILD entry, the UUID of the
                 ROOT is returned.  Otherwise, the UUID of the target is
                 returned.
    """
    ret = None
    p = dice_href(path, include_query=False, include_fragment=False)
    if '/' in p:
        for maybe_id in p.rsplit('/', 3)[1::2]:
            uuid_match = re.match(const.UUID_REGEX_WORD, maybe_id)
            if uuid_match:
                ret = maybe_id if preserve_case else maybe_id.lower()
                if root:
                    # Want to return the first one.  (If it's a ROOT path, this
                    # will also happen to be the last one.)
                    break
    return ret


def get_uuid_xag_from_path(path):
    uuid = get_req_path_uuid(path)
    parsed = urlparse.urlsplit(path)
    # parse_qs yields { 'key': ['value'], ... }
    qparms = urlparse.parse_qs(parsed.query) if parsed.query else {}
    return uuid.lower(), qparms.get('group', [None])[0]


def convert_bytes_to_gb(bytes_, low_value=.0001, dp=None):
    """Converts an integer of bytes to a decimal representation of gigabytes.

    If the value is too low, will return the 'low_value'.  This is useful
    for converting a small number of bytes (ex. 50) into gigabytes.  Rounding
    may be required.

    :param bytes_: The integer number of bytes.
    :param low_value: The minimum value that should be returned.
    :param dp: If specified, the value is rounded up to the specified number of
               decimal places by round_gb_size_up.  (Note: None and zero are
               very different.)
    :returns: The decimal value.
    """
    gb_size = bytes_ / float(units.Gi)
    if gb_size < low_value:
        return low_value
    if dp is not None:
        gb_size = round_gb_size_up(gb_size, dp=dp)
    return gb_size


def round_gb_size_up(gb_size, dp=2):
    """Rounds a GB disk size (as a decimal float) up to suit the platform.

    Use this method to ensure that new vdisks, LUs, etc. are big enough, as the
    platform generally rounds inputs to the nearest [whatever].  For example, a
    disk of size 4.321GB may wind up at 4.32GB after rounding, possibly leaving
    insufficient space for the image.
    :param gb_size: A decimal float representing the GB size to be rounded.
    :param dp: The number of decimal places to round (up) to.  May be zero
    (round to next highest integer) or negative, (e.g. -1 will round to the
    next highest ten).
    :return: A new decimal float which is greater than or equal to the input.
    """
    shift = 10.0**dp
    return float(math.ceil(gb_size * shift))/shift


def sanitize_mac_for_api(mac):
    """Converts a generalized mac address to one for the API.

    Takes any standard mac (case-insensitive, with or without colons) and
    formats it to uppercase and removes colons.  This is the format for
    the API.
    :param mac: The input mac.
    :returns: The sanitized mac.
    """
    return mac.replace(':', '').upper()


def sanitize_bool_for_api(bool_val):
    """Sanitizes a boolean value for use in the API."""
    return str(bool_val).lower()


def sanitize_float_for_api(float_val, precision=2):
    """Sanitizes a float value for use in the API."""
    template = '%.' + str(precision) + 'f'
    return template % float(float_val)


def sanitize_wwpn_for_api(wwpn):
    """Updates the format of the WWPN to match the expected PowerVM format.

    :param wwpn: The original WWPN.
    :return: A WWPN of the format expected by the API.
    """
    return wwpn.upper().replace(':', '')


def sanitize_file_name_for_api(name, prefix='', suffix='',
                               max_len=const.MaxLen.FILENAME_DEFAULT):
    """Generate a sanitized file name based on PowerVM's FileName.Pattern.

    :param name: The base name to sanitize.
    :param prefix: (Optional) A prefix to prepend to the 'name'.  No delimiter
                   is added.
    :param suffix: (Optional) A suffix to append to the 'name'.  No delimiter
                   is added.
    :param max_len: (Optional) The maximum allowable length of the final
                    sanitized string.  Defaults to the API's defined length for
                    FileName.Pattern.
    :return: A string scrubbed of all forbidden characters and trimmed for
             length as necessary.
    """
    def _scrub(in_name):
        """Returns in_name with illegal characters replaced with '_'."""
        return re.sub(r'[^.0-9A-Z_a-z]', '_', in_name)

    name, prefix, suffix = (_scrub(val) for val in (name, prefix, suffix))
    base_len = max_len - len(prefix) - len(suffix)
    if base_len <= 0:
        raise ValueError(_("Prefix and suffix together may not be more than "
                           "%d characters."), max_len - 1)
    name = name[:base_len]
    ret = prefix + name + suffix
    if not len(ret):
        raise ValueError(_("Total length must be at least 1 character."))
    return ret


def sanitize_partition_name_for_api(name, trunc_ok=True):
    """Sanitize a string to be suitable for use as a partition name.

    PowerVM's partition name restrictions are:
    - Between 1 and 31 characters, inclusive;
    - Containing ASCII characters between 0x20 (space) and 0x7E (~), inclusive,
      except ()\<>*$&?|[]'"`

    :param name: The name to scrub.  Invalid characters will be replaced with
                 '_'.
    :param trunc_ok: If True, and name exceeds 31 characters, it is truncated.
                     If False, and name exceeds 31 characters, ValueError is
                     raised.
    :return: The scrubbed string.
    :raise ValueError: If name is None or zero length; or if it exceeds length
                       31 and trunk_ok=False.
    """
    max_len = 31
    if not name:
        raise ValueError(_("The name parameter must be at least one character "
                           "long."))
    if not trunc_ok and len(name) > max_len:
        raise ValueError(_("The name parameter must not exceed %d characters "
                           "when trunk_ok is False."), max_len)
    return re.sub(r'[^- !#%+,./0-9:;=@A-Z^_a-z{}]', '_', name)[:max_len]


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


def find_wrapper(haystack, needle_uuid):
    """Finds the corresponding wrapper from a list given the UUID.

    :param haystack:  A list of wrappers.  Usually generated from a 'feed' that
                      has been loaded via the wrapper's wrap(response) method.
    :param needle_uuid: The UUID of the object to find in the list.
    :return: The corresponding wrapper for that UUID.  If not found, None.
    """
    for wrapper in haystack:
        if wrapper.uuid == needle_uuid:
            return wrapper
    return None


def xpath(*toks):
    """Constructs an XPath out of the passed-in string components."""
    return XPATH_DELIM.join(toks)
