# Copyright 2015 IBM Corp.
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
import unittest

import six

from pypowervm.tests.wrappers.util import pvmhttp


@six.add_metaclass(abc.ABCMeta)
class TestWrapper(unittest.TestCase):
    """Superclass for wrapper test cases; provides loading of data files.

    A single subclass tests a single wrapper class on a single file.

    Usage:
    o Subclass this class.
    o Provide the name of the data file to load, e.g.
        file = 'ssp.txt'
    o Indicate the wrapper class to be tested, e.g.
        wrapper_class_to_test = clust.SharedStoragePool
    o No __init__ or setUp is necessary.
    o In your test cases, make use of the following variables:
        - self.resp: The raw Response object from
          load_pvm_resp().get_response().  May represent an entry or a feed.
        - self.dwrap: A single instance of the wrapper_class_to_test extracted
          from self.resp.  If self.resp was a feed, this is the first entry.
        - self.entries: The result of load_from_response of the wrapper class.
          May be a single wrapper instance, in which case it's (nearly*)
          equivalent to self.dwrap, or a list of such wrappers.
          * Note that load_from_response injects each entry's etag into the
            wrapper instance.
    """

    # Load the response file just once
    _pvmfile = None

    @abc.abstractproperty
    def file(self):
        return None

    @abc.abstractproperty
    def wrapper_class_to_test(self):
        return None

    def setUp(self):
        super(TestWrapper, self).setUp()
        # Load the file just once...
        if self.__class__._pvmfile is None:
            self.__class__._pvmfile = pvmhttp.PVMFile(self.file)
        # ...but reconstruct the PVMResp every time
        self.resp = pvmhttp.PVMResp(
            pvmfile=self.__class__._pvmfile).get_response()
        # Some wrappers don't support etag.  Subclasses testing those wrappers
        # should not be using self.entries, so ignore.
        try:
            self.entries = self.wrapper_class_to_test.load_from_response(
                self.resp)
        except TypeError:
            pass
        if self.resp.feed:
            self.dwrap = self.wrapper_class_to_test(
                self.resp.feed.entries[0])
        else:
            self.dwrap = self.wrapper_class_to_test(self.resp.entry)