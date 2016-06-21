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
import pypowervm.util as u
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
_SRIOV_ADAPTER_ID = 'SRIOVAdapterID'
_SRIOV_ADAPTER_MODE = 'AdapterMode'
_SRIOV_ADAPTER_STATE = 'AdapterState'

_SRIOV_CONVERGED_ETHERNET_PHYSICAL_PORTS = 'ConvergedEthernetPhysicalPorts'
_SRIOV_ETHERNET_PHYSICAL_PORTS = 'EthernetPhysicalPorts'

# SR-IOV physical port constants

_SRIOVPP_CFG_SPEED = 'ConfiguredConnectionSpeed'
_SRIOVPP_CFG_MTU = 'ConfiguredMTU'
_SRIOVPP_CFG_OPTIONS = 'ConfiguredOptions'
_SRIOVPP_CURR_SPEED = 'CurrentConnectionSpeed'
_SRIOVPP_CURR_OPTIONS = 'CurrentOptions'
_SRIOVPP_LBL = 'Label'
_SRIOVPP_LOC_CODE = 'LocationCode'
_SRIOVPP_MAX_DIAG_LPS = 'MaximumDiagnosticsLogicalPorts'
_SRIOVPP_MAX_PROM_LPS = 'MaximumPromiscuousLogicalPorts'
_SRIOVPP_ID = 'PhysicalPortID'
_SRIOVPP_CAPABILITIES = 'PortCapabilities'
_SRIOVPP_TYPE = 'PortType'
_SRIOVPP_LP_LIMIT = 'PortLogicalPortLimit'
_SRIOVPP_SUBLBL = 'SubLabel'
_SRIOVPP_SUPP_SPEEDS = 'SupportedConnectionSpeeds'
_SRIOVPP_SUPP_MTUS = 'SupportedMTUs'
_SRIOVPP_SUPP_OPTIONS = 'SupportedOptions'
_SRIOVPP_SUPP_PRI_ACL = 'SupportedPriorityAccessControlList'
_SRIOVPP_LINK_STATUS = 'LinkStatus'
_SRIOVPP_ALLOC_CAPACITY = 'AllocatedCapacity'
_SRIOVPP_CFG_MAX_ETHERNET_LPS = 'ConfiguredMaxEthernetLogicalPorts'
_SRIOVPP_CFG_ETHERNET_LPS = 'ConfiguredEthernetLogicalPorts'
_SRIOVPP_MAX_PVID = 'MaximumPortVLANID'
_SRIOVPP_MAX_VLAN_ID = 'MaximumVLANID'
_SRIOVPP_MIN_ETHERNET_CAPACITY_GRAN = 'MinimumEthernetCapacityGranularity'
_SRIOVPP_MIN_PVID = 'MinimumPortVLANID'
_SRIOVPP_MIN_VLAN_ID = 'MinimumVLANID'
_SRIOVPP_MAX_SUPP_ETHERNET_LPS = 'MaxSupportedEthernetLogicalPorts'
_SRIOVPP_CFG_MX_FCOE_LPS = 'ConfiguredMaxFiberChannelOverEthernetLogicalPorts'
_SRIOVPP_DEF_FCTARG_BACK_DEV = 'DefaultFiberChannelTargetsForBackingDevice'
_SRIOVPP_DEF_FTARG_NBACK_DEV = 'DefaultFiberChannelTargetsForNonBackingDevice'
_SRIOVPP_CFG_FCOE_LPS = 'ConfiguredFiberChannelOverEthernetLogicalPorts'
_SRIOVPP_MIN_FCOE_CAPACITY_GRAN = 'MinimumFCoECapacityGranularity'
_SRIOVPP_FC_TARGET_ROUNDING_VALUE = 'FiberChannelTargetsRoundingValue'
_SRIOVPP_MX_SUPP_FCOE_LPS = 'MaxSupportedFiberChannelOverEthernetLogicalPorts'
_SRIOVPP_MAX_FC_TARGETS = 'MaximumFiberChannelTargets'

_SRIOVPP_EL_ORDER = (
    _SRIOVPP_CFG_SPEED, _SRIOVPP_CFG_MTU,
    _SRIOVPP_CFG_OPTIONS, _SRIOVPP_CURR_SPEED,
    _SRIOVPP_CURR_OPTIONS, _SRIOVPP_LBL, _SRIOVPP_LOC_CODE,
    _SRIOVPP_MAX_DIAG_LPS, _SRIOVPP_MAX_PROM_LPS,
    _SRIOVPP_ID, _SRIOVPP_CAPABILITIES, _SRIOVPP_TYPE,
    _SRIOVPP_LP_LIMIT, _SRIOVPP_SUBLBL, _SRIOVPP_SUPP_SPEEDS,
    _SRIOVPP_SUPP_MTUS, _SRIOVPP_SUPP_OPTIONS,
    _SRIOVPP_SUPP_PRI_ACL, _SRIOVPP_LINK_STATUS)

_SRIOVEPP_EL_ORDER = _SRIOVPP_EL_ORDER + (
    _SRIOVPP_ALLOC_CAPACITY,
    _SRIOVPP_CFG_MAX_ETHERNET_LPS,
    _SRIOVPP_CFG_ETHERNET_LPS, _SRIOVPP_MAX_PVID,
    _SRIOVPP_MAX_VLAN_ID, _SRIOVPP_MIN_ETHERNET_CAPACITY_GRAN,
    _SRIOVPP_MIN_PVID, _SRIOVPP_MIN_VLAN_ID,
    _SRIOVPP_MAX_SUPP_ETHERNET_LPS)

_SRIOVCPP_EL_ORDER = _SRIOVEPP_EL_ORDER + (
    _SRIOVPP_CFG_MX_FCOE_LPS,
    _SRIOVPP_DEF_FCTARG_BACK_DEV, _SRIOVPP_DEF_FTARG_NBACK_DEV,
    _SRIOVPP_CFG_FCOE_LPS, _SRIOVPP_MIN_FCOE_CAPACITY_GRAN,
    _SRIOVPP_FC_TARGET_ROUNDING_VALUE, _SRIOVPP_MX_SUPP_FCOE_LPS,
    _SRIOVPP_MAX_FC_TARGETS)

# SR-IOV logical port constants
_SRIOVLP_CFG_ID = 'ConfigurationID'
_SRIOVLP_ID = 'LogicalPortID'
_SRIOVLP_ADPT_ID = 'AdapterID'
_SRIOVLP_DRC_NAME = 'DynamicReconfigurationConnectorName'
_SRIOVLP_IS_FUNC = 'IsFunctional'
_SRIOVLP_IS_PROMISC = 'IsPromiscous'  # [sic]
_SRIOVLP_IS_DIAG = 'IsDiagnostic'
_SRIOVLP_IS_DEBUG = 'IsDebug'
_SRIOVLP_IS_HUGE_DMA = 'IsHugeDMA'
_SRIOVLP_DEV_NAME = 'DeviceName'
_SRIOVLP_CFG_CAPACITY = 'ConfiguredCapacity'
_SRIOVLP_PPORT_ID = 'PhysicalPortID'
_SRIOVLP_PVID = 'PortVLANID'
_SRIOVLP_LOC_CODE = 'LocationCode'
_SRIOVLP_TUNING_BUF_ID = 'TuningBufferID'
_SRIOVLP_VNIC_PORT_USAGE = 'VNICPortUsage'
_SRIOVLP_ASSOC_LPARS = 'AssociatedLogicalPartitions'
_SRIOVLP_ALLOWED_MACS = 'AllowedMACAddresses'
_SRIOVLP_MAC = 'MACAddress'
_SRIOVLP_CUR_MAC = 'CurrentMACAddress'
_SRIOVLP_8021Q_ALLOW_PRI = 'IEEE8021QAllowablePriorities'
_SRIOVLP_8021Q_PRI = 'IEEE8021QPriority'
_SRIOVLP_MAC_FLAGS = 'MACAddressFlags'
_SRIOVLP_NUM_ALLOWED_VLANS = 'NumberOfAllowedVLANs'
_SRIOVLP_ALLOWED_VLANS = 'AllowedVLANs'

_SRIOVLP_EL_ORDER = (
    _SRIOVLP_CFG_ID, _SRIOVLP_ID,
    _SRIOVLP_ADPT_ID, _SRIOVLP_DRC_NAME,
    _SRIOVLP_IS_FUNC, _SRIOVLP_IS_PROMISC,
    _SRIOVLP_IS_DIAG, _SRIOVLP_IS_DEBUG,
    _SRIOVLP_IS_HUGE_DMA, _SRIOVLP_DEV_NAME,
    _SRIOVLP_CFG_CAPACITY, _SRIOVLP_PPORT_ID,
    _SRIOVLP_PVID, _SRIOVLP_LOC_CODE,
    _SRIOVLP_TUNING_BUF_ID, _SRIOVLP_VNIC_PORT_USAGE,
    _SRIOVLP_ASSOC_LPARS, _SRIOVLP_ALLOWED_MACS,
    _SRIOVLP_MAC, _SRIOVLP_CUR_MAC,
    _SRIOVLP_8021Q_ALLOW_PRI, _SRIOVLP_8021Q_PRI,
    _SRIOVLP_MAC_FLAGS, _SRIOVLP_NUM_ALLOWED_VLANS,
    _SRIOVLP_ALLOWED_VLANS)

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
    def sriov_adap_id(self):
        """Not to be confused with the 'id' property (IOAdapter.AdapterID)."""
        return self._get_val_int(_SRIOV_ADAPTER_ID)

    @property
    def mode(self):
        return self._get_val_str(_SRIOV_ADAPTER_MODE)

    @mode.setter
    def mode(self, value):
        self.set_parm_value(_SRIOV_ADAPTER_MODE, value)

    @property
    def state(self):
        return self._get_val_str(_SRIOV_ADAPTER_STATE)

    def _convergedphysicalports(self):
        """Retrieve all Converged physical ports."""
        es = ewrap.WrapperElemList(
            self._find_or_seed(_SRIOV_CONVERGED_ETHERNET_PHYSICAL_PORTS),
            child_class=SRIOVConvPPort)
        return es

    def _ethernetphysicalports(self):
        """Retrieve all Ethernet physical ports."""
        es = ewrap.WrapperElemList(
            self._find_or_seed(_SRIOV_ETHERNET_PHYSICAL_PORTS),
            child_class=SRIOVEthPPort)
        return es

    @property
    def phys_ports(self):
        """Retrieve Combined list of all physical ports.

        Returns a list of converged and ethernet physical ports.
        This list is not modifiable, cannot insert or remove
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
                               has_metadata=True,
                               child_order=_SRIOVEPP_EL_ORDER)
class SRIOVEthPPort(ewrap.ElementWrapper):
    """The SRIOV Ethernet Physical port."""

    @property
    def label(self):
        return self._get_val_str(_SRIOVPP_LBL)

    @label.setter
    def label(self, value):
        self.set_parm_value(_SRIOVPP_LBL, value)

    @property
    def loc_code(self):
        return self._get_val_str(_SRIOVPP_LOC_CODE)

    @property
    def port_id(self):
        return self._get_val_int(_SRIOVPP_ID)

    @property
    def sublabel(self):
        return self._get_val_str(_SRIOVPP_SUBLBL)

    @sublabel.setter
    def sublabel(self, value):
        self.set_parm_value(_SRIOVPP_SUBLBL, value)

    @property
    def link_status(self):
        return self._get_val_bool(_SRIOVPP_LINK_STATUS)

    @property
    def cfg_max_lps(self):
        return self._get_val_int(_SRIOVPP_CFG_MAX_ETHERNET_LPS)

    @cfg_max_lps.setter
    def cfg_max_lps(self, value):
        self.set_parm_value(_SRIOVPP_CFG_MAX_ETHERNET_LPS, value)

    @property
    def cfg_lps(self):
        return self._get_val_int(_SRIOVPP_CFG_ETHERNET_LPS)

    @property
    def min_granularity(self):
        return self._get_val_int(_SRIOVPP_MIN_ETHERNET_CAPACITY_GRAN)

    @property
    def supp_max_lps(self):
        return self._get_val_int(_SRIOVPP_MAX_SUPP_ETHERNET_LPS)

    @property
    def allocated_capacity(self):
        """Gets the allocated capacity in a float-percentage format.

        :return: If the property is say "2.45%", a value of .0245 will be
                 returned.
        """
        return self._get_val_percent(_SRIOVPP_ALLOC_CAPACITY)


@ewrap.ElementWrapper.pvm_type('SRIOVConvergedNetworkAdapterPhysicalPort',
                               has_metadata=True,
                               child_order=_SRIOVCPP_EL_ORDER)
class SRIOVConvPPort(SRIOVEthPPort):
    """The SRIOV Converged Physical port."""
    pass


@ewrap.EntryWrapper.pvm_type('SRIOVEthernetLogicalPort',
                             has_metadata=True,
                             child_order=_SRIOVLP_EL_ORDER)
class SRIOVEthLPort(ewrap.EntryWrapper):
    """The SRIOV Ethernet Logical port."""

    @classmethod
    def bld(cls, adapter, sriov_adap_id, pport_id, pvid=None, is_promisc=True,
            cfg_capacity=None):
        """Create a wrapper used to create a logical port on the server.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param sriov_adap_id: Corresponds to SRIOVAdapter.SRIOVAdapterID,
                              *not* SRIOVAdapter.AdapterID
        :param pport_id: The physical port ID this logical port is part of.
        :param pvid: The port VLAN identifier for this logical port. Any
                     untagged traffic passing through this port will have
                     this VLAN tag added.
        :param is_promisc: If this value is True, all traffic will pass through
                           the logical port, regardless of MAC address.
        :param cfg_capacity: The configured capacity of the logical port as a
                             percentage.  This represents the minimum bandwidth
                             this logical port will receive, as a percentage
                             of bandwidth available from the physical port.
                             The valid values are 0.0 <= x <= 1.0 up to 2
                             decimal places.  This will be intrepreted as a
                             percentage, where 0.02 == 2%.
        """
        lport = super(SRIOVEthLPort, cls)._bld(adapter)
        lport._sriov_adap_id(sriov_adap_id)
        lport._pport_id(pport_id)
        if pvid is not None:
            lport.pvid = pvid
        lport._is_promisc(is_promisc)
        if cfg_capacity:
            lport._cfg_capacity(cfg_capacity)
        return lport

    @property
    def lport_id(self):
        return self._get_val_int(_SRIOVLP_ID)

    @property
    def sriov_adap_id(self):
        return self._get_val_int(_SRIOVLP_ADPT_ID)

    def _sriov_adap_id(self, value):
        self.set_parm_value(_SRIOVLP_ADPT_ID, value)

    @property
    def is_promisc(self):
        return self._get_val_bool(_SRIOVLP_IS_PROMISC)

    def _is_promisc(self, value):
        self.set_parm_value(_SRIOVLP_IS_PROMISC,
                            u.sanitize_bool_for_api(value))

    @property
    def dev_name(self):
        return self._get_val_str(_SRIOVLP_DEV_NAME)

    @property
    def cfg_capacity(self):
        """Gets the configured capacity in a float-percentage format.

        :return: If the property is say "2.45%", a value of .0245 will be
                 returned.
        """
        return self._get_val_percent(_SRIOVLP_CFG_CAPACITY)

    def _cfg_capacity(self, value):
        """The configured capacity

        :param value: The configured capacity value.  The valid values are
                      0.0 <= x <=1.0 up to 2 decimal places.  This will be
                      intrepreted as a percentage, where 0.02 == 2%.
        """
        self.set_parm_value(_SRIOVLP_CFG_CAPACITY,
                            u.sanitize_percent_for_api(value))

    @property
    def pport_id(self):
        """Gets the physical port short ID."""
        return self._get_val_int(_SRIOVLP_PPORT_ID)

    def _pport_id(self, value):
        """Internal setter for the physical port short ID."""
        self.set_parm_value(_SRIOVLP_PPORT_ID, value)

    @property
    def pvid(self):
        return self._get_val_int(_SRIOVLP_PVID)

    @pvid.setter
    def pvid(self, value):
        self.set_parm_value(_SRIOVLP_PVID, value)

    @property
    def loc_code(self):
        return self._get_val_str(_SRIOVLP_LOC_CODE)


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
