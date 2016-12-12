# Copyright 2014, 2016 IBM Corp.
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

import abc
import datetime as dt
import errno
import hashlib
import math
import re
import six
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
    xag list.  E.g. for xag=['b', 'c', 'a'], produce 'group=a,b,c'.

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
    # parse_qs returns { 'key': ['value'], ... }
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
            LOG.warning(_('Certificate has expired.'))
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
    # parse_qs returns { 'key': ['value'], ... }
    qparms = urlparse.parse_qs(parsed.query) if parsed.query else {}
    return uuid.lower(), qparms.get('group', [None])[0]


def convert_bytes_to_gb(bytes_, low_value=.0001, dp=None):
    """Converts an integer of bytes to a decimal representation of gigabytes.

    If the value is too low, will return the 'low_value'.  This is useful
    for converting a small number of bytes (ex. 50) into gigabytes.  Rounding
    may be required.

    :param bytes_: The integer number of bytes.
    :param low_value: The minimum value that should be returned.  (Note: if dp
                      is also specified, the value returned may be rounded up
                      and thus be higher than low_value.)
    :param dp: If specified, the value is rounded up to the specified number of
               decimal places by round_gb_size_up.  (Note: None and zero are
               very different.)
    :returns: The decimal value.
    """
    gb_size = bytes_ / float(units.Gi)
    if gb_size < low_value:
        gb_size = low_value
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


def sanitize_percent_for_api(float_val, precision=2):
    """Sanitizes a percent value for use in the API.

    :param float_val: A float where valid values are 0.0 <= x <= 1.0. For
                      example the input 0.02 will produce output '2%'.
    :return: A string representation of the passed percentage.
    """
    percent_float = float(float_val)
    if percent_float < 0 or percent_float > 1:
        raise ValueError('A float value 0 <= x <= 1.0 must be provided.')
    percent_float *= 100
    percent_float = sanitize_float_for_api(percent_float, precision)
    return str(percent_float) + '%'


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


def part_id_by_loc_code(loc_code):
    """Get a partition short ID for a provided virtual device location code.

    All location codes on a virtual device are of the form:
    <MachineType>.<Model>.<Serial>-V<PartID>-C<SlotNumber>

    :return: An int of the associated partition short ID.
    """
    id_match = re.search('.*-V(.+?)-.*', loc_code)
    return int(id_match.group(1)) if id_match else None


def xag_attrs(xagstr, base=const.DEFAULT_SCHEMA_ATTR):
    """Produce XML attributes for a property using extended attribute groups.

    :param xagstr: Extended attribute group name (from pypowervm.const.XAG).
    :param base: The dict of attributes to which to add the extended attribute
                 group.  Usually one of the pypowervm.const values near
                 DEFAULT_SCHEMA_ATTR (the default).
    :return: Dict of XML attributes suitable for the 'attrib' kwarg of a
             (pypowervm.entities or etree) Element constructor.
    """
    return dict(base, group=xagstr) if xagstr else base


def my_partition_id():
    """Return the short ID (not UUID) of the current partition, as an int."""
    with open('/proc/ppc64/lparcfg') as lparcfg:
        for line in lparcfg:
            if line.startswith('partition_id='):
                return int(line.split('=')[1].rstrip())


def parent_spec(parent, parent_type, parent_uuid):
    """Produce a canonical parent type and UUID suitable for read().

    :param parent: EntryWrapper representing the parent.  If specified,
                   parent_type and parent_uuid are ignored.
    :param parent_type: EntryWrapper class or schema_type string representing
                        the schema type of the parent.
    :param parent_uuid: String UUID of the parent.
    :return parent_type: String schema type of the parent.  The parent_type and
                         parent_uuid returns are both None or both valid
                         strings.
    :return parent_uuid: String UUID of the parent.  The parent_type and
                         parent_uuid returns are both None or both valid
                         strings.
    :raise ValueError: If parent is None and parent_type xor parent_uuid is
                       specified.
    """
    if all(param is None for param in (parent, parent_type, parent_uuid)):
        return None, None
    if parent is not None:
        return parent.schema_type, parent.uuid
    if any(param is None for param in (parent_type, parent_uuid)):
        # parent_type xor parent_uuid specified
        raise ValueError(_("Developer error: partial parent specification."))
    # Allow either string or class for parent_type
    if hasattr(parent_type, 'schema_type'):
        parent_type = parent_type.schema_type
    elif type(parent_type) is not str:
        raise ValueError(_("Developer error: parent_type must be either a "
                           "string schema type or a Wrapper subclass."))
    return parent_type, parent_uuid


def retry_io_command(base_cmd, *argv):
    """PEP475: Retry syscalls if EINTR signal received.

    https://www.python.org/dev/peps/pep-0475/

    Certain system calls can be interrupted by signal 4 (EINTR) for no good
    reason.  Per PEP475, these signals should be ignored.  This is implemented
    by default at the lowest level in py3, but we have to account for it in
    py2.

    :param base_cmd: The syscall to wrap.
    :param argv: Arguments to the syscall.
    :return: The return value from invoking the syscall.
    """
    while True:
        try:
            return base_cmd(*argv)
        except EnvironmentError as enve:
            if enve.errno != errno.EINTR:
                raise


@six.add_metaclass(abc.ABCMeta)
class _AllowedList(object):
    """For REST fields taking 'ALL', 'NONE', or [list of values].

    Subclasses should override parse_val and sanitize_for_api.
    """
    ALL = 'ALL'
    NONE = 'NONE'
    _GOOD_STRINGS = (ALL, NONE)

    @staticmethod
    def parse_val(val):
        """Parse a single list value from string to appropriate native type.

        :param val: A single value to parse.
        :return: The converted value.
        """
        # Default native type: str
        return val

    @staticmethod
    def sanitize_for_api(val):
        """Convert a native value to the expected string format for REST.

        :param val: The native value to convert.
        :return: Sanitized string value suitable for the REST API.
        :raise ValueError: If the string can't be converted.
        """
        # Default: Just string-convert
        return str(val)

    @classmethod
    def unmarshal(cls, rest_val):
        """Convert value from REST to a list of vals or an accepted string."""
        rest_val = rest_val.strip()
        if rest_val in cls._GOOD_STRINGS:
            return rest_val
        return [cls.parse_val(val) for val in rest_val.split()]

    @classmethod
    def const_or_list(cls, val):
        """Return one of the _GOOD_STRINGS, or the (sanitized) original list.

        :param val: One of:
                    - A string representing one of the _GOOD_STRINGS (case-
                      insensitive.
                    - A list containing a single value as above.
                    - A list containing values appropriate to the subclass.
        :return: One of:
                 - A string representing one of the _GOOD_STRINGS (in the
                   appropriate case).
                 - A list of the original values, validated and sanitized for
                   the REST API.
                 The objective is to be able to pass the return value directly
                 into a setter or bld method expecting the relevant type.
        :raise ValueError: If the input could not be interpreted/sanitized as
                           appropriate to the subclass.
        """
        ret = None
        if isinstance(val, str) and val.upper() in cls._GOOD_STRINGS:
            ret = val.upper()
        elif isinstance(val, list):
            if (len(val) == 1 and isinstance(val[0], str)
                    and val[0].upper() in cls._GOOD_STRINGS):
                ret = val[0].upper()
            else:
                ret = [cls.sanitize_for_api(ival) for ival in val]
        if ret is not None:
            return ret
        # Not a list, not a good value
        raise ValueError(_("Invalid value '%(bad_val)s'.  Expected one of "
                           "%(good_vals)s, or a list.") %
                         {'bad_val': val, 'good_vals': str(cls._GOOD_STRINGS)})

    @classmethod
    def marshal(cls, val):
        """Produce a string suitable for the REST API."""
        val = cls.const_or_list(val)
        return (' '.join([str(ival) for ival in val]) if isinstance(val, list)
                else val)


class VLANList(_AllowedList):
    """For REST fields of type AllowedVLANIDs.Union."""
    @staticmethod
    def parse_val(val):
        return int(val)

    @staticmethod
    def sanitize_for_api(val):
        try:
            return int(val)
        except (ValueError, TypeError):
            raise ValueError("Specify a list of VLAN integers or integer "
                             "strings; or 'ALL' for all VLANS or 'NONE' for "
                             "no VLANS.")


class MACList(_AllowedList):
    """For REST fields of type AllowedMACAddresses.Union."""
    # Default parse_val is fine

    @staticmethod
    def sanitize_for_api(val):
        return sanitize_mac_for_api(val)
