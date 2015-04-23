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

import mock

import unittest

from pypowervm import traits


class TestTraits(unittest.TestCase):

    @mock.patch('pypowervm.adapter.Session')
    def test_traits(self, mock_sess):
        # PVM MC, local auth
        mock_sess.mc_type = 'PVM'
        mock_sess.use_file_auth = True
        t = traits.APITraits(mock_sess)
        self.assertFalse(t.vnet_aware)
        self.assertFalse(t._is_hmc)
        self.assertTrue(t.local_api)
        self.assertFalse(t.has_lpar_profiles)
        self.assertTrue(t.dynamic_pvid)

        # PVM MC, remote auth
        mock_sess.mc_type = 'PVM'
        mock_sess.use_file_auth = False
        t = traits.APITraits(mock_sess)
        self.assertFalse(t.vnet_aware)
        self.assertFalse(t._is_hmc)
        self.assertFalse(t.local_api)
        self.assertFalse(t.has_lpar_profiles)
        self.assertTrue(t.dynamic_pvid)

        # HMC, local auth
        mock_sess.mc_type = 'HMC'
        mock_sess.use_file_auth = True
        t = traits.APITraits(mock_sess)
        self.assertTrue(t.vnet_aware)
        self.assertTrue(t._is_hmc)
        self.assertTrue(t.local_api)
        self.assertTrue(t.has_lpar_profiles)
        self.assertFalse(t.dynamic_pvid)

        # HMC, remote auth
        mock_sess.mc_type = 'HMC'
        mock_sess.use_file_auth = False
        t = traits.APITraits(mock_sess)
        self.assertTrue(t.vnet_aware)
        self.assertTrue(t._is_hmc)
        self.assertFalse(t.local_api)
        self.assertTrue(t.has_lpar_profiles)
        self.assertFalse(t.dynamic_pvid)
