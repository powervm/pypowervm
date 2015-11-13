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

import unittest

import mock
import requests.models as req_mod
import requests.structures as req_struct

import pypowervm.adapter as adp
import pypowervm.tests.lib as testlib
from pypowervm.tests.test_utils import pvmhttp
from pypowervm import traits
import pypowervm.wrappers.entry_wrapper as ewrap
import pypowervm.wrappers.network as net
import pypowervm.wrappers.storage as stor

_logon_response_text = testlib.file2b("logon_file.xml")
_feed_file = pvmhttp.load_pvm_resp(
    "fake_network_bridge.txt").response.body.encode('utf-8')
_entry_file = pvmhttp.load_pvm_resp(
    "fake_volume_group.txt").response.body.encode('utf-8')


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
        self.assertTrue(t.rmdev_job_available)
        self.assertTrue(t.has_high_slot)
        self.assertTrue(t.vea_as_ibmi_console)

        # PVM MC, remote auth
        mock_sess.mc_type = 'PVM'
        mock_sess.use_file_auth = False
        t = traits.APITraits(mock_sess)
        self.assertFalse(t.vnet_aware)
        self.assertFalse(t._is_hmc)
        self.assertFalse(t.local_api)
        self.assertFalse(t.has_lpar_profiles)
        self.assertTrue(t.dynamic_pvid)
        self.assertTrue(t.rmdev_job_available)
        self.assertTrue(t.has_high_slot)
        self.assertTrue(t.vea_as_ibmi_console)

        # HMC, remote auth
        mock_sess.mc_type = 'HMC'
        mock_sess.use_file_auth = False
        t = traits.APITraits(mock_sess)
        self.assertTrue(t.vnet_aware)
        self.assertTrue(t._is_hmc)
        self.assertFalse(t.local_api)
        self.assertTrue(t.has_lpar_profiles)
        self.assertFalse(t.dynamic_pvid)
        self.assertFalse(t.rmdev_job_available)
        self.assertFalse(t.has_high_slot)
        self.assertFalse(t.vea_as_ibmi_console)

    @mock.patch('requests.Session.request')
    def test_traits_into_wrappers(self, mock_request):
        # Note traits param is None, which reflects the real value of
        # self.traits during _logon's request.
        httpresp = req_mod.Response()
        httpresp._content = _logon_response_text
        httpresp.status_code = 200
        httpresp.headers = req_struct.CaseInsensitiveDict(
            {'X-MC-Type': 'PVM',
             'content-type':
                 'application/vnd.ibm.powervm.web+xml; type=LogonResponse'})
        mock_request.return_value = httpresp
        sess = adp.Session()
        self.assertEqual('PVM', sess.mc_type)
        self.assertIsNotNone(sess.traits)
        self.assertTrue(sess.traits.local_api)
        self.assertFalse(sess.traits._is_hmc)
        adapter = adp.Adapter(sess)
        self.assertEqual(sess.traits, adapter.traits)

        # Response => Feed => Entrys => EntryWrappers => sub-ElementWrappers
        httpresp._content = _feed_file
        resp = adapter.read('NetworkBridge')
        self.assertEqual(sess.traits, resp.adapter.traits)
        nblist = net.NetBridge.wrap(resp)
        for nb in nblist:
            self.assertIsInstance(nb, net.NetBridge)
            self.assertEqual(sess.traits, nb.traits)
        seas = nblist[0].seas
        for sea in seas:
            self.assertIsInstance(sea, net.SEA)
            self.assertEqual(sess.traits, sea.traits)
        trunk = seas[0].primary_adpt
        self.assertIsInstance(trunk, net.TrunkAdapter)
        self.assertEqual(sess.traits, trunk.traits)

        # Response => Entry => EntryWrapper => sub-EntryWrappers
        # => sub-sub-ElementWrapper
        httpresp._content = _entry_file
        resp = adapter.read('VolumeGroup', root_id='abc123')
        self.assertEqual(sess.traits, resp.adapter.traits)
        vgent = stor.VG.wrap(resp)
        self.assertIsInstance(vgent, stor.VG)
        self.assertEqual(sess.traits, vgent.traits)
        pvs = vgent.phys_vols
        for pvent in pvs:
            self.assertIsInstance(pvent, stor.PV)
            self.assertEqual(sess.traits, pvent.traits)

        # Building raw wrappers from scratch
        class MyEntryWrapper(ewrap.EntryWrapper):
            schema_type = 'SomeObject'

            @classmethod
            def bld(cls, adpt):
                return super(MyEntryWrapper, cls)._bld(adpt)

        mew = MyEntryWrapper.bld(adapter)
        self.assertIsInstance(mew, MyEntryWrapper)
        self.assertEqual(sess.traits, mew.traits)

        class MyElementWrapper(ewrap.ElementWrapper):
            schema_type = 'SomeObject'

            @classmethod
            def bld(cls, adpt):
                return super(MyElementWrapper, cls)._bld(adpt)

        mew = MyElementWrapper.bld(adapter)
        self.assertIsInstance(mew, MyElementWrapper)
        self.assertEqual(sess.traits, mew.traits)

if __name__ == '__main__':
    unittest.main()
