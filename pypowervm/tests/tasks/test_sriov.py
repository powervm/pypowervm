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

"""Tests for pypowervm.tasks.sriov."""

import mock
import testtools

import pypowervm.exceptions as ex
import pypowervm.tasks.sriov as tsriov
import pypowervm.tests.test_fixtures as fx
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.iocard as card
import pypowervm.wrappers.managed_system as ms


def fake_sriov(mode, state, sriov_adap_id, phys_ports):
    return mock.Mock(mode=mode, state=state, sriov_adap_id=sriov_adap_id,
                     phys_loc_code='sriov_loc%d' % sriov_adap_id,
                     phys_ports=phys_ports)


def fake_pport(sriov_adap_id, port_id, cfg_lps, alloc_cap):
    return mock.Mock(sriov_adap_id=sriov_adap_id, port_id=port_id,
                     loc_code='pport_loc%d' % port_id,
                     min_granularity=float(port_id) / 1000,
                     cfg_max_lps=20,
                     cfg_lps=cfg_lps,
                     allocated_capacity=alloc_cap,
                     link_status=True)


def good_sriov(sriov_adap_id, pports):
    return fake_sriov(card.SRIOVAdapterMode.SRIOV,
                      card.SRIOVAdapterState.RUNNING, sriov_adap_id, pports)

ded_sriov = fake_sriov(card.SRIOVAdapterMode.DEDICATED, None, 86, [])
down_sriov = fake_sriov(card.SRIOVAdapterMode.SRIOV,
                        card.SRIOVAdapterState.FAILED, 68, [])


def sys_wrapper(sriovs, vnic_capable=True, vnic_failover_capable=True):
    mock_sys = mock.Mock(asio_config=mock.Mock(sriov_adapters=sriovs))

    def get_cap(cap):
        capabilities = {
            'vnic_capable': vnic_capable,
            'vnic_failover_capable': vnic_failover_capable}
        return capabilities[cap]
    mock_sys.get_capability.side_effect = get_cap

    return mock_sys


class TestSriov(testtools.TestCase):

    def setUp(self):
        super(TestSriov, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.fake_sriovs = [
            good_sriov(1, [fake_pport(1, pid, lps, cap) for pid, lps, cap in (
                (11, 0, 0.95), (12, 9, 0.0), (13, 5, 0.03), (14, 20, 0.987))]),
            ded_sriov,
            good_sriov(2, [fake_pport(2, 21, 19, 0.3)]),
            down_sriov,
            good_sriov(3, []),
            good_sriov(4, [fake_pport(4, pid, 1, cap) for pid, cap in (
                (41, 0.02), (42, 0.01))]),
            good_sriov(5, [fake_pport(5, pid, lps, cap) for pid, lps, cap in (
                (51, 17, 0.49), (52, 3, 0.0), (53, 50, 0.05), (54, 11, 0.0),
                (55, 6, 0.4), (56, 13, 0.1), (57, 0, 0.15), (58, 7, 1.0))])]
        # Mark link status down on 5/55.
        self.fake_sriovs[6].phys_ports[4].link_status = False

    def test_get_good_sriovs(self):
        """Test _get_good_sriovs helper."""
        sriovs = tsriov._get_good_sriovs(self.fake_sriovs)
        self.assertEqual(5, len(sriovs))
        self.assertEqual(['sriov_loc%d' % x for x in range(1, 6)],
                         [sriov.phys_loc_code for sriov in sriovs])

        # Error case: none found.
        self.assertRaises(ex.NoRunningSharedSriovAdapters,
                          tsriov._get_good_sriovs, [ded_sriov, down_sriov])

    def test_get_good_pport_list(self):
        """Test _get_good_pport_list helper."""
        def validate_pports(pports, ids):
            # List of phys locs
            self.assertSetEqual({'pport_loc%d' % x for x in ids},
                                {pport.loc_code for pport in pports})
            # We added the appropriate sriov_adap_id
            for pport in pports:
                # Set up such that port ID xy always sits on adapter with ID x
                self.assertEqual(pport.port_id // 10, pport.sriov_adap_id)

        # Base case: no hits
        self.assertEqual([], tsriov._get_good_pport_list(
            self.fake_sriovs, ['nowt', 'to', 'see', 'here'], None, 0, False))
        # Validate redundancy - same thing but with nonzero redundancy
        self.assertRaises(
            ex.InsufficientSRIOVCapacity, tsriov._get_good_pport_list,
            self.fake_sriovs, ['nothing', 'to', 'see', 'here'], None, 1, False)
        # Make sure we can get the ones we specify, that are actually there.
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in {
                51, 13, 68, 123, 21, 57, 42}], None, 4, False)
        validate_pports(pports, {42, 13, 57, 21, 51})
        # Make sure we can filter by saturation (capacity/LPs).  14, 53, and 58
        # should filter themselves - they're already too full for their
        # min_granularity and/or configured LPs.
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in {
                58, 52, 14, 11, 53}], None, 0, False)
        validate_pports(pports, (52, 11))
        # Now specify capacity higher than 11 can handle - it should drop off
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in {
                58, 52, 14, 11, 53}], 0.06, 0, False)
        validate_pports(pports, {52})
        # Filter link-down ports.  14, 53, and 58 don't appear because they're
        # saturated by capacity and/or configured LPs.  55 doesn't appear
        # because it's link-down.
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in range(60)], None, 0,
            True)
        validate_pports(pports, {12, 52, 54, 42, 13, 41, 56, 57, 21, 51, 11})

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    def test_check_sys_vnic_capabilities(self, mock_sys_get):
        sys_yes_yes = sys_wrapper(None)
        sys_yes_no = sys_wrapper(None, vnic_failover_capable=False)
        sys_no_yes = sys_wrapper(None, vnic_capable=False)
        sys_no_no = sys_wrapper(None, vnic_capable=False,
                                vnic_failover_capable=False)
        # With sys param None, does a get; vnic & failover checks pass
        mock_sys_get.return_value = [sys_yes_yes]
        self.assertEqual(sys_yes_yes,
                         tsriov._check_sys_vnic_capabilities('adap', None, 2))
        mock_sys_get.assert_called_once_with('adap')

        mock_sys_get.reset_mock()

        # No get; vnic & !failover ok
        self.assertEqual(
            sys_yes_no,
            tsriov._check_sys_vnic_capabilities('adap', sys_yes_no, 1))
        mock_sys_get.assert_not_called()

        # Same, but 0 is a valid min
        self.assertEqual(
            sys_yes_no,
            tsriov._check_sys_vnic_capabilities('adap', sys_yes_no, 0))

        # vnic & !failover !ok
        self.assertRaises(
            ex.VNICFailoverNotSupportedSys,
            tsriov._check_sys_vnic_capabilities, 'adap', sys_yes_no, 2)

        # !vnic !ok even if failover ok (which would really never happen)
        self.assertRaises(
            ex.SystemNotVNICCapable,
            tsriov._check_sys_vnic_capabilities, 'adap', sys_no_yes, 2)

        # !vnic !failover !ok
        self.assertRaises(
            ex.SystemNotVNICCapable,
            tsriov._check_sys_vnic_capabilities, 'adap', sys_no_no, 1)

    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    def test_check_and_filter_vioses(self, mock_vioget):
        vios_yes_yes = mock.Mock(vnic_capable=True, vnic_failover_capable=True)
        vios_yes_no = mock.Mock(vnic_capable=True, vnic_failover_capable=False)
        vios_no_yes = mock.Mock(vnic_capable=False, vnic_failover_capable=True)
        vios_no_no = mock.Mock(vnic_capable=False, vnic_failover_capable=False)

        # No redundancy, no pre-seeded list.
        violist = [vios_yes_yes, vios_yes_no, vios_no_yes, vios_no_no]
        mock_vioget.return_value = violist
        # Because at least one VIOS was failover-capable, the non-capable one
        # is excluded.
        self.assertEqual([vios_yes_yes],
                         tsriov._check_and_filter_vioses('adap', None, 1))
        mock_vioget.assert_called_once_with('adap', xag=[], vios_wraps=None,
                                            find_min=1)

        mock_vioget.reset_mock()

        # With redundancy, pre-seeded list
        self.assertEqual([vios_yes_yes], tsriov._check_and_filter_vioses(
            'adap', violist, 2))
        mock_vioget.assert_called_once_with('adap', xag=[],
                                            vios_wraps=violist, find_min=1)

        # None capable
        violist = [vios_no_yes, vios_no_no]
        mock_vioget.return_value = violist
        self.assertRaises(ex.NoVNICCapableVIOSes,
                          tsriov._check_and_filter_vioses, 'adap', None, 1)

        # None redundancy capable
        violist = [vios_yes_no, vios_no_yes, vios_no_no]
        mock_vioget.return_value = violist
        self.assertRaises(ex.VNICFailoverNotSupportedVIOS,
                          tsriov._check_and_filter_vioses, 'adap', None, 2)

    @mock.patch('pypowervm.tasks.sriov._check_and_filter_vioses')
    @mock.patch('random.shuffle')
    def test_set_vnic_back_devs(self, mock_shuffle, mock_vioget):
        """Test set_vnic_back_devs."""
        mock_sys = sys_wrapper(self.fake_sriovs)
        mock_vioget.return_value = [mock.Mock(uuid='vios_uuid1'),
                                    mock.Mock(uuid='vios_uuid2'),
                                    mock.Mock(uuid='vios_uuid3')]
        self.adpt.build_href.side_effect = lambda *a, **k: '%s' % a[1]
        vnic = card.VNIC.bld(self.adpt, pvid=5)
        self.assertEqual(0, len(vnic.back_devs))
        # Silly case: redundancy of zero
        tsriov.set_vnic_back_devs(vnic, [], sys_w=mock_sys, redundancy=0)
        self.assertEqual(0, len(vnic.back_devs))
        mock_vioget.assert_called_once_with(self.adpt, None, 0)

        cap = 0.019
        # Things to note about the following:
        # - VIOSes rotate.  1, 2, 3, repeat.  If we hadn't mocked shuffle, the
        #   base order would be random, but they would still rotate in whatever
        #   that shuffled order was.
        # - The least-used (emptiest) physical ports come first...
        # - ...except (e.g. 21) we force distribution across cards, so...
        # - ...cards alternate until exhausted; hence 5 repeated at the end.
        # - Capacity set across the board according to the parameter.
        all_back_devs = [('vios_uuid1', 1, 12, cap),
                         ('vios_uuid2', 5, 52, cap),
                         ('vios_uuid3', 4, 42, cap),
                         ('vios_uuid1', 2, 21, cap),
                         ('vios_uuid2', 5, 54, cap),
                         ('vios_uuid3', 4, 41, cap),
                         ('vios_uuid1', 1, 13, cap),
                         ('vios_uuid2', 5, 56, cap),
                         ('vios_uuid3', 1, 11, cap),
                         ('vios_uuid1', 5, 57, cap),
                         ('vios_uuid2', 5, 55, cap),
                         ('vios_uuid3', 5, 51, cap)]
        # 5/55 is link-down.  When it drops off, the last one moves to VIOS 2.
        live_back_devs = all_back_devs[:10] + [('vios_uuid2', 5, 51, cap)]

        # Use 'em all
        tsriov.set_vnic_back_devs(vnic, ['pport_loc%d' % x for x in range(60)],
                                  sys_w=mock_sys, capacity=cap, redundancy=12)
        self.assertEqual(all_back_devs,
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        # Check port status - 55 drops off
        tsriov.set_vnic_back_devs(vnic, ['pport_loc%d' % x for x in range(60)],
                                  sys_w=mock_sys, capacity=cap, redundancy=11,
                                  check_port_status=True)
        self.assertEqual(live_back_devs,
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        # Fail if we can't satisfy redundancy
        self.assertRaises(
            ex.InsufficientSRIOVCapacity, tsriov.set_vnic_back_devs, vnic,
            ['pport_loc%d' % x for x in range(60)],
            sys_w=mock_sys, capacity=cap, redundancy=13)

        # The passed-in wrapper isn't modified if the method raises.
        self.assertEqual(live_back_devs,
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        # Make sure redundancy caps it.
        # By reusing vnic without resetting its back_devs, we're proving the
        # documented behavior that the method clears first.
        tsriov.set_vnic_back_devs(vnic, ['pport_loc%d' % x for x in range(60)],
                                  sys_w=mock_sys, capacity=cap, redundancy=5)
        self.assertEqual(all_back_devs[:5],
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        self.assertEqual(5, mock_shuffle.call_count)

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    def test_find_pports_for_portlabel(self, mock_sys_get):
        physnet = 'default'
        sriov_adaps = [
            mock.Mock(phys_ports=[
                mock.Mock(loc_code='port1', label='default'),
                mock.Mock(loc_code='port3', label='data1')]),
            mock.Mock(phys_ports=[
                mock.Mock(loc_code='port4', label='data2'),
                mock.Mock(loc_code='port2', label='default')])]
        sys = mock.Mock(asio_config=mock.Mock(sriov_adapters=sriov_adaps))
        mock_sys_get.return_value = [sys]
        pports = tsriov.find_pports_for_portlabel(physnet, sriov_adaps)
        self.assertEqual({'port1', 'port2'},
                         {pport.loc_code for pport in pports})

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    def test_find_pports_for_portlabel_blank(self, mock_sys_get):
        physnet = 'default'
        sriov_adaps = [
            mock.Mock(phys_ports=[
                mock.Mock(loc_code='port1', label=''),
                mock.Mock(loc_code='port3', label='data1')]),
            mock.Mock(phys_ports=[
                mock.Mock(loc_code='port4', label='data2'),
                mock.Mock(loc_code='port2', label='')])]
        sys = mock.Mock(asio_config=mock.Mock(sriov_adapters=sriov_adaps))
        mock_sys_get.return_value = [sys]
        pports = tsriov.find_pports_for_portlabel(physnet, sriov_adaps)
        self.assertEqual({'port1', 'port2'},
                         {pport.loc_code for pport in pports})


class TestSafeUpdatePPort(testtools.TestCase):

    @mock.patch('pypowervm.tasks.partition.get_partitions')
    @mock.patch('pypowervm.wrappers.iocard.VNIC.get')
    def test_get_lpar_vnics(self, mock_vnics, mock_get_pars):
        lpars = ['lpar1', 'lpar2', 'lpar3']
        mock_get_pars.return_value = lpars
        mock_vnics.side_effect = ['list1', 'list2', 'list3']
        self.assertEqual({'lpar%d' % i: 'list%d' % i for i in (1, 2, 3)},
                         tsriov.get_lpar_vnics('adap'))
        mock_get_pars.assert_called_once_with('adap', lpars=True, vioses=False)
        for lpar in lpars:
            mock_vnics.assert_any_call('adap', parent=lpar)

    def test_vnics_using_pport(self):
        lpar1 = mock.Mock()
        lpar1.configure_mock(name='lpar1', uuid='lpar_uuid1')
        lpar2 = mock.Mock()
        lpar2.configure_mock(name='lpar2', uuid='lpar_uuid2')
        vnic1 = mock.Mock(uuid='vnic_uuid1', back_devs=[
            mock.Mock(sriov_adap_id=1, pport_id=1),
            mock.Mock(sriov_adap_id=2, pport_id=2)])
        vnic2 = mock.Mock(uuid='vnic_uuid2', back_devs=[
            mock.Mock(sriov_adap_id=1, pport_id=2),
            mock.Mock(sriov_adap_id=2, pport_id=1)])
        vnic3 = mock.Mock(uuid='vnic_uuid3', back_devs=[
            mock.Mock(sriov_adap_id=3, pport_id=1),
            mock.Mock(sriov_adap_id=4, pport_id=2)])
        vnic4 = mock.Mock(uuid='vnic_uuid4', back_devs=[
            mock.Mock(sriov_adap_id=1, pport_id=2),
            mock.Mock(sriov_adap_id=4, pport_id=2)])
        lpar2vnics = {lpar1: [vnic1, vnic2], lpar2: [vnic3, vnic4]}
        # Not in use
        self.assertEqual([], tsriov._vnics_using_pport(mock.Mock(
            sriov_adap_id=1, port_id=3, loc_code='not_used'), lpar2vnics))
        # Used once
        ret = tsriov._vnics_using_pport(mock.Mock(
            sriov_adap_id=1, port_id=1, loc_code='loc1'), lpar2vnics)
        self.assertEqual(1, len(ret))
        # loc1 backs vNIC for LPAR lpar1 (lpar_uuid1 / vnic_uuid1)
        self.assertIn('loc1', ret[0])
        self.assertIn('lpar1', ret[0])
        self.assertIn('lpar_uuid1', ret[0])
        self.assertIn('vnic_uuid1', ret[0])
        # Used twice
        ret = tsriov._vnics_using_pport(mock.Mock(
            sriov_adap_id=1, port_id=2, loc_code='loc2'), lpar2vnics)
        self.assertEqual(2, len(ret))
        # Order of the return is not deterministic.  Reverse if necessary
        if 'lpar1' not in ret[0]:
            ret = ret[::-1]
        # loc2 backs vNIC for LPAR lpar1 (lpar_uuid1 / vnic_uuid2)
        self.assertIn('loc2', ret[0])
        self.assertIn('lpar1', ret[0])
        self.assertIn('lpar_uuid1', ret[0])
        self.assertIn('vnic_uuid2', ret[0])
        # loc2 backs vNIC for LPAR lpar2 (lpar_uuid2 / vnic_uuid4)
        self.assertIn('loc2', ret[1])
        self.assertIn('lpar2', ret[1])
        self.assertIn('lpar_uuid2', ret[1])
        self.assertIn('vnic_uuid4', ret[1])

    @mock.patch('pypowervm.tasks.sriov.get_lpar_vnics')
    @mock.patch('pypowervm.tasks.sriov._vnics_using_pport')
    def test_vet_port_usage(self, mock_vup, mock_glv):
        label_index = {'loc1': 'pre_label1', 'loc2': '', 'loc3': 'pre_label3',
                       'loc4': 'pre_label4'}
        # No LPs
        pport1 = mock.Mock(cfg_lps=0, loc_code='loc1', label='post_label1')
        # Pre-label empty, but label changed
        pport2 = mock.Mock(loc_code='loc2', label='post_label2')
        # Pre-label matches post-label
        pport3 = mock.Mock(loc_code='loc3', label='pre_label3')
        # Label changed
        pport4 = mock.Mock(loc_code='loc4', label='post_label4')
        pport5 = mock.Mock(loc_code='loc3', label='post_label3')
        # PPorts that hit the first three criteria (no LPs, label originally
        # unset, label unchanged) don't trigger expensive get_lpar_vnics or
        # _vnics_using_pport.
        sriov1 = mock.Mock(phys_ports=[pport1, pport2])
        sriov2 = mock.Mock(phys_ports=[pport3])
        ret = tsriov._vet_port_usage(
            mock.Mock(asio_config=mock.Mock(sriov_adapters=[sriov1, sriov2])),
            label_index)
        self.assertEqual([], ret)
        mock_vup.assert_not_called()
        mock_glv.assert_not_called()
        # Multiple pports that pass the easy criteria; get_lpar_vnics only
        # called once.
        mock_vup.side_effect = [1], [2]
        sriov3 = mock.Mock(phys_ports=[pport4, pport5])
        ret = tsriov._vet_port_usage(mock.Mock(
            adapter='adap', asio_config=mock.Mock(
                sriov_adapters=[sriov1, sriov3])), label_index)
        mock_glv.assert_called_once_with('adap')
        self.assertEqual([1, 2], ret)
        mock_vup.assert_has_calls([mock.call(pport4, mock_glv.return_value),
                                   mock.call(pport5, mock_glv.return_value)])

    @mock.patch('pypowervm.tasks.sriov._vet_port_usage')
    @mock.patch('pypowervm.tasks.sriov.LOG.warning')
    @mock.patch('fasteners.lock.ReaderWriterLock.write_lock')
    @mock.patch('pypowervm.wrappers.managed_system.System.getter')
    def test_safe_update_pports(self, mock_getter, mock_lock, mock_warn,
                                mock_vpu):
        mock_sys = mock.Mock(asio_config=mock.Mock(sriov_adapters=[
            mock.Mock(phys_ports=[mock.Mock(loc_code='loc1', label='label1'),
                                  mock.Mock(loc_code='loc2', label='label2')]),
            mock.Mock(phys_ports=[
                mock.Mock(loc_code='loc3', label='label3')])]))

        def changes_func(ret_bool):
            def changes(sys_w):
                mock_lock.assert_called()
                mock_lock.reset_mock()
                return ret_bool
            return changes

        # No force, no warnings, update requested
        mock_vpu.return_value = []
        self.assertEqual(mock_sys.update.return_value,
                         tsriov.safe_update_pports(
                             mock_sys, changes_func(True)))
        mock_warn.assert_not_called()
        # No force, no in-use, no update, use a getter: runs but doesn't update
        mock_sys.update.reset_mock()
        self.assertEqual(mock_getter.return_value, tsriov.safe_update_pports(
            ms.System.getter('adap'), changes_func(False)))
        mock_warn.assert_not_called()
        mock_getter.return_value.update.assert_not_called()
        # Update requested, some in-use, no force - raises
        mock_vpu.reset_mock()
        mock_vpu.return_value = [1]
        self.assertRaises(ex.CantUpdatePPortsInUse, tsriov.safe_update_pports,
                          mock_sys, changes_func(True), force=False)
        mock_warn.assert_not_called()
        mock_sys.update.assert_not_called()
        # Update requested, some in-use, force - runs & warns
        mock_vpu.reset_mock()
        mock_vpu.return_value = ['one', 'two']
        self.assertEqual(mock_sys.update.return_value,
                         tsriov.safe_update_pports(
                             mock_sys, changes_func(True), force=True))
        mock_warn.assert_has_calls([mock.call(mock.ANY), mock.call('one'),
                                    mock.call('two')])


class TestMisc(twrap.TestWrapper):
    file = 'sys_with_sriov.txt'
    wrapper_class_to_test = ms.System

    def test_find_pport(self):
        self.assertIsNone(tsriov.find_pport(self.dwrap, 'bogus'))
        pport = tsriov.find_pport(self.dwrap, 'U78C7.001.RCH0004-P1-C8-T2')
        self.assertEqual('U78C7.001.RCH0004-P1-C8',
                         pport.sriov_adap.phys_loc_code)
        self.assertEqual(1, pport.sriov_adap_id)
        # It's a converged port...
        self.assertIsInstance(pport, card.SRIOVConvPPort)
        # ...which is also an ethernet port
        self.assertIsInstance(pport, card.SRIOVEthPPort)
        self.assertEqual('U78C7.001.RCH0004-P1-C8-T2', pport.loc_code)
        self.assertEqual(1, pport.port_id)
