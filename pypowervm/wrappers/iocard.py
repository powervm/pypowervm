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
_SRIOV_ADAPTER_STATE = 'AdapterState'

_SRIOV_CONVERGED_ETHERNET_PHYSICAL_PORTS = 'ConvergedEthernetPhysicalPorts'
_SRIOV_ETHERNET_PHYSICAL_PORTS = 'EthernetPhysicalPorts'

# SR-IOV physical port constants
_PVM_SRIOV_PHYSICAL_PORT_TYPE_CONVERGED = 'converged'
_PVM_SRIOV_PHYSICAL_PORT_TYPE_ETHERNET = 'ethernet'

_SRIOVPP_CONFIGURED_SPEED = 'ConfiguredConnectionSpeed'
_SRIOVPP_MTU = 'ConfiguredMTU'
_SRIOV_PP_CONFIGURED_OPTIONS = 'ConfiguredOptions'
_SRIOV_PP_CURRENT_SPEED = 'ConfiguredConnectionSpeed'
_SRIOV_PP_CURRENT_OPTIONS = 'CurrentOptions'
_SRIOV_PP_LBL = 'Label'
_SRIOV_PP_LOCATION_CODE = 'LocationCode'
_SRIOV_PP_MAX_DIAG_LOGICAL_PORTS = 'MaximumDiagnosticsLogicalPorts'
_SRIOV_PP_MAX_PROM_LOGICAL_PORTS = 'MaximumPromiscuousLogicalPorts'
_SRIOV_PP_ID = 'PhysicalPortID'
_SRIOV_PP_CAPABILITIES = 'PortCapabilities'
_SRIOV_PP_TYPE = 'PortType'
_SRIOV_PP_LOGICAL_PORT_LIMIT = 'PortLogicalPortLimit'
_SRIOV_PP_SUBLBL = 'SubLabel'
_SRIOV_PP_SUPPORTED_SPEEDS = 'SupportedConnectionSpeeds'
_SRIOV_PP_SUPPORTED_MTUS = 'SupportedMTUs'
_SRIOV_PP_SUPPORTED_OPTIONS = 'SupportedOptions'
_SRIOV_PP_SUPPORTED_PRI_ACL = 'SupportedPriorityAccessControlList'
_SRIOV_PP_LINK_STATUS = 'LinkStatus'
_SRIOV_PP_ALLOC_CAPACITY = 'AllocatedCapacity'
_SRIOV_PP_CFG_MAX_ETHERNET_LOGICAL_PORTS = 'ConfiguredMaxEthernetLogicalPorts'
_SRIOV_PP_CFG_ETHERNET_LOGICAL_PORTS = 'ConfiguredEthernetLogicalPorts'
_SRIOV_PP_MAX_PVID = 'MaximumPortVLANID'
_SRIOV_PP_VLAN_ID = 'MaximumVLANID'
_SRIOV_PP_MIN_ETHERNET_CAPACITY_GRAN = 'MinimumEthernetCapacityGranularity'
_SRIOV_PP_MIN_PVID = 'MinimumPortVLANID'
_SRIOV_PP_MIN_VLAN_ID = 'MinimumVLANID'
_SRIOV_PP_MAX_SUPP_ETHERNET_LOGICAL_PORTS = 'MaxSupportedEthernetLogicalPorts'
_SRIOV_PP_CFG_MX_FCOE_LPS = 'ConfiguredMaxFiberChannelOverEthernetLogicalPorts'
_SRIOV_PP_DEF_FCTARG_BACK_DEV = 'DefaultFiberChannelTargetsForBackingDevice'
_SRIOV_PP_DEF_FTARG_NBACK_DEV = 'DefaultFiberChannelTargetsForNonBackingDevice'
_SRIOV_PP_CF_FCOE_LPORTS = 'ConfiguredFiberChannelOverEthernetLogicalPorts'
_SRIOV_PP_MIN_FCOE_CAPACITY_GRANULARITY = 'MinimumFCoECapacityGranularity'
_SRIOV_PP_FC_TARGET_ROUNDING_VALUE = 'FiberChannelTargetsRoundingValue'
_SRIOV_PP_MXSUP_FCOELPORTS = 'MaxSupportedFiberChannelOverEthernetLogicalPorts'
_SRIOV_PP_MAX_FC_TARGES = 'MaximumFiberChannelTargets'


_SRIOVPP_EL_ORDER = (
    _SRIOVPP_CONFIGURED_SPEED, _SRIOVPP_MTU,
    _SRIOV_PP_CONFIGURED_OPTIONS, _SRIOV_PP_CURRENT_SPEED,
    _SRIOV_PP_CURRENT_OPTIONS, _SRIOV_PP_LBL, _SRIOV_PP_LOCATION_CODE,
    _SRIOV_PP_MAX_DIAG_LOGICAL_PORTS, _SRIOV_PP_MAX_PROM_LOGICAL_PORTS,
    _SRIOV_PP_ID, _SRIOV_PP_CAPABILITIES, _SRIOV_PP_TYPE,
    _SRIOV_PP_LOGICAL_PORT_LIMIT, _SRIOV_PP_SUBLBL, _SRIOV_PP_SUPPORTED_SPEEDS,
    _SRIOV_PP_SUPPORTED_MTUS, _SRIOV_PP_SUPPORTED_OPTIONS,
    _SRIOV_PP_SUPPORTED_PRI_ACL, _SRIOV_PP_LINK_STATUS)

_SRIOVEPP_EL_ORDER = _SRIOVPP_EL_ORDER + (
    _SRIOV_PP_ALLOC_CAPACITY,
    _SRIOV_PP_CFG_MAX_ETHERNET_LOGICAL_PORTS,
    _SRIOV_PP_CFG_ETHERNET_LOGICAL_PORTS, _SRIOV_PP_MAX_PVID,
    _SRIOV_PP_VLAN_ID, _SRIOV_PP_MIN_ETHERNET_CAPACITY_GRAN,
    _SRIOV_PP_MIN_PVID, _SRIOV_PP_MIN_VLAN_ID,
    _SRIOV_PP_MAX_SUPP_ETHERNET_LOGICAL_PORTS)

_SRIOVCPP_EL_ORDER = _SRIOVEPP_EL_ORDER + (
    _SRIOV_PP_CFG_MX_FCOE_LPS,
    _SRIOV_PP_DEF_FCTARG_BACK_DEV, _SRIOV_PP_DEF_FTARG_NBACK_DEV,
    _SRIOV_PP_CF_FCOE_LPORTS, _SRIOV_PP_MIN_FCOE_CAPACITY_GRANULARITY,
    _SRIOV_PP_FC_TARGET_ROUNDING_VALUE, _SRIOV_PP_MXSUP_FCOELPORTS,
    _SRIOV_PP_MAX_FC_TARGES)

# Physical Fibre Channel Port Constants
_PFC_PORT_LOC_CODE = 'LocationCode'
_PFC_PORT_NAME = 'PortName'
_PFC_PORT_UDID = 'UniqueDeviceID'
PFC_PORT_WWPN = 'WWPN'
_PFC_PORT_AVAILABLE_PORTS = 'AvailablePorts'
_PFC_PORT_TOTAL_PORTS = 'TotalPorts'
PFC_PORTS_ROOT = 'PhysicalFibreChannelPorts'
PFC_PORT_ROOT = 'PhysicalFibreChannelPort'


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
        """A set of Physical Fibre Channel Ports.

        The set of PhysFCPort's that are attached to this adapter.
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
        return self.set_parm_value(_SRIOV_ADAPTER_MODE, value)

    @property
    def state(self):
        return self._get_val_str(_SRIOV_ADAPTER_STATE)

    def _convergedphysicalports(self):
        """Retrieve all Converged physical ports."""
        es = ewrap.WrapperElemList(self._find_or_seed(
                                   _SRIOV_CONVERGED_ETHERNET_PHYSICAL_PORTS),
                                   child_class=SRIOVConvPPort)
        return es

    def _ethernetphysicalports(self):
        """Retrieve all Ethernet physical ports."""
        es = ewrap.WrapperElemList(self._find_or_seed(
                                   _SRIOV_ETHERNET_PHYSICAL_PORTS),
                                   child_class=SRIOVEthPPort)
        return es

    @property
    def phys_ports(self):
        """Retrieve Combined list of all physical ports.

        Returns a list of converged and ethernet physical ports.
        This list is not modifiable, cannot insert or remote
        items from it, however, individual item can be updated.
        For example, label and sublabels can be updated.
        """
        allports = []
        cports = self._convergedphysicalports()
        eports = self._ethernetphysicalports()
        for c in cports:
            allports.append(c)
        for e in eports:
            allports.append(e)
        return allports


@ewrap.ElementWrapper.pvm_type('SRIOVEthernetPhysicalPort',
                               child_order=_SRIOVEPP_EL_ORDER)
class SRIOVEthPPort(ewrap.ElementWrapper):
    """The SRIOV Ethernet Physical port."""

    @property
    def label(self):
        return self._get_val_str(_SRIOV_PP_LBL)

    @label.setter
    def label(self, value):
        return self.set_parm_value(_SRIOV_PP_LBL, value)

    @property
    def loc_code(self):
        return self._get_val_str(_SRIOV_PP_LOCATION_CODE)

    @property
    def port_id(self):
        return self._get_val_int(_SRIOV_PP_ID)

    @property
    def sublabel(self):
        return self._get_val_str(_SRIOV_PP_SUBLBL)

    @sublabel.setter
    def sublabel(self, value):
        return self.set_parm_value(_SRIOV_PP_SUBLBL, value)

    @property
    def link_status(self):
        return self._get_val_bool(_SRIOV_PP_LINK_STATUS)

    @property
    def cfg_max_ports(self):
        return self._get_val_int(_SRIOV_PP_CFG_MAX_ETHERNET_LOGICAL_PORTS)

    @cfg_max_ports.setter
    def cfg_max_ports(self, value):
        return self.set_parm_value(_SRIOV_PP_CFG_MAX_ETHERNET_LOGICAL_PORTS,
                                   value)

    @property
    def min_granularity(self):
        return self._get_val_int(_SRIOV_PP_MIN_ETHERNET_CAPACITY_GRAN)

    @property
    def supp_max_ports(self):
        return self._get_val_int(_SRIOV_PP_MAX_SUPP_ETHERNET_LOGICAL_PORTS)


@ewrap.ElementWrapper.pvm_type('SRIOVConvergedNetworkAdapterPhysicalPort',
                               child_order=_SRIOVCPP_EL_ORDER)
class SRIOVConvPPort(SRIOVEthPPort, ewrap.ElementWrapper):
    """The SRIOV Converged Physical port."""
    pass


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
