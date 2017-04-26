# Copyright 2014, 2017 IBM Corp.
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
"""Low-level communication with the PowerVM REST API."""
import abc
import copy
import errno
import hashlib
import os
import uuid

if os.name == 'posix':
    import pwd
import re
import threading
import time
import xml.sax.saxutils as sax_utils

from lxml import etree

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

from oslo_log import log as logging
import requests
import requests.exceptions as rqex
import six
import six.moves.urllib.parse as urllib
import weakref

from pypowervm import const as c
import pypowervm.entities as ent
import pypowervm.exceptions as pvmex
from pypowervm.i18n import _
from pypowervm import traits as pvm_traits
from pypowervm import util
from pypowervm.utils import retry


# Preserve CDATA on the way in (also ensures it is not altered on the way out)
etree.set_default_parser(etree.XMLParser(strip_cdata=False, encoding='utf-8'))

# Setup logging
LOG = logging.getLogger(__name__)

# Register the namespaces we'll use
etree.register_namespace('atom', c.ATOM_NS)
etree.register_namespace('xsi', c.XSI_NS)
etree.register_namespace('web', c.WEB_NS)
etree.register_namespace('uom', c.UOM_NS)


class Session(object):
    """Responsible for PowerVM API session management."""
    def __init__(self, host='localhost', username=None, password=None,
                 auditmemento=None, protocol=None, port=None, timeout=1200,
                 certpath='/etc/ssl/certs/', certext='.crt', conn_tries=1):
        """Persistent authenticated session with the REST API server.

        Two authentication modes are supported: password- and file-based.

        :param host: IP or resolvable hostname for the REST API server.
        :param username: User ID for authentication.  Optional for file-based
                         authentication.
        :param password: Authentication password.  If specified, password-based
                         authentication is used.  If omitted, file-based
                         authentication is used.
        :param auditmemento: Tag for log entry identification on the REST API
                             server.  If omitted, one will be generated.
        :param protocol: TCP protocol for communication with the REST API
                         server.  Must be either 'http' or 'https'.  If
                         unspecified, will default to 'http' for file-based
                         local authentication and 'https' otherwise.
        :param port: TCP port on which the REST API server communicates.  If
                     unspecified, will default based on the protocol parameter:
                     protocol='http' => port=12080;
                     protocol='https' => port=12443.
        :param timeout: See timeout param on requests.Session.request.  Default
                        is 20 minutes.
        :param certpath: Directory in which the certificate file can be found.
                         Certificate file path is constructed as
                         {certpath}{host}{certext}.  For example, given
                         host='localhost', certpath='/etc/ssl/certs/',
                         certext='.crt', the certificate file path will be
                         '/etc/ssl/certs/localhost.crt'.  This is ignored if
                         protocol is http.
        :param certext: Certificate file extension.
        :param conn_tries: Number of times to try connecting to the REST server
                           if a ConnectionError is received.  The default, one,
                           means we only try once.  We sleep for two seconds
                           (subject to change in future versions) between
                           retries.
        :return: A logged-on session suitable for passing to the Adapter
                 constructor.
        """
        # Key off lack of password to indicate file-based authentication.  In
        # this case, 'host' is often 'localhost' (or something that resolves to
        # it), but it's also possible consumers will be using e.g. SSH keys
        # allowing them to grab the file from a remote host.
        self.use_file_auth = password is None
        self.password = password
        if self.use_file_auth and not username:
            # Generate a unique username, used by the file auth mechanism
            username = 'pypowervm_%s' % uuid.uuid4()
        self.username = username

        if protocol is None:
            protocol = 'http' if self.use_file_auth else 'https'
        if protocol not in c.PORT_DEFAULT_BY_PROTO.keys():
            raise ValueError(_('Invalid protocol "%s"') % protocol)
        self.protocol = protocol

        self.host = host

        if host != 'localhost' and protocol == 'http':
            LOG.warning(_('Unencrypted communication with PowerVM! Revert '
                          'configuration to https.'))

        if port is None:
            port = c.PORT_DEFAULT_BY_PROTO[self.protocol]
        self.port = port

        if not auditmemento:
            # Assume 'default' unless we can calculate the proper default
            auditmemento = 'default'
            if os.name == 'posix':
                try:
                    auditmemento = pwd.getpwuid(os.getuid())[0]
                except Exception:
                    LOG.warning(_("Calculating default audit memento failed, "
                                  "using 'default'."))
        self.auditmemento = auditmemento

        # Support IPv6 addresses
        if self.host[0] != '[' and ':' in self.host:
            self.dest = '%s://[%s]:%i' % (self.protocol, self.host, self.port)
        else:
            self.dest = '%s://%s:%i' % (self.protocol, self.host, self.port)

        self.timeout = timeout
        self.certpath = certpath
        self.certext = certext

        self._lock = threading.RLock()
        self._logged_in = False
        self._relogin_unsafe = False
        self._eventlistener = None

        # Will be set by _logon()
        self._sessToken = None
        self.mc_type = None
        self.schema_version = None
        self.traits = None

        # Record which object initialized the session.  This is to protect
        # against clones created by deepcopy or other methods.
        self._init_by = id(self)

        # External session config
        cfg_module_path = os.environ.get('PYPOWERVM_SESSION_CONFIG', None)
        if cfg_module_path:
            import imp
            imp.load_source('sesscfg', cfg_module_path).session_config(self)

        self._logon(conn_tries=conn_tries)

        # HMC should never use file auth.  This should never happen - if it
        # does, it indicates that we got a bad Logon response, or processed it
        # incorrectly.
        if self.use_file_auth and self.mc_type == 'HMC':
            raise pvmex.Error(_("Local authentication not supported on HMC."))

        # Set the API traits after logon.
        self.traits = pvm_traits.APITraits(self)

    def __del__(self):
        # Refuse to clean up clones.
        if self._init_by != id(self):
            return

        try:
            # deleting the session will shutdown the event listener
            if self.has_event_listener:
                self._eventlistener.shutdown()
        finally:
            self._logoff()

    def get_event_listener(self):
        if not self.has_event_listener:
            LOG.info(_("Setting up event listener for %s"), self.host)
            self._eventlistener = _EventListener(self)
        return self._eventlistener

    @property
    def has_event_listener(self):
        return self._eventlistener is not None

    @staticmethod
    def _chunkreader(filehandle, chunksize):
        if hasattr(filehandle, 'read'):
            while True:
                d = filehandle.read(chunksize)
                if not d:
                    break
                yield d
        else:
            for d in filehandle:
                yield d

    def request(self, method, path, headers=None, body='', sensitive=False,
                verify=False, timeout=-1, auditmemento=None, relogin=True,
                login=False, filehandle=None, chunksize=65536):
        """Send an HTTP/HTTPS request to a PowerVM interface.

        :param filehandle: For downloads (with method == 'GET'), a writable
                           file-like (anything with a write() method) to which
                           the download content should be written.
                           For uploads (with method == 'PUT' or 'POST'), this
                           may be a readable file-like (anything with a read()
                           method) or an iterable from which the upload content
                           should be retrieved.
                           When None (the default), response text goes to the
                           body of the returned Response.
        :param chunksize: For downloads, the content is written to filehandle
                          in increments of (at most) chunksize bytes.
                          For uploads when filehandle is a file-like, the
                          content is sent through the request in increments of
                          (at most) chunksize bytes.
                          For uploads when filehandle is an iterable, this arg
                          is ignored - content chunks are sent through the
                          request in whatever size the iterable yields them.
                          For other request types, this arg is ignored.
        """
        # Don't use mutable default args
        if headers is None:
            headers = {}

        session = requests.Session()
        session.verify = verify

        url = self.dest + path

        # If timeout isn't specified, use session default
        if timeout == -1:
            timeout = self.timeout

        if auditmemento:
            headers['X-Audit-Memento'] = auditmemento
        else:
            headers['X-Audit-Memento'] = self.auditmemento

        isupload = False
        isdownload = False
        if filehandle:
            if method in ['PUT', 'POST']:
                isupload = True
            elif method in ['GET']:
                isdownload = True
            else:
                raise ValueError(_('Unexpected filehandle on %s request')
                                 % method)

        if isupload:
            LOG.trace('sending %s %s headers=%s body=<file contents>',
                      method, url, headers if not sensitive else "<sensitive>")
        else:
            LOG.trace('sending %s %s headers=%s body=%s', method, url,
                      headers if not sensitive else "<sensitive>",
                      body if not sensitive else "<sensitive>")

        # Add X-API-Session header after above so it's not printed in log
        sess_token_try = None
        if not login:
            with self._lock:
                assert self._sessToken, "missing session token"
                headers['X-API-Session'] = self._sessToken
                sess_token_try = self._sessToken

        try:
            if isupload:
                response = session.request(
                    method, url, data=self._chunkreader(filehandle, chunksize),
                    headers=headers, timeout=timeout)
            elif isdownload:
                response = session.request(method, url, stream=True,
                                           headers=headers, timeout=timeout)
            else:
                response = session.request(method, url, data=body,
                                           headers=headers, timeout=timeout)
        except rqex.SSLError as e:
            # TODO(IBM) Get better responses here...this isn't good.
            msg = '%s for %s %s: %s' % (e.__class__.__name__, method, url, e)
            LOG.warning(msg)
            raise pvmex.SSLError(msg)
        except rqex.ConnectionError as e:
            msg = '%s for %s %s: %s' % (e.__class__.__name__, method, url, e)
            LOG.warning(msg)
            raise pvmex.ConnectionError(msg)
        except rqex.Timeout as e:
            msg = '%s for %s %s: %s' % (e.__class__.__name__, method, url, e)
            LOG.warning(msg)
            raise pvmex.TimeoutError(msg)
        except Exception as e:
            LOG.exception(_('Unexpected error for %(meth)s %(url)s'),
                          {'meth': method, 'url': url})
            raise pvmex.Error(_('Unexpected error: %(class)s for %(method)s '
                                '%(url)s: %(excp)s') %
                              {'class': e.__class__.__name__, 'method': method,
                               'url': url, 'excp': str(e)})
        finally:
            session.close()

        # remove X-API-Session header so it won't get printed
        if not login:
            try:
                del headers['X-API-Session']
            except KeyError:
                # something modifying the submitted request headers??
                # TODO(IBM): why does this happen and what else may result?
                pass

        LOG.trace('result: %s (%s) for %s %s', response.status_code,
                  response.reason, method, url)
        LOG.trace('response headers: %s',
                  response.headers if not sensitive else "<sensitive>")

        if response.status_code in [c.HTTPStatus.OK_NO_CONTENT,
                                    c.HTTPStatus.NO_CHANGE]:
            return Response(method, path, response.status_code,
                            response.reason, response.headers,
                            reqheaders=headers, reqbody=body)
        else:
            LOG.trace('response body:\n%s',
                      response.text if not sensitive else "<sensitive>")

        # re-login processing
        if response.status_code == c.HTTPStatus.UNAUTHORIZED:
            LOG.debug('Processing HTTP Unauthorized')
            with self._lock:
                if not relogin:
                    LOG.debug('Requester specified no re-login')
                elif self._relogin_unsafe:
                    LOG.warning(_('Re-login has been deemed unsafe. This '
                                  'Session instance should no longer be '
                                  'used.'))
                else:
                    if self._sessToken != sess_token_try:
                        LOG.debug('Re-login done elsewhere for %s', self.host)
                    else:
                        self._logged_in = False
                        LOG.info(_('Attempting re-login %s'), self.host)
                        try:
                            self._logon()
                        except pvmex.Error as e:
                            if e.response:
                                if (e.response.status ==
                                        c.HTTPStatus.UNAUTHORIZED):
                                    # can't continue re-login attempts lest we
                                    # lock the account
                                    self._relogin_unsafe = True
                                    LOG.warning(
                                        _('Re-login 401, response body:\n%s'),
                                        e.response.body)
                                else:
                                    # safe to try re-login again in this case
                                    LOG.warning(
                                        _('Re-login failed, resp body:\n%s'),
                                        e.response.body)
                            else:
                                # safe to try re-login again in this case
                                LOG.warning(_('Re-login failed:\n%s'), e)
                            e.orig_response = Response(
                                method, path, response.status_code,
                                response.reason, response.headers,
                                reqheaders=headers, reqbody=body,
                                body=response.text)
                            raise

                    # Retry the original request
                    try:
                        return self.request(method, path, headers, body,
                                            sensitive=sensitive, verify=verify,
                                            timeout=timeout, relogin=False)
                    except pvmex.HttpUnauth as e:
                        # This is a special case... normally on a 401 we
                        # would retry login, but we won't here because
                        # we just did that... Handle it specially.
                        LOG.warning(
                            _('Re-attempt failed with another 401, response '
                              'body:\n%s'), e.response.body)
                        raise pvmex.Error(
                            _('suspicious HTTP 401 response for %(method)s '
                              '%(path)s: token is brand new') %
                            {'method': method, 'path': path})

        resp = None
        if not isdownload:
            resp = Response(method, path, response.status_code,
                            response.reason, response.headers,
                            reqheaders=headers, reqbody=body,
                            body=response.text)

        if 200 <= response.status_code < 300:
            if isdownload:
                for chunk in response.iter_content(chunksize):
                    filehandle.write(chunk)
                resp = Response(method, path, response.status_code,
                                response.reason, response.headers,
                                reqheaders=headers, reqbody=body)
            return resp
        else:
            if isdownload:
                errtext = ''
                for chunk in response.iter_content(chunksize):
                    errtext += chunk
                resp = Response(method, path, response.status_code,
                                response.reason, response.headers,
                                reqheaders=headers, reqbody=body,
                                body=errtext)
            raise self._get_httperror(resp)

    @staticmethod
    def _get_httperror(resp):
        """Return (don't raise) an HttpError subclass appropriate to resp."""
        status = resp.status
        if status == c.HTTPStatus.NOT_FOUND:
            return pvmex.HttpNotFound(resp)
        if status == c.HTTPStatus.UNAUTHORIZED:
            return pvmex.HttpUnauth(resp)
        # Default general HttpError
        return pvmex.HttpError(resp)

    def _logon(self, conn_tries=1):
        """Create an authentication token on the REST server for this Session.

        :param conn_tries: Number of times to try connecting to the REST server
                           if a ConnectionError is received.  The default, one,
                           means we only try once.  We sleep for two seconds
                           (subject to change in future versions) between
                           retries.
        """
        def delay_func(try_num, max_tries, *args, **kwargs):
            delay = 2
            LOG.warning(_("Failed to connect to REST server - is the pvm-rest "
                          "service started?  Retrying %(try_num)d of "
                          "%(max_tries)d after %(delay)d seconds."),
                        dict(try_num=try_num, max_tries=max_tries - 1,
                             delay=delay, args=args, kwargs=kwargs))
            time.sleep(delay)

        LOG.info(_("Session logging on %s"), self.host)
        headers = {
            'Accept': c.TYPE_TEMPLATE % ('web', 'LogonResponse'),
            'Content-Type': c.TYPE_TEMPLATE % ('web', 'LogonRequest')
        }
        if self.use_file_auth:
            body = c.LOGONREQUEST_TEMPLATE_FILE % {'userid': self.username}
        else:
            passwd = sax_utils.escape(self.password)
            body = c.LOGONREQUEST_TEMPLATE_PASS % {'userid': self.username,
                                                   'passwd': passwd}

        # Convert it to a string-type from unicode-type encoded with UTF-8
        # Without the socket code will implicitly convert the type with ASCII
        body = body.encode('utf-8')

        if self.protocol == 'http' or not self.certpath:
            # certificate validation is disabled
            verify = False
        elif util.validate_certificate(self.host, self.port, self.certpath,
                                       self.certext):
            # Attempt to validate based on certificates stored in self.certpath
            verify = False
        else:
            # Have the requests module validate the certificate
            verify = True
        try:
            # relogin=False to prevent multiple attempts with same credentials
            resp = retry.retry(
                tries=conn_tries, delay_func=delay_func, http_codes=[404],
                retry_except=pvmex.ConnectionError)(self.request)(
                    'PUT', c.LOGON_PATH, headers=headers, body=body,
                    sensitive=True, verify=verify, relogin=False, login=True)
        except pvmex.Error as e:
            if e.response:
                # strip out sensitive data
                e.response.reqbody = "<sensitive>"
            raise

        # parse out X-API-Session value
        root = etree.fromstring(resp.body.encode('utf-8'))

        with self._lock:
            tok = (self._get_auth_tok_from_file(root, resp)
                   if self.use_file_auth
                   else self._get_auth_tok(root, resp))
            self._sessToken = tok
            self._logged_in = True
            self.mc_type = resp.headers.get('X-MC-Type', 'HMC')
            self.schema_version = root.get('schemaVersion')
            self.traits = pvm_traits.APITraits(self)

    @staticmethod
    def _get_auth_tok(root, resp):
        """Extract session token from password-based Logon response.

        :param root: etree.fromstring-parsed root of the LogonResponse.
        :param resp: The entire response payload from the LogonRequest.
        :return: X-API-Session token for use with subsequent requests.
        """
        tok = root.findtext('{%s}X-API-Session' % c.WEB_NS)
        if not tok:
            resp.reqbody = "<sensitive>"
            msg = _("Failed to parse a session token from the PowerVM "
                    "response.")
            LOG.error(msg + (_(' Body= %s'), resp.body))
            raise pvmex.Error(msg, response=resp)
        return tok

    @staticmethod
    def _get_auth_tok_from_file(root, resp):
        """Extract session token from file-based Logon response.

        :param root: etree.fromstring-parsed root of the LogonResponse.
        :param resp: The entire response payload from the LogonRequest.
        :return: X-API-Session token for use with subsequent requests.
        """
        tokfile_path = root.findtext('{%s}X-API-SessionFile' % c.WEB_NS)
        if not tokfile_path:
            msg = _("Failed to parse a session file path from the PowerVM "
                    "response.")
            LOG.error(msg + (_(' Body= %s'), resp.body))
            raise pvmex.Error(msg, response=resp)
        try:
            with open(tokfile_path, 'r') as tokfile:
                tok = tokfile.read().strip(' \n')
        except IOError as ioe:
            if ioe.errno == errno.EACCES:
                raise pvmex.AuthFileReadError(access_file=str(tokfile_path))
            else:
                raise pvmex.AuthFileAccessError(access_file=str(tokfile_path),
                                                error=os.strerror(ioe.errno))
        if not tok:
            msg = _("Token file %s didn't contain a readable session "
                    "token.") % tokfile_path
            LOG.error(msg)
            raise pvmex.Error(msg, response=resp)
        return tok

    def _logoff(self):
        with self._lock:
            if not self._logged_in:
                return
            LOG.info(_("Session logging off %s"), self.host)
            try:
                # relogin=False to prevent multiple attempts
                self.request('DELETE', c.LOGON_PATH, relogin=False)
            except Exception:
                LOG.exception(_('Problem logging off.  Ignoring.'))

            self._logged_in = False
            # this should only ever be called when Session has gone out of
            # scope, but just in case someone calls it directly while requests
            # are in flight, set _relogin_unsafe so that those requests won't
            # enter relogin processing when they get an HTTP 401.
            self._relogin_unsafe = True


class Adapter(object):
    """REST API Adapter for PowerVM remote management."""
    def __init__(self, session=None, use_cache=False, helpers=None):
        """Create a new Adapter instance, connected to a Session.

        :param session: (Optional) A Session instance.  If not specified, a
                        new, local, file-authentication-based Session will be
                        created and used.
        :param use_cache: Do not use.  Caching not supported.
        :param helpers: A list of decorator methods in which to wrap the HTTP
                        request call.  See the pypowervm.helpers package for
                        examples.
        """
        if use_cache:
            raise pvmex.CacheNotSupportedException()

        self.session = session if session else Session()
        self._helpers = self._standardize_helper_list(helpers)

    @staticmethod
    def _standardize_helper_list(helpers):
        if isinstance(helpers, list) or helpers is None:
            return helpers
        else:
            return [helpers]

    @property
    def helpers(self):
        """Returns a copy of the list of helpers for the adapter."""
        return list(self._helpers) if self._helpers else []

    @property
    def traits(self):
        return self.session.traits

    def _request(self, method, path, helpers=None, **kwds):
        """Common request method.

        All Adapter requests will be funnelled through here.  This makes a
        convenient place to attach the Adapter helpers.
        """
        helpers = self._standardize_helper_list(helpers)
        if helpers is None:
            helpers = self._helpers

        # Build the stack of helper functions to call.
        # The base will always be the session.request method
        func = self.session.request

        # Stack the helpers by reversing the order list
        if helpers is not None:
            for helper in helpers[::-1]:
                func = helper(func)

        # Now just call the function
        resp = func(method, path, **kwds)

        # Assuming the response is a Response, attach this adapter to it.
        if isinstance(resp, Response):
            resp.adapter = self
        return resp

    def create(self, element, root_type, root_id=None, child_type=None,
               child_id=None, suffix_type=None, suffix_parm=None, detail=None,
               service='uom', content_service=None, timeout=-1,
               auditmemento=None, sensitive=False, helpers=None):
        """Create a new resource.

        Will build the URI path using the provided arguments.
        """
        self._validate('create', root_type, root_id, child_type, child_id,
                       suffix_type, suffix_parm, detail)
        path = self.build_path(service, root_type, root_id, child_type,
                               child_id, suffix_type, suffix_parm, detail,
                               xag=[])
        return self.create_by_path(
            element, path, content_service=content_service, timeout=timeout,
            auditmemento=auditmemento, sensitive=sensitive, helpers=helpers)

    def create_job(self, job, root_type, root_id=None, child_type=None,
                   child_id=None, timeout=-1, auditmemento=None,
                   sensitive=False, helpers=None):
        if not job.tag == 'JobRequest':
            raise ValueError(_('job must be a JobRequest element'))

        op = job.findtext('RequestedOperation/OperationName')
        if not op:
            raise ValueError(_('JobRequest is missing OperationName'))

        return self.create(job, root_type, root_id, child_type, child_id,
                           suffix_type='do', suffix_parm=op,
                           content_service='web', timeout=timeout,
                           auditmemento=auditmemento, sensitive=sensitive,
                           helpers=helpers)

    def create_by_path(self, element, path, content_service=None, timeout=-1,
                       auditmemento=None, sensitive=False, helpers=None):
        """Create a new resource where the URI path is already known."""
        path = util.dice_href(path)
        m = re.search(r'%s(\w+)/(\w+)' % c.API_BASE_PATH, path)
        if not m:
            raise ValueError(_('path=%s is not a PowerVM API reference') %
                             path)
        if not content_service:
            content_service = m.group(1)

        headers = {'Accept': 'application/atom+xml; charset=UTF-8'}
        if re.search('/do/', path):
            headers['Content-Type'] = c.TYPE_TEMPLATE % (content_service,
                                                         'JobRequest')
        else:
            # strip off details, if present
            p = urlparse.urlparse(path).path
            headers['Content-Type'] = c.TYPE_TEMPLATE % (
                content_service, p.rsplit('/', 1)[1])

        resp = self._request('PUT', path, helpers=helpers, headers=headers,
                             body=element.toxmlstring(), timeout=timeout,
                             auditmemento=auditmemento, sensitive=sensitive)
        resp._unmarshal_atom()
        return resp

    def read(self, root_type, root_id=None, child_type=None, child_id=None,
             suffix_type=None, suffix_parm=None, detail=None, service='uom',
             etag=None, timeout=-1, auditmemento=None, age=-1, xag=None,
             sensitive=False, helpers=None, add_qp=None):
        """Retrieve an existing resource.

        Will build the URI path using the provided arguments.

        :param root_type: String ROOT REST element type.
        :param root_id: String ROOT REST element UUID.  If unspecified, the
                        feed of root_type is fetched.  Required if child_type
                        is specified.
        :param child_type: String CHILD REST element type.
        :param child_id: String CHILD REST element UUID.  If unspecified, the
                         feed of child_type is fetched.
        :param suffix_type: Suffix type added to the path (with '/').  For
                            special URIs, like Job requests (e.g. 'do' in
                            .../do/Something).
        :param suffix_parm: Suffix parameter added to the path (with '/'). For
                            special URIs, like Job requests (e.g. 'Something'
                            in .../do/Something).
        :param detail: Requested detail level of the response.  Obsolete.
        :param service: REST service type, one of pypowervm.const.SERVICE_BY_NS
        :param etag: Not used (caching disabled).
        :param timeout: Timeout in seconds for the HTTP request.
        :param auditmemento: X-Audit-Memento header registered in the REST
                             server logs for debug purposes, allowing this
                             request to be identified therein.
        :param age: Not used (caching disabled).
        :param xag: List of extended attribute group enum values.  If
                    unspecified or None, 'None' will be appended.  If the empty
                    list (xag=[]), no extended attribute query parameter will
                    be added, resulting in the server's default extended
                    attribute group behavior.
        :param sensitive: If True, headers and payloads will be hidden in log
                          entries.
        :param helpers: A list of decorator methods in which to wrap the HTTP
                        request call.  See the pypowervm.helpers package for
                        examples.
        :param add_qp: Optional list of (key, value) tuples to add to the query
                       string of the request.
        :return: Response object representing the result of the query.
        """
        self._validate('read', root_type, root_id, child_type, child_id,
                       suffix_type, suffix_parm, detail)
        path = self.build_path(service, root_type, root_id, child_type,
                               child_id, suffix_type, suffix_parm, detail,
                               xag=xag, add_qp=add_qp)
        return self.read_by_path(path, etag, timeout=timeout,
                                 auditmemento=auditmemento, age=age,
                                 sensitive=sensitive, helpers=helpers)

    def read_job(self, job_id, etag=None, timeout=-1, auditmemento=None,
                 sensitive=False, helpers=None):
        return self.read('jobs', job_id, etag=etag, timeout=timeout,
                         auditmemento=auditmemento, sensitive=sensitive,
                         helpers=helpers)

    def read_jobs(self, root_type=None, root_id=None, child_type=None,
                  child_id=None, detail=None, etag=None, timeout=-1,
                  auditmemento=None, sensitive=False, helpers=None):
        return self.read(root_type, root_id, child_type, child_id,
                         suffix_type='jobs', detail=detail, etag=etag,
                         timeout=timeout, auditmemento=auditmemento,
                         sensitive=sensitive, helpers=helpers)

    def read_by_href(self, href, suffix_type=None, suffix_parm=None,
                     detail=None, etag=None, timeout=-1, auditmemento=None,
                     age=-1, sensitive=False, helpers=None, xag=None):
        """Retrieve an existing resource based on a link's href."""
        o = urlparse.urlparse(href)
        hostname_mismatch = (o.hostname.lower() != self.session.host.lower())
        if hostname_mismatch or o.port != self.session.port:
            LOG.debug('href=%s will be modified to use %s:%s',
                      href, self.session.host, self.session.port)
        path = self.extend_path(util.dice_href(href), suffix_type, suffix_parm,
                                detail, xag=xag)
        return self.read_by_path(path, etag=etag, timeout=timeout,
                                 auditmemento=auditmemento, age=age,
                                 sensitive=sensitive, helpers=helpers)

    def read_by_path(self, path, etag=None, timeout=-1, auditmemento=None,
                     age=-1, sensitive=False, helpers=None):
        """Retrieve an existing resource where URI path is already known."""

        path = util.dice_href(path)
        resp = self._read_by_path(path, etag, timeout, auditmemento,
                                  sensitive, helpers=helpers)
        if 'atom' in resp.reqheaders['Accept']:
            resp._unmarshal_atom()

        return resp

    def _read_by_path(self, path, etag, timeout, auditmemento, sensitive,
                      helpers=None):
        m = re.search(r'%s(\w+)/(\w+)' % c.API_BASE_PATH, path)
        if not m:
            raise ValueError(_('path=%s not a PowerVM API reference') % path)
        headers = {}
        json_search_str = (c.UUID_REGEX + '/quick$' + '|/quick/' + r'|\.json$')
        if re.search(json_search_str, util.dice_href(path, include_query=False,
                                                     include_fragment=False)):
            # Successful request will return application/json; errors (like 400
            # or 404) will return application/atom+xml.
            headers['Accept'] = '*/*'
        else:
            headers['Accept'] = 'application/atom+xml'
        if etag:
            headers['If-None-Match'] = etag
        resp = self._request('GET', path, helpers=helpers, headers=headers,
                             timeout=timeout, auditmemento=auditmemento,
                             sensitive=sensitive)
        return resp

    def update(self, data, etag, root_type, root_id=None, child_type=None,
               child_id=None, suffix_type=None, service='uom', timeout=-1,
               auditmemento=None, xag=None, sensitive=False, helpers=None):
        """Update an existing resource.

        Will build the URI path using the provided arguments.
        """
        self._validate('update', root_type, root_id, child_type, child_id,
                       suffix_type)
        path = self.build_path(service, root_type, root_id, child_type,
                               child_id, suffix_type, xag=xag)
        return self.update_by_path(data, etag, path, timeout=timeout,
                                   auditmemento=auditmemento,
                                   sensitive=sensitive, helpers=helpers)

    def update_by_path(self, data, etag, path, timeout=-1, auditmemento=None,
                       sensitive=False, helpers=None):
        """Update an existing resource where the URI path is already known."""
        path = util.dice_href(path)
        m = re.match(r'%s(\w+)/(\w+)' % c.API_BASE_PATH, path)
        if not m:
            raise ValueError(_('path=%s is not a PowerVM API reference') %
                             path)
        headers = {'Accept': 'application/atom+xml; charset=UTF-8'}
        if m.group(1) == 'pcm':
            headers['Content-Type'] = 'application/xml'
        else:
            t = path.rsplit('/', 2)[1]
            headers['Content-Type'] = c.TYPE_TEMPLATE % (m.group(1), t)
        if etag:
            headers['If-Match'] = etag
        if hasattr(data, 'toxmlstring'):
            body = data.toxmlstring()
        else:
            body = data
        resp = self._request(
            'POST', path, helpers=helpers, headers=headers, body=body,
            timeout=timeout, auditmemento=auditmemento, sensitive=sensitive)

        resp._unmarshal_atom()
        return resp

    def delete(self, root_type, root_id=None, child_type=None, child_id=None,
               suffix_type=None, suffix_parm=None, service='uom', etag=None,
               timeout=-1, auditmemento=None, helpers=None):
        """Delete an existing resource.

        Will build the URI path using the provided arguments.
        """
        self._validate('delete', root_type, root_id, child_type, child_id,
                       suffix_type, suffix_parm)
        path = self.build_path(service, root_type, root_id, child_type,
                               child_id, suffix_type, suffix_parm)
        return self.delete_by_path(path, etag, timeout=timeout,
                                   auditmemento=auditmemento, helpers=helpers)

    def delete_by_href(self, href, etag=None, timeout=-1, auditmemento=None,
                       helpers=None):
        """Delete an existing resource based on a link's href."""
        o = urlparse.urlparse(href)
        hostname_mismatch = (o.hostname.lower() != self.session.host.lower())
        if hostname_mismatch or o.port != self.session.port:
            LOG.debug('href=%s will be modified to use %s:%s', href,
                      self.session.host, self.session.port)
        return self.delete_by_path(o.path, etag=etag, timeout=timeout,
                                   auditmemento=auditmemento, helpers=helpers)

    def delete_by_path(self, path, etag=None, timeout=-1, auditmemento=None,
                       helpers=None):
        """Delete an existing resource where the URI path is already known."""
        path = util.dice_href(path, include_query=False,
                              include_fragment=False)
        m = re.search(r'%s(\w+)/(\w+)' % c.API_BASE_PATH, path)
        if not m:
            raise ValueError(_('path=%s is not a PowerVM API reference') %
                             path)
        headers = {}
        if etag:
            headers['If-Match'] = etag
        return self._request('DELETE', path, helpers=helpers, headers=headers,
                             timeout=timeout, auditmemento=auditmemento)

    def upload_file(self, filedescr, filehandle, chunksize=65536,
                    timeout=-1, auditmemento=None, replacing=False,
                    helpers=None):
        try:
            fileid = filedescr.findtext('FileUUID')
            mediatype = filedescr.findtext('InternetMediaType')
        except Exception:
            raise ValueError(_('Invalid file descriptor'))

        path = c.API_BASE_PATH + 'web/File/contents/' + fileid
        headers = {'Accept': 'application/vnd.ibm.powervm.web+xml',
                   'Content-Type': mediatype}

        return self._request('POST' if replacing else 'PUT',
                             path, helpers=helpers, headers=headers,
                             timeout=timeout, auditmemento=auditmemento,
                             filehandle=filehandle, chunksize=chunksize)

    def download_file(self, filedescr, filehandle, chunksize=65536,
                      timeout=-1, auditmemento=None, helpers=None):
        try:
            fileid = filedescr.findtext('FileUUID')
            mediatype = filedescr.findtext('InternetMediaType')
        except Exception:
            raise ValueError(_('Invalid file descriptor'))

        path = c.API_BASE_PATH + 'web/File/contents/' + fileid
        headers = {'Accept': mediatype}

        return self._request('GET', path, helpers=helpers, headers=headers,
                             timeout=timeout, auditmemento=auditmemento,
                             filehandle=filehandle, chunksize=chunksize)

    def build_href(
            self, root_type, root_id=None, child_type=None, child_id=None,
            suffix_type=None, suffix_parm=None, detail=None, xag=None,
            service='uom'):
        p = self.build_path(
            service, root_type, root_id, child_type, child_id, suffix_type,
            suffix_parm, detail, xag=xag)
        return self.session.dest + p

    @classmethod
    def build_path(cls, service, root_type, root_id=None, child_type=None,
                   child_id=None, suffix_type=None, suffix_parm=None,
                   detail=None, xag=None, add_qp=None):
        path = c.API_BASE_PATH + service + '/' + root_type
        if root_id:
            path += '/' + root_id
            if child_type:
                path += '/' + child_type
                if child_id:
                    path += '/' + child_id
        return cls.extend_path(path, suffix_type=suffix_type,
                               suffix_parm=suffix_parm, detail=detail,
                               xag=xag, add_qp=add_qp)

    @staticmethod
    def extend_path(basepath, suffix_type=None, suffix_parm=None, detail=None,
                    xag=None, add_qp=None):
        """Extend a base path with zero or more of suffix, detail, and xag.

        :param basepath: The path string to be extended.
        :param suffix_type: Suffix key (string) to be appended.
        :param suffix_parm: Suffix parameter value to be appended.  Ignored if
                            suffix_type is not specified.
        :param detail: Value for the 'detail' query parameter.
        :param xag: List of extended attribute group enum values.  If
                    unspecified or None, 'None' will be appended.  If the empty
                    list (xag=[]), no extended attribute query parameter will
                    be added, resulting in the server's default extended
                    attribute group behavior.
        :param add_qp: Optional list of (key, value) tuples to add to the query
                       string of the request.
        :return: String base path (without protocol://server:port part).
        """
        path = basepath
        if suffix_type:
            # operations, do, jobs, cancel, quick, search, ${search-string}
            path = util.extend_basepath(path, '/' + suffix_type)
            if suffix_parm:
                path = util.extend_basepath(path, '/' + suffix_parm)
        if detail:
            path += ('&' if '?' in path else '?') + 'detail=' + detail

        # Explicit xag is always honored as-is.  If unspecified, we usually
        # want to include group=None.  However, there are certain classes of
        # URI from which we want to omit ?group entirely.
        if xag is None:
            xagless_suffixes = ('quick', 'do')
            if suffix_type in xagless_suffixes:
                xag = []
        path = util.check_and_apply_xag(path, xag)

        if add_qp:
            parsed = urlparse.urlsplit(path)
            qparms = urlparse.parse_qsl(parsed.query) if parsed.query else []
            qparms.extend(add_qp)
            qstr = urllib.urlencode(qparms)
            path = urlparse.urlunsplit((parsed.scheme, parsed.netloc,
                                        parsed.path, qstr, parsed.fragment))

        return path

    @staticmethod
    def _validate(req_method, root_type, root_id=None, child_type=None,
                  child_id=None, suffix_type=None, suffix_parm=None,
                  detail=None):
        # 'detail' param currently unused
        if child_type and not root_id:
            raise ValueError(_('Expected root_id'))
        if child_id and not child_type:
            raise ValueError(_('Expected child_type'))
        if req_method == 'create':
            if suffix_type:
                if suffix_type != 'do':
                    raise ValueError(_('Unexpected suffix_type=%s') %
                                     suffix_type)
                if not suffix_parm:
                    raise ValueError(_('Expected suffix_parm'))
                if child_type and not child_id:
                    raise ValueError(_('Expected child_id'))
            else:
                if child_id:
                    raise ValueError(_('Unexpected child_id'))
                if root_id and not child_type:
                    raise ValueError(_('Unexpected root_id'))
        elif req_method == 'read':
            # no read-specific validation at this time
            pass
        elif req_method == 'update':
            if 'preferences' in [root_type, child_type]:
                if child_id:
                    raise ValueError(_('Unexpected child_id'))
                if root_id and not child_type:
                    raise ValueError(_('Unexpected root_id'))
            else:
                if not root_id:
                    raise ValueError(_('Expected root_id'))
                if child_type and not child_id:
                    raise ValueError(_('Expected child_id'))
                if suffix_type is not None and suffix_type != 'cancel':
                    raise ValueError(_('Unexpected suffix_type=%s') %
                                     suffix_type)
        elif req_method == 'delete':
            if suffix_type:
                if suffix_type != 'jobs':
                    raise ValueError(_('Unexpected suffix_type=%s') %
                                     suffix_type)
                if not suffix_parm:
                    raise ValueError(_('Expected suffix_parm'))
            else:
                if not root_id:
                    raise ValueError(_('Expected root_id'))
                if child_type and not child_id:
                    raise ValueError(_('Expected child_id'))
        else:
            raise ValueError(_('Unexpected req_method=%s') % req_method)


class Response(object):
    """Response to PowerVM API Adapter method invocation."""

    def __init__(self, reqmethod, reqpath, status, reason, headers,
                 reqheaders=None, reqbody='', body='', orig_reqpath=''):
        """Represents an HTTP request/response from Adapter.request().

        :param reqmethod: The HTTP method of the request (e.g. 'GET', 'PUT')
        :param reqpath: The path (not URI) of the request.  Construct the URI
                        by prepending Response.adapter.session.dest.
        :param status: Integer HTTP status code (e.g. 200)
        :param reason: String HTTP Reason code (e.g. 'No Content')
        :param headers: Dict of headers from the HTTP response.
        :param reqheaders: Dict of headers from the HTTP request.
        :param reqbody: String payload of the HTTP request.
        :param body: String payload of the HTTP response.
        :param orig_reqpath: Not used.
        """
        self.reqmethod = reqmethod
        self.reqpath = reqpath
        self.reqheaders = reqheaders if reqheaders else {}
        self.reqbody = reqbody
        self.status = status
        self.reason = reason
        self.headers = headers
        self.body = body
        self.feed = None
        self.entry = None
        # Set by _request()
        self.adapter = None

    def __deepcopy__(self, memo=None):
        """Produce a deep (except for adapter) copy of this Response."""
        ret = self.__class__(
            self.reqmethod, self.reqpath, self.status, self.reason,
            copy.deepcopy(self.headers, memo=memo),
            reqheaders=copy.deepcopy(self.reqheaders, memo=memo),
            reqbody=self.reqbody, body=self.body)
        if self.feed is not None:
            ret.feed = copy.deepcopy(self.feed, memo=memo)
        if self.entry is not None:
            ret.entry = copy.deepcopy(self.entry, memo=memo)
        # Adapter is the one thing not deep-copied
        ret.adapter = self.adapter
        return ret

    @property
    def etag(self):
        return self.headers.get('etag', None)

    @property
    def atom(self):
        return self.feed if self.feed else self.entry

    def _extract_atom(self):
        """Unmarshal my body and set my feed or entry accordingly.

        :return: A message indicating the reason for the error, or None if no
                 error occurred.
        """
        err_reason = None
        root = None
        try:
            root = etree.fromstring(self.body)
        except Exception as e:
            err_reason = (_('Error parsing XML response from PowerVM: '
                            '%s') % str(e))
        if root is not None and root.tag == str(
                etree.QName(c.ATOM_NS, 'feed')):
            self.feed = ent.Feed.unmarshal_atom_feed(root, self)
        elif root is not None and root.tag == str(
                etree.QName(c.ATOM_NS, 'entry')):
            self.entry = ent.Entry.unmarshal_atom_entry(root, self)
        elif root is not None and '/Debug/' in self.reqpath:
            # Special case for Debug URIs - caller is expected to make use
            # of self.body only, and understand how it's formatted.
            pass
        elif err_reason is None:
            err_reason = _('Response is not an Atom feed/entry')

        return err_reason

    def _unmarshal_atom(self):
        err_reason = None
        if self.body:
            err_reason = self._extract_atom()
        elif self.reqmethod == 'GET':
            if self.status == c.HTTPStatus.OK_NO_CONTENT:
                if util.is_instance_path(self.reqpath):
                    err_reason = _('Unexpected HTTP 204 for request')
                else:
                    # PowerVM returns HTTP 204 (No Content) when you
                    # ask for a feed that has no entries.
                    self.feed = ent.Feed({}, [])
            elif self.status == c.HTTPStatus.NO_CHANGE:
                pass
            else:
                err_reason = _('Unexpectedly empty response body')

        if err_reason is not None:
            LOG.error(_('%(err_reason)s:\n'
                        'request headers: %(reqheaders)s\n\n'
                        'request body: %(reqbody)s\n\n'
                        'response headers: %(respheaders)s\n\n'
                        'response body: %(respbody)s'),
                      {'err_reason': err_reason,
                       'reqheaders': self.reqheaders, 'reqbody': self.reqbody,
                       'respheaders': self.headers, 'respbody': self.body})
            raise pvmex.AtomError(_('Atom error for %(method)s %(path)s: '
                                    '%(reason)s') %
                                  {'method': self.reqmethod,
                                   'path': self.reqpath, 'reason': err_reason},
                                  self)


@six.add_metaclass(abc.ABCMeta)
class EventListener(object):

    @abc.abstractmethod
    def subscribe(self, handler):
        """Subscribe an EvenHandler to receive events.

        :param handler: EventHandler
        """

    @abc.abstractmethod
    def unsubscribe(self, handler):
        """Unubscribe an EvenHandler from receiving events.

        :param handler: EventHandler
        """

    @abc.abstractmethod
    def shutdown(self):
        """Shutdown this EventListener."""


class _EventListener(EventListener):
    def __init__(self, session, timeout=-1):
        """The event listener associated with a Session.

        This class should not be instantiated directly.  Instead construct
        a Session and use get_event_listener() to create it.

        :param session: The Session this listener is to use.
        :param timeout: How long to wait for any events to be returned.
                        -1 = wait indefinitely.
        """
        if session is None:
            raise ValueError(_('Session must not be None'))
        if session.has_event_listener:
            raise ValueError(_('An event listener is already active on the '
                               'session.'))
        self.appid = hashlib.md5(session._sessToken).hexdigest()
        self.timeout = timeout if timeout != -1 else session.timeout
        self._lock = threading.RLock()
        self.handlers = []
        self._pthread = None
        self.host = session.host
        self.adp = None
        self._prime(session)

    def _prime(self, session):
        try:
            # Establish a weak reference proxy to the session.  This is needed
            # because we don't want a circular reference to the session.
            self.adp = Adapter(weakref.proxy(session))
            # initialize
            events, raw_events, evtwraps = self._get_events()
        except pvmex.Error as e:
            raise pvmex.Error(_('Failed to initialize event feed listener: '
                                '%s') % e)
        if not events.get('general') == 'init':
            # Something else is sharing this feed!
            raise ValueError(_('Application id "%s" not unique') % self.appid)
        # No errors initializing, so dispatch what we recieved.
        self._dispatch_events(events, raw_events, evtwraps)

    def subscribe(self, handler):
        if not isinstance(handler, _EventHandler):
            raise ValueError('Handler must be an EventHandler')
        if self.adp is None:
            raise Exception(_('Shutting down'))
        with self._lock:
            if handler in self.handlers:
                raise ValueError(_('This handler is already subscribed'))
            self.handlers.append(handler)
            if not self._pthread:
                self._pthread = _EventPollThread(self)
                self._pthread.start()

    def unsubscribe(self, handler):
        if not isinstance(handler, _EventHandler):
            raise ValueError(_('Handler must be an EventHandler'))
        with self._lock:
            if handler not in self.handlers:
                raise ValueError(_('Handler not found in subscriber list'))
            self.handlers.remove(handler)
            if not self.handlers:
                self._pthread.stop()
                self._pthread = None

    def shutdown(self):
        LOG.info(_('Shutting down EventListener for %s'), self.host)
        with self._lock:
            for handler in self.handlers:
                self.unsubscribe(handler)
        LOG.info(_('EventListener shutdown complete for %s'), self.host)

    def getevents(self):
        all_events = self._get_events()
        # Legacy method returned just the events.
        return all_events[0]

    def _get_events(self):
        """Gets the events and formats them into 'events' and 'raw_events'."""
        events = {}
        raw_events = []
        event_wraps = []
        resp = None

        # Read event feed
        try:
            resp = self.adp.read('Event?QUEUE_CLIENTKEY_METHOD='
                                 'USE_APPLICATIONID&QUEUE_APPLICATIONID=%s'
                                 % self.appid, timeout=self.timeout)
        except Exception as e:
            LOG.warning(_('Error while getting PowerVM events: %s.  (Is the '
                          'pvm-rest service down?)'), e)
            # Don't die.  The handler will retry.  But sleep so we don't thrash
            time.sleep(5)

        if resp:
            # Parse event feed
            for entry in resp.feed.entries:
                self._format_events(entry, events, raw_events)
            # Do this here to avoid circular imports
            import pypowervm.wrappers.event as event_wrap
            event_wraps = event_wrap.Event.wrap(resp)

        return events, raw_events, event_wraps

    def _format_events(self, entry, events, raw_events):
        """Formats an event Entry into events and raw events.

        This method operates on the events and raw_events lists themselves.
        It does not pass back the results.

        :param entry: The event entry to format for the list of events.
        :param events: A dictionary of events to add, remove, or update.
        :param raw_events: A dictionary of raw events to add to.
        """
        etype = entry.element.findtext('EventType')
        href = entry.element.findtext('EventData')
        if etype == 'NEW_CLIENT':
            events['general'] = 'init'
        elif etype in ['CACHE_CLEARED', 'MISSING_EVENTS']:
            # Clears all prior events
            keys = [k for k in events]
            for k in keys:
                del events[k]
            events['general'] = 'invalidate'
        elif etype == 'ADD_URI':
            events[href] = 'add'
        elif etype == 'DELETE_URI':
            events[href] = 'delete'
        elif etype in ['MODIFY_URI', 'INVALID_URI', 'HIDDEN_URI']:
            if href not in events:
                events[href] = 'invalidate'
        elif etype not in ['VISIBLE_URI', 'CUSTOM_CLIENT_EVENT']:
            LOG.error(_('Unexpected EventType=%s'), etype)

        # Now format the event for the raw handlers
        eid = entry.element.findtext('EventID')
        edetail = entry.element.findtext('EventDetail')
        raw_events.append({'EventType': etype, 'EventData': href,
                           'EventID': eid, 'EventDetail': edetail})

    def _dispatch_events(self, events, raw_events, wrap_events):
        """Invoke appropriate EventHandler 'process' callback.

        :param events: Events dict of the format {<uri>: <action>} - see
                       docstring for EventHandler.process.
        :param raw_events: List of event dicts of the format
                           {'EventType': <type>, 'EventData': <uri>,
                            'EventID': <id>, 'EventDetail': <detail>}
        :param wrap_events: List of pypowervm.wrappers.event.Event wrappers.
        """
        def call_handler(handler):
            try:
                if isinstance(handler, WrapperEventHandler):
                    handler.process(wrap_events)
                elif isinstance(handler, RawEventHandler):
                    handler.process(raw_events)
                else:
                    handler.process(events)
            except Exception:
                LOG.exception(_('Error while processing PowerVM events'))

        # Notify subscribers
        with self._lock:
            for hndlr in self.handlers:
                call_handler(hndlr)


@six.add_metaclass(abc.ABCMeta)
class _EventHandler(object):
    """Common class for all Event handlers.

    Event handlers are called to process events from the EventListener.
    """

    @abc.abstractmethod
    def process(self, events):
        """Process the event that comes back from the API.

        :param events: Events from the API.
        """
        pass


@six.add_metaclass(abc.ABCMeta)
class EventHandler(_EventHandler):
    """Used to handle events from the API.

    The session can poll for events back from the API.  An event will give a
    small indication of something that has occurred within the system.
    An example may be a ClientNetworkAdapter being created against an LPAR.

    Implement this class and add it to the Session's event listener to process
    events back from the API.
    """
    @abc.abstractmethod
    def process(self, events):
        """Process the event that comes back from the API.

        :param events: A dictionary of events that has come back from the
                       system.

                       Format:
                         - Key -> URI of event
                         - Value -> Action of event.  May be one of the
                                    following: add, delete or invalidate

                       A special key of 'general' may exist.  The value for
                       this is init or invalidate.  init indicates that the
                       whole system is being initialized.  An invalidate
                       indicates that the API event system has been refreshed
                       and the user should do a clean get of the data it needs.
        """
        pass


@six.add_metaclass(abc.ABCMeta)
class RawEventHandler(_EventHandler):
    """Used to handle raw events from the API.

    With this handler, no processing is done on the events. The events
    will be passed as a sequence of dicts.

    Implement this class and add it to the Session's event listener to process
    events back from the API.
    """
    @abc.abstractmethod
    def process(self, events):
        """Process the event that comes back from the API.

        :param events: A sequence of event dicts that has come back from the
                       system.

                       Format:
                       [
                            {
                               'EventType': <type>,
                               'EventID': <id>,
                               'EventData': <data>,
                               'EventDetail': <detail>
                            },
                       ]
        """
        pass


@six.add_metaclass(abc.ABCMeta)
class WrapperEventHandler(_EventHandler):
    """Used to handle wrapped events from the API.

    With this handler, no processing is done on the events. The events
    will be passed as a list of pypowervm.wrappers.event.Event.

    Implement this class and add it to the Session's event listener to process
    events back from the API.
    """
    @abc.abstractmethod
    def process(self, events):
        """Process the event that comes back from the API.

        :param events: A list of pypowervm.wrappers.event.Event that has come
                       back from the system.  See that wrapper class for
                       details.
        """
        pass


class _EventPollThread(threading.Thread):
    def __init__(self, eventlistener):
        threading.Thread.__init__(self)
        self.eventlistener = eventlistener
        self.done = False

    def run(self):
        while not self.done:
            events, raw_events, evtwraps = self.eventlistener._get_events()
            self.eventlistener._dispatch_events(events, raw_events, evtwraps)

    def stop(self):
        self.done = True
