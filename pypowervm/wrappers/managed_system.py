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

import pypowervm.wrappers.constants as c
import pypowervm.wrappers.entry_wrapper as ewrap

import logging

LOG = logging.getLogger(__name__)


class ManagedSystem(ewrap.EntryWrapper):

    def get_system_name(self):
        return self.get_parm_value(c.SYSTEM_NAME)

    def get_model(self):
        return self.get_parm_value(c.MACHINE_MODEL)

    def get_type(self):
        return self.get_parm_value(c.MACHINE_TYPE)

    def get_serial(self):
        return self.get_parm_value(c.MACHINE_SERIAL)

    def get_system_state(self):
        return self.get_parm_value(c.STATE, 'unknown')

    def get_proc_units(self):
        return self.get_parm_value(c.PROC_UNITS_INSTALLED, 0)

    def get_proc_units_configurable(self):
        return self.get_parm_value(c.PROC_UNITS_CONFIGURABLE, 0)

    def get_proc_units_avail(self):
        return self.get_parm_value(c.PROC_UNITS_AVAIL, 0)

    def get_max_sys_procs_limit(self):
        return self.get_parm_value_int(c.MAX_PROCS_PER_PARTITION, 0)

    def get_max_procs_per_aix_linux_lpar(self):
        val = self.get_parm_value_int(c.MAX_PROCS_PER_AIX_LINUX_PARTITION, 0)
        # Some systems will not have maximum procs per lpar based on
        # partition type. In that case, use system max procs per partition.
        if val == 0:
            val = self.get_max_sys_procs_limit()

        return val

    def get_max_sys_vcpus_limit(self):
        return self.get_parm_value_int(c.MAX_VCPUS_PER_PARTITION, 0)

    def get_max_vcpus_per_aix_linux_lpar(self):
        val = self.get_parm_value_int(c.MAX_VCPUS_PER_AIX_LINUX_PARTITION, 0)
        # Some systems will not have maximum vcpus per lpar based on
        # partition type. In that case, use system max vcpus per partition.
        if val == 0:
            val = self.get_max_sys_vcpus_limit()

        return val

    def get_memory_total(self):
        return self.get_parm_value_int(c.MEMORY_INSTALLED, 0)

    def get_memory_free(self):
        return self.get_parm_value_int(c.MEMORY_AVAIL, 0)

    def get_memory_configurable(self):
        return self.get_parm_value_int(c.MEMORY_CONFIGURABLE, 0)

    def get_memory_region_size(self):
        return self.get_parm_value_int(c.MEMORY_REGION_SIZE, 0)

    def get_firmware_memory(self):
        return self.get_parm_value_int(c.SYS_FIRMWARE_MEM, 0)

    def get_host_ip_address(self):
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

    def get_proc_compat_modes(self):
        """List of strings containing the processor compatibility modes."""
        return self.get_parm_values(c.PROC_COMPAT_MODES)

    def get_migration_data(self):
        """returns: The migration properties from PowerVM."""

        max_migr_sup = self.get_parm_value_int(c.MAX_FIRMWARE_MIGR)
        act_migr_sup = self.get_parm_value_int(c.MAX_ACTIVE_MIGR)
        inact_migr_sup = self.get_parm_value_int(c.MAX_INACTIVE_MIGR)
        pref_act_migr_sup = act_migr_sup
        pref_inact_migr_sup = inact_migr_sup
        act_migr_prog = self.get_parm_value_int(c.ACTIVE_MIGR_RUNNING)
        inact_migr_prog = self.get_parm_value_int(c.INACTIVE_MIGR_RUNNING)

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

    def get_vios_links(self):
        """List of hrefs from AssociatedVirtualIOServers."""
        ret_links = []
        vios_links = self._entry.element.findall(c.VIOS_LINK)

        # If we found some VIOSes
        if vios_links:
            for link in vios_links:
                ret_links.append(link.getattrib()['href'])

        return ret_links
