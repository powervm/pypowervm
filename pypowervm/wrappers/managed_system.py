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

MS_ROOT = 'ManagedSystem'

MTMS_ROOT = 'MachineTypeModelAndSerialNumber'
MTMS_MT = 'MachineType'
MTMS_MODEL = 'Model'
MTMS_SERIAL = 'SerialNumber'


def find_entry_by_mtms(resp, mtms):
    """Queries through a query of ManagedSystem's to find a match.

    :param mtms: The Machine Type Model & Serial Number string.
                 Example format: "8247-22L*1234567"
    :return: The ManagedSystem wrapper from the response that matches that
             value.  None otherwise.
    """
    mtms_w = MTMS(mtms_str=mtms)
    entries = resp.feed.findentries(c.MACHINE_SERIAL, mtms_w.serial)
    if entries is None:
        return None

    # Confirm same model and type
    wrappers = [ManagedSystem.load(entry=x) for x in entries]
    for wrapper in wrappers:
        if wrapper.mtms == mtms_w:
            return wrapper

    # No matching MTM Serial was found
    return None


class ManagedSystem(ewrap.EntryWrapper):
    schema_type = c.SYS

    @property
    def system_name(self):
        return self._get_val_str(c.SYSTEM_NAME)

    @property
    def mtms(self):
        return MTMS.load(element=self._element.find(MTMS_ROOT))

    @property
    def system_state(self):
        return self._get_val_str(c.STATE, 'unknown')

    @property
    def proc_units(self):
        return self._get_val_str(c.PROC_UNITS_INSTALLED, 0)

    @property
    def proc_units_configurable(self):
        return self._get_val_str(c.PROC_UNITS_CONFIGURABLE, 0)

    @property
    def proc_units_avail(self):
        return self._get_val_str(c.PROC_UNITS_AVAIL, 0)

    @property
    def max_sys_procs_limit(self):
        return self._get_val_int(c.MAX_PROCS_PER_PARTITION, 0)

    @property
    def max_procs_per_aix_linux_lpar(self):
        val = self._get_val_int(c.MAX_PROCS_PER_AIX_LINUX_PARTITION, 0)
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
        return self._get_val_int(c.MAX_VCPUS_PER_PARTITION, 0)

    @property
    def max_vcpus_per_aix_linux_lpar(self):
        val = self._get_val_int(c.MAX_VCPUS_PER_AIX_LINUX_PARTITION, 0)
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
        return self._get_val_int(c.MEMORY_INSTALLED, 0)

    @property
    def memory_free(self):
        return self._get_val_int(c.MEMORY_AVAIL, 0)

    @property
    def memory_configurable(self):
        return self._get_val_int(c.MEMORY_CONFIGURABLE, 0)

    @property
    def memory_region_size(self):
        return self._get_val_int(c.MEMORY_REGION_SIZE, 0)

    @property
    def firmware_memory(self):
        return self._get_val_int(c.SYS_FIRMWARE_MEM, 0)

    @property
    def host_ip_address(self):
        prop = c.HOST_IP_ADDRESS
        val = self._get_val_str(prop)

        return val

    def get_capabilities(self):
        """returns: The system capabilities from Power."""
        # VirtualEthernetCustomMACAddressCapable (custom_mac_addr_capable) will
        # default to True, which is the correct setting for POWER7 servers.
        cap_data = {'active_lpar_mobility_capable':
                    self._get_val_bool(c.ACTIVE_LPM_CAP),
                    'inactive_lpar_mobility_capable':
                    self._get_val_bool(c.INACTIVE_LPM_CAP),
                    'ibmi_lpar_mobility_capable':
                    self._get_val_bool(c.IBMi_LPM_CAP, False),
                    'custom_mac_addr_capable':
                    self._get_val_bool(c.VETH_MAC_ADDR_CAP, True),
                    'ibmi_restrictedio_capable':
                    self._get_val_bool(c.IBMi_RESTRICTEDIO_CAP, False)
                    }
        return cap_data

    @property
    def proc_compat_modes(self):
        """List of strings containing the processor compatibility modes.

        This is a READ-ONLY list.
        """
        return tuple(self._get_vals(c.PROC_COMPAT_MODES))

    @property
    def migration_data(self):
        """returns: The migration properties from PowerVM.

        This information should not be changed and should be treated as read
        only.
        """

        max_migr_sup = self._get_val_int(c.MAX_FIRMWARE_MIGR)
        act_migr_sup = self._get_val_int(c.MAX_ACTIVE_MIGR)
        inact_migr_sup = self._get_val_int(c.MAX_INACTIVE_MIGR)
        pref_act_migr_sup = act_migr_sup
        pref_inact_migr_sup = inact_migr_sup
        act_migr_prog = self._get_val_int(c.ACTIVE_MIGR_RUNNING)
        inact_migr_prog = self._get_val_int(c.INACTIVE_MIGR_RUNNING)

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
    schema_type = 'MachineTypeModelAndSerialNumber'
    has_metadata = True

    def __init__(self, mtms_str=None, machine_type=None, model=None,
                 serial=None):
        """Creates a new MTMS ElementWrapper.

        If mtms_str is specified, it is parsed first.

        If machine_type, model, and/or serial is specified, their values are
        used, overriding any parsed values from mtms_str.

        :param mtms_str: String representation of Machine Type, Model,
        and Serial
                     Number.  The format is
                     Machine Type - Model Number * Serial
                     Example: 8247-22L*1234567
        :param machine_type: String representing Machine Type.  Four
                             alphanumeric characters.
        :param model: String representing Model Number.  Three alphanumeric
                      characters.
        :param serial: String representing Serial Number.  Seven alphanumeric
                       characters.
        """
        super(MTMS, self).__init__()
        if mtms_str is not None:
            mtm, sn = mtms_str.split('*', 1)
            mt, md = mtm.split('-', 1)

            # Assignment order is significant
            self.machine_type = mt
            self.model = md
            self.serial = sn
        if machine_type:
            self.machine_type = machine_type
        if model:
            self.model = model
        if serial:
            self.serial = serial

    @property
    def machine_type(self):
        return self._get_val_str(MTMS_MT)

    @machine_type.setter
    def machine_type(self, mt):
        self.set_parm_value(MTMS_MT, mt)

    @property
    def model(self):
        return self._get_val_str(MTMS_MODEL)

    @model.setter
    def model(self, md):
        self.set_parm_value(MTMS_MODEL, md)

    @property
    def serial(self):
        return self._get_val_str(MTMS_SERIAL)

    @serial.setter
    def serial(self, sn):
        self.set_parm_value(MTMS_SERIAL, sn)

    @property
    def mtms_str(self):
        """Builds a string representation of the MTMS.

        Does not override default __str__ as that is useful for debug
        purposes.
        """
        return self.machine_type + '-' + self.model + '*' + self.serial
