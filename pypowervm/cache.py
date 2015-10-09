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

"""Caching of PowerVM REST API responses. Disabled by default."""

import copy
import datetime as dt
import threading

from oslo_log import log as logging

from pypowervm import util

# Set up logging
LOG = logging.getLogger(__name__)

cachesize = 1024


class _Cache(object):
    def __init__(self, host, order='byaccess'):
        if order not in ['byaccess', 'byadd']:
            raise ValueError('invalid order=%s', order)
        self._order = order
        self._keys = []
        self._data = {}
        self._lock = threading.RLock()
        self.host = host

    def __iter__(self):
        # use deepcopy so that the contents can't be changed
        return copy.deepcopy(self._data).__iter__()

    def clear(self):
        with self._lock:
            LOG.debug("%s cache cleared" % self.host)
            self._keys = []
            self._data = {}

    def get(self, key, age=-1):
        if not age:
            return
        with self._lock:
            if key in self._keys:
                if self._order == 'byaccess':
                    # keep keys in least-accessed-first order
                    self._keys.append(self._keys.pop(self._keys.index(key)))
                (t, d) = self._data.get(key, (dt.timedelta(0), None))
                if d is not None:
                    if age < 0 or (dt.datetime.now() - t <
                                   dt.timedelta(seconds=age)):
                        LOG.debug("%s cache get for %s" % (self.host, key))
                        return copy.deepcopy(d)

    def set(self, key, value):
        if not key:
            raise ValueError('key must not be empty')
        if not value:
            raise ValueError('value must not be empty')
        with self._lock:
            LOG.debug("%s cache set for %s" % (self.host, key))

            if key not in self._keys:
                # new add, nothing already there
                self._keys.append(key)
                if len(self._keys) > cachesize:
                    # limit the size of the cache
                    rem_key = self._keys.pop(0)
                    LOG.debug("%s cache overflow for %s" %
                              (self.host, rem_key))
                    del self._data[rem_key]
            elif self._order == 'byaccess':
                # keep paths in least-accessed-first order
                self._keys.append(self._keys.pop(self._keys.index(key)))

            # deepcopy of value is the responsibility of the caller
            self._data[key] = (dt.datetime.now(), value)

    def touch(self, key):
        with self._lock:
            if key not in self._keys:
                LOG.debug("%s cache touch did not find %s" % (self.host, key))
            else:
                LOG.debug("%s cache touch for %s" % (self.host, key))
                self._keys.append(self._keys.pop(self._keys.index(key)))
                (t, d) = self._data.get(key, (0, None))
                self._data[key] = (dt.datetime.now(), d)

    def remove(self, key):
        with self._lock:
            if key in self._keys:
                LOG.debug("%s cache remove for %s" % (self.host, key))
                self._keys.remove(key)
                del self._data[key]


class _PVMCache(_Cache):
    def __init__(self, host, order='byaccess'):
        super(_PVMCache, self).__init__(host, order)
        # keep track of uuid & its links
        # this is used to figure out all the feed path
        # entry should only be remove if entry is deleted
        self._uuid_feeds_map = {}

    def clear(self):
        with self._lock:
            self._uuid_feeds_map = {}
            super(_PVMCache, self).clear()

    def get(self, key, age=-1):
        return super(_PVMCache, self).get(self._get_internal_key(key), age)

    # TODO(IBM): Base class override with different signature.
    def set(self, key, paths, value):
        if not key:
            raise ValueError('key must not be empty')
        if not paths:
            raise ValueError('paths must not be empty')
        if not value:
            raise ValueError('value must not be empty')
        with self._lock:
            i_key = self._get_internal_key(key)
            LOG.debug("%s cache set for %s" % (self.host, i_key))
            if i_key not in self._keys:
                # new add, nothing already there
                self._keys.append(i_key)
                if len(self._keys) > cachesize:
                    # limit the size of the cache
                    rem_key = self._keys.pop(0)
                    LOG.debug("%s cache overflow for %s" %
                              (self.host, rem_key))
                    del self._data[rem_key]
            elif self._order == 'byaccess':
                # keep paths in least-accessed-first order
                self._keys.append(self._keys.pop(self._keys.index(i_key)))
            entry_uuid = self._get_entry_uuid(key)

            if entry_uuid:
                feedpaths = []
                for path in paths:
                    feedpaths.append(path.rsplit('/', 1)[0])
                self._update_feed_paths(entry_uuid.lower(), feedpaths)
            # deepcopy of value is the responsibility of the caller
            self._data[i_key] = (dt.datetime.now(), value)

    def touch(self, key):
        super(_PVMCache, self).touch(self._get_internal_key(key))

    def remove(self, key, delete=False):
        with self._lock:
            i_key = self._get_internal_key(key.split('?', 1)[0])
            keys_to_remove = []
            for k in self._keys:
                if k == i_key or k.startswith(i_key + '?'):
                    keys_to_remove.append(k)
            for k in keys_to_remove:
                LOG.debug("%s cache remove for %s via %s" % (self.host,
                                                             k, key))
                self._keys.remove(k)
                del self._data[k]
                entry_uuid = util.get_req_path_uuid(key)
                if delete and entry_uuid:
                    # change this part
                    del self._uuid_feeds_map[entry_uuid]

    @staticmethod
    def _get_internal_key(key):
        # extract the internal key from the path. If it's a feed, leave the
        # key as is. Otherwise, it's uuid?group=xag
        uuid, xag_str = util.get_uuid_xag_from_path(key)
        if not uuid:
            return key
        return uuid + '?group=' + xag_str if xag_str else uuid

    def get_feed_paths(self, key):
        with self._lock:
            feed_paths = []
            entry_uuid, xag_str = util.get_uuid_xag_from_path(key)
            if entry_uuid:
                default_feed_path = key.rsplit('/', 1)[0]
                keys = self._uuid_feeds_map.get(entry_uuid.lower(), [])
                if default_feed_path not in keys:
                    keys = self._update_feed_paths(entry_uuid.lower(),
                                                   [default_feed_path])
                for k in keys:
                    if xag_str:
                        feed_paths.append(k + '?group=' + xag_str)
                    else:
                        feed_paths.append(k)
            LOG.debug('key %s feed_paths = %s' % (key, feed_paths))
            return feed_paths

    def _update_feed_paths(self, entry_uuid, new_paths):
        with self._lock:
            paths = self._uuid_feeds_map.get(entry_uuid, [])
            if not paths:
                self._uuid_feeds_map[entry_uuid] = new_paths
            else:
                for n in new_paths:
                    if n not in paths:
                        paths.append(n)
                self._uuid_feeds_map[entry_uuid] = paths
            return paths
