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
import pypowervm.wrappers.iocard as card


def fake_sriov(mode, state, sriov_adap_id, phys_ports):
    return mock.Mock(mode=mode, state=state, sriov_adap_id=sriov_adap_id,
                     phys_loc_code='sriov_loc%d' % sriov_adap_id,
                     phys_ports=phys_ports)


def fake_pport(sriov_adap_id, port_id, alloc_cap):
    return mock.Mock(sriov_adap_id=sriov_adap_id, port_id=port_id,
                     loc_code='pport_loc%d' % port_id,
                     min_granularity=float(port_id) / 1000,
                     allocated_capacity=alloc_cap)


def good_sriov(sriov_adap_id, pports):
    return fake_sriov(card.SRIOVAdapterMode.SRIOV,
                      card.SRIOVAdapterState.RUNNING, sriov_adap_id, pports)

ded_sriov = fake_sriov(card.SRIOVAdapterMode.DEDICATED, None, 86, [])
down_sriov = fake_sriov(card.SRIOVAdapterMode.SRIOV,
                        card.SRIOVAdapterState.FAILED, 68, [])


class TestSriov(testtools.TestCase):

    def setUp(self):
        super(TestSriov, self).setUp()
        self.adpt = self.useFixture(fx.AdapterFx()).adpt
        self.fake_sriovs = [
            good_sriov(1, [fake_pport(1, pid, cap) for pid, cap in (
                (11, 0.95), (12, 0.0), (13, 0.03), (14, 0.987))]),
            ded_sriov, good_sriov(2, [fake_pport(2, 21, 0.3)]), down_sriov,
            good_sriov(3, []),
            good_sriov(4, [fake_pport(4, pid, cap) for pid, cap in (
                (41, 0.02), (42, 0.01))]),
            good_sriov(5, [fake_pport(5, pid, cap) for pid, cap in (
                (51, 0.49), (52, 0.0), (53, 0.95), (54, 0.0),
                (55, 0.4), (56, 0.1), (57, 0.15), (58, 1.0))])]

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    def test_get_good_sriovs(self, mock_get):
        """Test _get_good_sriovs helper."""
        # When sriov_adaps=None, does a GET.
        mock_get.return_value = [mock.Mock(asio_config=mock.Mock(
            sriov_adapters=self.fake_sriovs))]
        sriovs = tsriov._get_good_sriovs('adap')
        mock_get.assert_called_once_with('adap')
        self.assertEqual(5, len(sriovs))
        self.assertEqual(['sriov_loc%d' % x for x in range(1, 6)],
                         [sriov.phys_loc_code for sriov in sriovs])

        # When sriov_adaps is passed in.
        mock_get.reset_mock()
        sriovs = tsriov._get_good_sriovs('adap', sriov_adaps=self.fake_sriovs)
        mock_get.assert_not_called()
        self.assertEqual(5, len(sriovs))
        self.assertEqual(['sriov_loc%d' % x for x in range(1, 6)],
                         [sriov.phys_loc_code for sriov in sriovs])

        # Error case: none found.
        self.assertRaises(ex.NoRunningSharedSriovAdapters,
                          tsriov._get_good_sriovs, 'adap',
                          sriov_adaps=[ded_sriov, down_sriov])

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
            self.fake_sriovs, ['nothing', 'to', 'see', 'here'], None, 0))
        # Validate min_returns - same thing but with nonzero minimum
        self.assertRaises(
            ex.InsufficientSRIOVCapacity, tsriov._get_good_pport_list,
            self.fake_sriovs, ['nothing', 'to', 'see', 'here'], None, 1)
        # Make sure we can get the ones we specify, that are actually there.
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in {51, 13, 68, 123, 21,
                                                           57, 42}], None, 4)
        validate_pports(pports, {42, 13, 57, 21, 51})
        # Make sure we can filter by capacity.  14, 53, and 58 should filter
        # themselves - they're already too full for their min_granularity
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in {58, 52, 14, 11,
                                                           53}], None, 0)
        validate_pports(pports, (52, 11))
        # Now specify capacity higher than 11 can handle - it should drop off
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in {58, 52, 14, 11,
                                                           53}], 0.06, 0)
        validate_pports(pports, {52})
        # Hit 'em all
        pports = tsriov._get_good_pport_list(
            self.fake_sriovs, ['pport_loc%d' % x for x in range(60)], None, 0)
        validate_pports(pports, {12, 52, 54, 42, 13, 41, 56, 57, 21, 55, 51,
                                 11})

    @mock.patch('pypowervm.tasks.partition.get_active_vioses')
    @mock.patch('random.shuffle')
    def test_set_vnic_back_devs(self, mock_shuffle, mock_vioget):
        """Test set_vnic_back_devs."""
        mock_vioget.return_value = [mock.Mock(uuid='vios_uuid1'),
                                    mock.Mock(uuid='vios_uuid2'),
                                    mock.Mock(uuid='vios_uuid3')]
        self.adpt.build_href.side_effect = lambda *a, **k: '%s' % a[1]
        vnic = card.VNIC.bld(self.adpt, 5)
        self.assertEqual(0, len(vnic.back_devs))
        # Silly case: min/max of zero
        tsriov.set_vnic_back_devs(vnic, [], sriov_adaps=self.fake_sriovs,
                                  min_redundancy=0, max_redundancy=0)
        self.assertEqual(0, len(vnic.back_devs))
        mock_vioget.assert_called_once_with(self.adpt, xag=[], vios_wraps=None,
                                            find_min=1)
        # max_redundancy is capped by len(pports)
        tsriov.set_vnic_back_devs(vnic, [], sriov_adaps=self.fake_sriovs,
                                  min_redundancy=0, max_redundancy=10)
        self.assertEqual(0, len(vnic.back_devs))

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
        # Use 'em all
        tsriov.set_vnic_back_devs(vnic, ['pport_loc%d' % x for x in range(60)],
                                  sriov_adaps=self.fake_sriovs, capacity=cap,
                                  min_redundancy=0, max_redundancy=100)
        self.assertEqual(all_back_devs,
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        # Fail if we can't satisfy min_redundancy
        self.assertRaises(
            ex.InsufficientSRIOVCapacity, tsriov.set_vnic_back_devs, vnic,
            ['pport_loc%d' % x for x in range(60)],
            sriov_adaps=self.fake_sriovs, capacity=cap, min_redundancy=13,
            max_redundancy=100)

        # The passed-in wrapper isn't modified if the method raises.
        self.assertEqual(all_back_devs,
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        # Make sure max_redundancy caps it.
        # By reusing vnic without resetting its back_devs, we're proving the
        # documented behavior that the method clears first.
        tsriov.set_vnic_back_devs(vnic, ['pport_loc%d' % x for x in range(60)],
                                  sriov_adaps=self.fake_sriovs, capacity=cap,
                                  min_redundancy=0, max_redundancy=5)
        self.assertEqual(all_back_devs[:5],
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        self.assertEqual(5, mock_shuffle.call_count)


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
    def test_safe_update_pports(self, mock_lock, mock_warn, mock_vpu):
        mock_sys = mock.Mock(asio_config=mock.Mock(sriov_adapters=[
            mock.Mock(phys_ports=[mock.Mock(loc_code='loc1', label='label1'),
                                  mock.Mock(loc_code='loc2', label='label2')]),
            mock.Mock(phys_ports=[
                mock.Mock(loc_code='loc3', label='label3')])]))

        def sup_caller(sys_w, force=None):
            """Because assertRaises() on a context manager is difficult."""
            if force is None:
                with tsriov.safe_update_pports(sys_w):
                    mock_lock.assert_called()
            else:
                with tsriov.safe_update_pports(sys_w, force=force):
                    mock_lock.assert_called()
            mock_vpu.assert_called_once_with(sys_w, {
                'loc1': 'label1', 'loc2': 'label2', 'loc3': 'label3'})
            sys_w.update.assert_called_once_with()
            sys_w.update.reset_mock()

        # No force, no warnings - finishes
        mock_vpu.return_value = []
        sup_caller(mock_sys)
        mock_warn.assert_not_called()
        # Warnings, no force - raises
        mock_vpu.reset_mock()
        mock_vpu.return_value = [1]
        self.assertRaises(ex.CantUpdatePPortsInUse, sup_caller, mock_sys)
        mock_warn.assert_not_called()
        # Warnings, force - logs
        mock_vpu.reset_mock()
        mock_vpu.return_value = ['one', 'two']
        sup_caller(mock_sys, force=True)
        mock_warn.assert_has_calls([mock.call(mock.ANY), mock.call('one'),
                                    mock.call('two')])
