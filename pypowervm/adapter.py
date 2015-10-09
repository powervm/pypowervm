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

"""Low-level communication with the PowerVM REST API."""

import abc
import copy
import datetime as dt
import errno
import hashlib
import os

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

import oslo_concurrency.lockutils as locku
from oslo_log import log as logging
import requests
import requests.exceptions as rqex
import six

from pypowervm import cache
from pypowervm import const as c
import pypowervm.entities as ent
import pypowervm.exceptions as pvmex
from pypowervm import traits as pvm_traits
from pypowervm import util

# Preserve CDATA on the way in (also ensures it is not mucked with on the way
# out)
etree.set_default_parser(etree.XMLParser(strip_cdata=False, encoding='utf-8'))


# Setup logging
LOG = logging.getLogger(__name__)

register_namespace = etree.register_namespace

# Register the namespaces we'll use
register_namespace('atom', c.ATOM_NS)
register_namespace('xsi', c.XSI_NS)
register_namespace('web', c.WEB_NS)
register_namespace('uom', c.UOM_NS)


class Session(object):
    """Responsible for PowerVM API session management."""

    def __init__(self, host='localhost', username=None, password=None,
                 auditmemento=None, protocol=None, port=None, timeout=1200,
                 certpath='/etc/ssl/certs/', certext='.crt'):
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
            # Generate a username, which is used by the file auth mechanism
            # only to name the file.  Username indicates the time (seconds
            # since the epoch) of the instantiation of this Session instance.
            username = 'pypowervm_%d' % int(time.mktime(time.gmtime()))
        self.username = username

        if protocol is None:
            protocol = 'http' if self.use_file_auth else 'https'
        if protocol not in c.PORT_DEFAULT_BY_PROTO.keys():
            raise ValueError('Invalid protocol "%s"' % protocol)
        self.protocol = protocol

        self.host = host

        if host != 'localhost' and protocol == 'http':
            LOG.warn('Unencrypted communication with PowerVM! ' +
                     'Revert configuration to https.')

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
                    LOG.warn("Calculating default audit memento failed, using "
                             "'default'.")
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

        self._logon()

        # HMC should never use file auth.  This should never happen - if it
        # does, it indicates that we got a bad Logon response, or processed it
        # incorrectly.
        if self.use_file_auth and self.mc_type == 'HMC':
            raise pvmex.Error("Local authentication not supported on HMC.")

        # Set the API traits after logon.
        self.traits = pvm_traits.APITraits(self)

    def __del__(self):
        try:
            if self._eventlistener:
                self._eventlistener.shutdown()
        finally:
            self._logoff()

    def get_event_listener(self):
        if not self._eventlistener:
            # spawn a separate session for listening to events. If we used the
            # same session, Session.__del__() would never be called
            # TODO(IBM): investigate whether we can find a way to share the
            # session
            LOG.info("setting up event listener for %s" % self.host)
            listen_session = Session(self.host,
                                     self.username,
                                     self.password,
                                     auditmemento=self.auditmemento,
                                     protocol=self.protocol,
                                     port=self.port,
                                     timeout=self.timeout,
                                     certpath=self.certpath,
                                     certext=self.certext)
            self._eventlistener = EventListener(listen_session)
        return self._eventlistener

    def request(self, method, path, headers=None, body='', sensitive=False,
                verify=False, timeout=-1, auditmemento=None, relogin=True,
                login=False, filehandle=None, chunksize=65536):
        """Send an HTTP/HTTPS request to a PowerVM interface."""

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
                raise ValueError('unexpected filehandle on %s request'
                                 % method)

        if isupload:
            LOG.debug('sending %s %s headers=%s body=<file contents>' %
                      (method, url,
                       headers if not sensitive else "<sensitive>"))
        else:
            LOG.debug('sending %s %s headers=%s body=%s' %
                      (method, url,
                       headers if not sensitive else "<sensitive>",
                       body if not sensitive else "<sensitive>"))

        # Add X-API-Session header after above so it's not printed in log
        sess_token_try = None
        if not login:
            with self._lock:
                assert self._sessToken, "missing session token"
                headers['X-API-Session'] = self._sessToken
                sess_token_try = self._sessToken

        try:
            if isupload:

                def chunkreader():
                    while True:
                        d = filehandle.read(chunksize)
                        if not d:
                            break
                        yield d

                response = session.request(method, url, data=chunkreader(),
                                           headers=headers, timeout=timeout)
            elif isdownload:
                response = session.request(method, url, stream=True,
                                           headers=headers, timeout=timeout)
            else:
                response = session.request(method, url, data=body,
                                           headers=headers, timeout=timeout)
        except rqex.SSLError as e:
            msg = '%s for %s %s: %s' % (e.__class__.__name__, method, url, e)
            LOG.warn(msg)
            raise pvmex.SSLError(msg)
        except rqex.ConnectionError as e:
            msg = '%s for %s %s: %s' % (e.__class__.__name__, method, url, e)
            LOG.warn(msg)
            raise pvmex.ConnectionError(msg)
        except rqex.Timeout as e:
            msg = '%s for %s %s: %s' % (e.__class__.__name__, method, url, e)
            LOG.warn(msg)
            raise pvmex.TimeoutError(msg)
        except Exception as e:
            LOG.exception('Unexpected error for %s %s' % (method, url))
            raise pvmex.Error('Unexpected error: %s for %s %s: %s' %
                              (e.__class__.__name__, method, url, e))
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

        LOG.debug('result: %s (%s) for %s %s' %
                  (response.status_code, response.reason, method, url))
        LOG.debug('response headers: %s' %
                  (response.headers if not sensitive else "<sensitive>"))

        if response.status_code in [c.HTTPStatus.OK_NO_CONTENT,
                                    c.HTTPStatus.NO_CHANGE]:
            return Response(method, path, response.status_code,
                            response.reason, response.headers,
                            reqheaders=headers, reqbody=body)
        else:
            LOG.debug('response body:\n%s' %
                      (response.text if not sensitive else "<sensitive>"))

        # re-login processing
        if response.status_code == c.HTTPStatus.UNAUTHORIZED:
            LOG.debug('Processing HTTP Unauthorized')

            with self._lock:
                if not relogin:
                    LOG.debug('Requester specified no re-login')
                elif self._relogin_unsafe:
                    LOG.warn('Re-login has been deemed unsafe. ' +
                             'This Session instance should no longer be used.')
                else:
                    if self._sessToken != sess_token_try:
                        LOG.debug('Someone else handled re-login for %s'
                                  % self.host)
                    else:
                        self._logged_in = False

                        LOG.info('Attempting re-login %s' % self.host)
                        try:
                            self._logon()
                        except pvmex.Error as e:
                            if e.response:
                                if (e.response.status ==
                                        c.HTTPStatus.UNAUTHORIZED):
                                    # can't continue re-login attempts lest we
                                    # lock the account
                                    self._relogin_unsafe = True
                                    LOG.warn('Re-login 401, response body:\n%s'
                                             % e.response.body)
                                else:
                                    # safe to try re-login again in this case
                                    LOG.warn('Re-login failed, resp body:\n%s'
                                             % e.response.body)
                            else:
                                # safe to try re-login again in this case
                                LOG.warn('Re-login failed:\n%s' % str(e))
                            e.orig_response = Response(
                                method, path, response.status_code,
                                response.reason, response.headers,
                                reqheaders=headers, reqbody=body,
                                body=response.text)
                            raise e

                    # Retry the original request
                    try:
                        return self.request(method, path, headers, body,
                                            sensitive=sensitive, verify=verify,
                                            timeout=timeout, relogin=False)
                    except pvmex.HttpError as e:
                        if e.response.status == c.HTTPStatus.UNAUTHORIZED:
                            # This is a special case... normally on a 401 we
                            # would retry login, but we won't here because
                            # we just did that... Handle it specially.
                            LOG.warn('Re-attempt failed with another 401, ' +
                                     'response body:\n%s' % e.response.body)
                            raise pvmex.Error('suspicious HTTP 401 response ' +
                                              'for %s %s: token is brand new' %
                                              (method, path))
                        raise

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
            raise pvmex.HttpError(resp)

    def _logon(self):
        LOG.info("Session logging on %s" % self.host)
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
            # Attempt to validate ourselves based on certificates stored in
            # self.certpath
            verify = False
        else:
            # Have the requests module validate the certificate
            verify = True
        try:
            # relogin=False to prevent multiple attempts with same credentials
            resp = self.request('PUT', c.LOGON_PATH, headers=headers,
                                body=body, sensitive=True, verify=verify,
                                relogin=False, login=True)
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
            msg = "Failed to parse a session token from the PowerVM response."
            LOG.error((msg + ' body= %s') % resp.body)
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
            msg = ("Failed to parse a session file path from the PowerVM "
                   "response.")
            LOG.error((msg + ' body= %s') % resp.body)
            raise pvmex.Error(msg, response=resp)
        try:
            with open(tokfile_path, 'r') as tokfile:
                tok = tokfile.read().strip(' \n')
        except IOError as ioe:
            if ioe.errno == errno.EACCES:
                raise pvmex.AuthFileReadError(access_file=str(tokfile_path))
            else:
                raise pvmex.AuthFileAccessError(access_file=str(tokfile_path))
        if not tok:
            # TODO(IBM): T9N
            msg = ("Token file %s didn't contain a readable session token." %
                   tokfile_path)
            LOG.error(msg)
            raise pvmex.Error(msg, response=resp)
        return tok

    def _logoff(self):
        with self._lock:
            if not self._logged_in:
                return
            LOG.info("Session logging off %s" % self.host)
            try:
                # relogin=False to prevent multiple attempts
                self.request('DELETE', c.LOGON_PATH, relogin=False)
            except Exception:
                LOG.exception('Problem logging off.  Ignoring.')

            self._logged_in = False
            # this should only ever be called when Session has gone out of
            # scope, but just in case someone calls it directly while requests
            # are in flight, set _relogin_unsafe so that those requests won't
            # enter relogin processing when they get an HTTP 401.
            self._relogin_unsafe = True


class Adapter(object):
    """REST API Adapter for PowerVM remote management."""

    # TODO(IBM): way to retrieve cache timestamp along with / instead of data?

    def __init__(self, session=None, use_cache=False, helpers=None):
        """Create a new Adapter instance, connected to a Session.

        :param session: (Optional) A Session instance.  If not specified, a
                        new, local, file-authentication-based Session will be
                        created and used.
        :param use_cache: (Optional) Cache REST responses for faster operation.
        :param helpers: A list of decorator methods in which to wrap the HTTP
                        request call.  See the pypowervm.helpers package for
                        examples.
        """
        self.session = session if session else Session()
        self._cache = None
        self._eventlistener = None
        self._refreshtime4path = {}
        self._helpers = self._standardize_helper_list(helpers)
        if use_cache:
            self._cache = cache._PVMCache(session.host)
            # Events may not always be sent when they should, but they should
            # be trustworthy when they are sent.
            try:
                self._eventlistener = session.get_event_listener()
            except Exception:
                LOG.exception('Failed to register for events.  Events will '
                              'not be used.')
            if self._eventlistener is not None:
                self._evthandler = _CacheEventHandler(self._cache)
                self._eventlistener.subscribe(self._evthandler)

    def __del__(self):
        if self._eventlistener is not None:
            self._eventlistener.unsubscribe(self._evthandler)

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
            raise ValueError('job must be a JobRequest element')

        op = job.findtext('RequestedOperation/OperationName')
        if not op:
            raise ValueError('JobRequest is missing OperationName')

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
            raise ValueError('path=%s is not a PowerVM API reference' % path)
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
        resp_to_cache = None
        is_cacheable = self._cache and not any(p in path for p in
                                               c.UNCACHEABLE)
        if is_cacheable:
            # TODO(IBM): are there cases where PUT response differs from GET?
            # TODO(IBM): only cache this when we don't have event support?
            # If events are supported for this element, they should quickly
            # invalidate this cache entry. But if events aren't available, or
            # could be missed, caching the response may be useful.
            # We will cache unmarshalled to reduce cache overhead, but we do
            # need to unmarshall to determine all paths to use as cache key, so
            # save this off (unmarshalled) to cache a little later.
            resp_to_cache = copy.deepcopy(resp)
        resp._unmarshal_atom()
        if resp_to_cache:
            paths = util.determine_paths(resp)
            new_path = util.extend_basepath(
                resp.reqpath, '/' + resp.entry.uuid)
            self._cache.set(new_path, paths, resp_to_cache)
            # need to invalidate the feeds containing this entry
            feed_paths = self._cache.get_feed_paths(new_path)
            for feed_path in feed_paths:
                self._cache.remove(feed_path)
        return resp

    def read(self, root_type, root_id=None, child_type=None, child_id=None,
             suffix_type=None, suffix_parm=None, detail=None, service='uom',
             etag=None, timeout=-1, auditmemento=None, age=-1, xag=None,
             sensitive=False, helpers=None):
        """Retrieve an existing resource.

        Will build the URI path using the provided arguments.
        """
        self._validate('read', root_type, root_id, child_type, child_id,
                       suffix_type, suffix_parm, detail)
        path = self.build_path(service, root_type, root_id, child_type,
                               child_id, suffix_type, suffix_parm, detail,
                               xag=xag)
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
            LOG.debug('href=%s will be modified to use %s:%s' %
                      (href, self.session.host, self.session.port))
        path = self.extend_path(util.dice_href(href), suffix_type, suffix_parm,
                                detail, xag=xag)
        return self.read_by_path(path, etag=etag, timeout=timeout,
                                 auditmemento=auditmemento, age=age,
                                 sensitive=sensitive, helpers=helpers)

    def read_by_path(self, path, etag=None, timeout=-1, auditmemento=None,
                     age=-1, sensitive=False, helpers=None):
        """Retrieve an existing resource where URI path is already known."""

        @locku.synchronized(path)
        def _locked_refresh(refresh_time, _cached_resp, _etag,
                            _etag_from_cache):
            # If the request time is after the last time we started this,
            # then for all intents and purposes the data is current
            _refresh_time = self._refreshtime4path.get(path)
            if _refresh_time is not None and _refresh_time >= refresh_time:
                # The callers request was queued behind the lock before
                # we started updating, so we know any operations they
                # were expecting should be reflected in the latest data.
                # Re-retrieve from cache
                if _etag_from_cache:
                    # this optimization won't work in this case because the
                    # cache has already been refreshed since getting this etag
                    # value from the cache
                    _etag = None
                    _etag_from_cache = False
                # don't need to check age because we know we just refreshed
                rsp = self._get_resp_from_cache(path, etag=_etag)
                if rsp:
                    if _etag and _etag == rsp.etag:
                        # ETag matches what caller specified, so return an
                        # HTTP 304 (Not Modified) response
                        rsp.status = c.HTTPStatus.NO_CHANGE
                        rsp.body = ''
                    elif 'atom' in rsp.reqheaders['Accept']:
                        rsp._unmarshal_atom()
                    return rsp

            # Either first to get the lock or found the cache to be empty
            # First, note the time so it can be checked by the next guy
            self._refreshtime4path[path] = dt.datetime.now()
            # Now read from PowerVM
            rsp = self._read_by_path(path, _etag, timeout, auditmemento,
                                     sensitive, helpers=helpers)
            resp_to_cache = None
            if is_cacheable:
                if rsp.status == c.HTTPStatus.NO_CHANGE:
                    # don't want to cache the 304, which has no body
                    # instead, just update the cache ordering
                    self._cache.touch(path)
                    if _etag_from_cache:
                        # the caller didn't specify that ETag, so they won't
                        # be expecting a 304 response... return from the cache
                        rsp = _cached_resp
                else:
                    # cache unmarshalled to reduce cache overhead
                    # But we need to unmarshall to determine all paths, so
                    # save this off (unmarshalled) to cache a little later
                    resp_to_cache = copy.deepcopy(rsp)
            if 'atom' in rsp.reqheaders['Accept']:
                rsp._unmarshal_atom()
            if resp_to_cache:
                self._cache.set(path, util.determine_paths(rsp),
                                resp_to_cache)
            return rsp

        # end _locked_refresh

        path = util.dice_href(path)
        # First, test whether we should be pulling from cache, determined
        # by asking a) is there a cache? and b) is this path cacheable?
        is_cacheable = self._cache and not any(p in path for p in
                                               c.UNCACHEABLE)
        resp = None
        cached_resp = None
        etag_from_cache = False

        if is_cacheable:
            # Attempt to retrieve from cache
            max_age = util.get_max_age(path, self._eventlistener is not None,
                                       self.session.schema_version)
            if age == -1 or age > max_age:
                age = max_age

            # If requested entry is not in cache, check for feed in
            # cache and build entry response from that.
            resp = self._get_resp_from_cache(path, age, etag)
            if resp:
                if etag and etag == resp.etag:
                    # ETag matches what caller specified, so return an
                    # HTTP 304 (Not Modified) response
                    resp.status = c.HTTPStatus.NO_CHANGE
                    resp.body = ''
                elif 'atom' in resp.reqheaders['Accept']:
                    resp._unmarshal_atom()
            elif not etag:
                # we'll bypass the cache, but if there is a cache entry that
                # doesn't meet the age requirement, we can still optimize
                # our GET request by using its ETag to see if it has changed
                cached_resp = self._get_resp_from_cache(path)
                if cached_resp:
                    etag = cached_resp.etag
                    etag_from_cache = True
        if not resp:
            # If the path is cacheable but it's not currently in our cache,
            # then do the request in series and use the cached results
            # if possible
            if is_cacheable:
                resp = _locked_refresh(dt.datetime.now(), cached_resp, etag,
                                       etag_from_cache)
            else:
                resp = self._read_by_path(path, etag, timeout, auditmemento,
                                          sensitive, helpers=helpers)
                if 'atom' in resp.reqheaders['Accept']:
                    resp._unmarshal_atom()

        return resp

    def _read_by_path(self, path, etag, timeout, auditmemento, sensitive,
                      helpers=None):
        m = re.search(r'%s(\w+)/(\w+)' % c.API_BASE_PATH, path)
        if not m:
            raise ValueError('path=%s is not a PowerVM API reference' % path)
        headers = {}
        json_search_str = (c.UUID_REGEX + '/quick$' + '|/quick/' + r'|\.json$')
        if re.search(json_search_str, util.dice_href(path, include_query=False,
                                                     include_fragment=False)):
            headers['Accept'] = 'application/json'
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

    def _check_cache_etag_mismatch(self, path, etag):
        """ETag didn't match - see if we need to invalidate entry in cache.

        :param path: The path (not URI) of the request that failed 304.
        :param etag: The etag of the payload sent with the request
        """
        resp = self._cache.get(path)
        if resp and etag == resp.etag:
            # need to invalidate this in the cache
            self._cache.remove(path)
        # see if we need to invalidate feed in cache
        # extract entry uuid
        uuid = util.get_req_path_uuid(path)
        # extract feed paths pertaining to the entry
        feed_paths = self._cache.get_feed_paths(path)
        for feed_path in feed_paths:
            resp = self._build_entry_resp(feed_path, uuid)
            if not resp or etag == resp.etag:
                # need to invalidate this in the cache
                self._cache.remove(feed_path)
                LOG.debug('Invalidate feed %s for uuid %s' %
                          (feed_path, uuid))

    def update_by_path(self, data, etag, path, timeout=-1, auditmemento=None,
                       sensitive=False, helpers=None):
        """Update an existing resource where the URI path is already known."""
        path = util.dice_href(path)
        try:
            m = re.match(r'%s(\w+)/(\w+)' % c.API_BASE_PATH, path)
            if not m:
                raise ValueError('path=%s is not a PowerVM API reference' %
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
                timeout=timeout, auditmemento=auditmemento,
                sensitive=sensitive)
        except pvmex.HttpError as e:
            if self._cache and e.response.status == c.HTTPStatus.ETAG_MISMATCH:
                self._check_cache_etag_mismatch(path, etag)
            raise
        resp_to_cache = None
        is_cacheable = self._cache and not any(p in path for p in
                                               c.UNCACHEABLE)
        if is_cacheable:
            # TODO(IBM): are there cases where POST response differs from GET?
            # TODO(IBM): only cache this when we don't have event support?
            # If events are supported for this element, they should quickly
            # invalidate this cache entry. But if events aren't available, or
            # could be missed, caching the response may be useful.
            # We will cache unmarshalled to reduce cache overhead, but we do
            # need to unmarshall to determine all paths to use as cache key, so
            # save this off (unmarshalled) to cache a little later.
            resp_to_cache = copy.deepcopy(resp)
        resp._unmarshal_atom()
        if resp_to_cache:
            paths = util.determine_paths(resp)
            self._cache.set(path, paths, resp_to_cache)
            # need to invalidate the feeds containing this entry
            feed_paths = self._cache.get_feed_paths(path)
            for feed_path in feed_paths:
                self._cache.remove(feed_path)
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
            LOG.debug('href=%s will be modified to use %s:%s' %
                      (href, self.session.host, self.session.port))
        return self.delete_by_path(o.path, etag=etag, timeout=timeout,
                                   auditmemento=auditmemento, helpers=helpers)

    def delete_by_path(self, path, etag=None, timeout=-1, auditmemento=None,
                       helpers=None):
        """Delete an existing resource where the URI path is already known."""
        path = util.dice_href(path, include_query=False,
                              include_fragment=False)
        try:
            resp = self._delete_by_path(path, etag, timeout, auditmemento,
                                        helpers=helpers)
        except pvmex.HttpError as e:
            if self._cache and e.response.status == c.HTTPStatus.ETAG_MISMATCH:
                self._check_cache_etag_mismatch(path, etag)
            raise
        if self._cache is not None:
            # get feed_paths before removing the entry (won't work after)
            feed_paths = self._cache.get_feed_paths(path)
            # need to invalidate this in the cache
            self._cache.remove(path, delete=True)
            # also need to invalidate the feeds containing this entry
            for feed_path in feed_paths:
                self._cache.remove(feed_path)

        return resp

    def _delete_by_path(self, path, etag, timeout, auditmemento, helpers=None):
        m = re.search(r'%s(\w+)/(\w+)' % c.API_BASE_PATH, path)
        if not m:
            raise ValueError('path=%s is not a PowerVM API reference' % path)
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
            raise ValueError('Invalid file descriptor')

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
            raise ValueError('Invalid file descriptor')

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

    def _build_entry_resp(self, feed_path, uuid, etag=None, age=-1):
        """Build Response based on entry within a cached feed."""
        feed_resp = self._cache.get(feed_path, age)
        if not feed_resp or not feed_resp.body:
            return

        resp = None
        root = etree.fromstring(feed_resp.body)
        entry_body, entry_etag = get_entry_from_feed(root, uuid)
        if entry_body:
            # generate reqpath based on the feed and including uuid
            reqpath = feed_resp.reqpath
            parms_str = ''
            if '?' in feed_resp.reqpath:
                reqpath, parms_str = feed_resp.reqpath.rsplit('?', 1)

            reqpath = reqpath + '/' + uuid
            if parms_str:
                reqpath = reqpath + '?' + parms_str
            if entry_etag and etag == entry_etag:
                resp = Response(feed_resp.reqmethod,
                                reqpath,
                                c.HTTPStatus.NO_CHANGE,
                                feed_resp.reason,
                                feed_resp.headers,
                                body='',
                                orig_reqpath=feed_resp.reqpath)
                LOG.debug('Built HTTP 304 resp from cached feed')
            else:
                # should we upate the parameters?
                resp = Response(feed_resp.reqmethod,
                                reqpath,
                                feed_resp.status,
                                feed_resp.reason,
                                feed_resp.headers,
                                feed_resp.reqheaders,
                                body=entry_body,
                                orig_reqpath=feed_resp.reqpath)
                # override the etag in the header
                if entry_etag:
                    resp.headers['etag'] = entry_etag
                elif etag:
                    # if there is no entry etag and etag is specified,
                    # just return
                    return
                LOG.debug('built entry from cached feed etag=%s body=%s' %
                          (entry_etag, entry_body))

        return resp

    @classmethod
    def build_path(cls, service, root_type, root_id=None, child_type=None,
                   child_id=None, suffix_type=None, suffix_parm=None,
                   detail=None, xag=None):
        path = c.API_BASE_PATH + service + '/' + root_type
        if root_id:
            path += '/' + root_id
            if child_type:
                path += '/' + child_type
                if child_id:
                    path += '/' + child_id
        return cls.extend_path(path, suffix_type, suffix_parm, detail, xag)

    @staticmethod
    def extend_path(basepath, suffix_type=None, suffix_parm=None, detail=None,
                    xag=None):
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
        :return:
        """
        path = basepath
        if suffix_type:
            # operations, do, jobs, cancel, quick, search, ${search-string}
            path = util.extend_basepath(path, '/' + suffix_type)
            if suffix_parm:
                path = util.extend_basepath(path, '/' + suffix_parm)
        if detail:
            sep = '&' if '?' in path else '?'
            path += sep + 'detail=' + detail

        # Explicit xag is always honored as-is.  If unspecified, we usually
        # want to include group=None.  However, there are certain classes of
        # URI from which we want to omit ?group entirely.
        if xag is None:
            xagless_suffixes = ('quick', 'do')
            if suffix_type in xagless_suffixes:
                xag = []
        path = util.check_and_apply_xag(path, xag)

        return path

    @staticmethod
    def _validate(req_method, root_type, root_id=None, child_type=None,
                  child_id=None, suffix_type=None, suffix_parm=None,
                  detail=None):
        # 'detail' param currently unused
        if child_type and not root_id:
            raise ValueError('Expected root_id')
        if child_id and not child_type:
            raise ValueError('Expected child_type')
        if req_method == 'create':
            if suffix_type:
                if suffix_type != 'do':
                    raise ValueError('Unexpected suffix_type=%s' % suffix_type)
                if not suffix_parm:
                    raise ValueError('Expected suffix_parm')
                if child_type and not child_id:
                    raise ValueError('Expected child_id')
            else:
                if child_id:
                    raise ValueError('Unexpected child_id')
                if root_id and not child_type:
                    raise ValueError('Unexpected root_id')
        elif req_method == 'read':
            # no read-specific validation at this time
            pass
        elif req_method == 'update':
            if 'preferences' in [root_type, child_type]:
                if child_id:
                    raise ValueError('Unexpected child_id')
                if root_id and not child_type:
                    raise ValueError('Unexpected root_id')
            else:
                if not root_id:
                    raise ValueError('Expected root_id')
                if child_type and not child_id:
                    raise ValueError('Expected child_id')
                if suffix_type is not None and suffix_type != 'cancel':
                    raise ValueError('Unexpected suffix_type=%s' % suffix_type)
        elif req_method == 'delete':
            if suffix_type:
                if suffix_type != 'jobs':
                    raise ValueError('Unexpected suffix_type=%s' % suffix_type)
                if not suffix_parm:
                    raise ValueError('Expected suffix_parm')
            else:
                if not root_id:
                    raise ValueError('Expected root_id')
                if child_type and not child_id:
                    raise ValueError('Expected child_id')
        else:
            raise ValueError('Unexpected req_method=%s' % req_method)

    def _get_resp_from_cache(self, path, age=-1, etag=None):
        """Extract Response from cached data (either entry or feed)."""
        cached_resp = self._cache.get(path, age=age)
        if cached_resp is None:
            # check the feed
            uuid, xag_str = util.get_uuid_xag_from_path(path)
            if uuid:
                feed_paths = self._cache.get_feed_paths(path)
                LOG.debug('Checking cached feeds %s for uuid %s %s' %
                          (feed_paths, uuid, xag_str))
                for f_path in feed_paths:
                    cached_resp = self._build_entry_resp(f_path, uuid, etag,
                                                         age)
                    if cached_resp is not None:
                        break
        else:
            LOG.debug('Found cached entry for path %s' % path)

        return cached_resp

    def invalidate_cache_elem_by_path(self, path, invalidate_feeds=False):
        """Invalidates a cache entry where the URI path is already known."""
        path = util.dice_href(path)

        if self._cache is not None:
            # need to invalidate this path in the cache
            self._cache.remove(path)
            # if user wants to invalidate feeds as well,
            # invalidate_feeds will equal True
            if invalidate_feeds:
                feed_paths = self._cache.get_feed_paths(path)
                for feed_path in feed_paths:
                    self._cache.remove(feed_path)

    # Invalidates the cache entry apart from CRUD operations
    def invalidate_cache_elem(self, root_type, root_id=None, child_type=None,
                              child_id=None, service='uom',
                              invalidate_feeds=False):
        """Invalidates a cache entry.

        Will build the URI path using the provided arguments.
        """
        self._validate('read', root_type, root_id, child_type, child_id)
        path = self.build_path(service, root_type, root_id,
                               child_type, child_id)
        self.invalidate_cache_elem_by_path(path, invalidate_feeds)


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
        :param orig_reqpath: The original reqpath if the Response is built from
                             a cached feed.
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
        self.orig_reqpath = orig_reqpath
        # Set by _request()
        self.adapter = None

    def __deepcopy__(self, memo=None):
        """Produce a deep (except for adapter) copy of this Response."""
        ret = self.__class__(
            self.reqmethod, self.reqpath, self.status, self.reason,
            copy.deepcopy(self.headers, memo=memo),
            reqheaders=copy.deepcopy(self.reqheaders, memo=memo),
            reqbody=self.reqbody, body=self.body,
            orig_reqpath=self.orig_reqpath)
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

    def _unmarshal_atom(self):
        err_reason = None
        if self.body:
            root = None
            try:
                root = etree.fromstring(self.body)
            except Exception as e:
                err_reason = ('Error parsing XML response from PowerVM: %s' %
                              str(e))
            if root is not None and root.tag == str(
                    etree.QName(c.ATOM_NS, 'feed')):
                self.feed = ent.Feed.unmarshal_atom_feed(root, self)
            elif root is not None and root.tag == str(
                    etree.QName(c.ATOM_NS, 'entry')):
                self.entry = ent.Entry.unmarshal_atom_entry(root, self)
            elif err_reason is None:
                err_reason = 'response is not an Atom feed/entry'
        elif self.reqmethod == 'GET':
            if self.status == c.HTTPStatus.OK_NO_CONTENT:
                if util.is_instance_path(self.reqpath):
                    err_reason = 'unexpected HTTP 204 for request'
                else:
                    # PowerVM returns HTTP 204 (No Content) when you
                    # ask for a feed that has no entries.
                    self.feed = ent.Feed({}, [])
            elif self.status == c.HTTPStatus.NO_CHANGE:
                pass
            else:
                err_reason = 'unexpectedly empty response body'

        if err_reason is not None:
            LOG.error(('%(err_reason)s:\n'
                       'request headers: %(reqheaders)s\n\n'
                       'request body: %(reqbody)s\n\n'
                       'response headers: %(respheaders)s\n\n'
                       'response body: %(respbody)s')
                      % {'err_reason': err_reason,
                         'reqheaders': self.reqheaders,
                         'reqbody': self.reqbody,
                         'respheaders': self.headers,
                         'respbody': self.body})
            raise pvmex.AtomError('Atom error for %s %s: %s'
                                  % (self.reqmethod, self.reqpath, err_reason),
                                  self)


class EventListener(object):
    def __init__(self, session, timeout=-1, interval=15):
        if session is None:
            raise ValueError('session must not be None')
        self.appid = hashlib.md5(session._sessToken).hexdigest()
        self.timeout = timeout if timeout != -1 else session.timeout
        self.interval = interval
        self._lock = threading.RLock()
        self.handlers = []
        self._pthread = None
        try:
            self.adp = Adapter(session, use_cache=False)
            # initialize
            allevents = self.getevents()
        except pvmex.Error as e:
            raise pvmex.Error('Failed to initialize event feed listener: %s'
                              % e)
        if not allevents.get('general') == 'init':
            # Something else is sharing this feed!
            raise ValueError('Application id "%s" is not unique' % self.appid)

    def subscribe(self, handler):
        if not isinstance(handler, EventHandler):
            raise ValueError('Handler must be an EventHandler')
        if self.adp is None:
            raise Exception('Shutting down')
        with self._lock:
            if handler in self.handlers:
                raise ValueError('This handler is already subscribed')
            self.handlers.append(handler)
            if not self._pthread:
                self._pthread = _EventPollThread(self, self.interval)
                self._pthread.start()

    def unsubscribe(self, handler):
        if not isinstance(handler, EventHandler):
            raise ValueError('Handler must be an EventHandler')
        with self._lock:
            if handler not in self.handlers:
                raise ValueError('This handler not found in subscriber list')
            self.handlers.remove(handler)
            if not self.handlers:
                self._pthread.stop()
                self._pthread = None

    def shutdown(self):
        host = self.adp.session.host
        LOG.info('Shutting down EventListener for %s' % host)
        with self._lock:
            for handler in self.handlers:
                self.unsubscribe(handler)
            self.adp = None
        LOG.info('EventListener shutdown complete for %s' % host)

    def getevents(self):

        events = {}

        # Read event feed
        try:
            resp = self.adp.read('Event?QUEUE_CLIENTKEY_METHOD='
                                 'USE_APPLICATIONID&QUEUE_APPLICATIONID=%s'
                                 % self.appid, timeout=self.timeout)
        except pvmex.Error:
            # TODO(IBM): improve error handling
            LOG.exception('error while getting PowerVM events')
            return events

        # Parse event feed
        for entry in resp.feed.entries:
            etype = entry.element.findtext('EventType')
            href = entry.element.findtext('EventData')
            if etype == 'NEW_CLIENT':
                events['general'] = 'init'
            elif etype in ['CACHE_CLEARED', 'MISSING_EVENTS']:
                events = {'general': 'invalidate'}
                break
            elif etype == 'ADD_URI':
                events[href] = 'add'
            elif etype == 'DELETE_URI':
                events[href] = 'delete'
            elif etype in ['MODIFY_URI', 'INVALID_URI', 'HIDDEN_URI']:
                if href not in events:
                    events[href] = 'invalidate'
            elif etype not in ['VISIBLE_URI']:
                LOG.error('unexpected EventType=%s' % etype)

        # Notify subscribers
        with self._lock:
            for h in self.handlers:
                try:
                    h.process(events)
                except Exception:
                    LOG.exception('error while processing PowerVM events')

        return events


@six.add_metaclass(abc.ABCMeta)
class EventHandler(object):
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


class _EventPollThread(threading.Thread):
    def __init__(self, eventlistener, interval):
        threading.Thread.__init__(self)
        self.eventlistener = eventlistener
        self.interval = interval
        self.done = False
        # self.daemon = True

    def run(self):
        while not self.done:
            self.eventlistener.getevents()
            interval = self.interval
            while interval > 0 and not self.done:
                time.sleep(1)
                interval -= 1

    def stop(self):
        self.done = True


class _CacheEventHandler(EventHandler):
    def __init__(self, the_cache):
        self.cache = the_cache

    def process(self, events):
        for k, v in six.iteritems(events):
            if k == 'general' and v == 'invalidate':
                self.cache.clear()
            elif v in ['delete', 'invalidate']:
                path = util.dice_href(k)
                # remove from cache
                self.cache.remove(path)
                # if entry, remove corresponding feeds from cache
                feed_paths = self.cache.get_feed_paths(path)
                for feed_path in feed_paths:
                    self.cache.remove(feed_path)


def get_entry_from_feed(feedelem, uuid):
    """Parse atom feed to extract the entry matching to the uuid."""
    if not feedelem:
        return None, None
    uuid = uuid.lower()
    entry = None
    etag = None
    for f_elem in list(feedelem):
        if f_elem.tag == str(etree.QName(c.ATOM_NS, 'entry')):
            etag = None
            for e_elem in list(f_elem):
                if not list(e_elem):
                    pat = '{%s}' % c.ATOM_NS
                    if re.match(pat, e_elem.tag):
                        # Strip off atom namespace qualification for easier
                        # access
                        param_name = (e_elem.tag[e_elem.tag.index('}')
                                                 + 1:len(e_elem.tag)])
                    else:
                        # Leave qualified anything that is not in the atom
                        # namespace
                        param_name = e_elem.tag
                    if param_name == '{%s}etag' % c.UOM_NS:
                        etag = e_elem.text
                    elif param_name == 'id' and e_elem.text.lower() == uuid:
                        entry = etree.tostring(f_elem)

        if entry is not None:
            return entry, etag
    return None, None
