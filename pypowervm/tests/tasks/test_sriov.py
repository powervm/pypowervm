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


def fake_pport(port_id, alloc_cap):
    return mock.Mock(port_id=port_id, loc_code='pport_loc%d' % port_id,
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
            good_sriov(1, [fake_pport(pid, cap) for pid, cap in (
                (11, 0.95), (12, 0.0), (13, 0.02), (14, 0.987))]),
            ded_sriov, good_sriov(2, [fake_pport(21, 0.3)]), down_sriov,
            good_sriov(3, []),
            good_sriov(4, [fake_pport(pid, cap) for pid, cap in (
                (41, 0.02), (42, 0.01))]),
            good_sriov(5, [fake_pport(pid, cap) for pid, cap in (
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

        vnic.back_devs = []
        # Fail if we can't satisfy min_redundancy
        self.assertRaises(
            ex.InsufficientSRIOVCapacity, tsriov.set_vnic_back_devs, vnic,
            ['pport_loc%d' % x for x in range(60)],
            sriov_adaps=self.fake_sriovs, capacity=cap, min_redundancy=13,
            max_redundancy=100)

        vnic.back_devs = []
        # Make sure max_redundancy caps it
        tsriov.set_vnic_back_devs(vnic, ['pport_loc%d' % x for x in range(60)],
                                  sriov_adaps=self.fake_sriovs, capacity=cap,
                                  min_redundancy=0, max_redundancy=5)
        self.assertEqual(all_back_devs[:5],
                         [(bd.vios_href, bd.sriov_adap_id, bd.pport_id,
                           bd.capacity) for bd in vnic.back_devs])

        self.assertEqual(5, mock_shuffle.call_count)
