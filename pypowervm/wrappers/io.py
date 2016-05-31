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

"""Wrappers, constants, and helpers around IOAdapter and its children."""
import pypowervm.wrappers.entry_wrapper as ewrap

# Constants for generic I/O Adapter
IO_ADPT_ROOT = 'IOAdapter'
_IO_ADPT_ID = 'AdapterID'
_IO_ADPT_DESC = 'Description'
_IO_ADPT_DEV_NAME = 'DeviceName'
_IO_ADPT_DEV_TYPE = 'DeviceType'
_IO_ADPT_DYN_NAME = 'DynamicReconfigurationConnectorName'
_IO_ADPT_PHYS_LOC = 'PhysicalLocation'
_IO_ADPT_UDID = 'UniqueDeviceID'
_IO_ADPT_CHOICE = 'IOAdapterChoice'

# SR-IOV Adapter constants
_SRIOV_ADAPTER_MODE = 'AdapterMode'

# Physical Fibre Channel Port Constants
_PFC_PORT_LOC_CODE = 'LocationCode'
_PFC_PORT_NAME = 'PortName'
_PFC_PORT_UDID = 'UniqueDeviceID'
PFC_PORT_WWPN = 'WWPN'
_PFC_PORT_AVAILABLE_PORTS = 'AvailablePorts'
_PFC_PORT_TOTAL_PORTS = 'TotalPorts'
PFC_PORTS_ROOT = 'PhysicalFibreChannelPorts'


class SRIOVAdapterMode(object):
    """Enumeration for SRIOV adapter modes (from SRIOVAdapterMode.Enum)."""
    SRIOV = 'Sriov'
    DEDICATED = 'Dedicated'
    FORCE_DEDICATED = 'ForceDedicated'
    UNKNOWN = 'unknown'


class SRIOVAdapterState(object):
    """Enumeration for SRIOV adapter states (from SRIOVAdapterState.Enum)."""
    INITIALIZING = 'Initializing'
    NOT_CONFIG = 'NotConfigured'
    POWERED_OFF = 'PoweredOff'
    POWERING_OFF = 'PoweringOff'
    RUNNING = 'Running'
    DUMPING = 'Dumping'
    FAILED = 'Failed'
    MISSING = 'Missing'
    MISMATCH = 'PCIEIDMismatch'


@ewrap.ElementWrapper.pvm_type(IO_ADPT_ROOT, has_metadata=True)
class IOAdapter(ewrap.ElementWrapper):
    """A generic IO Adapter.

    This is a device plugged in to the system.  The location code indicates
    where it is plugged into the system.
    """

    @property
    def id(self):
        """The adapter system id."""
        return self._get_val_str(_IO_ADPT_ID)

    @property
    def description(self):
        return self._get_val_str(_IO_ADPT_DESC)

    @property
    def dev_name(self):
        return self._get_val_str(_IO_ADPT_DEV_NAME)

    @property
    def dev_type(self):
        return self._get_val_str(_IO_ADPT_DEV_TYPE)

    @property
    def drc_name(self):
        return self._get_val_str(_IO_ADPT_DYN_NAME)

    @property
    def phys_loc_code(self):
        return self._get_val_str(_IO_ADPT_PHYS_LOC)

    @property
    def udid(self):
        return self._get_val_str(_IO_ADPT_UDID)


@ewrap.ElementWrapper.pvm_type('PhysicalFibreChannelAdapter',
                               has_metadata=True)
class PhysFCAdapter(IOAdapter):
    """A Physical Fibre Channel I/O Adapter.

    Extends the generic I/O Adapter, but provides port detail as well.
    The adapter has a set of Physical Fibre Channel Ports (PhysFCPort).
    """

    @property
    def fc_ports(self):
        """The set of PhysFCPort's that are attached to this adapter.
        The data on this should be considered read only.
        """
        es = ewrap.WrapperElemList(self._find_or_seed(PFC_PORTS_ROOT),
                                   PhysFCPort)
        return es


@ewrap.ElementWrapper.pvm_type('PhysicalFibreChannelPort', has_metadata=True)
class PhysFCPort(ewrap.ElementWrapper):
    """A Physical Fibre Channel Port."""

    @classmethod
    def bld_ref(cls, adapter, name):
        """Create a wrapper that serves as a reference to a port.
        This is typically used when another element (ex. Virtual FC Mapping)
        requires a port to be specified in it.  Rather than query to find
        the port, one can simply be built and referenced as a child element.
        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name of the physical FC port.  End users need to
                     verify the port name.  Typically starts with 'fcs'.
        """
        port = super(PhysFCPort, cls)._bld(adapter)
        port._name(name)
        return port

    @property
    def loc_code(self):
        return self._get_val_str(_PFC_PORT_LOC_CODE)

    @property
    def name(self):
        return self._get_val_str(_PFC_PORT_NAME)

    def _name(self, value):
        return self.set_parm_value(_PFC_PORT_NAME, value)

    @property
    def udid(self):
        return self._get_val_str(_PFC_PORT_UDID)

    @property
    def wwpn(self):
        return self._get_val_str(PFC_PORT_WWPN)

    @property
    def npiv_available_ports(self):
        return self._get_val_int(_PFC_PORT_AVAILABLE_PORTS, 0)

    @property
    def npiv_total_ports(self):
        return self._get_val_int(_PFC_PORT_TOTAL_PORTS, 0)


@ewrap.ElementWrapper.pvm_type('SRIOVAdapter', has_metadata=True)
class SRIOVAdapter(IOAdapter):
    """The SR-IOV adapters for this system."""

    @property
    def mode(self):
        return self._get_val_str(_SRIOV_ADAPTER_MODE)

    @mode.setter
    def mode(self, value):
        return self.set_parm_value(_SRIOV_ADAPTER_MODE, str(value))


@ewrap.ElementWrapper.pvm_type(_IO_ADPT_CHOICE, has_metadata=False)
class LinkAggrIOAdapterChoice(ewrap.ElementWrapper):
    """A free I/O Adapter link aggregation choice.

    Flattens this two step heirarchy to pull the information needed directly
    from the IOAdapter element.
    """
    def __get_prop(self, func):
        """Thin wrapper to get the IOAdapter and get a property."""
        elem = self._find('IOAdapter')
        if elem is None:
            return None

        io_adpt = IOAdapter.wrap(elem)
        return getattr(io_adpt, func)

    @property
    def id(self):
        return self.__get_prop('id')

    @property
    def description(self):
        return self.__get_prop('description')

    @property
    def dev_name(self):
        return self.__get_prop('dev_name')

    @property
    def dev_type(self):
        return self.__get_prop('dev_type')

    @property
    def drc_name(self):
        return self.__get_prop('drc_name')

    @property
    def phys_loc_code(self):
        return self.__get_prop('phys_loc_code')

    @property
    def udid(self):
        return self.__get_prop('udid')
