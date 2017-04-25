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

import mock
import six
import testtools

from pypowervm import exceptions as pv_e
from pypowervm.tasks import slot_map
from pypowervm.tests.test_utils import pvmhttp
from pypowervm.utils import lpar_builder as lb
from pypowervm.wrappers import iocard as ioc
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
vnicfeed = loadf(ioc.VNIC, 'vnic_feed.txt')


class SlotMapTestImplLegacy(slot_map.SlotMapStore):
    """Legacy subclass overriding load/save/delete directly."""
    def __init__(self, inst_key, load=True, load_ret=None):
        self._load_ret = load_ret
        super(SlotMapTestImplLegacy, self).__init__(inst_key, load=load)

    def load(self):
        return self._load_ret

    def save(self):
        pass

    def delete(self):
        pass


class SlotMapTestImpl(slot_map.SlotMapStore):
    """New-style subclass overriding _load/_save/_delete."""
    def __init__(self, inst_key, load=True, load_ret=None):
        self._load_ret = load_ret
        super(SlotMapTestImpl, self).__init__(inst_key, load=load)

    def _load(self, key):
        return self._load_ret

    def _save(self, key, blob):
        pass

    def _delete(self, key):
        pass


class TestSlotMapStoreLegacy(testtools.TestCase):
    """Test slot_map.SlotMapStore with a legacy impl."""

    def __init__(self, *args, **kwargs):
        """Initialize with a legacy SlotMapStore implementation."""
        super(TestSlotMapStoreLegacy, self).__init__(*args, **kwargs)
        self.smt_impl = SlotMapTestImplLegacy

    def test_ioclass_consts(self):
        """Make sure the IOCLASS constants are disparate."""
        constl = [key for key in dir(slot_map.IOCLASS) if not
                  key.startswith('_')]
        self.assertEqual(len(constl), len(set(constl)))

    def test_init_calls_load(self):
        """Ensure SlotMapStore.__init__ calls load or not based on the parm."""
        with mock.patch.object(self.smt_impl, 'load') as mock_load:
            mock_load.return_value = None
            loads = self.smt_impl('foo')
            mock_load.assert_called_once_with()
            self.assertEqual('foo', loads.inst_key)
            mock_load.reset_mock()
            doesnt_load = self.smt_impl('bar', load=False)
            self.assertEqual('bar', doesnt_load.inst_key)
            mock_load.assert_not_called()

    @mock.patch('pickle.loads')
    def test_init_deserialize(self, mock_unpickle):
        """Ensure __init__ deserializes or not based on what's loaded."""
        # By default, load returns None, so nothing to unpickle
        doesnt_unpickle = self.smt_impl('foo')
        mock_unpickle.assert_not_called()
        self.assertEqual({}, doesnt_unpickle.topology)
        unpickles = self.smt_impl('foo', load_ret='abc123')
        mock_unpickle.assert_called_once_with('abc123')
        self.assertEqual(mock_unpickle.return_value, unpickles.topology)

    @mock.patch('pickle.dumps')
    @mock.patch('pypowervm.tasks.slot_map.SlotMapStore.topology',
                new_callable=mock.PropertyMock)
    def test_serialized(self, mock_topo, mock_pickle):
        """Validate the serialized property."""
        mock_pickle.return_value = 'abc123'
        smt = self.smt_impl('foo')
        self.assertEqual('abc123', smt.serialized)
        mock_pickle.assert_called_once_with(mock_topo.return_value, protocol=2)
        mock_topo.assert_called_once()

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    @mock.patch('pypowervm.wrappers.network.VSwitch.get')
    def test_vswitch_id2name(self, mock_vsw_get, mock_sys_get):
        """Ensure _vswitch_id2name caches, and gets the right content."""
        mock_vsw_get.return_value = vswitchfeed
        mock_sys_get.return_value = ['sys']
        smt = self.smt_impl('foo')
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
    @mock.patch('warnings.warn')
    def test_register_cna(self, mock_warn, mock_vsw_get, mock_sys_get):
        """Test deprecated register_cna."""
        mock_vsw_get.return_value = vswitchfeed
        mock_sys_get.return_value = ['sys']
        smt = self.smt_impl('foo')
        for cna in cnafeed1:
            smt.register_cna(cna)
        self.assertEqual({3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}},
                         smt.topology)
        # The vswitch_map is cached in the slot_map, so these only get
        # called once
        self.assertEqual(mock_vsw_get.call_count, 1)
        self.assertEqual(mock_sys_get.call_count, 1)

        self.assertEqual(mock_warn.call_count, 3)

    @mock.patch('warnings.warn')
    def test_drop_cna(self, mock_warn):
        """Test deprecated drop_cna."""
        smt = self.smt_impl('foo')
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
        self.assertEqual(mock_warn.call_count, 4)

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    @mock.patch('pypowervm.wrappers.network.VSwitch.get')
    def test_register_vnet(self, mock_vsw_get, mock_sys_get):
        """Test register_vnet."""
        mock_vsw_get.return_value = vswitchfeed
        mock_sys_get.return_value = ['sys']
        smt = self.smt_impl('foo')
        for vnic in vnicfeed:
            smt.register_vnet(vnic)
        for cna in cnafeed1:
            smt.register_vnet(cna)
        self.assertEqual({3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}},
                          7: {'VNIC': {'AE7A25E59A07': None}},
                          8: {'VNIC': {'AE7A25E59A08': None}}},
                         smt.topology)
        # The vswitch_map is cached in the slot_map, so these only get
        # called once
        self.assertEqual(mock_vsw_get.call_count, 1)
        self.assertEqual(mock_sys_get.call_count, 1)

    def test_register_vnet_exception(self):
        """Test register_vnet raises exception without CNA or VNIC."""
        smt = self.smt_impl('foo')
        self.assertRaises(pv_e.InvalidVirtualNetworkDeviceType,
                          smt.register_vnet, None)

    def test_drop_vnet(self):
        """Test drop_vnet."""
        smt = self.smt_impl('foo')
        smt._slot_topo = {3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}},
                          7: {'VNIC': {'AE7A25E59A07': None}},
                          8: {'VNIC': {'AE7A25E59A08': None}}}

        # Drop the first CNA and VNIC and verify it was removed
        smt.drop_vnet(cnafeed1[0])
        smt.drop_vnet(vnicfeed[0])
        self.assertEqual({4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}},
                          8: {'VNIC': {'AE7A25E59A08': None}}},
                         smt.topology)

        # Drop all remaining VNICs
        for vnic in vnicfeed:
            smt.drop_vnet(vnic)
        self.assertEqual({4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}},
                         smt.topology)
        # Drop all remaining CNAs
        for cna in cnafeed1:
            smt.drop_vnet(cna)
        self.assertEqual({}, smt.topology)

    def test_drop_vnet_exception(self):
        """Test drop_vnet raises exception without CNA or VNIC."""
        smt = self.smt_impl('foo')
        self.assertRaises(pv_e.InvalidVirtualNetworkDeviceType,
                          smt.drop_vnet, None)

    def test_register_vfc_mapping(self):
        """Test register_vfc_mapping."""
        smt = self.smt_impl('foo')
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
        smt = self.smt_impl('foo')
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
        smt = self.smt_impl('foo')
        for vio in (vio1, vio2):
            for vscsimap in vio.scsi_mappings:
                smt.register_vscsi_mapping(vscsimap)
        self.assertEqual(
            {2: {'LU': {'274d7bb790666211e3bc1a00006cae8b013842794fa0b8e9dd771'
                        'd6a32accde003': '0x8500000000000000',
                        '274d7bb790666211e3bc1a00006cae8b0148326cf1e5542c583ec'
                        '14327771522b0': '0x8300000000000000',
                        '274d7bb790666211e3bc1a00006cae8b01ac18997ab9bc23fb247'
                        '56e9713a93f90': '0x8400000000000000',
                        '274d7bb790666211e3bc1a00006cae8b01c96f590914bccbc8b7b'
                        '88c37165c0485': '0x8200000000000000'},
                 'PV': {'01M0lCTTIxNDUzMTI2MDA1MDc2ODAyODIwQTlEQTgwMDAwMDAwMDA'
                        'wNTJBOQ==': '0x8600000000000000'},
                 'VDisk': {'0300004c7a00007a00000001466c54110f.16':
                           '0x8100000000000000'},
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
             3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1':
                           '0x8700000000000000'}}},
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
        smt = self.smt_impl('foo')
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
                'VDisk': {'0300004c7a00007a00000001466c54110f.16':
                          '0x8100000000000000'},
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
            3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1':
                          '0x8700000000000000'}}
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
                 'VDisk': {'0300004c7a00007a00000001466c54110f.16':
                           '0x8100000000000000'},
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
             3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1':
                           '0x8700000000000000'}}},
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
                 'VDisk': {'0300004c7a00007a00000001466c54110f.16':
                           '0x8100000000000000'},
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
             3: {'VDisk': {'0300025d4a00007a000000014b36d9deaf.1':
                           '0x8700000000000000'}}},
            smt.topology)

    @mock.patch('pypowervm.wrappers.managed_system.System.get')
    @mock.patch('pypowervm.wrappers.network.VSwitch.get')
    def test_serialize_unserialize(self, mock_vsw_get, mock_sys_get):
        """Ensure that saving/loading doesn't corrupt the data."""
        mock_vsw_get.return_value = vswitchfeed
        mock_sys_get.return_value = ['sys']
        # Set up a nice, big, complicated source slot map
        smt1 = self.smt_impl('foo')
        for cna in cnafeed1:
            smt1.register_vnet(cna)
        for vnic in vnicfeed:
            smt1.register_vnet(vnic)
        i = 1
        for vio in (vio1, vio2):
            for vscsimap in vio.scsi_mappings:
                smt1.register_vscsi_mapping(vscsimap)
            for vfcmap in vio.vfc_mappings:
                smt1.register_vfc_mapping(vfcmap, 'fab%d' % i)
                i += 1
        # Serialize, and make a new slot map that loads that serialized data
        smt2 = self.smt_impl('bar', load_ret=smt1.serialized)
        # Ensure their topologies are identical
        self.assertEqual(smt1.topology, smt2.topology)

    def test_max_vslots(self):
        """Test setting/getting the max_vslots."""
        smt = self.smt_impl('foo')
        # Starts off unset
        self.assertIsNone(smt.max_vslots)
        # Can assign initially
        smt.register_max_vslots(123)
        self.assertEqual(123, smt.max_vslots)
        # Can overwrite
        smt.register_max_vslots(234)
        self.assertEqual(234, smt.max_vslots)
        # Can throw other stuff in there
        i = 1
        for vio in (vio1, vio2):
            for vfcmap in vio.vfc_mappings:
                smt.register_vfc_mapping(vfcmap, 'fab%d' % i)
                i += 1
        # max_vslots still set
        self.assertEqual(234, smt.max_vslots)
        # Topology not polluted by max_vslots
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


class TestSlotMapStore(TestSlotMapStoreLegacy):
    """Test slot_map.SlotMapStore with a new-style impl."""

    def __init__(self, *args, **kwargs):
        """Initialize with a new-style SlotMapStore implementation."""
        super(TestSlotMapStore, self).__init__(*args, **kwargs)
        self.smt_impl = SlotMapTestImpl
        self.load_meth_nm = '_load'

    def test_init_calls_load(self):
        """Ensure SlotMapStore.__init__ calls load or not based on the parm.

        This overrides the legacy test of the same name to ensure that _load
        gets invoked properly.
        """
        with mock.patch.object(self.smt_impl, '_load') as mock_load:
            mock_load.return_value = None
            loads = self.smt_impl('foo')
            mock_load.assert_called_once_with('foo')
            self.assertEqual('foo', loads.inst_key)
            mock_load.reset_mock()
            doesnt_load = self.smt_impl('bar', load=False)
            self.assertEqual('bar', doesnt_load.inst_key)
            mock_load.assert_not_called()

    @mock.patch('pypowervm.tasks.slot_map.SlotMapStore.serialized',
                new_callable=mock.PropertyMock)
    def test_save_when_needed(self, mock_ser):
        """Overridden _save call invoked only when needed."""
        with mock.patch.object(self.smt_impl, '_save') as mock_save:
            smt = self.smt_impl('foo')
            smt.save()
            # Nothing changed yet
            mock_save.assert_not_called()
            smt.register_vfc_mapping(vio1.vfc_mappings[0], 'fabric')
            # Not yet...
            mock_save.assert_not_called()
            smt.save()
            # Now it's been called.
            mock_save.assert_called_once_with('foo', mock_ser.return_value)
            mock_save.reset_mock()
            # Saving again has no effect
            smt.save()
            mock_save.assert_not_called()
            # Verify it works on drop too
            smt.drop_vfc_mapping(vio1.vfc_mappings[0], 'fabric')
            mock_save.assert_not_called()
            smt.save()
            # Now it's been called.
            mock_save.assert_called_once_with('foo', mock_ser.return_value)
            mock_save.reset_mock()
            # Saving again has no effect
            smt.save()
            mock_save.assert_not_called()

    def test_delete(self):
        """Overridden _delete is called properly when delete is invoked."""
        with mock.patch.object(self.smt_impl, '_delete') as mock_delete:
            smt = self.smt_impl('foo')
            smt.delete()
            mock_delete.assert_called_once_with('foo')


class TestRebuildSlotMapLegacy(testtools.TestCase):
    """Test for RebuildSlotMap class with legacy SlotMapStore subclass.

    Tests BuildSlotMap class's get methods as well.
    """

    def __init__(self, *args, **kwargs):
        """Initialize with a particular SlotMapStore implementation."""
        super(TestRebuildSlotMapLegacy, self).__init__(*args, **kwargs)
        self.smt_impl = SlotMapTestImplLegacy

    def setUp(self):
        super(TestRebuildSlotMapLegacy, self).setUp()
        self.vio1 = mock.Mock(uuid='vios1')
        self.vio2 = mock.Mock(uuid='vios2')

    def test_get_mgmt_vea_slot(self):
        smt = self.smt_impl('foo')

        # Make sure it returns the next slot available
        smt._slot_topo = {3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'VFC': {'fab1': None}}}
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None,
                                      ['fab1'])
        self.assertEqual((None, 7), rsm.get_mgmt_vea_slot())
        # Second call should return the same slot, as there is only one mgmt
        # vif per VM
        self.assertEqual((None, 7), rsm.get_mgmt_vea_slot())

        # Make sure it returns the existing MGMT switch
        smt._slot_topo = {3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}}
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, [])
        self.assertEqual(('3AEAC528A7E3', 6), rsm.get_mgmt_vea_slot())

        # Make sure it returns None if there is no real data
        smt._slot_topo = {}
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, [])
        self.assertEqual((None, None), rsm.get_mgmt_vea_slot())

    def test_vea_build_out(self):
        """Test _vea_build_out."""
        # Create a slot topology that will be converted to a rebuild map
        smt = self.smt_impl('foo')
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

    def test_vnic_build_out(self):
        """Test _vnic_build_out."""
        smt = self.smt_impl('foo')
        smt._slot_topo = {5: {'VNIC': {'72AB8C392CD6': None}},
                          6: {'VNIC': {'111111111111': None}},
                          7: {'VNIC': {'45F16A97BC7E': None}}}

        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, {})

        self.assertEqual(
            {'VNIC': {'72AB8C392CD6': 5,
                      '111111111111': 6,
                      '45F16A97BC7E': 7}},
            rsm._build_map)

        self.assertEqual(5, rsm.get_vnet_slot('72AB8C392CD6'))
        self.assertEqual(6, rsm.get_vnet_slot('111111111111'))
        self.assertEqual(7, rsm.get_vnet_slot('45F16A97BC7E'))

    def test_max_vslots(self):
        """Ensure max_vslots returns the set value, or 10 + highest slot."""
        # With max_vslots unset and nothing in the topology...
        smt = self.smt_impl('foo')
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, {})
        # ...max_vslots defaults to 64
        self.assertEqual(lb.DEF_MAX_SLOT, rsm.get_max_vslots())

        # When unset, and the highest registered slot is small...
        smt._slot_topo = {3: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}}
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, {})
        # ...max_vslots still defaults to 64
        self.assertEqual(lb.DEF_MAX_SLOT, rsm.get_max_vslots())

        # When unset, and the highest registered slot is big...
        smt._slot_topo = {62: {'CNA': {'5E372CFD9E6D': 'ETHERNET0'}},
                          4: {'CNA': {'2A2E57A4DE9C': 'ETHERNET0'}},
                          6: {'CNA': {'3AEAC528A7E3': 'MGMTSWITCH'}}}
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, {})
        # ...max_vslots derives to 10 + highest
        self.assertEqual(72, rsm.get_max_vslots())

        # With max_vslots set, even if it's lower than 64...
        smt.register_max_vslots(23)
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2], None, {})
        # ...max_vslots returns the exact value
        self.assertEqual(23, rsm.get_max_vslots())

    def test_rebuild_fails_w_vopt(self):
        """Test RebuildSlotMap fails when a Vopt exists in topology."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_W_VOPT
        self.assertRaises(
            pv_e.InvalidHostForRebuildInvalidIOType,
            slot_map.RebuildSlotMap, smt,
            [self.vio1, self.vio2], VOL_TO_VIO1, {})

    def test_rebuild_w_vdisk(self):
        """Test RebuildSlotMap deterministic."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_W_VDISK
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2],
                                      VOL_TO_VIO1, {})
        # Deterministic. vios1 gets slot 1
        for udid in rsm._build_map['VDisk']['vios1']:
            slot, lua = rsm.get_vscsi_slot(self.vio1, udid)
            self.assertEqual(1, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_W_VDISK[slot][slot_map.IOCLASS.VDISK][udid],
                             lua)

        # Deterministic. vios2 gets slot 2
        for udid in rsm._build_map['VDisk']['vios2']:
            slot, lua = rsm.get_vscsi_slot(self.vio2, udid)
            self.assertEqual(2, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_W_VDISK[slot][slot_map.IOCLASS.VDISK][udid],
                             lua)

        # The build map won't actually have these as keys but
        # the get should return None nicely.
        slot, lua = rsm.get_vscsi_slot(self.vio1, 'vd_udid3')
        self.assertIsNone(slot)

    def test_lu_vscsi_build_out_1(self):
        """Test RebuildSlotMap deterministic."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_LU_1
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2],
                                      VOL_TO_VIO1, {})

        # Deterministic. vios1 gets slot 1
        for udid in rsm._build_map['LU']['vios1']:
            slot, lua = rsm.get_vscsi_slot(self.vio1, udid)
            self.assertEqual(1, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_LU_1[slot][slot_map.IOCLASS.LU][udid], lua)

        # Deterministic. vios2 gets slot 2
        for udid in rsm._build_map['LU']['vios2']:
            slot, lua = rsm.get_vscsi_slot(self.vio2, udid)
            self.assertEqual(2, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_LU_1[slot][slot_map.IOCLASS.LU][udid], lua)

        # The build map won't actually have these as keys but
        # the get should return None nicely.
        slot, lua = rsm.get_vscsi_slot(self.vio1, 'lu_udid4')
        self.assertIsNone(slot)
        slot, lua = rsm.get_vscsi_slot(self.vio2, 'lu_udid2')
        self.assertIsNone(slot)

    def test_pv_vscsi_build_out_1(self):
        """Test RebuildSlotMap deterministic."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_PV_1
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2],
                                      VOL_TO_VIO1, {})

        # Deterministic. vios1 gets slot 1
        for udid in rsm._build_map['PV']['vios1']:
            self.assertEqual(
                1, rsm.get_pv_vscsi_slot(self.vio1, udid))
            slot, lua = rsm.get_vscsi_slot(self.vio1, udid)
            self.assertEqual(1, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_PV_1[slot][slot_map.IOCLASS.PV][udid], lua)

        # Deterministic. vios2 gets slot 2
        for udid in rsm._build_map['PV']['vios2']:
            self.assertEqual(
                2, rsm.get_pv_vscsi_slot(self.vio2, udid))
            slot, lua = rsm.get_vscsi_slot(self.vio2, udid)
            self.assertEqual(2, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_PV_1[slot][slot_map.IOCLASS.PV][udid], lua)

        # The build map won't actually have these as keys but
        # the get should return None nicely.
        self.assertIsNone(
            rsm.get_pv_vscsi_slot(self.vio1, 'pv_udid4'))
        self.assertIsNone(
            rsm.get_pv_vscsi_slot(self.vio2, 'pv_udid2'))

    def test_mix_vscsi_build_out_1(self):
        """Test RebuildSlotMap deterministic."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_MIX_1
        rsm = slot_map.RebuildSlotMap(smt, [self.vio1, self.vio2],
                                      VOL_TO_VIO1, {})

        # Deterministic. vios1 gets slot 1
        for udid in rsm._build_map['PV']['vios1']:
            slot, lua = rsm.get_vscsi_slot(self.vio1, udid)
            self.assertEqual(1, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_MIX_1[slot][slot_map.IOCLASS.PV][udid], lua)

        for udid in rsm._build_map['LU']['vios1']:
            slot, lua = rsm.get_vscsi_slot(self.vio1, udid)
            self.assertEqual(1, slot)
            # Make sure we got the right LUA for this UDID
            self.assertEqual(SCSI_MIX_1[slot][slot_map.IOCLASS.LU][udid], lua)

        # The build map won't actually have these as keys but
        # the get should return None nicely.
        slot, lua = rsm.get_vscsi_slot(self.vio2, 'lu_udid2')
        self.assertIsNone(slot)
        slot, lua = rsm.get_vscsi_slot(self.vio2, 'pv_udid2')
        self.assertIsNone(slot)

    def test_vscsi_build_out_arbitrary_dest_vioses(self):
        """Test RebuildSlotMap with multiple candidate dest VIOSes."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_ARB_MAP

        rsm = slot_map.RebuildSlotMap(
            smt, [self.vio1, self.vio2], VTV_2V_ARB, {})

        # Since this isn't deterministic we want to make sure each UDID
        # got their slot assigned to one VIOS and not the other.
        expected_map = {'lu_udid1': 47, 'pv_udid2': 9, 'lu_udid3': 23,
                        'pv_udid4': 56}
        for udid, eslot in six.iteritems(expected_map):
            aslot1, lua1 = rsm.get_vscsi_slot(self.vio1, udid)
            aslot2, lua2 = rsm.get_vscsi_slot(self.vio2, udid)
            if aslot1 is None:
                self.assertEqual(eslot, aslot2)
                if SCSI_ARB_MAP[eslot].get(slot_map.IOCLASS.LU):
                    self.assertEqual(
                        SCSI_ARB_MAP[eslot][slot_map.IOCLASS.LU][udid], lua2)
                else:
                    self.assertEqual(
                        SCSI_ARB_MAP[eslot][slot_map.IOCLASS.PV][udid], lua2)
            else:
                self.assertEqual(eslot, aslot1)
                self.assertIsNone(aslot2)
                if SCSI_ARB_MAP[eslot].get(slot_map.IOCLASS.LU):
                    self.assertEqual(
                        SCSI_ARB_MAP[eslot][slot_map.IOCLASS.LU][udid], lua1)
                else:
                    self.assertEqual(
                        SCSI_ARB_MAP[eslot][slot_map.IOCLASS.PV][udid], lua1)

    def test_vscsi_build_out_full_coverage(self):
        """Test rebuild with 2 slots per udid and 2 candidate VIOSes."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_PV_2S_2V_MAP

        rsm = slot_map.RebuildSlotMap(
            smt, [self.vio1, self.vio2], VTV_2V_ARB, {})
        expected_map = {'lu_udid1': [5, 23], 'pv_udid2': [6, 24],
                        'lu_udid3': [7, 25], 'pv_udid4': [8, 26]}

        # We know what slots the UDIDs should get but not what VIOSes they'll
        # belong to. So we'll assert that one VIOS gets 1 slot and the other
        # VIOS gets the other for each UDID.
        for udid, (eslot1, eslot2) in six.iteritems(expected_map):
            if rsm.get_pv_vscsi_slot(self.vio1, udid) != eslot1:
                self.assertEqual(
                    eslot1, rsm.get_pv_vscsi_slot(self.vio2, udid))
                self.assertEqual(
                    eslot2, rsm.get_pv_vscsi_slot(self.vio1, udid))
            else:
                # We already know vio1 got the first slot
                self.assertEqual(
                    eslot2, rsm.get_pv_vscsi_slot(self.vio2, udid))
            aslot1, lua1 = rsm.get_vscsi_slot(self.vio1, udid)
            aslot2, lua2 = rsm.get_vscsi_slot(self.vio2, udid)
            if eslot1 == aslot1:
                self.assertEqual(eslot2, aslot2)
                self.assertEqual(
                    SCSI_PV_2S_2V_MAP[eslot1][slot_map.IOCLASS.PV][udid], lua1)
                self.assertEqual(
                    SCSI_PV_2S_2V_MAP[eslot2][slot_map.IOCLASS.PV][udid], lua2)
            else:
                self.assertEqual(eslot1, aslot2)
                self.assertEqual(eslot2, aslot1)
                self.assertEqual(
                    SCSI_PV_2S_2V_MAP[eslot1][slot_map.IOCLASS.PV][udid], lua2)
                self.assertEqual(
                    SCSI_PV_2S_2V_MAP[eslot2][slot_map.IOCLASS.PV][udid], lua1)

    def test_pv_udid_not_found_on_dest(self):
        """Test RebuildSlotMap fails when UDID not found on dest."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_PV_3

        self.assertRaises(
            pv_e.InvalidHostForRebuildNoVIOSForUDID, slot_map.RebuildSlotMap,
            smt, [self.vio1, self.vio2], BAD_VOL_TO_VIO_FOR_PV_3, {})

    def test_more_pv_udids_than_dest_vioses_fails(self):
        """Test RebuildSlotMap fails when there's not enough VIOSes."""
        smt = self.smt_impl('foo')
        smt._slot_topo = SCSI_PV_1

        self.assertRaises(
            pv_e.InvalidHostForRebuildNotEnoughVIOS, slot_map.RebuildSlotMap,
            smt, [self.vio1, self.vio2], VOL_TO_VIO_1_VIOS_PV1, {})

    def test_npiv_build_out(self):
        """Test _npiv_build_out."""
        # Create a topology that will be converted to a rebuild map
        smt = self.smt_impl('foo')
        vios1 = mock.Mock()
        vios1.get_pfc_wwpns = mock.Mock(return_value=['wwpn1'])
        vios2 = mock.Mock()
        vios2.get_pfc_wwpns = mock.Mock(return_value=['wwpn2'])
        smt._slot_topo = {
            3: {'VFC': {'fab1': None}}, 4: {'VFC': {'fab7': None}},
            5: {'VFC': {'fab10': None}}, 6: {'VFC': {'fab8': None}},
            7: {'VFC': {'fab9': None}}, 8: {'VFC': {'fab9': None}},
            9: {'VFC': {'fab1': None}}, 10: {'VFC': {'fab9': None}},
            11: {'VFC': {'fab1': None}}, 12: {'VFC': {'fab7': None}},
            113: {'VFC': {'fab7': None}}, 114: {'VFC': {'fab7': None}}}

        # Run the actual test and verify an exception is raised
        self.assertRaises(
            pv_e.InvalidHostForRebuildFabricsNotFound, slot_map.RebuildSlotMap,
            smt, [vios1, vios2], None, ['fab1'])

        # Run the actual test
        fabrics = ['fab1', 'fab2', 'fab7', 'fab8', 'fab9', 'fab10', 'fab27']
        rsm = slot_map.RebuildSlotMap(smt, [vios1, vios2], None, fabrics)

        # Verify rebuild map was created successfully
        self.assertEqual({'VFC': {'fab1': [3, 9, 11], 'fab10': [5], 'fab2': [],
                                  'fab27': [], 'fab7': [4, 12, 113, 114],
                                  'fab8': [6], 'fab9': [7, 8, 10]}},
                         rsm._build_map)

        # Verify the getters return the slots correctly
        self.assertEqual([3, 9, 11], rsm.get_vfc_slots('fab1', 3))
        self.assertEqual([4, 12, 113, 114], rsm.get_vfc_slots('fab7', 4))
        self.assertEqual([6], rsm.get_vfc_slots('fab8', 1))
        self.assertEqual([7, 8, 10], rsm.get_vfc_slots('fab9', 3))
        self.assertEqual([5], rsm.get_vfc_slots('fab10', 1))
        self.assertEqual([], rsm.get_vfc_slots('fab2', 0))
        self.assertEqual([], rsm.get_vfc_slots('fab27', 0))

        # Check None paths
        self.assertEqual([], rsm.get_vfc_slots('badfab', 0))
        self.assertEqual([None], rsm.get_vfc_slots('badfab', 1))
        self.assertEqual([None, None], rsm.get_vfc_slots('badfab', 2))

        # Check error path.
        self.assertRaises(pv_e.InvalidHostForRebuildSlotMismatch,
                          rsm.get_vfc_slots, 'fab1', 2)


class TestRebuildSlotMap(TestRebuildSlotMapLegacy):
    """Test for RebuildSlotMap class with new-style SlotMapStore subclass.

    Tests BuildSlotMap class's get methods as well.
    """

    def __init__(self, *args, **kwargs):
        """Initialize with a particular SlotMapStore implementation."""
        super(TestRebuildSlotMap, self).__init__(*args, **kwargs)
        self.smt_impl = SlotMapTestImpl

SCSI_W_VOPT = {
    1: {
        slot_map.IOCLASS.VOPT: {
            slot_map.IOCLASS.VOPT: 'vopt_name'
        },
        slot_map.IOCLASS.PV: {
            'pv_udid1': 'pv_lua_1',
            'pv_udid2': 'pv_lua_2'
        }
    }
}

SCSI_W_VDISK = {
    1: {
        slot_map.IOCLASS.VDISK: {
            'vd_udid1': 'vd_lua_1',
            'vd_udid2': 'vd_lua_2'
        },
        slot_map.IOCLASS.PV: {
            'pv_udid1': 'pv_lua_1',
            'pv_udid2': 'pv_lua_2'
        }
    },
    2: {
        slot_map.IOCLASS.VDISK: {
            'vd_udid1': 'vd_lua_1',
            'vd_udid2': 'vd_lua_2'
        }
    }
}

SCSI_LU_1 = {
    1: {
        slot_map.IOCLASS.LU: {
            'lu_udid1': 'lu_lua_1',
            'lu_udid2': 'lu_lua_2',
            'lu_udid3': 'lu_lua_3'
        }
    },
    2: {
        slot_map.IOCLASS.LU: {
            'lu_udid1': 'lu_lua_1',
            'lu_udid3': 'lu_lua_3',
            'lu_udid4': 'lu_lua_4'
        }
    }
}

SCSI_PV_1 = {
    1: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': 'pv_lua_1',
            'pv_udid2': 'pv_lua_2',
            'pv_udid3': 'pv_lua_3'
        }
    },
    2: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': 'pv_lua_1',
            'pv_udid3': 'pv_lua_3',
            'pv_udid4': 'pv_lua_4'
        }
    }
}

SCSI_MIX_1 = {
    1: {
        slot_map.IOCLASS.LU: {
            'lu_udid1': 'lu_lua_1',
            'lu_udid2': 'lu_lua_2'
        },
        slot_map.IOCLASS.PV: {
            'pv_udid1': 'pv_lua_1',
            'pv_udid2': 'pv_lua_2'
        }
    }
}

SCSI_ARB_MAP = {
    47: {
        slot_map.IOCLASS.LU: {
            'lu_udid1': 'lu_lua_1'
        }
    },
    9: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': 'pv_lua_2'
        }
    },
    23: {
        slot_map.IOCLASS.LU: {
            'lu_udid3': 'lu_lua_3'
        }
    },
    56: {
        slot_map.IOCLASS.PV: {
            'pv_udid4': 'pv_lua_4'
        }
    }
}

SCSI_PV_2S_2V_MAP = {
    5: {
        slot_map.IOCLASS.PV: {
            'lu_udid1': 'pv_lua_1'
        }
    },
    6: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': 'pv_lua_2'
        }
    },
    7: {
        slot_map.IOCLASS.PV: {
            'lu_udid3': 'pv_lua_3'
        }
    },
    8: {
        slot_map.IOCLASS.PV: {
            'pv_udid4': 'pv_lua_4'
        }
    },
    23: {
        slot_map.IOCLASS.PV: {
            'lu_udid1': 'pv_lua_1'
        }
    },
    24: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': 'pv_lua_2'
        }
    },
    25: {
        slot_map.IOCLASS.PV: {
            'lu_udid3': 'pv_lua_3'
        }
    },
    26: {
        slot_map.IOCLASS.PV: {
            'pv_udid4': 'pv_lua_4'
        }
    }
}

SCSI_PV_3 = {
    23: {
        slot_map.IOCLASS.PV: {
            'pv_udid1': 'pv_lua_1'
        }
    },
    12: {
        slot_map.IOCLASS.PV: {
            'pv_udid2': 'pv_lua_2'
        }
    },
    4: {
        slot_map.IOCLASS.PV: {
            'pv_udid3': 'pv_lua_3'
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
        'vios1'
    ],
    'lu_udid3': [
        'vios1',
        'vios2'
    ],
    'lu_udid4': [
        'vios2'
    ],
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
    ],
    'vd_udid1': [
        'vios1',
        'vios2'
    ],
    'vd_udid2': [
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
    'lu_udid1': [
        'vios1',
        'vios2'
    ],
    'pv_udid2': [
        'vios1',
        'vios2'
    ],
    'lu_udid3': [
        'vios1',
        'vios2'
    ],
    'pv_udid4': [
        'vios1',
        'vios2'
    ]
}
