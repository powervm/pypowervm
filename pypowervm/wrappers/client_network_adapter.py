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

import logging

import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

LOG = logging.getLogger(__name__)


class ClientNetworkAdapter(ewrap.EntryWrapper):
    """Wrapper object for ClientNetworkAdapter schema."""

    @property
    def slot(self):
        return int(self.get_parm_value(c.VIR_SLOT_NUM))

    @property
    def mac(self):
        """Returns the Mac Address for the adapter.

        Typical format would be: AABBCCDDEEFF
        The API returns a format with no colons and is upper cased.
        """
        return self.get_parm_value(c.MAC_ADDRESS)

    @property
    def pvid(self):
        """Returns the Port VLAN ID."""
        return self.get_parm_value_int(c.PORT_VLAN_ID)
