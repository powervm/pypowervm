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
"""Test pypowervm.tasks.slot_map."""

import copy
import mock
import six
import testtools

from pypowervm import exceptions as pv_e
from pypowervm.tasks import slot_map
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.wrappers import network as net
from pypowervm.wrappers import storage as stor
from pypowervm.wrappers import virtual_io_server as vios


def loadf(wcls, fname):
    return wcls.wrap(pvmhttp.load_pvm_resp(fname).get_response())

# Load data files just once, since the wrappers will be read-only
vio1 = loadf(vios.VIOS, 'fake_vios_ssp_npiv.txt')
vio2 = loadf(vios.VIOS, 'fake_vios_mappings.txt')
cnafeed1 = loadf(net.CNA, 'cna_feed1.txt')
vswitchfeed = loadf(net.VSwitch, 'vswitch_feed.txt')


class SlotMapTestImpl(slot_map.SlotMapStore):

    def __init__(self, inst_key, load=True, load_ret=None):
        self._load_ret = load_ret
        self.load_calls = 0
        super(SlotMapTestImpl, self).__init__(inst_key, load=load)

    def set_load_ret(self, val):
        self._load_ret = val

    def load(self):
        self.load_calls += 1
        return self._load_ret


class TestSlotMapStore(testtools.TestCase):
    """Test slot_map.SlotMapStore."""

    def test_ioclass_consts(self):
        """Make sure the IOCLASS constants are disparate."""
        constl = [key for key in dir(slot_map.IOCLASS) if not
                  key.startswith('_')]
        self.assertEqual(len(constl), len(set(constl)))

    def test_init_calls_load(self):
        """Ensure SlotMapStore.__init__ calls load or not based on the parm."""
        loads = SlotMapTestImpl('foo')
        self.assertEqual(1, loads.load_calls)
        self.assertEqual('foo', loads.inst_key)
        doesnt_load = SlotMapTestImpl('bar', load=False)
        self.assertEqual(0, doesnt_load.load_calls)

    @mock.patch('pickle.loads')
    def test_init_deserialize(self, mock_unpickle):
        """Ensure __init__ deserializes or not based on what's loaded."""
        # By default, load returns None, so nothing to unpickle
        doesnt_unpickle = SlotMapTestImpl('foo')
        mock_unpickle.assert_not_called()
        self.assertEqual({}, doesnt_unpickle.topology)
        unpickles = SlotMapTestImpl('foo', load_ret='abc123')
        mock_unpickle.assert_called_once_with('abc123')
        self.assertEqual(mock_unpickle.return_value, unpickles.topology)

    @mock.patch('pickle.dumps')
    @mock.patch('pypowervm.tasks.slot_map.SlotMapStore.topology',
                new_callable=mock.PropertyMock)
    def test_serialized(self, mock_topo, mock_pickle):
        """Validate the serialized property."""
        mock_pickle.return_value = 'abc123'
        smt = SlotMapTestImpl('foo')
        self.assertEqual('abc123', smt.serialized)
        mock_pickle.assert_called_once_with(mock_topo.return_value, protocol=2)
        mock_topo.assert_called_once()

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    @mock.patch('pypowervm.wrappers.network.VSwitch.get')
    def test_vswitch_id2name(self, mock_vsw_get, mock_sys_get):
        """Ensure _vswitch_id2name caches, and gets the right content."""
        mock_vsw_get.return_value = vswitchfeed
        mock_sys_get.return_value = ['sys']
        smt = SlotMapTestImpl('foo')
        # We didn't cache yet
        mock_vsw_get.assert_not_called()
        mock_sys_get.assert_not_called()
        map1 = smt._vswitch_id2name('adap')
        # Now we grabbed the REST data
        mock_vsw_get.assert_called_once_with('adap', parent='sys')
        mock_sys_get.assert_called_once_with('adap')

        mock_vsw_get.reset_mock()
        mock_sys_get.reset_mock()
        map2 = smt._vswitch_id2name('adap2')
        # The same data is returned each time
        self.assertEqual(map2, map1)
        # The second call didn't re-fetch from REST
        mock_vsw_get.assert_not_called()
        mock_sys_get.assert_not_called()
        # Make sure the data is in the right shape
        self.assertEqual({0: 'ETHERNET0', 1: 'MGMTSWITCH'}, map1)

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    @mock.patch('pypowervm.wrappers.network.VSwitch.get')
    def test_register_cna(self, mock_vsw_get, mock_sys_get):
        """Test register_cna."""
        mock_vsw_get.return_value = vswitchfeed
        mock_sys_get.return_value = ['sys']
        smt = SlotMapTestImpl('foo')
        for cna in cnafeed1:
            smt.register_cna(cna)
        self.assertEqual({3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}},
                         smt.topology)

    def test_drop_cna(self):
        """Test drop_cna."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = {3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}}

        # Drop the first CNA and verify it was removed
        smt.drop_cna(cnafeed1[0])
        self.assertEqual({4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}},
                         smt.topology)

        # Drop all remaining CNAs, including a redundant drop on index 0
        for cna in cnafeed1:
            smt.drop_cna(cna)
        self.assertEqual({}, smt.topology)

    def test_register_vfc_mapping(self):
        """Test register_vfc_mapping."""
        smt = SlotMapTestImpl('foo')
        i = 1
        for vio in (vio1, vio2):
            for vfcmap in vio.vfc_mappings:
                smt.register_vfc_mapping(vfcmap, 'fab%d' % i)
                i += 1
        self.assertEqual({3: {'VFC': {'fab1': None, 'fab10': None,
                                      'fab11': None, 'fab12': None,
                                      'fab13': None, 'fab14': None,
                                      'fab15': None, 'fab16': None,
                                      'fab17': None, 'fab18': None,
                                      'fab19': None, 'fab20': None,
                                      'fab21': None, 'fab22': None,
                                      'fab23': None, 'fab24': None,
                                      'fab25': None, 'fab26': None,
                                      'fab28': None, 'fab29': None,
                                      'fab3': None, 'fab30': None,
                                      'fab31': None, 'fab32': None,
                                      'fab33': None, 'fab4': None,
                                      'fab5': None, 'fab6': None,
                                      'fab7': None, 'fab8': None,
                                      'fab9': None}},
                          6: {'VFC': {'fab2': None}},
                          8: {'VFC': {'fab27': None}}}, smt.topology)

    def test_drop_vfc_mapping(self):
        """Test drop_vfc_mapping."""
        # Init data to test with
        mock_server_adapter = mock.Mock(lpar_slot_num=3)
        vfcmap = mock.Mock(server_adapter=mock_server_adapter)
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = {3: {'VFC': {'fab1': None, 'fab10': None,
                                      'fab7': None, 'fab8': None,
                                      'fab9': None}},
                          6: {'VFC': {'fab2': None}},
                          8: {'VFC': {'fab27': None}}}

        # Drop a single slot entry and verify it is removed
        smt.drop_vfc_mapping(vfcmap, 'fab1')
        self.assertEqual({3: {'VFC': {'fab10': None,
                                      'fab7': None, 'fab8': None,
                                      'fab9': None}},
                          6: {'VFC': {'fab2': None}},
                          8: {'VFC': {'fab27': None}}},
                         smt.topology)

        # Drop remaining LPAR 3 slot entries and verify they are removed
        for i in range(7, 11):
            smt.drop_vfc_mapping(vfcmap, 'fab%s' % str(i))
        self.assertEqual({6: {'VFC': {'fab2': None}},
                          8: {'VFC': {'fab27': None}}},
                         smt.topology)

    def test_register_vscsi_mappings(self):
        """Test register_vscsi_mappings."""
        smt = SlotMapTestImpl('foo')
        for vio in (vio1, vio2):
            for vscsimap in vio.scsi_mappings:
                smt.register_vscsi_mapping(vscsimap)
        self.assertEqual(
            {2: {'LU': {'274d7bb790666211e3bc1a00006cae8b013842794fa0b8e9dd771'
                        'd6a32accde003': None,
                        '274d7bb790666211e3bc1a00006cae8b0148326cf1e5542c583ec'
                        '14327771522b0': None,
                        '274d7bb790666211e3bc1a00006cae8b01ac18997ab9bc23fb247'
                        '56e9713a93f90': None,
                        '274d7bb790666211e3bc1a00006cae8b01c96f590914bccbc8b7b'
                        '88c37165c0485': None},
                 'PV': {'01M0lCTTIxNDUzMTI2MDA1MDc2ODAyODIwQTlEQTgwMDAwMDAwMDA'
                        'wNTJBOQ==': None},
                 'VDisk': {'0300004c7a00007a00000001466c54110f.16': 0.125},
                 'VOptMedia': {
                     '0evopt_19bbb46ad15747d79fe08f8464466144':
                         'vopt_19bbb46ad15747d79fe08f8464466144',
                     '0evopt_2c7aa01349714368a3d040bb0d613a67':
                         'vopt_2c7aa01349714368a3d040bb0d613a67',
                     '0evopt_2e51e8b4b9f04b159700e654b2436a01':
                         'vopt_2e51e8b4b9f04b159700e654b2436a01',
                     '0evopt_84d7bfcf44964f398e60254776b94d41':
                         'vopt_84d7bfcf44964f398e60254776b94d41',
                     '0evopt_de86c46e07004993b412c948bd5047c2':
                         'vopt_de86c46e07004993b412c948bd5047c2'}},
             3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1': 60.0}}},
            smt.topology)

    def test_drop_vscsi_mappings(self):
        """Test drop_vscsi_mappings."""
        # Init objects to test with
        bstor = mock.Mock(stor.LU,
                          udid='274d7bb790666211e3bc1a00006cae8b01c96f59091'
                          '4bccbc8b7b88c37165c0485')
        mock_server_adapter = mock.Mock(lpar_slot_num=2)
        vscsimap = mock.Mock(backing_storage=bstor,
                             server_adapter=mock_server_adapter)
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = {
            2: {'LU': {'274d7bb790666211e3bc1a00006cae8b013842794fa0b8e9dd771'
                       'd6a32accde003': None,
                       '274d7bb790666211e3bc1a00006cae8b0148326cf1e5542c583ec'
                       '14327771522b0': None,
                       '274d7bb790666211e3bc1a00006cae8b01ac18997ab9bc23fb247'
                       '56e9713a93f90': None,
                       '274d7bb790666211e3bc1a00006cae8b01c96f590914bccbc8b7b'
                       '88c37165c0485': None},
                'PV': {'01M0lCTTIxNDUzMTI2MDA1MDc2ODAyODIwQTlEQTgwMDAwMDAwMDA'
                       'wNTJBOQ==': None},
                'VDisk': {'0300004c7a00007a00000001466c54110f.16': 0.125},
                'VOptMedia': {
                    '0evopt_19bbb46ad15747d79fe08f8464466144':
                        'vopt_19bbb46ad15747d79fe08f8464466144',
                    '0evopt_2c7aa01349714368a3d040bb0d613a67':
                        'vopt_2c7aa01349714368a3d040bb0d613a67',
                    '0evopt_2e51e8b4b9f04b159700e654b2436a01':
                        'vopt_2e51e8b4b9f04b159700e654b2436a01',
                    '0evopt_84d7bfcf44964f398e60254776b94d41':
                        'vopt_84d7bfcf44964f398e60254776b94d41',
                    '0evopt_de86c46e07004993b412c948bd5047c2':
                        'vopt_de86c46e07004993b412c948bd5047c2'}},
            3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1': 60.0}}
        }

        # Remove a single LU entry and verify it was removed
        smt.drop_vscsi_mapping(vscsimap)
        self.assertEqual(
            {2: {'LU': {'274d7bb790666211e3bc1a00006cae8b013842794fa0b8e9dd771'
                        'd6a32accde003': None,
                        '274d7bb790666211e3bc1a00006cae8b0148326cf1e5542c583ec'
                        '14327771522b0': None,
                        '274d7bb790666211e3bc1a00006cae8b01ac18997ab9bc23fb247'
                        '56e9713a93f90': None},
                 'PV': {'01M0lCTTIxNDUzMTI2MDA1MDc2ODAyODIwQTlEQTgwMDAwMDAwMDA'
                        'wNTJBOQ==': None},
                 'VDisk': {'0300004c7a00007a00000001466c54110f.16': 0.125},
                 'VOptMedia': {
                     '0evopt_19bbb46ad15747d79fe08f8464466144':
                         'vopt_19bbb46ad15747d79fe08f8464466144',
                     '0evopt_2c7aa01349714368a3d040bb0d613a67':
                         'vopt_2c7aa01349714368a3d040bb0d613a67',
                     '0evopt_2e51e8b4b9f04b159700e654b2436a01':
                         'vopt_2e51e8b4b9f04b159700e654b2436a01',
                     '0evopt_84d7bfcf44964f398e60254776b94d41':
                         'vopt_84d7bfcf44964f398e60254776b94d41',
                     '0evopt_de86c46e07004993b412c948bd5047c2':
                         'vopt_de86c46e07004993b412c948bd5047c2'}},
             3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1': 60.0}}},
            smt.topology)

        # Remove all other LPAR 2 LU entries and verify they are removed
        udids = ['274d7bb790666211e3bc1a00006cae8b013842794fa0b8e9dd771'
                 'd6a32accde003',
                 '274d7bb790666211e3bc1a00006cae8b0148326cf1e5542c583ec'
                 '14327771522b0',
                 '274d7bb790666211e3bc1a00006cae8b01ac18997ab9bc23fb247'
                 '56e9713a93f90']
        for udid in udids:
            bstor.udid = udid
            smt.drop_vscsi_mapping(vscsimap)
        self.assertEqual(
            {2: {'PV': {'01M0lCTTIxNDUzMTI2MDA1MDc2ODAyODIwQTlEQTgwMDAwMDAwMDA'
                        'wNTJBOQ==': None},
                 'VDisk': {'0300004c7a00007a00000001466c54110f.16': 0.125},
                 'VOptMedia': {
                     '0evopt_19bbb46ad15747d79fe08f8464466144':
                         'vopt_19bbb46ad15747d79fe08f8464466144',
                     '0evopt_2c7aa01349714368a3d040bb0d613a67':
                         'vopt_2c7aa01349714368a3d040bb0d613a67',
                     '0evopt_2e51e8b4b9f04b159700e654b2436a01':
                         'vopt_2e51e8b4b9f04b159700e654b2436a01',
                     '0evopt_84d7bfcf44964f398e60254776b94d41':
                         'vopt_84d7bfcf44964f398e60254776b94d41',
                     '0evopt_de86c46e07004993b412c948bd5047c2':
                         'vopt_de86c46e07004993b412c948bd5047c2'}},
             3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1': 60.0}}},
            smt.topology)

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    @mock.patch('pypowervm.wrappers.network.VSwitch.get')
    def test_serialize_unserialize(self, mock_vsw_get, mock_sys_get):
        """Ensure that saving/loading doesn't corrupt the data."""
        mock_vsw_get.return_value = vswitchfeed
        mock_sys_get.return_value = ['sys']
        # Set up a nice, big, complicated source slot map
        smt1 = SlotMapTestImpl('foo')
        for cna in cnafeed1:
            smt1.register_cna(cna)
        i = 1
        for vio in (vio1, vio2):
            for vscsimap in vio.scsi_mappings:
                smt1.register_vscsi_mapping(vscsimap)
            for vfcmap in vio.vfc_mappings:
                smt1.register_vfc_mapping(vfcmap, 'fab%d' % i)
                i += 1
        # Serialize, and make a new slot map that loads that serialized data
        smt2 = SlotMapTestImpl('bar', load_ret=smt1.serialized)
        # Ensure their topologies are identical
        self.assertEqual(smt1.topology, smt2.topology)


class TestRebuildSlotMap(testtools.TestCase):
    """Test for RebuildSlotMap class

    Tests BuildSlotMap class's get methods as well.
    """

    def setUp(self):
        super(TestRebuildSlotMap, self).setUp()
        self.vio1 = mock.Mock(uuid='vios1')
        self.vio2 = mock.Mock(uuid='vios2')

        # The vol_to_vio definitions that are used by multiple test cases
        # need to be deep copied because _pv_vscsi_build_out relies on these
        # dictionaries for consistency by removing elements from them.
        self.vtv_2v_arb = copy.deepcopy(VTV_2V_ARB)

    def test_vea_build_out(self):
        """Test _vea_build_out."""
        # Create a slot topology that will be converted to a rebuild map
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = {3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}}

        # Run the actual test
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, {})

        # Verify rebuild map was created successfully
        self.assertEqual(
            {'CNA': {'2A2E57A4DE9C': 4, '5E372CFD9E6D': 3},
             'MGMTCNA': {'mac': '3AEAC528A7E3', 'slot': 6}},
            rsm._build_map)

        # Verify the VEA slot can be read by MAC address
        self.assertEqual(3, rsm.get_vea_slot('5E372CFD9E6D'))
        self.assertEqual(4, rsm.get_vea_slot('2A2E57A4DE9C'))
        self.assertEqual(None, rsm.get_vea_slot('3AEAC528A7E3'))
        self.assertEqual(('3AEAC528A7E3', 6), rsm.get_mgmt_vea_slot())

    def test_rebuild_fails_w_lu(self):
        """Test RebuildSlotMap fails when LUs exist in topology."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_W_LU
        self.assertRaises(
            pv_e.InvalidHostForRebuildInvalidIOType,
            slot_map.RebuildSlotMap, smt,
            [self.vio1, self.vio2], VOL_TO_VIO1, {})

    def test_rebuild_fails_w_vopt(self):
        """Test RebuildSlotMap fails when a Vopt exists in topology."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_W_VOPT
        self.assertRaises(
            pv_e.InvalidHostForRebuildInvalidIOType,
            slot_map.RebuildSlotMap, smt,
            [self.vio1, self.vio2], VOL_TO_VIO1, {})

    def test_rebuild_fails_w_vdisk(self):
        """Test RebuildSlotMap fails when VDisks exist in topology."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_W_VDISK
        self.assertRaises(
            pv_e.InvalidHostForRebuildInvalidIOType,
            slot_map.RebuildSlotMap, smt,
            [self.vio1, self.vio2], VOL_TO_VIO1, {})

    def test_pv_vscsi_build_out_1(self):
        """Test RebuildSlotMap deterministic."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_PV_1
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2],
                                      VOL_TO_VIO2, {})

        # Deterministic. vios1 gets slot 1
        for udid in rsm._build_map['PV']['vios1']:
            self.assertEqual(
                1, rsm.get_pv_vscsi_slot(self.vio1, udid))

        # Deterministic. vios2 gets slot 2
        for udid in rsm._build_map['PV']['vios2']:
            self.assertEqual(
                2, rsm.get_pv_vscsi_slot(self.vio2, udid))

        # The build map won't actually have these as keys but
        # the get should return None nicely.
        self.assertIsNone(
            rsm.get_pv_vscsi_slot(self.vio1, 'pv_udid4'))
        self.assertIsNone(
            rsm.get_pv_vscsi_slot(self.vio2, 'pv_udid2'))

    def test_pv_vscsi_build_out_arbitrary_dest_vioses(self):
        """Test RebuildSlotMap with multiple candidate dest VIOSes."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_PV_ARB_MAP

        rsm = slot_map.RebuildSlotMap(
            smt, [self.vio1, self.vio2], self.vtv_2v_arb, {})

        # Since this isn't deterministic we want to make sure each UDID
        # got their slot assigned to one VIOS and not the other.
        expected_map = {'pv_udid1': 47, 'pv_udid2': 9, 'pv_udid3': 23,
                        'pv_udid4': 56}
        for udid, slot in six.iteritems(expected_map):
            if not rsm.get_pv_vscsi_slot(self.vio1, udid):
                self.assertEqual(
                    slot, rsm.get_pv_vscsi_slot(self.vio2, udid))
            else:
                self.assertEqual(
                    slot, rsm.get_pv_vscsi_slot(self.vio1, udid))
                self.assertIsNone(rsm.get_pv_vscsi_slot(self.vio2, udid))

    def test_pv_vscsi_build_out_full_coverage(self):
        """Test rebuild with 2 slots per udid and 2 candidate VIOSes."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_PV_2S_2V_MAP

        rsm = slot_map.RebuildSlotMap(
            smt, [self.vio1, self.vio2], self.vtv_2v_arb, {})
        expected_map = {'pv_udid1': [5, 23], 'pv_udid2': [6, 24],
                        'pv_udid3': [7, 25], 'pv_udid4': [8, 26]}

        # We know what slots the UDIDs should get but not what VIOSes they'll
        # belong to. So we'll assert that one VIOS gets 1 slot and the other
        # VIOS gets the other for each UDID.
        for udid, slots in six.iteritems(expected_map):
            if rsm.get_pv_vscsi_slot(self.vio1, udid) != slots[0]:
                self.assertEqual(
                    slots[0], rsm.get_pv_vscsi_slot(self.vio2, udid))
                self.assertEqual(
                    slots[1], rsm.get_pv_vscsi_slot(self.vio1, udid))
            else:
                # We already know vio1 got the first slot
                self.assertEqual(
                    slots[1], rsm.get_pv_vscsi_slot(self.vio2, udid))

    def test_pv_udid_not_found_on_dest(self):
        """Test RebuildSlotMap fails when UDID not found on dest."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_PV_3
        self.assertRaises(
            pv_e.InvalidHostForRebuildNotEnoughVIOS,
            slot_map.RebuildSlotMap, smt,
            [self.vio1, self.vio2], BAD_VOL_TO_VIO_FOR_PV_3, {})

    def test_more_pv_udids_than_dest_vioses_fails(self):
        """Test RebuildSlotMap fails when there's not enough VIOSes."""
        smt = SlotMapTestImpl('foo')
        smt._slot_topo = SCSI_PV_1
        self.assertRaises(
            pv_e.InvalidHostForRebuildNotEnoughVIOS,
            slot_map.RebuildSlotMap, smt, [self.vio1, self.vio2],
            VOL_TO_VIO_1_VIOS_PV1, {})

SCSI_W_LU = {
    1: {
        slot_map.IOCLASS.LU: {
            'lu_udid1': None,
            'lu_udid2': None
        },
        slot_map.IOCLASS.PV: {
            'pv_udid1': None,
            'pv_udid2': None
        }
    }
}

SCSI_W_VOPT = {
    1: {
        slot_map.IOCLASS.VOPT: {
            slot_map.IOCLASS.VOPT: None
        },
        slot_map.IOCLASS.PV: {
            'pv_udid1': None,
            'pv_udid2': None
        }
    }
}

SCSI_W_VDISK = {
    1: {
        slot_map.IOCLASS.VDISK: {
            'vd_udid1': 1024.0,
            'vd_udid2': 2048.0
        },
        slot_map.IOCLASS.PV: {
            'pv_udid1': None,
            'pv_udid2': None
        }
    }
}

SCSI_PV_1 = {
    1: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': None,
            'pv_udid2': None,
            'pv_udid3': None
        }
    },
    2: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': None,
            'pv_udid3': None,
            'pv_udid4': None
        }
    }
}

SCSI_PV_ARB_MAP = {
    47: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': None
        }
    },
    9: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': None
        }
    },
    23: {
        slot_map.IOCLASS.PV: {
            'pv_udid3': None
        }
    },
    56: {
        slot_map.IOCLASS.PV: {
            'pv_udid4': None
        }
    }
}

SCSI_PV_2S_2V_MAP = {
    5: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': None
        }
    },
    6: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': None
        }
    },
    7: {
        slot_map.IOCLASS.PV: {
            'pv_udid3': None
        }
    },
    8: {
        slot_map.IOCLASS.PV: {
            'pv_udid4': None
        }
    },
    23: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': None
        }
    },
    24: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': None}
    },
    25: {
        slot_map.IOCLASS.PV: {
            'pv_udid3': None
        }
    },
    26: {
        slot_map.IOCLASS.PV: {
            'pv_udid4': None
        }
    }
}

SCSI_PV_3 = {
    23: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': None
        }
    },
    12: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': None
        }
    },
    4: {
        slot_map.IOCLASS.PV: {
            'pv_udid3': None
        }
    }
}

BAD_VOL_TO_VIO_FOR_PV_3 = {
    'pv_udid1': [
        'vios1',
        'vios2'
    ],
    'pv_udid2': [
        'vios1',
        'vios2'
    ]
}

VOL_TO_VIO1 = {
    'lu_udid1': [
        'vios1',
        'vios2'
    ],
    'lu_udid2': [
        'vios1',
        'vios2'
    ],
    'pv_udid1': [
        'vios1',
        'vios2'
    ],
    'pv_udid2': [
        'vios1',
        'vios2'
    ]
}

VOL_TO_VIO2 = {
    'pv_udid1': [
        'vios1',
        'vios2'
    ],
    'pv_udid2': [
        'vios1'
    ],
    'pv_udid3': [
        'vios1',
        'vios2'
    ],
    'pv_udid4': [
        'vios2'
    ]
}

VOL_TO_VIO_1_VIOS_PV1 = {
    'pv_udid1': [
        'vios1'
    ],
    'pv_udid2': [
        'vios1'
    ],
    'pv_udid3': [
        'vios1'
    ],
    'pv_udid4': [
        'vios1'
    ]
}

VTV_2V_ARB = {
    'pv_udid1': [
        'vios1',
        'vios2'
    ],
    'pv_udid2': [
        'vios1',
        'vios2'
    ],
    'pv_udid3': [
        'vios1',
        'vios2'
    ],
    'pv_udid4': [
        'vios1',
        'vios2'
    ]
}
