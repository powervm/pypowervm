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

from pypowervm import adapter as adpt
import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

import logging

LOG = logging.getLogger(__name__)

MS_ROOT = 'ManagedSystem'

MTMS_ROOT = 'MachineTypeModelAndSerialNumber'
MTMS_MT = 'MachineType'
MTMS_MODEL = 'Model'
MTMS_SERIAL = 'SerialNumber'


def find_entry_by_mtms(resp, mtms):
    """Queries through a query of ManagedSystem's to find a match.

    :param mtms: The Machine Type Model Number & Serial.
                 Example format: 8247-22L*1234567
    :return: The ManagedSystem wrapper from the response that matches that
             value.  None otherwise.
    """
    mtms_w = MTMS(crt_mtms(mtms))
    entries = resp.feed.findentries(c.MACHINE_SERIAL, mtms_w.serial)
    if entries is None:
        return None

    # Confirm same model and type
    wrappers = [ManagedSystem(x) for x in entries]
    for wrapper in wrappers:
        if wrapper.mtms == mtms_w:
            return wrapper

    # No matching MTM Serial was found
    return None


def crt_mtms(mtms):
    """Converts a MTMS String into an Element that can be used for MTMS Wrapper.

    The MTMS String format is Machine Type - Model Number * Serial
    Example: 8247-22L*1234567
    """
    mtm, sn = mtms.split('*', 1)
    mt, md = mtm.split('-', 1)

    meta = adpt.Element('Metadata', children=[adpt.Element('Atom')])

    return adpt.Element(MTMS_ROOT, children=[meta,
                                             adpt.Element(MTMS_MT, text=mt),
                                             adpt.Element(MTMS_MODEL, text=md),
                                             adpt.Element(MTMS_SERIAL,
                                                          text=sn)])


class ManagedSystem(ewrap.EntryWrapper):

    @property
    def system_name(self):
        return self.get_parm_value(c.SYSTEM_NAME)

    @property
    def mtms(self):
        return MTMS(self._element.find(MTMS_ROOT))

    @property
    def system_state(self):
        return self.get_parm_value(c.STATE, 'unknown')

    @property
    def proc_units(self):
        return self.get_parm_value(c.PROC_UNITS_INSTALLED, 0)

    @property
    def proc_units_configurable(self):
        return self.get_parm_value(c.PROC_UNITS_CONFIGURABLE, 0)

    @property
    def proc_units_avail(self):
        return self.get_parm_value(c.PROC_UNITS_AVAIL, 0)

    @property
    def max_sys_procs_limit(self):
        return self.get_parm_value(c.MAX_PROCS_PER_PARTITION, 0, converter=int)

    @property
    def max_procs_per_aix_linux_lpar(self):
        val = self.get_parm_value(c.MAX_PROCS_PER_AIX_LINUX_PARTITION, 0,
                                  converter=int)
        # Some systems will not have maximum procs per lpar based on
        # partition type. In that case, use system max procs per partition.
        if val == 0:
            val = self.max_sys_procs_limit

        return val

    @max_procs_per_aix_linux_lpar.setter
    def max_procs_per_aix_linux_lpar(self, value):
        self.set_parm_value(c.MAX_PROCS_PER_AIX_LINUX_PARTITION, str(value))

    @property
    def max_sys_vcpus_limit(self):
        return self.get_parm_value(c.MAX_VCPUS_PER_PARTITION, 0, converter=int)

    @property
    def max_vcpus_per_aix_linux_lpar(self):
        val = self.get_parm_value(c.MAX_VCPUS_PER_AIX_LINUX_PARTITION, 0,
                                  converter=int)
        # Some systems will not have maximum vcpus per lpar based on
        # partition type. In that case, use system max vcpus per partition.
        if val == 0:
            val = self.max_sys_vcpus_limit

        return val

    @max_vcpus_per_aix_linux_lpar.setter
    def max_vcpus_per_aix_linux_lpar(self, value):
        self.set_parm_value(c.MAX_VCPUS_PER_AIX_LINUX_PARTITION, str(value))

    @property
    def memory_total(self):
        return self.get_parm_value(c.MEMORY_INSTALLED, 0, converter=int)

    @property
    def memory_free(self):
        return self.get_parm_value(c.MEMORY_AVAIL, 0, converter=int)

    @property
    def memory_configurable(self):
        return self.get_parm_value(c.MEMORY_CONFIGURABLE, 0, converter=int)

    @property
    def memory_region_size(self):
        return self.get_parm_value(c.MEMORY_REGION_SIZE, 0, converter=int)

    @property
    def firmware_memory(self):
        return self.get_parm_value(c.SYS_FIRMWARE_MEM, 0, converter=int)

    @property
    def host_ip_address(self):
        prop = c.HOST_IP_ADDRESS
        val = self.get_parm_value(prop)

        return val

    def get_capabilities(self):
        """returns: The system capabilities from Power."""
        # VirtualEthernetCustomMACAddressCapable (custom_mac_addr_capable) will
        # default to True, which is the correct setting for POWER7 servers.
        cap_data = {'active_lpar_mobility_capable':
                    self.get_parm_value_bool(c.ACTIVE_LPM_CAP),
                    'inactive_lpar_mobility_capable':
                    self.get_parm_value_bool(c.INACTIVE_LPM_CAP),
                    'ibmi_lpar_mobility_capable':
                    self.get_parm_value_bool(c.IBMi_LPM_CAP, False),
                    'custom_mac_addr_capable':
                    self.get_parm_value_bool(c.VETH_MAC_ADDR_CAP, True),
                    'ibmi_restrictedio_capable':
                    self.get_parm_value_bool(c.IBMi_RESTRICTEDIO_CAP, False)
                    }
        return cap_data

    @property
    def proc_compat_modes(self):
        """List of strings containing the processor compatibility modes.

        This is a READ-ONLY list.
        """
        return tuple(self.get_parm_values(c.PROC_COMPAT_MODES))

    @property
    def migration_data(self):
        """returns: The migration properties from PowerVM.

        This information should not be changed and should be treated as read
        only.
        """

        max_migr_sup = self.get_parm_value(c.MAX_FIRMWARE_MIGR, converter=int)
        act_migr_sup = self.get_parm_value(c.MAX_ACTIVE_MIGR, converter=int)
        inact_migr_sup = self.get_parm_value(c.MAX_INACTIVE_MIGR,
                                             converter=int)
        pref_act_migr_sup = act_migr_sup
        pref_inact_migr_sup = inact_migr_sup
        act_migr_prog = self.get_parm_value(c.ACTIVE_MIGR_RUNNING,
                                            converter=int)
        inact_migr_prog = self.get_parm_value(c.INACTIVE_MIGR_RUNNING,
                                              converter=int)

        migr_data = {'max_migration_ops_supported': max_migr_sup,
                     'active_migrations_supported': act_migr_sup,
                     'inactive_migrations_supported': inact_migr_sup,
                     'preferred_active_migrations_supported':
                     pref_act_migr_sup,
                     'preferred_inactive_migrations_supported':
                     pref_inact_migr_sup,
                     'active_migrations_in_progress': act_migr_prog,
                     'inactive_migrations_in_progress': inact_migr_prog,
                     }
        return migr_data

    @property
    def vios_links(self):
        """List of hrefs from AssociatedVirtualIOServers.

        This is a READ-ONLY list.
        """
        return self.get_href(c.VIOS_LINK)


class MTMS(ewrap.ElementWrapper):
    """The Machine Type, Model and Serial Number wrapper."""

    @property
    def machine_type(self):
        return self.get_parm_value(MTMS_MT)

    @property
    def model(self):
        return self.get_parm_value(MTMS_MODEL)

    @property
    def serial(self):
        return self.get_parm_value(MTMS_SERIAL)

    def mtms_str(self):
        """Builds a string representation of the MTMS.

        Does not override default __str__ as that is useful for debug
        purposes.
        """
        return self.machine_type + '-' + self.model + '*' + self.serial
