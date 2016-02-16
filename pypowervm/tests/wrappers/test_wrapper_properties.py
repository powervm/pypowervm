# Copyright 2016 IBM Corp.
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

"""Tests for properties of EntryWrapper/ElementWrapper subclasses."""

import testtools

import pypowervm.const as c
from pypowervm.utils import wrappers as wutil
from pypowervm.wrappers import base_partition as bp
from pypowervm.wrappers import enterprise_pool as epool
from pypowervm.wrappers import entry_wrapper as ewrap
from pypowervm.wrappers import logical_partition as lpar
from pypowervm.wrappers import virtual_io_server as vios


class TestXAGs(testtools.TestCase):

    def verify_xags(self, wcls, expected_xags):
        """Verify extended attribute groups for properties of a wrapper class.

        :param wcls: The pypowervm.wrappers.entry_wrapper.Wrapper subclass to
                     test.
        :param expected_xags: A dict mapping wcls's property names to their
                              respective extended attribute group names.  Can
                              (should) only include those properties for which
                              an extended attribute group is registered.  (If
                              it contains any other properties, the value must
                              be None.)  Format is { prop_name: xag_name }
        """
        for prop in dir(wcls):
            actual = wcls.get_xag_for_prop(prop)
            expected = expected_xags.get(prop, None)
            self.assertEqual(expected, actual,
                             message="%s.%s" % (wcls.__name__, prop))

    def test_xags(self):
        """Verify xags associated with properties of wrapper classes."""
        # The following wrapper classes have no properties with xags
        for wcls in wutil.wrapper_class_iter():
            if wcls is vios.VIOS:
                self.verify_xags(wcls, {
                    'media_repository': c.XAG.VIO_STOR,
                    'ip_addresses': c.XAG.VIO_NET,
                    'vfc_mappings': c.XAG.VIO_FMAP,
                    'scsi_mappings': c.XAG.VIO_SMAP,
                    'seas': c.XAG.VIO_NET,
                    'trunk_adapters': c.XAG.VIO_NET,
                    'phys_vols': c.XAG.VIO_STOR,
                    'io_adpts_for_link_agg': c.XAG.VIO_NET,
                    'nvram': c.XAG.NVRAM,
                })
            elif wcls is epool.Pool:
                self.verify_xags(wcls, {
                    'compliance_hours_left': c.XAG.ADV
                })
            elif wcls is epool.PoolMember:
                self.verify_xags(wcls, {
                    'proc_compliance_hours_left': c.XAG.ADV,
                    'mem_compliance_hours_left': c.XAG.ADV
                })
            elif wcls in (bp.BasePartition, lpar.LPAR):
                self.verify_xags(wcls, {
                    'nvram': c.XAG.NVRAM
                })
            # Include an elif for each Wrapper subclass that has xags defined.
            else:
                self.verify_xags(wcls, {})

    def test_wrapper_registration(self):
        """All wrapper subclasses must be registered via [base_]pvm_type."""
        for wcls in wutil.wrapper_class_iter():
            if wcls not in (ewrap.Wrapper, ewrap.ElementWrapper,
                            ewrap.EntryWrapper):
                self.assertTrue(wcls._registered,
                                "%s not registered" % wcls.__name__)
