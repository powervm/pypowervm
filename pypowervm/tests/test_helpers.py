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

import functools
import unittest

import mock

import pypowervm.adapter as adp


def cat_string_helper(func, string):
    def wrapper(*args, **kwds):
        return func(*args, **kwds) + string
    return wrapper


class TestHelpers(unittest.TestCase):
    def test_none(self):
        adpt = adp.Adapter('mock_session', helpers=None)
        self.assertEqual([], adpt.helpers)

    def test_single(self):
        hlp = functools.partial(cat_string_helper, string="purple!")
        adpt = adp.Adapter('mock_session', helpers=hlp)
        self.assertEqual([hlp], adpt.helpers)

    def test_single_list(self):
        hlp = functools.partial(cat_string_helper, string="purple!")
        hlp_list = [hlp]
        adpt = adp.Adapter('mock_session', helpers=hlp_list)
        self.assertEqual(hlp_list, adpt.helpers)
        # Use this test to ensure the list returned is a copy
        self.assertNotEqual(id(hlp_list), id(adpt.helpers))

    def test_multi_list(self):
        hlp1 = functools.partial(cat_string_helper, string="1")
        hlp2 = functools.partial(cat_string_helper, string="2")
        adpt = adp.Adapter('mock_session',
                           helpers=[hlp1, hlp2])
        self.assertEqual([hlp1, hlp2], adpt.helpers)

    @mock.patch('pypowervm.adapter.Session')
    def test_no_helpers(self, mock_sess):

        mock_sess.request.return_value = 'ReturnValue'
        adpt = adp.Adapter(mock_sess)
        self.assertEqual('ReturnValue',
                         adpt._request('method', 'path'))

    @mock.patch('pypowervm.adapter.Session')
    def test_runs(self, mock_sess):

        hlp1 = functools.partial(cat_string_helper, string="1")
        hlp2 = functools.partial(cat_string_helper, string="2")
        hlp3 = functools.partial(cat_string_helper, string="3")

        mock_sess.request.return_value = 'countdown:'
        adpt = adp.Adapter(
            mock_sess, helpers=[hlp1, hlp2, hlp3])
        self.assertEqual('countdown:321',
                         adpt._request('method', 'path'))

        # Override adapter helpers
        self.assertEqual('countdown:2',
                         adpt._request('method', 'path', helpers=hlp2))

        # No adapter helpers, but request helper
        adpt = adp.Adapter(mock_sess)
        self.assertEqual('countdown:1',
                         adpt._request('method', 'path', helpers=[hlp1]))

    @mock.patch('pypowervm.adapter.Session')
    def test_invalid_helper(self, mock_sess):

        hlp = "bad helper, shame on you"

        mock_sess.request.return_value = 'Should not get returned'
        adpt = adp.Adapter(mock_sess, helpers=hlp)
        with self.assertRaises(TypeError):
            adpt._request('method', 'path')

        adpt = adp.Adapter(mock_sess)
        with self.assertRaises(TypeError):
            adpt._request('method', 'path', helpers=[hlp])
