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
import pypowervm.const as pc
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
_SRIOVPP_CFG_FLOWCTL = 'ConfiguredFlowControl'
_SRIOVPP_CFG_MTU = 'ConfiguredMTU'
_SRIOVPP_CFG_OPTIONS = 'ConfiguredOptions'
_SRIOVPP_CFG_SWMODE = 'ConfiguredPortSwitchMode'
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
_SRIOVPP_DEF_PORTVF_CFG = 'DefaultPortVFConfigurationOption'
_SRIOVPP_SEL_PORTVF_CFG = 'SelectedPortVFConfigurationOption'
_SRIOVPP_SUPP_PORTVF_CFG = 'SupportedPortVFConfigurationOptions'
_SRIOVPP_ALLOC_CAPACITY = 'AllocatedCapacity'
_SRIOVPP_CFG_MAX_ETHERNET_LPS = 'ConfiguredMaxEthernetLogicalPorts'
_SRIOVPP_CFG_ETHERNET_LPS = 'ConfiguredEthernetLogicalPorts'
_SRIOVPP_MAX_PVID = 'MaximumPortVLANID'
_SRIOVPP_MAX_VLAN_ID = 'MaximumVLANID'
_SRIOVPP_MIN_ETHERNET_CAPACITY_GRAN = 'MinimumEthernetCapacityGranularity'
_SRIOVPP_MIN_PVID = 'MinimumPortVLANID'
_SRIOVPP_MIN_VLAN_ID = 'MinimumVLANID'
_SRIOVPP_MAX_SUPP_ETHERNET_LPS = 'MaxSupportedEthernetLogicalPorts'
_SRIOVPP_MAX_ALLOW_ETH_VLANS = 'MaximumAllowedEthVLANs'
_SRIOVPP_MAX_ALLOW_ETH_MACS = 'MaximumAllowedEthMACs'
_SRIOVPP_SUPP_VLAN_RESTR = 'SupportedVLANRestrictions'
_SRIOVPP_SUPP_MAC_RESTR = 'SupportedMACRestrictions'
_SRIOVPP_CFG_MX_FCOE_LPS = 'ConfiguredMaxFiberChannelOverEthernetLogicalPorts'
_SRIOVPP_DEF_FCTARG_BACK_DEV = 'DefaultFiberChannelTargetsForBackingDevice'
_SRIOVPP_DEF_FTARG_NBACK_DEV = 'DefaultFiberChannelTargetsForNonBackingDevice'
_SRIOVPP_CFG_FCOE_LPS = 'ConfiguredFiberChannelOverEthernetLogicalPorts'
_SRIOVPP_MIN_FCOE_CAPACITY_GRAN = 'MinimumFCoECapacityGranularity'
_SRIOVPP_FC_TARGET_ROUNDING_VALUE = 'FiberChannelTargetsRoundingValue'
_SRIOVPP_MX_SUPP_FCOE_LPS = 'MaxSupportedFiberChannelOverEthernetLogicalPorts'
_SRIOVPP_MAX_FC_TARGETS = 'MaximumFiberChannelTargets'

_SRIOVPP_EL_ORDER = (
    _SRIOVPP_CFG_SPEED, _SRIOVPP_CFG_FLOWCTL, _SRIOVPP_CFG_MTU,
    _SRIOVPP_CFG_OPTIONS, _SRIOVPP_CFG_SWMODE, _SRIOVPP_CURR_SPEED,
    _SRIOVPP_CURR_OPTIONS, _SRIOVPP_LBL, _SRIOVPP_LOC_CODE,
    _SRIOVPP_MAX_DIAG_LPS, _SRIOVPP_MAX_PROM_LPS,
    _SRIOVPP_ID, _SRIOVPP_CAPABILITIES, _SRIOVPP_TYPE,
    _SRIOVPP_LP_LIMIT, _SRIOVPP_SUBLBL, _SRIOVPP_SUPP_SPEEDS,
    _SRIOVPP_SUPP_MTUS, _SRIOVPP_SUPP_OPTIONS,
    _SRIOVPP_SUPP_PRI_ACL, _SRIOVPP_LINK_STATUS, _SRIOVPP_DEF_PORTVF_CFG,
    _SRIOVPP_SEL_PORTVF_CFG, _SRIOVPP_SUPP_PORTVF_CFG)

_SRIOVEPP_EL_ORDER = _SRIOVPP_EL_ORDER + (
    _SRIOVPP_ALLOC_CAPACITY,
    _SRIOVPP_CFG_MAX_ETHERNET_LPS,
    _SRIOVPP_CFG_ETHERNET_LPS, _SRIOVPP_MAX_PVID,
    _SRIOVPP_MAX_VLAN_ID, _SRIOVPP_MIN_ETHERNET_CAPACITY_GRAN,
    _SRIOVPP_MIN_PVID, _SRIOVPP_MIN_VLAN_ID,
    _SRIOVPP_MAX_SUPP_ETHERNET_LPS, _SRIOVPP_MAX_ALLOW_ETH_VLANS,
    _SRIOVPP_MAX_ALLOW_ETH_MACS, _SRIOVPP_SUPP_VLAN_RESTR,
    _SRIOVPP_SUPP_MAC_RESTR)

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
    _SRIOVLP_CFG_ID, _SRIOVLP_ID, _SRIOVLP_ADPT_ID, _SRIOVLP_DRC_NAME,
    _SRIOVLP_IS_FUNC, _SRIOVLP_IS_PROMISC, _SRIOVLP_IS_DIAG, _SRIOVLP_IS_DEBUG,
    _SRIOVLP_IS_HUGE_DMA, _SRIOVLP_DEV_NAME, _SRIOVLP_CFG_CAPACITY,
    _SRIOVLP_PPORT_ID, _SRIOVLP_PVID, _SRIOVLP_LOC_CODE,
    _SRIOVLP_TUNING_BUF_ID, _SRIOVLP_VNIC_PORT_USAGE, _SRIOVLP_ASSOC_LPARS,
    _SRIOVLP_ALLOWED_MACS, _SRIOVLP_MAC, _SRIOVLP_CUR_MAC,
    _SRIOVLP_8021Q_ALLOW_PRI, _SRIOVLP_8021Q_PRI, _SRIOVLP_MAC_FLAGS,
    _SRIOVLP_NUM_ALLOWED_VLANS, _SRIOVLP_ALLOWED_VLANS)

# Top-level VNIC properties
_VNIC_DED = 'VirtualNICDedicated'
_VNIC_ADP_TYPE = 'AdapterType'
_VNIC_DRC_NAME = 'DynamicReconfigurationConnectorName'
_VNIC_LOC_CODE = 'LocationCode'
_VNIC_LPAR_ID = 'LocalPartitionID'
_VNIC_REQ_ADP = 'RequiredAdapter'
_VNIC_VARIED_ON = 'VariedOn'
_VNIC_USE_NEXT_AVAIL_SLOT = 'UseNextAvailableSlotID'
_VNIC_USE_NEXT_AVAIL_HIGH_SLOT = 'UseNextAvailableHighSlotID'
_VNIC_SLOT_NUM = 'VirtualSlotNumber'
_VNIC_ENABLED = 'Enabled'
_VNIC_DETAILS = 'Details'
_VNIC_BACK_DEVS = 'AssociatedBackingDevices'

_VNIC_EL_ORDER = (
    _VNIC_DED, _VNIC_ADP_TYPE, _VNIC_DRC_NAME, _VNIC_LOC_CODE, _VNIC_LPAR_ID,
    _VNIC_REQ_ADP, _VNIC_VARIED_ON, _VNIC_USE_NEXT_AVAIL_SLOT,
    _VNIC_USE_NEXT_AVAIL_HIGH_SLOT, _VNIC_SLOT_NUM, _VNIC_ENABLED,
    _VNIC_DETAILS, _VNIC_BACK_DEVS)

# Properties for _VNICDetails (schema: VirtualNICDetails.Type)
_VNICD_PVID = 'PortVLANID'
_VNICD_PVID_PRI = 'PortVLANIDPriority'
_VNICD_ALLOWED_VLANS = 'AllowedVLANIDs'
_VNICD_MAC = 'MACAddress'
_VNICD_ALLOWED_OS_MACS = 'AllowedOperatingSystemMACAddresses'
_VNICD_OS_DEV_NAME = 'OSDeviceName'
_VNICD_DES_MODE = 'DesiredMode'
_VNICD_DES_CAP_PCT = 'DesiredCapacityPercentage'
_VNICD_AUTO_FB = 'AutoFailBack'

_VNICD_EL_ORDER = (
    _VNICD_PVID, _VNICD_PVID_PRI, _VNICD_ALLOWED_VLANS, _VNICD_MAC,
    _VNICD_ALLOWED_OS_MACS, _VNICD_OS_DEV_NAME, _VNICD_DES_MODE,
    _VNICD_DES_CAP_PCT, _VNICD_DES_CAP_PCT)

# Properties for VNICBackDev (schema: VirtualNICSRIOVBackingDevice)
_VNICBD_CHOICE = 'VirtualNICBackingDeviceChoice'
_VNICBD = 'VirtualNICSRIOVBackingDevice'
_VNICBD_DEV_TYP = 'DeviceType'
_VNICBD_VIOS = 'AssociatedVirtualIOServer'
_VNICBD_SWITCH = 'AssociatedVirtualNICSwitch'
_VNICBD_VNIC = 'AssociatedVirtualNICDedicated'
_VNICBD_ACTIVE = 'IsActive'
_VNICBD_STATUS = 'Status'
_VNICBD_FAILOVER_PRI = 'FailOverPriority'
_VNICBD_ACTION = 'BackingDeviceAction'
_VNICBD_SRIOV_ADP_ID = 'RelatedSRIOVAdapterID'
_VNICBD_CUR_CAP_PCT = 'CurrentCapacityPercentage'
_VNICBD_PPORT_ID = 'RelatedSRIOVPhysicalPortID'
_VNICBD_LPORT = 'RelatedSRIOVLogicalPort'
_VNICBD_DES_CAP_PCT = 'DesiredCapacityPercentage'
# For building the VIOS HREF.  (Would have liked to use pypowervm.wrappers.
# virtual_io_server.VIOS.schema_type, but circular import.)
_VIOS = 'VirtualIOServer'

_VNICBD_EL_ORDER = (
    _VNICBD_DEV_TYP, _VNICBD_VIOS, _VNICBD_SWITCH, _VNICBD_VNIC,
    _VNICBD_ACTIVE, _VNICBD_STATUS, _VNICBD_FAILOVER_PRI, _VNICBD_ACTION,
    _VNICBD_SRIOV_ADP_ID, _VNICBD_CUR_CAP_PCT, _VNICBD_PPORT_ID, _VNICBD_LPORT,
    _VNICBD_DES_CAP_PCT)

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
    """Enumeration for SR-IOV adapter modes (from SRIOVAdapterMode.Enum)."""
    SRIOV = 'Sriov'
    DEDICATED = 'Dedicated'
    FORCE_DEDICATED = 'ForceDedicated'
    UNKNOWN = 'unknown'


class SRIOVAdapterState(object):
    """Enumeration for SR-IOV adapter states (from SRIOVAdapterState.Enum)."""
    INITIALIZING = 'Initializing'
    NOT_CONFIG = 'NotConfigured'
    POWERED_OFF = 'PoweredOff'
    POWERING_OFF = 'PoweringOff'
    RUNNING = 'Running'
    DUMPING = 'Dumping'
    FAILED = 'Failed'
    MISSING = 'Missing'
    MISMATCH = 'PCIEIDMismatch'


class SRIOVSpeed(object):
    """Enumeration for SR-IOV speed (from SRIOVConnectionSpeed.Enum)."""
    E10M = 'E10Mbps'
    E100M = 'E100Mbps'
    E1G = 'E1Gbps'
    E10G = 'E10Gbps'
    E40G = 'E40Gbps'
    E100G = 'E100Gbps'
    AUTO = 'Auto'
    UNKNOWN = 'Unknown'


class SRIOVPPMTU(object):
    """SR-IOV Phys Port Max Transmission Unit (SRIOVPhysicalPortMTU.Enum)."""
    E1500 = "E_1500"
    E9000 = "E_9000"
    UNKNOWN = 'Unknown'


class VNICBackDevStatus(object):
    """Enumeration of possible VNIC backing device statuses."""
    OPERATIONAL = 'OPERATIONAL'
    POWERED_OFF = 'POWERED_OFF'
    LINK_DOWN = 'LINK_DOWN'
    NETWORK_ERROR = 'NETWORK_ERROR'
    UNRESPONSIVE = 'UNRESPONSIVE'
    ADAPTER_ERROR = 'ADAPTER_ERROR'
    UNKNOWN = 'UNKNOWN'


class VNICPortUsage(object):
    """Enumeration of possible VNIC port usages."""
    NOT_VNIC = 'NOT_VNIC'
    DEDICATED_VNIC = 'DEDICATED_VNIC'
    SHARED_VNIC = 'SHARED_VNIC'


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
    def bld_ref(cls, adapter, name, ref_tag=None):
        """Create a wrapper that serves as a reference to a port.

        This is typically used when another element (ex. Virtual FC Mapping)
        requires a port to be specified in it.  Rather than query to find
        the port, one can simply be built and referenced as a child element.
        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param name: The name of the physical FC port.  End users need to
                     verify the port name.  Typically starts with 'fcs'.
        :param ref_tag: (Optional, Default=None) If set, override the
                        default 'PhysicalFibreChannelPort' tag/label in the
                        element with the string specified.
        """
        port = super(PhysFCPort, cls)._bld(adapter)
        port._name(name)
        if ref_tag:
            port.element.tag = ref_tag
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
        elem = self._find(_SRIOV_CONVERGED_ETHERNET_PHYSICAL_PORTS)
        if elem is None:
            return None
        return ewrap.WrapperElemList(elem, child_class=SRIOVConvPPort)

    def _ethernetphysicalports(self):
        """Retrieve all Ethernet physical ports."""
        elem = self._find(_SRIOV_ETHERNET_PHYSICAL_PORTS)
        if elem is None:
            return None
        return ewrap.WrapperElemList(elem, child_class=SRIOVEthPPort)

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
        for c in cports or []:
            allports.append(c)
        for e in eports or []:
            allports.append(e)
        # Set the ports' backpointers to this SRIOVAdapter
        for pport in allports:
            pport._sriov_adap = self
        return allports


@ewrap.ElementWrapper.pvm_type('SRIOVEthernetPhysicalPort', has_metadata=True,
                               child_order=_SRIOVEPP_EL_ORDER)
class SRIOVEthPPort(ewrap.ElementWrapper):
    """The SR-IOV Ethernet Physical port."""

    def __init__(self):
        super(SRIOVEthPPort, self).__init__()
        # This must be set by the instantiating SRIOVAdapter.
        self._sriov_adap = None

    @property
    def sriov_adap(self):
        """Backpointer to the SRIOVAdapter owning this physical port."""
        if self._sriov_adap is None:
            raise NotImplementedError("Developer error: SRIOVAdapter pointer "
                                      "not set!")
        return self._sriov_adap

    @property
    def sriov_adap_id(self):
        """The integer sriov_adap_id of the SRIOVAdapter owning this port."""
        return self.sriov_adap.sriov_adap_id

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
        """Gets the minimum granularity in a float-percentage format.

        :return: If the property is say "2.45%", a value of .0245 will be
                 returned.
        """
        return self._get_val_percent(_SRIOVPP_MIN_ETHERNET_CAPACITY_GRAN)

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

    @property
    def curr_speed(self):
        return self._get_val_str(_SRIOVPP_CURR_SPEED)

    @property
    def mtu(self):
        """Result should be a SRIOVPPMTU value."""
        return self._get_val_str(_SRIOVPP_CFG_MTU)

    @mtu.setter
    def mtu(self, val):
        """Input val should be a SRIOVPPMTU value."""
        self.set_parm_value(_SRIOVPP_CFG_MTU, val)

    @property
    def switch_mode(self):
        """Result should be a network.VSwitchMode value."""
        return self._get_val_str(_SRIOVPP_CFG_SWMODE)

    @switch_mode.setter
    def switch_mode(self, val):
        """Input val should be a network.VSwitchMode value."""
        self.set_parm_value(_SRIOVPP_CFG_SWMODE, val)

    @property
    def flow_ctl(self):
        return self._get_val_bool(_SRIOVPP_CFG_FLOWCTL)

    @flow_ctl.setter
    def flow_ctl(self, val):
        self.set_parm_value(_SRIOVPP_CFG_FLOWCTL, u.sanitize_bool_for_api(val))


@ewrap.ElementWrapper.pvm_type('SRIOVConvergedNetworkAdapterPhysicalPort',
                               has_metadata=True,
                               child_order=_SRIOVCPP_EL_ORDER)
class SRIOVConvPPort(SRIOVEthPPort):
    """The SR-IOV Converged Physical port."""
    pass


@ewrap.EntryWrapper.pvm_type('SRIOVEthernetLogicalPort',
                             child_order=_SRIOVLP_EL_ORDER)
class SRIOVEthLPort(ewrap.EntryWrapper):
    """The SR-IOV Ethernet Logical port."""

    @classmethod
    def bld(cls, adapter, sriov_adap_id, pport_id, pvid=None, mac=None,
            allowed_vlans=u.VLANList.ALL, allowed_macs=u.MACList.ALL,
            is_promisc=False, cfg_capacity=None):
        """Create a wrapper used to create a logical port on the server.

        :param adapter: A pypowervm.adapter.Adapter (for traits, etc.)
        :param sriov_adap_id: Corresponds to SRIOVAdapter.SRIOVAdapterID,
                              *not* SRIOVAdapter.AdapterID
        :param pport_id: The physical port ID this logical port is part of.
        :param pvid: The port VLAN identifier for this logical port. Any
                     untagged traffic passing through this port will have
                     this VLAN tag added.
        :param mac: The MAC address to assign to the logical port.
        :param allowed_vlans: An integer list of VLANS allowed on this logical
                              port. Specify pypowervm.util.VLANList.ALL to
                              allow all VLANs or .NONE to allow no VLANs on
                              this logical port. Default: ALL.
        :param allowed_macs: List of string MAC addresses allowed on this
                             logical port. Specify pypowervm.util.MACList.ALL
                             to allow all MAC addresses, or .NONE to allow no
                             MAC addresses on this logical port.  Default: ALL.
        :param is_promisc: Set to True if using the logical port for bridging
                           (e.g. SEA, OVS, etc.); False if assigning directly
                           to an LPAR.  Only one logical port per physical port
                           may be promiscuous.
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
        lport.allowed_vlans = allowed_vlans
        if mac is not None:
            lport._mac(mac)
        lport.allowed_macs = allowed_macs
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
    def allowed_vlans(self):
        vlan_str = self._get_val_str(_SRIOVLP_ALLOWED_VLANS)
        return u.VLANList.unmarshal(vlan_str) if vlan_str is not None else None

    @allowed_vlans.setter
    def allowed_vlans(self, vlans):
        self.set_parm_value(_SRIOVLP_ALLOWED_VLANS, u.VLANList.marshal(vlans))

    @property
    def mac(self):
        """MAC address of the format XXXXXXXXXXXX (12 uppercase hex digits).

        This is the MAC address "burned into" the logical port.  The actual MAC
        address on the interface (cur_mac) may be this value or the value set
        from within the OS on the VM.
        """
        return self._get_val_str(_SRIOVLP_MAC)

    def _mac(self, value):
        self.set_parm_value(_SRIOVLP_MAC, u.sanitize_mac_for_api(value))

    @property
    def allowed_macs(self):
        amstr = self._get_val_str(_SRIOVLP_ALLOWED_MACS)
        return u.MACList.unmarshal(amstr) if amstr is not None else None

    @allowed_macs.setter
    def allowed_macs(self, maclist):
        self.set_parm_value(_SRIOVLP_ALLOWED_MACS, u.MACList.marshal(maclist))

    @property
    def cur_mac(self):
        """MAC address of the format XXXXXXXXXXXX (12 uppercase hex digits).

        This is the real value set on the interface, possibly by the VM's OS.

        Note that some SR-IOV cards are broken and don't report the OS-assigned
        value correctly.  In such cases, cur_mac will report the same as mac.
        """
        return self._get_val_str(_SRIOVLP_CUR_MAC)

    @property
    def loc_code(self):
        return self._get_val_str(_SRIOVLP_LOC_CODE)

    @property
    def vnic_port_usage(self):
        return self._get_val_str(_SRIOVLP_VNIC_PORT_USAGE)


@ewrap.EntryWrapper.pvm_type(_VNIC_DED, child_order=_VNIC_EL_ORDER)
class VNIC(ewrap.EntryWrapper):
    """A dedicated, possibly-redundant Virtual NIC."""

    @classmethod
    def bld(cls, adapter, pvid=None, slot_num=None,
            allowed_vlans=u.VLANList.ALL, mac_addr=None,
            allowed_macs=u.MACList.ALL, back_devs=None):
        """Build a new VNIC wrapper suitable for .create()

        A VNIC is a CHILD object on a LogicalPartition.  Usage models:
            vnic = VNIC.bld(...)
            vnic.back_devs.append(back_dev1)
            ...
        or
            vnic = VNIC.bld(..., back_devs=[back_dev1, back_dev2, ...])
        then
            vnic.create(parent=lpar_wrap)

        :param adapter: pypowervm.adapter.Adapter for REST API communication.
        :param pvid: Port VLAN ID for this vNIC.  If not specified, the vNIC's
                     traffic is untagged.
        :param slot_num: Desired virtual slot number on the owning LPAR.
        :param allowed_vlans: An integer list of VLANS allowed on this vNIC.
                              Specify pypowervm.util.VLANList.ALL to allow all
                              VLANs or .NONE to allow no VLANs on this vNIC.
                              Default: ALL.
        :param mac_addr: MAC address for the vNIC.
        :param allowed_macs: List of string MAC addresses allowed on this vNIC.
                             Specify pypowervm.util.MACList.ALL to allow all
                             MAC addresses, or .NONE to allow no MAC addresses
                             on this vNIC.  Default: ALL.
        :param back_devs: List of VNICBackDev wrappers each indicating a
                          combination of VIOS, SR-IOV adapter and physical port
                          on which to create the VF for the backing device.
                          See VNICBackDev.bld.  If not specified to bld, at
                          least one must be added before the VNIC can be
                          created.
        :return: A new VNIC wrapper.
        """
        vnic = super(VNIC, cls)._bld(adapter)
        if slot_num is not None:
            vnic._slot(slot_num)
        else:
            vnic._use_next_avail_slot_id = True

        vnic._details = _VNICDetails._bld_new(
            adapter, pvid=pvid, allowed_vlans=allowed_vlans, mac_addr=mac_addr,
            allowed_macs=allowed_macs)

        if back_devs:
            vnic.back_devs = back_devs
        return vnic

    @property
    def drc_name(self):
        return self._get_val_str(_VNIC_DRC_NAME)

    @property
    def lpar_id(self):
        """The integer ID, not UUID, of the LPAR owning this VNIC."""
        return self._get_val_int(_VNIC_LPAR_ID)

    @property
    def slot(self):
        return self._get_val_int(_VNIC_SLOT_NUM)

    def _slot(self, val):
        self.set_parm_value(_VNIC_SLOT_NUM, val)

    @property
    def _use_next_avail_slot_id(self):
        """Use next available (high) slot ID, true or false."""
        unasi_field = (_VNIC_USE_NEXT_AVAIL_HIGH_SLOT
                       if self.traits.has_high_slot
                       else _VNIC_USE_NEXT_AVAIL_SLOT)
        return self._get_val_bool(unasi_field)

    @_use_next_avail_slot_id.setter
    def _use_next_avail_slot_id(self, unasi):
        """Use next available (high) slot ID.

        :param unasi: Boolean value to set (True or False)
        """
        unasi_field = (_VNIC_USE_NEXT_AVAIL_HIGH_SLOT
                       if self.traits.has_high_slot
                       else _VNIC_USE_NEXT_AVAIL_SLOT)
        self.set_parm_value(unasi_field, u.sanitize_bool_for_api(unasi))

    @property
    def pvid(self):
        """The integer port VLAN ID, or None if the vNIC has no PVID."""
        return self._details.pvid

    @pvid.setter
    def pvid(self, val):
        self._details.pvid = val

    @property
    def allowed_vlans(self):
        return self._details.allowed_vlans

    @allowed_vlans.setter
    def allowed_vlans(self, vlans):
        self._details.allowed_vlans = vlans

    @property
    def mac(self):
        """MAC address of the format XXXXXXXXXXXX (12 uppercase hex digits)."""
        return self._details.mac

    def _mac(self, val):
        self._details._mac(val)

    @property
    def allowed_macs(self):
        return self._details.allowed_macs

    @allowed_macs.setter
    def allowed_macs(self, maclist):
        self._details.allowed_macs = maclist

    @property
    def capacity(self):
        """The capacity (float, 0.0-1.0) of the active backing logical port."""
        return self._details.capacity

    @property
    def _details(self):
        return _VNICDetails.wrap(self._find_or_seed(_VNIC_DETAILS))

    @_details.setter
    def _details(self, val):
        self.element.replace(self._find_or_seed(_VNIC_DETAILS), val.element)

    @property
    def back_devs(self):
        return ewrap.WrapperElemList(self._find_or_seed(_VNIC_BACK_DEVS),
                                     child_class=VNICBackDev,
                                     indirect=_VNICBD_CHOICE)

    @back_devs.setter
    def back_devs(self, new_devs):
        self.replace_list(_VNIC_BACK_DEVS, new_devs, indirect=_VNICBD_CHOICE)

    @property
    def auto_pri_failover(self):
        return self._details.auto_pri_failover

    @auto_pri_failover.setter
    def auto_pri_failover(self, val):
        self._details.auto_pri_failover = val


@ewrap.ElementWrapper.pvm_type(_VNIC_DETAILS, has_metadata=True,
                               child_order=_VNICD_EL_ORDER)
class _VNICDetails(ewrap.ElementWrapper):
    """The 'Details' sub-element of a VirtualNICDedicated."""

    @classmethod
    def _bld_new(cls, adapter, pvid=None, allowed_vlans=u.VLANList.ALL,
                 mac_addr=None, allowed_macs=u.MACList.ALL):
        """Create a new _VNICDetails wrapper suitable for insertion into a VNIC.

        Not to be called outside of VNIC.bld().

        :param adapter: pypowervm.adapter.Adapter for REST API communication.
        :param pvid: Port VLAN ID for this vNIC.  If not specified, the vNIC's
                     traffic is untagged.
        :param allowed_vlans: An integer list of VLANS allowed on this vNIC.
                              Specify pypowervm.util.VLANList.ALL to allow all
                              VLANs or .NONE to allow no VLANs on this vNIC.
                              Default: ALL.
        :param mac_addr: MAC address for the vNIC.
        :param allowed_macs: List of string MAC addresses allowed on this vNIC.
                             Specify pypowervm.util.MACList.ALL to allow all
                             MAC addresses, or .NONE to allow no MAC addresses
                             on this vNIC.  Default: ALL.
        :return: A new _VNICDetails wrapper.
        """
        vnicd = super(_VNICDetails, cls)._bld(adapter)
        if pvid is not None:
            vnicd.pvid = pvid
        vnicd.allowed_vlans = allowed_vlans
        if mac_addr is not None:
            vnicd._mac(mac_addr)
        vnicd.allowed_macs = allowed_macs
        return vnicd

    @property
    def pvid(self):
        """The integer port VLAN ID, or None if the vNIC has no PVID."""
        return self._get_val_int(_VNICD_PVID)

    @pvid.setter
    def pvid(self, val):
        self.set_parm_value(_VNICD_PVID, val)

    @property
    def allowed_vlans(self):
        vlan_str = self._get_val_str(_VNICD_ALLOWED_VLANS)
        return u.VLANList.unmarshal(vlan_str) if vlan_str is not None else None

    @allowed_vlans.setter
    def allowed_vlans(self, vlans):
        self.set_parm_value(_VNICD_ALLOWED_VLANS, u.VLANList.marshal(vlans))

    @property
    def mac(self):
        """MAC address of the format XXXXXXXXXXXX (12 uppercase hex digits)."""
        return self._get_val_str(_VNICD_MAC)

    def _mac(self, val):
        self.set_parm_value(_VNICD_MAC, u.sanitize_mac_for_api(val))

    @property
    def allowed_macs(self):
        amstr = self._get_val_str(_VNICD_ALLOWED_OS_MACS)
        return u.MACList.unmarshal(amstr) if amstr is not None else None

    @allowed_macs.setter
    def allowed_macs(self, maclist):
        self.set_parm_value(_VNICD_ALLOWED_OS_MACS, u.MACList.marshal(maclist))

    @property
    def capacity(self):
        """The capacity (float, 0.0-1.0) of the active backing logical port."""
        return self._get_val_percent(_VNICD_DES_CAP_PCT)

    @property
    def auto_pri_failover(self):
        return self._get_val_bool(_VNICD_AUTO_FB)

    @auto_pri_failover.setter
    def auto_pri_failover(self, val):
        self.set_parm_value(_VNICD_AUTO_FB, u.sanitize_bool_for_api(val))


@ewrap.ElementWrapper.pvm_type(_VNICBD, has_metadata=True,
                               child_order=_VNICBD_EL_ORDER)
class VNICBackDev(ewrap.ElementWrapper):
    """SR-IOV backing device for a vNIC."""

    @classmethod
    def bld(cls, adapter, vios_uuid, sriov_adap_id, pport_id, capacity=None,
            failover_pri=None):
        """Create a new VNICBackDev, suitable for inclusion in a VNIC wrapper.

        :param adapter: pypowervm.adapter.Adapter for REST API communication.
        :param vios_uuid: String UUID of the Virtual I/O Server to host the
                          vNIC server for this backing device.
        :param sriov_adap_id: Integer SR-IOV Adapter ID of the SR-IOV adapter
                              owning the physical port on which the backing VF
                              is to be created: SRIOVAdapter.sriov_adap_id.
        :param pport_id: Integer physical port ID of SR-IOV physical port on
                         which the VF is to be created: SRIOVEthPPort.port_id
        :param capacity: Float value between 0.0 and 1.0 indicating the minimum
                         fraction of the physical port's bandwidth allocated to
                         traffic over this backing device.  Must be a multiple
                         of SRIOVEthPPort.min_granularity for the physical port
                         indicated by pport_id.  If not specified,
                         SRIOVEthPPort.min_granularity is used by the platform.
        :param failover_pri: Positive integer value representing the failover
                             priority of this backing device.
        :return: A new VNICBackDev, suitable for inclusion in a VNIC wrapper.
        """
        bdev = super(VNICBackDev, cls)._bld(adapter)
        # TODO(IBM): Verify that this can be ManagedSystem-less
        bdev._vios_href(adapter.build_href(_VIOS, vios_uuid, xag=[]))
        bdev._sriov_adap_id(sriov_adap_id)
        bdev._pport_id(pport_id)
        if capacity is not None:
            bdev._capacity(capacity)
        if failover_pri is not None:
            bdev.failover_pri = failover_pri
        return bdev

    @property
    def vios_href(self):
        return self.get_href(_VNICBD_VIOS, one_result=True)

    def _vios_href(self, href):
        self.set_href(_VNICBD_VIOS, href)

    @property
    def sriov_adap_id(self):
        return self._get_val_int(_VNICBD_SRIOV_ADP_ID)

    def _sriov_adap_id(self, val):
        self.set_parm_value(_VNICBD_SRIOV_ADP_ID, val)

    @property
    def pport_id(self):
        return self._get_val_int(_VNICBD_PPORT_ID)

    def _pport_id(self, val):
        self.set_parm_value(_VNICBD_PPORT_ID, val)

    @property
    def lport_href(self):
        return self.get_href(_VNICBD_LPORT, one_result=True)

    @property
    def capacity(self):
        """Gets the allocated capacity in a float-percentage format.

        :return: If the property is say "2.45%", a value of .0245 will be
                 returned.
        """
        return self._get_val_percent(_VNICBD_CUR_CAP_PCT)

    def _capacity(self, float_val):
        self.set_parm_value(_VNICBD_CUR_CAP_PCT,
                            u.sanitize_percent_for_api(float_val))

    @property
    def failover_pri(self):
        """The failover priority value for this backing device.

        :return: A value between 1 and 100, inclusive, with a lower number
                 indicating the higher priority (i.e. the backingdevice with
                 priority 1 will take precedence over that with priority 2).
        """
        return self._get_val_int(_VNICBD_FAILOVER_PRI)

    @failover_pri.setter
    def failover_pri(self, val):
        self.set_parm_value(_VNICBD_FAILOVER_PRI, val, attrib=pc.ATTR_KSV140)

    @property
    def is_active(self):
        return self._get_val_bool(_VNICBD_ACTIVE)

    @property
    def status(self):
        return self._get_val_str(_VNICBD_STATUS)


@ewrap.ElementWrapper.pvm_type(_IO_ADPT_CHOICE, has_metadata=False)
class LinkAggrIOAdapterChoice(ewrap.ElementWrapper):
    """A free I/O Adapter link aggregation choice.

    Flattens this two step hierarchy to pull the information needed directly
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
