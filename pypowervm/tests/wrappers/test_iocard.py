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

import unittest

import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.util as u
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.managed_system as ms
import pypowervm.wrappers.network as net


class TestSRIOVAdapter(twrap.TestWrapper):

    file = 'sys_with_sriov.txt'
    wrapper_class_to_test = ms.System

    def setUp(self):
        super(TestSRIOVAdapter, self).setUp()
        self.sriovs = self.dwrap.asio_config.sriov_adapters

    def test_list(self):
        self.assertEqual(4, len(self.sriovs))
        for sriov in self.sriovs:
            self.assertIsInstance(sriov, card.SRIOVAdapter)

    def test_attrs(self):
        desc = 'PCIe2 4-port (10Gb FCoE & 1GbE) SR&RJ45 Adapter'

        self.assertEqual('553713696', self.sriovs[0].id)
        self.assertEqual(desc, self.sriovs[0].description)
        self.assertEqual('U78C7.001.RCH0004-P1-C8',
                         self.sriovs[0].phys_loc_code)

    def test_ids(self):
        """Test .id and .sriov_adap_id."""
        # AdapterID inherited from IOAdapter
        self.assertEqual('553713696', self.sriovs[0].id)
        self.assertEqual(1, self.sriovs[0].sriov_adap_id)

        self.assertEqual('553713680', self.sriovs[2].id)
        self.assertIsNone(self.sriovs[2].sriov_adap_id)

    def test_mode(self):
        self.assertEqual('Sriov', self.sriovs[0].mode)
        # Test setter
        self.sriovs[0].mode = 'unknown'
        self.assertEqual('unknown', self.sriovs[0].mode)

    def test_state(self):
        self.assertEqual('Running', self.sriovs[0].state)

    def test_physical_ports(self):
        adapter = self.sriovs[0]

        phyports = adapter.phys_ports
        self.assertEqual(4, len(phyports))

        # Get converged and ethernet physical ports each
        conv_port, eth_port = self.sriovs[0].phys_ports[:3:2]

        # Converged physical ports test
        self.assertEqual(self.sriovs[0], conv_port.sriov_adap)
        self.assertEqual(self.sriovs[0].sriov_adap_id, conv_port.sriov_adap_id)

        self.assertEqual(None, conv_port.label)
        conv_port.label = 'updatedlabel'
        self.assertEqual('updatedlabel', conv_port.label)

        self.assertEqual('U78C7.001.RCH0004-P1-C8-T1', conv_port.loc_code)

        self.assertEqual(0, conv_port.port_id)

        self.assertEqual(None, conv_port.sublabel)
        conv_port.sublabel = 'updatedsublabel'
        self.assertEqual('updatedsublabel', conv_port.sublabel)

        self.assertEqual(True, conv_port.link_status)

        self.assertEqual(20, conv_port.cfg_max_lps)
        conv_port.cfg_max_lps = 40
        self.assertEqual(40, conv_port.cfg_max_lps)

        self.assertEqual(2, conv_port.cfg_lps)

        self.assertEqual(0.02, conv_port.min_granularity)

        self.assertEqual(20, conv_port.supp_max_lps)

        self.assertEqual(0.02, conv_port.allocated_capacity)

        # Ethernet physical ports test
        self.assertEqual(self.sriovs[0], eth_port.sriov_adap)
        self.assertEqual(self.sriovs[0].sriov_adap_id, eth_port.sriov_adap_id)

        self.assertEqual(None, eth_port.label)
        eth_port.label = 'updatedlabel'
        self.assertEqual('updatedlabel', eth_port.label)

        self.assertEqual('U78C7.001.RCH0004-P1-C8-T3', eth_port.loc_code)

        self.assertEqual(2, eth_port.port_id)

        self.assertEqual(None, eth_port.sublabel)
        eth_port.sublabel = 'updatedsublabel'
        self.assertEqual('updatedsublabel', eth_port.sublabel)

        self.assertEqual(True, eth_port.link_status)

        self.assertEqual(4, eth_port.cfg_max_lps)
        eth_port.cfg_max_lps = 40
        self.assertEqual(40, eth_port.cfg_max_lps)

        self.assertEqual(0.02, eth_port.min_granularity)

        self.assertEqual(4, eth_port.supp_max_lps)

        self.assertEqual(0.02, eth_port.allocated_capacity)

        self.assertEqual(card.SRIOVSpeed.E1G, eth_port.curr_speed)

        self.assertEqual(card.SRIOVPPMTU.E1500, eth_port.mtu)
        eth_port.mtu = card.SRIOVPPMTU.E9000
        self.assertEqual(card.SRIOVPPMTU.E9000, eth_port.mtu)

        self.assertFalse(eth_port.flow_ctl)
        eth_port.flow_ctl = True
        self.assertTrue(eth_port.flow_ctl)

        self.assertEqual(net.VSwitchMode.VEB, eth_port.switch_mode)
        eth_port.switch_mode = net.VSwitchMode.VEPA
        self.assertEqual(net.VSwitchMode.VEPA, eth_port.switch_mode)

    def test_physical_ports_no_vivify(self):
        """Don't accidentally vivify [Converged]EthernetPhysicalPorts.

        See https://bugs.launchpad.net/pypowervm/+bug/1617050
        This test case has to prove that, when EthernetPhysicalPorts doesn't
        exist in the XML, asking for phys_ports doesn't create it.
        """
        # 2nd and 3rd SRIOV adapters have no pports
        adp = self.sriovs[2]
        self.assertNotIn('<EthernetPhysicalPorts ', adp.toxmlstring())
        self.assertNotIn('<ConvergedEthernetPhysicalPorts ', adp.toxmlstring())
        self.assertEqual([], adp.phys_ports)
        self.assertNotIn('<EthernetPhysicalPorts ', adp.toxmlstring())
        self.assertNotIn('<ConvergedEthernetPhysicalPorts ', adp.toxmlstring())


class TestLogicalPort(twrap.TestWrapper):

    file = 'sriov_lp_feed.txt'
    wrapper_class_to_test = card.SRIOVEthLPort

    def test_logical_ports(self):
        # Verify logical port getters
        lport = self.dwrap
        self.assertEqual(654327810, lport.lport_id)
        self.assertEqual(1, lport.sriov_adap_id)
        self.assertFalse(lport.is_promisc)
        self.assertEqual('PHB 4098', lport.dev_name)
        self.assertEqual(0.02, lport.cfg_capacity)
        self.assertEqual(2, lport.pport_id)
        self.assertEqual(0, lport.pvid)
        self.assertEqual(u.VLANList.ALL, lport.allowed_vlans)
        self.assertEqual('8ACA227C6E00', lport.mac)
        self.assertEqual(u.MACList.NONE, lport.allowed_macs)
        self.assertEqual('000000000000', lport.cur_mac)
        self.assertEqual('U78CB.001.WZS0485-P1-C5-T3-S2', lport.loc_code)
        self.assertEqual(card.VNICPortUsage.NOT_VNIC, lport.vnic_port_usage)

        # Verify logical port setters
        lport._sriov_adap_id(2)
        self.assertEqual(2, lport.sriov_adap_id)
        lport._is_promisc('true')
        self.assertTrue(lport.is_promisc)
        lport._pport_id(3)
        self.assertEqual(3, lport.pport_id)
        lport.allowed_vlans = [1, 2, 3]
        self.assertEqual([1, 2, 3], lport.allowed_vlans)
        lport.allowed_macs = u.MACList.ALL
        self.assertEqual(u.MACList.ALL, lport.allowed_macs)
        lport._cfg_capacity(0.0)
        self.assertEqual(0.0, lport.cfg_capacity)
        lport._cfg_capacity(1.0)
        self.assertEqual(1.0, lport.cfg_capacity)

        # Verify setter validation
        self.assertRaises(ValueError, lport._cfg_capacity, '5.0%')
        self.assertRaises(ValueError, lport._cfg_capacity, '2')
        self.assertRaises(ValueError, lport._cfg_capacity, float(2))
        self.assertRaises(ValueError, lport._cfg_capacity, '1.01')
        self.assertRaises(ValueError, lport._cfg_capacity, float(1.01))
        self.assertRaises(ValueError, lport._cfg_capacity, '-0.01')
        self.assertRaises(ValueError, lport._cfg_capacity, float(-0.01))
        self.assertRaises(ValueError, lport._cfg_capacity, 'garbage')
        self.assertRaises(ValueError, lport._cfg_capacity, '0.72%')

        # Verify bld method
        # With default kwargs
        lport = card.SRIOVEthLPort.bld(
            self.adpt, 5, 6)
        self.assertEqual(5, lport.sriov_adap_id)
        self.assertFalse(lport.is_promisc)
        self.assertIsNone(lport.cfg_capacity)
        self.assertEqual(6, lport.pport_id)
        self.assertIsNone(lport.pvid)
        self.assertEqual(u.MACList.ALL, lport.allowed_vlans)
        self.assertIsNone(lport.mac)
        self.assertEqual(u.MACList.ALL, lport.allowed_macs)
        # With explicit kwargs
        lport = card.SRIOVEthLPort.bld(
            self.adpt, 5, 6, pvid=2230, mac='12:ab:34:CD:56:ef',
            allowed_vlans=[1, 2, 3], allowed_macs=u.MACList.NONE,
            is_promisc=True, cfg_capacity=0.05)
        self.assertEqual(5, lport.sriov_adap_id)
        self.assertTrue(lport.is_promisc)
        self.assertEqual(0.05, lport.cfg_capacity)
        self.assertEqual(6, lport.pport_id)
        self.assertEqual(2230, lport.pvid)
        self.assertEqual([1, 2, 3], lport.allowed_vlans)
        self.assertEqual('12AB34CD56EF', lport.mac)
        self.assertEqual(u.MACList.NONE, lport.allowed_macs)


class TestVNIC(twrap.TestWrapper):
    file = 'vnic_feed.txt'
    wrapper_class_to_test = card.VNIC

    def test_vnic_props(self):
        self.assertEqual('U8286.42A.21C1B6V-V10-C3', self.dwrap.drc_name)
        self.assertEqual(10, self.dwrap.lpar_id)
        self.assertEqual(7, self.dwrap.slot)

    def test_vnic_and_backdev_bld(self):
        # Defaults in kwargs
        vnic = card.VNIC.bld(self.adpt)
        backdevs = vnic.back_devs
        self.assertEqual(self.adpt, vnic.adapter)
        self.assertIsNone(vnic.pvid)
        self.assertIsNotNone(backdevs)
        self.assertEqual(0, len(backdevs))
        # Fields without setters
        self.assertIsNone(vnic.drc_name)
        self.assertIsNone(vnic.lpar_id)
        self.assertIsNone(vnic.capacity)
        # Fields with setters not invoked (because not specified)
        self.assertIsNone(vnic.slot)
        self.assertTrue(vnic._use_next_avail_slot_id)
        self.assertFalse(vnic._get_val_bool(card._VNIC_USE_NEXT_AVAIL_SLOT))
        self.assertEqual(u.VLANList.ALL, vnic.allowed_vlans)
        self.assertIsNone(vnic.mac)
        self.assertEqual(u.MACList.ALL, vnic.allowed_macs)
        self.assertFalse(vnic.auto_pri_failover)
        vnic.auto_pri_failover = True
        self.assertTrue(vnic.auto_pri_failover)
        vnic.auto_pri_failover = False
        self.assertFalse(vnic.auto_pri_failover)

        # Values in kwargs

        def build_href(sch, uuid, **kwargs):
            self.assertEqual('VirtualIOServer', sch)
            self.assertEqual([], kwargs['xag'])
            return 'http://' + uuid
        self.adpt.build_href.side_effect = build_href

        backdevs = [card.VNICBackDev.bld(self.adpt, 'vios_uuid', 3, 4),
                    card.VNICBackDev.bld(self.adpt, 'vios_uuid2', 5, 6,
                                         capacity=0.3456789, failover_pri=50)]
        vnic = card.VNIC.bld(
            self.adpt, pvid=7, slot_num=8, allowed_vlans=[1, 2],
            mac_addr='m:a:c',
            allowed_macs=['AB:12:CD:34:EF:56', '12ab34cd56ef'],
            back_devs=backdevs)
        backdevs = vnic.back_devs
        self.assertEqual(self.adpt, vnic.adapter)
        self.assertIsNone(vnic.drc_name)
        self.assertIsNone(vnic.lpar_id)
        self.assertEqual(7, vnic.pvid)
        self.assertEqual(8, vnic.slot)
        self.assertFalse(vnic._use_next_avail_slot_id)
        self.assertFalse(vnic._get_val_bool(card._VNIC_USE_NEXT_AVAIL_SLOT))
        self.assertEqual([1, 2], vnic.allowed_vlans)
        self.assertEqual(['AB12CD34EF56', '12AB34CD56EF'], vnic.allowed_macs)
        self.assertEqual('MAC', vnic.mac)
        self.assertIsNotNone(backdevs)
        self.assertEqual(2, len(backdevs))
        bd1, bd2 = backdevs
        self.assertEqual(self.adpt, bd1.adapter)
        self.adpt.build_href.assert_any_call('VirtualIOServer', 'vios_uuid',
                                             xag=[])
        self.assertEqual('http://vios_uuid', bd1.vios_href)
        self.assertEqual(3, bd1.sriov_adap_id)
        self.assertEqual(4, bd1.pport_id)
        self.assertIsNone(bd1.capacity)
        self.assertEqual(self.adpt, bd2.adapter)
        self.adpt.build_href.assert_any_call('VirtualIOServer', 'vios_uuid2',
                                             xag=[])
        self.assertEqual('http://vios_uuid2', bd2.vios_href)
        self.assertEqual(5, bd2.sriov_adap_id)
        self.assertEqual(6, bd2.pport_id)
        self.assertEqual(0.3457, bd2.capacity)
        self.assertIsNone(bd1.failover_pri)
        self.assertEqual(bd2.failover_pri, 50)
        bd1.failover_pri = 42
        bd2.failover_pri = 60
        self.assertEqual(bd1.failover_pri, 42)
        self.assertEqual(bd2.failover_pri, 60)

    def test_details_props_inner(self):
        self._test_details_props(self.dwrap._details)

    def test_details_props_outer(self):
        self._test_details_props(self.dwrap)

    def _test_details_props(self, dets):
        self.assertEqual(0, dets.pvid)
        dets.pvid = 123
        self.assertEqual(123, dets.pvid)
        self.assertEqual(u.VLANList.ALL, dets.allowed_vlans)
        dets.allowed_vlans = [1, 2, 3]
        self.assertEqual([1, 2, 3], dets.allowed_vlans)
        self.assertEqual(0.02, dets.capacity)

        def bad_capacity_setter(val):
            dets.capacity = val
        self.assertRaises(AttributeError, bad_capacity_setter, '0.04')

        def bad_vlans_setter(val):
            dets.allowed_vlans = val
        self.assertRaises(ValueError, bad_vlans_setter, 'foo')
        self.assertRaises(ValueError, bad_vlans_setter, ['a', 'b', 'c'])
        self.assertEqual('AE7A25E59A07', dets.mac)
        self.assertEqual(u.MACList.ALL, dets.allowed_macs)
        dets.allowed_macs = ['AB:12:cd:34:EF:56', '12ab34CD56ef']
        self.assertEqual(['AB12CD34EF56', '12AB34CD56EF'],
                         dets.allowed_macs)

        def bad_macs_setter(val):
            dets.allowed_macs = val
        self.assertRaises(ValueError, bad_macs_setter, 'foo')

    def test_backdev_props(self):
        self.assertEqual(2, len(self.dwrap.back_devs))
        backdev = self.dwrap.back_devs[0]
        self.assertEqual(
            'https://9.1.2.3:12443/rest/api/uom/ManagedSystem/1cab7366-6b73-34'
            '2c-9f43-ddfeb9f8edd3/VirtualIOServer/3E3F9BFC-C4EE-439E-B70A-1D36'
            '9213ED83', backdev.vios_href)
        self.assertEqual(1, backdev.sriov_adap_id)
        self.assertEqual(0, backdev.pport_id)
        self.assertEqual(
            'https://9.1.2.3:12443/rest/api/uom/VirtualIOServer/3E3F9BFC-C4EE-'
            '439E-B70A-1D369213ED83/SRIOVEthernetLogicalPort/af2a8c95-58d1-349'
            '6-9af6-8cd562f0e839', backdev.lport_href)
        self.assertEqual(0.02, backdev.capacity)
        self.assertFalse(backdev.is_active)
        self.assertEqual(backdev.status, card.VNICBackDevStatus.LINK_DOWN)
        self.assertTrue(self.dwrap.back_devs[1].is_active)
        self.assertEqual(self.dwrap.back_devs[1].status,
                         card.VNICBackDevStatus.OPERATIONAL)

if __name__ == "__main__":
    unittest.main()
