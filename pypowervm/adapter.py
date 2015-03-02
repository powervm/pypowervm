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

import abc
import copy
import datetime as dt
import hashlib
import logging
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
    from urllib.parse import urlparse

import oslo_concurrency.lockutils as locku
import requests
import requests.exceptions as rqex
import six

from pypowervm import cache
from pypowervm import const
import pypowervm.exceptions as pvmex
from pypowervm import util

# Preserve CDATA on the way in (also ensures it is not mucked with on the way
# out)
etree.set_default_parser(etree.XMLParser(strip_cdata=False, encoding='utf-8'))

QName = etree.QName


# Setup logging
LOG = logging.getLogger(__name__)

register_namespace = etree.register_namespace

# Register the namespaces we'll use
register_namespace('atom', const.ATOM_NS)
register_namespace('xsi', const.XSI_NS)
register_namespace('web', const.WEB_NS)
register_namespace('uom', const.UOM_NS)


class Session(object):
    """Responsible for PowerVM API session management."""

    # TODO(IBM): Pull these defaults into an INI
    def __init__(self, host, username, password, auditmemento=None,
                 protocol='https', port=12443, timeout=60,
                 certpath='/etc/ssl/certs/', certext='.crt'):
        self.username = username
        self.password = password

        audmem = auditmemento
        if not audmem:
            # Assume 'default' unless we can calculate the proper default
            audmem = 'default'
            if os.name == 'posix':
                try:
                    audmem = pwd.getpwuid(os.getuid())[0]
                except Exception:
                    LOG.warn("Calculating default audit memento failed, using "
                             "'default'.")
        self.auditmemento = audmem

        self.protocol = protocol
        if protocol == 'http':
            LOG.warn('Unencrypted communication with PowerVM! ' +
                     'Revert configuration to https.')
        if self.protocol not in ['https', 'http']:
            raise ValueError('Invalid protocol "%s"' % self.protocol)
        self.host = host
        self.port = port
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
        self._sessToken = None
        self.schema_version = None
        self._eventlistener = None
        self._logon()

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

        # Don't use mutable default args
        if headers is None:
            headers = {}

        """Send an HTTP/HTTPS request to a PowerVM interface."""

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

        if response.status_code in [204, 304]:
            return Response(method, path, response.status_code,
                            response.reason, response.headers,
                            reqheaders=headers, reqbody=body)
        else:
            LOG.debug('response body:\n%s' %
                      (response.text if not sensitive else "<sensitive>"))

        # re-login processing
        if response.status_code == 401:
            LOG.debug('Processing HTTP 401')

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
                                if e.response.status == 401:
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
                            unmarshal_httperror(e.orig_response)
                            raise e

                    # Retry the original request
                    try:
                        return self.request(method, path, headers, body,
                                            sensitive=sensitive, verify=verify,
                                            timeout=timeout, relogin=False)
                    except pvmex.HttpError as e:
                        if e.response.status == 401:
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
            errmsg = 'HTTP error for %s %s: %s (%s)' % (method, path,
                                                        response.status_code,
                                                        response.reason)
            unmarshal_httperror(resp)
            raise pvmex.HttpError(errmsg, resp)

    def _logon(self):
        LOG.info("Session logging on %s" % self.host)
        headers = {
            'Accept': const.TYPE_TEMPLATE % ('web', 'LogonResponse'),
            'Content-Type': const.TYPE_TEMPLATE % ('web', 'LogonRequest')
        }
        passwd = sax_utils.escape(self.password)
        body = const.LOGONREQUEST_TEMPLATE % {'userid': self.username,
                                              'passwd': passwd}
        # Convert it to a string-type from unicode-type encoded with UTF-8
        # Without the socket code will implicitly convert the type with ASCII
        body = body.encode('utf-8')

        if not self.certpath:
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
            resp = self.request('PUT', const.LOGON_PATH, headers=headers,
                                body=body, sensitive=True, verify=verify,
                                relogin=False, login=True)
        except pvmex.Error as e:
            if e.response:
                # strip out sensitive data
                e.response.reqbody = "<sensitive>"
            if isinstance(e, pvmex.HttpError):
                # clarify the error message
                raise pvmex.HttpError('HTTP error on Logon: %s (%s)' %
                                      (e.response.status, e.response.reason),
                                      e.response)
            raise

        # parse out X-API-Session value
        root = etree.fromstring(resp.body.encode('utf-8'))

        with self._lock:
            tok = root.findtext('{%s}X-API-Session' % const.WEB_NS)
            if not tok:
                resp.reqbody = "<sensitive>"
                msg = "failed to parse session token from PowerVM response"
                LOG.error((msg + ' body= %s') % resp.body)
                raise pvmex.Error(msg, response=resp)
            self._sessToken = tok
            self._logged_in = True
            self.schema_version = root.get('schemaVersion')

    def _logoff(self):
        with self._lock:
            if not self._logged_in:
                return
            LOG.info("Session logging off %s" % self.host)
            try:
                # relogin=False to prevent multiple attempts
                self.request('DELETE', const.LOGON_PATH, relogin=False)
            except Exception:
                LOG.exception('Problem logging off.  Ignoring.')
                pass
            self._logged_in = False
            # this should only ever be called when Session has gone out of
            # scope, but just in case someone calls it directly while requests
            # are in flight, set _relogin_unsafe so that those requests won't
            # enter relogin processing when they get an HTTP 401.
            self._relogin_unsafe = True


class Adapter(object):
    """REST API Adapter for PowerVM remote management."""

    # TODO(IBM): way to retrieve cache timestamp along with / instead of data?

    def __init__(self, session, use_cache=False, helpers=None):
        self.session = session
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
                self._evthandler = _EventHandler(self._cache)
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
        return func(method, path, **kwds)

    def create(self, element, root_type, root_id=None, child_type=None,
               child_id=None, suffix_type=None, suffix_parm=None, detail=None,
               service='uom', content_service=None, timeout=-1,
               auditmemento=None, xag=None, sensitive=False, helpers=None):
        """Create a new resource.

        Will build the URI path using the provided arguments.
        """
        self._validate('create', root_type, root_id, child_type, child_id,
                       suffix_type, suffix_parm, detail)
        path = self.build_path(service, root_type, root_id, child_type,
                               child_id, suffix_type, suffix_parm, detail,
                               xag=xag)
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
        path = util.sanitize_path(path)
        m = re.search('%s(\w+)/(\w+)' % const.API_BASE_PATH, path)
        if not m:
            raise ValueError('path=%s is not a PowerVM API reference' % path)
        if not content_service:
            content_service = m.group(1)

        headers = {'Accept': 'application/atom+xml; charset=UTF-8'}
        if re.search('/do/', path):
            headers['Content-Type'] = const.TYPE_TEMPLATE % (content_service,
                                                             'JobRequest')
        else:
            p = path.split('\?', 1)[0]  # strip off details, if present
            headers['Content-Type'] = const.TYPE_TEMPLATE % (
                content_service, p.rsplit('/', 1)[1])

        resp = self._request('PUT', path, helpers=helpers, headers=headers,
                             body=element.toxmlstring(), timeout=timeout,
                             auditmemento=auditmemento, sensitive=sensitive)
        resp_to_cache = None
        is_cacheable = self._cache and not any(p in path for p in
                                               const.UNCACHEABLE)
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
            # we're creating, so what we send is the full entity
            # so it should be safe to strip off xag (no xag = all)
            new_path = (resp.reqpath.split('?', 1)[0] + '/' +
                        resp.entry.properties['id'])
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
                     age=-1, sensitive=False, helpers=None):
        """Retrieve an existing resource based on a link's href."""
        o = urlparse.urlparse(href)
        hostname_mismatch = (o.hostname.lower() != self.session.host.lower())
        if hostname_mismatch or o.port != self.session.port:
            LOG.debug('href=%s will be modified to use %s:%s' %
                      (href, self.session.host, self.session.port))
        path = self.extend_path(o.path, suffix_type, suffix_parm, detail)
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
                    if _etag and _etag == rsp.headers.get('etag'):
                        # ETag matches what caller specified, so return an
                        # HTTP 304 (Not Modified) response
                        rsp.status = 304
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
                if rsp.status == 304:
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

        path = util.sanitize_path(path)
        # First, test whether we should be pulling from cache, determined
        # by asking a) is there a cache? and b) is this path cacheable?
        is_cacheable = self._cache and not any(p in path for p in
                                               const.UNCACHEABLE)
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
                if etag and etag == resp.headers.get('etag'):
                    # ETag matches what caller specified, so return an
                    # HTTP 304 (Not Modified) response
                    resp.status = 304
                    resp.body = ''
                elif 'atom' in resp.reqheaders['Accept']:
                    resp._unmarshal_atom()
            elif not etag:
                # we'll bypass the cache, but if there is a cache entry that
                # doesn't meet the age requirement, we can still optimize
                # our GET request by using its ETag to see if it has changed
                cached_resp = self._get_resp_from_cache(path)
                if cached_resp:
                    etag = cached_resp.headers.get('etag')
                    etag_from_cache = True
        if not resp:
            resp = _locked_refresh(dt.datetime.now(), cached_resp, etag,
                                   etag_from_cache)
        return resp

    def _read_by_path(self, path, etag, timeout, auditmemento, sensitive,
                      helpers=None):
        m = re.search('%s(\w+)/(\w+)' % const.API_BASE_PATH, path)
        if not m:
            raise ValueError('path=%s is not a PowerVM API reference' % path)
        headers = {}
        # isrespatom = False
        json_search_str = (const.UUID_REGEX + '/quick$' +
                           '|/quick/' +
                           '|.json$')
        if re.search(json_search_str, path):
            headers['Accept'] = 'application/json'
        else:
            # isrespatom = True
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
        path = util.sanitize_path(path)
        try:
            resp = self._update_by_path(data, etag, path, timeout,
                                        auditmemento, sensitive,
                                        helpers=helpers)
        except pvmex.HttpError as e:
            if self._cache and e.response.status == 412:
                # ETag didn't match
                # see if we need to invalidate entry in cache
                resp = self._cache.get(path)
                if resp and etag == resp.headers.get('etag'):
                    # need to invalidate this in the cache
                    self._cache.remove(path)
                # see if we need to invalidate feed in cache
                # extract the entry uuid
                uuid = util.get_req_path_uuid(path)
                # extract feed paths pertaining to the entry
                feed_paths = self._cache.get_feed_paths(path)
                for feed_path in feed_paths:
                    resp = self._build_entry_resp(feed_path, uuid)
                    if not resp or etag == resp.headers.get('etag'):
                        # need to invalidate this in the cache
                        self._cache.remove(feed_path)
                        LOG.debug('Invalidate feed %s for uuid %s' %
                                  (feed_path, uuid))
            raise
        resp_to_cache = None
        is_cacheable = self._cache and not any(p in path for p in
                                               const.UNCACHEABLE)
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

    def _update_by_path(self, data, etag, path, timeout, auditmemento,
                        sensitive, helpers=None):
        m = re.match('%s(\w+)/(\w+)' % const.API_BASE_PATH, path)
        if not m:
            raise ValueError('path=%s is not a PowerVM API reference' % path)
        headers = {'Accept': 'application/atom+xml; charset=UTF-8'}
        if m.group(1) == 'pcm':
            headers['Content-Type'] = 'application/xml'
        else:
            t = path.rsplit('/', 2)[1]
            headers['Content-Type'] = const.TYPE_TEMPLATE % (m.group(1), t)
        if etag:
            headers['If-Match'] = etag
        if hasattr(data, 'toxmlstring'):
            body = data.toxmlstring()
        else:
            body = data
        return self._request('POST', path, helpers=helpers, headers=headers,
                             body=body, timeout=timeout,
                             auditmemento=auditmemento, sensitive=sensitive)

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
        path = util.sanitize_path(path)
        try:
            resp = self._delete_by_path(path, etag, timeout, auditmemento,
                                        helpers=helpers)
        except pvmex.HttpError as e:
            if self._cache and e.response.status == 412:
                # ETag didn't match
                # see if we need to invalidate entry in cache
                resp = self._cache.get(path)
                if resp and etag == resp.headers.get('etag'):
                    # need to invalidate this in the cache
                    self._cache.remove(path)
                # see if we need to invalidate feed in cache
                # extract entry uuid
                uuid = util.get_req_path_uuid(path)
                # extract feed paths pertaining to the entry
                feed_paths = self._cache.get_feed_paths(path)
                for feed_path in feed_paths:
                    resp = self._build_entry_resp(feed_path, uuid)
                    if not resp or etag == resp.headers.get('etag'):
                        # need to invalidate this in the cache
                        self._cache.remove(feed_path)
                        LOG.debug('Invalidate feed %s for uuid %s' %
                                  (feed_path, uuid))
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
        m = re.search('%s(\w+)/(\w+)' % const.API_BASE_PATH, path)
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

        path = const.API_BASE_PATH + 'web/File/contents/' + fileid
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

        path = const.API_BASE_PATH + 'web/File/contents/' + fileid
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
                                304,
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

    @staticmethod
    def build_job_parm(name, value):
        p = Element('JobParameter', attrib={'schemaVersion': 'V1_0'},
                    ns=const.WEB_NS)
        p.append(Element('ParameterName', text=name, ns=const.WEB_NS))
        p.append(Element('ParameterValue', text=value, ns=const.WEB_NS))
        return p

    @classmethod
    def build_path(cls, service, root_type, root_id=None, child_type=None,
                   child_id=None, suffix_type=None, suffix_parm=None,
                   detail=None, xag=None):
        path = const.API_BASE_PATH + service + '/' + root_type
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
        path = basepath
        if suffix_type:
            # operations, do, jobs, cancel, quick, search, ${search-string}
            path += '/' + suffix_type
            if suffix_parm:
                path += '/' + suffix_parm
        if detail:
            path += '?detail=' + detail
        if xag:
            # sort xag in order
            xag.sort()
            path += '?group=%s' % ','.join(xag)
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
            pass  # no read-specific validation at this time
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
        path = util.sanitize_path(path)

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
        # to keep track of original reqpath
        # if the Response is built from cached feed
        self.orig_reqpath = orig_reqpath

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
                    QName(const.ATOM_NS, 'feed')):
                self.feed = Feed.unmarshal_atom_feed(root)
            elif root is not None and root.tag == str(
                    QName(const.ATOM_NS, 'entry')):
                self.entry = Entry.unmarshal_atom_entry(root)
            elif err_reason is None:
                err_reason = 'response is not an Atom feed/entry'
        elif self.reqmethod == 'GET':
            if self.status == 204:
                if re.match(const.UUID_REGEX,
                            self.reqpath.split('?')[0].rsplit('/', 1)[1]):
                    err_reason = 'unexpected HTTP 204 for request'
                else:
                    # PowerVM returns HTTP 204 (No Content) when you
                    # ask for a feed that has no entries.
                    self.feed = Feed({}, [])
            elif self.status == 304:
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


class Feed(object):
    """Represents an Atom Feed returned from PowerVM."""
    def __init__(self, properties, entries):
        self.properties = properties
        self.entries = entries

    def findentries(self, subelem, text):
        entries = []
        for entry in self.entries:
            subs = entry.element.findall(subelem)
            for s in subs:
                if s.text == text:
                    entries.append(entry)
                    break
        return entries

    @classmethod
    def unmarshal_atom_feed(cls, feedelem):
        """Factory method producing a Feed object from a parsed ElementTree

        :param feedelem: Parsed ElementTree object representing an atom feed.
        :return: a new Feed object representing the feedelem parameter.
        """
        feedprops = {}
        entries = []
        for child in list(feedelem):
            if child.tag == str(QName(const.ATOM_NS, 'entry')):
                entries.append(Entry.unmarshal_atom_entry(child))
            elif not list(child):
                pat = '{%s}' % const.ATOM_NS
                if re.match(pat, child.tag):
                    # strip off atom namespace qualification for easier access
                    param_name = child.tag[child.tag.index('}') + 1:]
                else:
                    # leave qualified anything that is not in the atom
                    # namespace
                    param_name = child.tag
                # TODO(IBM): handle links?
                feedprops[param_name] = child.text
        return cls(feedprops, entries)


class Entry(object):
    """Represents an Atom Entry returned by the PowerVM API."""
    def __init__(self, properties, element):
        self.properties = properties
        self.element = Element.wrapelement(element)

    @classmethod
    def unmarshal_atom_entry(cls, entryelem):
        """Factory method producing an Entry object from a parsed ElementTree

        :param entryelem: Parsed ElementTree object representing an atom entry.
        :return: a new Entry object representing the entryelem parameter.
        """
        entryprops = {}
        element = None
        for child in list(entryelem):
            if child.tag == str(QName(const.ATOM_NS, 'content')):
                # PowerVM API only has one element per entry
                element = child[0]
            elif not list(child):
                pat = '{%s}' % const.ATOM_NS
                if re.match(pat, child.tag):
                    # strip off atom namespace qualification for easier access
                    param_name = child.tag[child.tag.index('}') + 1:]
                else:
                    # leave qualified anything that is not in the atom
                    # namespace
                    param_name = child.tag
                if param_name == 'link':
                    entryprops[param_name] = child.get('href')
                    rel = child.get('rel')
                    if rel:
                        if 'links' not in entryprops:
                            entryprops['links'] = {}
                        if rel not in entryprops['links']:
                            entryprops['links'][rel] = []
                        entryprops['links'][rel].append(child.get('href'))
                elif param_name == 'category':
                    entryprops[param_name] = child.get('term')
                elif param_name == '{%s}etag' % const.UOM_NS:
                    entryprops['etag'] = child.text
                elif child.text:
                    entryprops[param_name] = child.text
        return cls(entryprops, element)


class Element(object):
    def __init__(self, tag, ns=const.UOM_NS, attrib=None, text='',
                 children=(), cdata=False):
        # Defaults shouldn't be mutable
        attrib = attrib if attrib else {}
        if ns:
            self.element = etree.Element(str(QName(ns, tag)),
                                         attrib=attrib)
        else:
            self.element = etree.Element(tag, attrib=attrib)
        if text:
            self.element.text = etree.CDATA(text) if cdata else text
        for c in children:
            self.element.append(c.element)

    def __len__(self):
        return len(self.element)

    def __getitem__(self, index):
        return Element.wrapelement(self.element[index])

    def __setitem__(self, index, value):
        if not isinstance(value, Element):
            raise ValueError('Value must be of type Element')
        self.element[index] = value.element

    def __delitem__(self, index):
        del self.element[index]

    def __eq__(self, other):
        if other is None:
            return False
        return self._element_equality(self, other)

    def _element_equality(self, one, two):
        """Tests element equality.

        There is no common mechanism for defining 'equality' in the element
        tree.  This provides a good enough equality that meets the schema
        definition.

        :param one: The first element.  Is the backing element.
        :param two: The second element.  Is the backing element.
        :returns: True if the children, text, attributes and tag are equal.
        """

        # Make sure that the children length is equal
        one_children = one.getchildren()
        two_children = two.getchildren()
        if len(one_children) != len(two_children):
            return False

        # If there are no children, different set of tests
        if len(one_children) == 0:
            if one.text != two.text:
                return False

            if one.tag != two.tag:
                return False
        else:
            # Recursively validate
            for one_child in one_children:
                found = util.find_equivalent(one_child, two_children)
                if found is None:
                    return False

                # Found a match, remove it as it is no longer a valid match.
                # Its equivalence was validated by the upper block.
                two_children.remove(found)

        return True

    def getchildren(self):
        """Returns the children as a list of Elements."""
        return [Element.wrapelement(i) for i in self.element.getchildren()]

    @classmethod
    def wrapelement(cls, element):
        if element is None:
            return None
        e = cls('element')  # create with minimum inputs
        e.element = element  # assign element over the one __init__ creates
        return e

    def toxmlstring(self):
        return etree.tostring(self.element)

    @property
    def tag(self):
        tag = self.element.tag
        m = re.search('\{.*\}(.*)', tag)
        return tag if not m else m.group(1)

    @tag.setter
    def tag(self, tag):
        ns = self.namespace
        if ns:
            self.element.tag = '{%s}%s' % (ns, tag)
        else:
            self.element.tag = tag

    @property
    def namespace(self):
        qtag = self.element.tag
        m = re.search('\{(.*)\}', qtag)
        return m.group(1) if m else ''

    @namespace.setter
    def namespace(self, ns):
        tag = self.tag
        self.element.tag = '{%s}%s' % (ns, tag)

    @property
    def text(self):
        return self.element.text

    @text.setter
    def text(self, text):
        self.element.text = text

    @property
    def attrib(self):
        return self.element.attrib

    @attrib.setter
    def attrib(self, attrib):
        self.element.attrib = attrib

    def get(self, key, default=None):
        """Gets the element attribute named key.

        Returns the attribute value, or default if the attribute was not found.
        """
        return self.element.get(key, default)

    def items(self):
        """Returns the element attributes as a sequence of (name, value) pairs.

        The attributes are returned in an arbitrary order.
        """
        return self.element.items()

    def keys(self):
        """Returns the element attribute names as a list.

        The names are returned in an arbitrary order.
        """
        return self.element.keys()

    def set(self, key, value):
        """Set the attribute key on the element to value."""
        self.element.set(key, value)

    def append(self, subelement):
        """Adds subelement to the end of this element's list of subelements."""
        self.element.append(subelement.element)

    def find(self, match):
        """Finds the first subelement matching match.

        :param match: May be a tag name or path.
        :return: an element instance or None.
        """
        qpath = Element._qualifypath(match, self.namespace)
        e = self.element.find(qpath)
        if e is not None:  # must specify "is not None" here to work
            return Element.wrapelement(e)
        else:
            return None

    def findall(self, match):
        """Finds all matching subelements.

        :param match: May be a tag name or path.
        :return: a list containing all matching elements in document order.
        """
        qpath = Element._qualifypath(match, self.namespace)
        e_iter = self.element.findall(qpath)
        elems = []
        for e in e_iter:
            elems.append(Element.wrapelement(e))
        return elems

    def findtext(self, match, default=None):
        """Finds text for the first subelement matching match.

        :param match: May be a tag name or path.
        :return: the text content of the first matching element, or default
                 if no element was found. Note that if the matching element
                 has no text content an empty string is returned.
        """
        qpath = Element._qualifypath(match, self.namespace)
        text = self.element.findtext(qpath, default)
        return text if text else default

    def insert(self, index, subelement):
        """Inserts subelement at the given position in this element.

        :raises TypeError: if subelement is not an etree.Element.
        """
        self.element.insert(index, subelement.element)

    def iter(self, tag=None):
        """Creates a tree iterator with the current element as the root.

        The iterator iterates over this element and all elements below it, in
        document (depth first) order. If tag is not None or '*', only elements
        whose tag equals tag are returned from the iterator. If the tree
        structure is modified during iteration, the result is undefined.
        """
        # Determine which iterator to use
        # etree.Element.getiterator has been deprecated in favor of
        # etree.Element.iter, but the latter was not added until python 2.7
        if hasattr(self.element, 'iter'):
            lib_iter = self.element.iter
        else:
            lib_iter = self.element.getiterator

        # Fix up the tag value
        if not tag or tag == '*':
            qtag = None
        else:
            qtag = str(QName(self.namespace, tag))

        it = lib_iter(tag=qtag)

        for e in it:
            yield Element.wrapelement(e)

    def replace(self, existing, new_element):
        """Replaces the existing child Element with the new one."""
        self.element.replace(existing.element,
                             new_element.element)

    def remove(self, subelement):
        """Removes subelement from the element.

        Unlike the find* methods this method compares elements based on the
        instance identity, not on tag value or contents.
        """
        self.element.remove(subelement.element)

    @staticmethod
    def _qualifypath(path, ns):
        if not ns:
            return path
        parts = path.split('/')
        for i in range(len(parts)):
            if parts[i] and not re.match('[\.\*\[\{]', parts[i]):
                parts[i] = str(QName(ns, parts[i]))
        return '/'.join(parts)


class ElementIterator(object):
    def __init__(self, it):
        self.it = it

    def __next__(self):
        return Element.wrapelement(next(self.it))


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
            self.oper = Adapter(session, use_cache=False)
            allevents = self.getevents()  # initialize
        except pvmex.Error as e:
            raise pvmex.Error('Failed to initialize event feed listener: %s'
                              % e)
        if not allevents.get('general') == 'init':
            # Something else is sharing this feed!
            raise ValueError('Application id "%s" is not unique' % self.appid)

    def subscribe(self, handler):
        if not isinstance(handler, EventHandler):
            raise ValueError('Handler must be an EventHandler')
        if self.oper is None:
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
        host = self.oper.session.host
        LOG.info('Shutting down EventListener for %s' % host)
        with self._lock:
            for handler in self.handlers:
                self.unsubscribe(handler)
            self.oper = None
        LOG.info('EventListener shutdown complete for %s' % host)

    def getevents(self):

        events = {}

        # Read event feed
        try:
            resp = self.oper.read('Event?QUEUE_CLIENTKEY_METHOD='
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
    @abc.abstractmethod
    def process(self, events):
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


class _EventHandler(EventHandler):
    def __init__(self, the_cache):
        self.cache = the_cache

    def process(self, events):
        for k, v in six.iteritems(events):
            if k == 'general':
                if v == 'invalidate':
                    self.cache.clear()
            elif v in ['delete', 'invalidate']:
                path = util.sanitize_path(urlparse.urlparse(k).path)
                # remove from cache
                self.cache.remove(path)
                # if entry, remove corresponding feeds from cache
                feed_paths = self.cache.get_feed_paths(path)
                for feed_path in feed_paths:
                    self.cache.remove(feed_path)


def unmarshal_httperror(resp):
    # Attempt to extract PowerVM API's HttpErrorResponse object
    try:
        root = etree.fromstring(resp.body)
        if root is not None and root.tag == str(QName(const.ATOM_NS, 'entry')):
            resp.err = Entry.unmarshal_atom_entry(root).element
    except Exception:
        pass


def get_entry_from_feed(feedelem, uuid):
    """Parse atom feed to extract the entry matching to the uuid."""
    if not feedelem:
        return None, None
    uuid = uuid.lower()
    entry = None
    etag = None
    for f_elem in list(feedelem):
        if f_elem.tag == str(QName(const.ATOM_NS, 'entry')):
            etag = None
            for e_elem in list(f_elem):
                if not list(e_elem):
                    pat = '{%s}' % const.ATOM_NS
                    if re.match(pat, e_elem.tag):
                        # Strip off atom namespace qualification for easier
                        # access
                        param_name = (e_elem.tag[e_elem.tag.index('}')
                                                 + 1:len(e_elem.tag)])
                    else:
                        # Leave qualified anything that is not in the atom
                        # namespace
                        param_name = e_elem.tag
                    if param_name == '{%s}etag' % const.UOM_NS:
                        etag = e_elem.text
                    elif param_name == 'id':
                        if e_elem.text.lower() == uuid:
                            entry = etree.tostring(f_elem)

        if entry is not None:
            return entry, etag
    return None, None
