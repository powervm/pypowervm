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

import logging
import unittest

from pypowervm.tests.wrappers.util import pvmhttp
import pypowervm.wrappers.management_console as mc

_MC_HTTPRESP_FILE = "managementconsole.txt"
_MC_SSH_HTTPRESP_FILE = "managementconsole_ssh.txt"


logging.basicConfig()

_MGND_SYS = ('https://9.1.2.3:12443/rest/api/uom/ManagementConsole/b3416a32-4'
             '6f9-3df9-819e-39349001af0c/ManagedSystem/a168a3ec-bb3e-3ead-86c'
             '1-7d98b9d50239', 'https://9.1.2.3:12443/rest/api/uom/Management'
             'Console/b3416a32-46f9-3df9-819e-39349001af0c/ManagedSystem/caae'
             '9209-25e5-35cd-a71a-ed55c03f294d')

_PUB_KEY = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCuA/Av0jMYlG54YitgxQXho8iO'
            'ZfY+WkBnuFfweESZOy824Ce9FvPqXsNL+nPAgKWG3TONwJldYgCgnBsFXUizkcne'
            '9Dt/T/zs2Bzl7b1YPrXyYS1hxKFrV/pYEERUiFa9ppR+M8mxdNYO0+ph356LO3mb'
            'xOM6nEZ1L6l6RUvbUwV9Zuw3Hpiz1lAV6d6EwMHJZ+WFlipJ2wxpM4QUKmb0V2UJ'
            'oHAb7tp3zipr3CCo0NtnpcD7wxsFhtz2ccRvNMbGhe1i9KikmBtQQDl1adMSbBL2'
            '+tGmyqHNq/H6d75bfXOUCl7NKtUq7VVGcXDOlTS1CDdLdmUn0l4z0AlyciQt wlp'
            '@9.0.0.0')
_AUTH_KEYS = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3shE8yLGII+BPaPMIOdNgA6'
              'ZyDYKobCtXE6td8X9dgI0Sz08YCUQY9pOeWr/D63LwJaYsgqVspQaUEM5WH6s2'
              'eNKAERYayog6iCEaqApDDQETuf4XQ0JXo08izRPpMeRZwp3/RhNJVrxNheUp9n'
              'kHI3Mbx7jHvgwih48BTeqfj8L1Nnp4srhYDuzuN6NhUvbWLKJAjaQojRLSYEty'
              's5ASq7v+D+OEXqVBSRheKf5eWOdEF68sBYpOaS4qLycZjd5YGPUg0b+DfME2jr'
              '8kjbig1js8omgljSvKIwHIKfrfWPwKbWxtHaqWzTT+fUPygD7IDxPqsSEQIAjN'
              'PWmWQM+D wlp@9.0.0.0',
              'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCyl3+yXyoYAzvScxTiWqxe0P'
              'DwYvTHwLsIkgAY7s7n+8tUR7zA0dYWggl4aCfOAE2RMF0zKoFyRK8a9M/I1kVC'
              'YLb9y1rWp76jnxZpRBD/1DjjQ0qW5e1fbdrS52mJcFLL1+MzeoLT7+6GeMUcgN'
              'rmZQMUqSbwF+Rdxv56YTdx9u0EH1qaT/H0syp1Y8EHCaBVwdZcmNQLBFaYnVxH'
              'NHTQMYMTqokkyrZ9whSaK98OiYQO//5gnJzESOxOURYTzLKLz8WPkiONM6QgF+'
              'E5Zobt/REr3Tq8l1e1V/e2+7owFkMMte14I2sfK8QnZUrpJziXv3gwOpUP34gD'
              'ud6ceBlv wlp@9.0.0.0')


class TestMCEntryWrapper(unittest.TestCase):

    def setUp(self):
        super(TestMCEntryWrapper, self).setUp()

        mc_http = pvmhttp.load_pvm_resp(_MC_HTTPRESP_FILE)
        self.assertNotEqual(mc_http, None,
                            "Could not load %s" %
                            _MC_HTTPRESP_FILE)
        self.wrapper = mc.Console.wrap(mc_http.response.feed.entries[0])

        mc_http = pvmhttp.load_pvm_resp(_MC_SSH_HTTPRESP_FILE)
        self.assertNotEqual(mc_http, None,
                            "Could not load %s" %
                            _MC_SSH_HTTPRESP_FILE)
        self.ssh_wrap = mc.Console.wrap(mc_http.response.feed.entries[0])

    def test_mgm_console(self):
        self.assertEqual(self.wrapper.name, "hmc7")

        self.assertEqual(self.wrapper.mtms.model, "f93")

        self.assertEqual(self.wrapper.mtms.machine_type, "Ve57")

        self.assertEqual(self.wrapper.mtms.serial, "2911559")

        self.assertEqual(_MGND_SYS, self.wrapper.mgnd_sys_links)

        con_inf = self.wrapper.network_infaces.console_interface
        self.assertEqual('eth0', con_inf.name)
        self.assertEqual('9.1.2.3 fe80:0:0:0:5054:ff:fed8:a951',
                         con_inf.address)

        self.assertEqual(_PUB_KEY, self.ssh_wrap.ssh_public_key)
        self.assertEqual(_AUTH_KEYS, self.ssh_wrap.ssh_authorized_keys)
