# Copyright 2014, 2017 IBM Corp.
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

import mock
import testtools

import pypowervm.const as pc
import pypowervm.exceptions as ex
import pypowervm.tests.test_utils.test_wrapper_abc as twrap
import pypowervm.wrappers.storage as stor
import pypowervm.wrappers.virtual_io_server as vios


class TestVolumeGroup(twrap.TestWrapper):

    file = 'fake_volume_group.txt'
    wrapper_class_to_test = stor.VG

    def test_base(self):
        """Tests baseline function within the Volume Group."""
        self.assertEqual('image_pool', self.dwrap.name)
        self.assertEqual(1063.3, self.dwrap.capacity)
        self.assertEqual(1051.1, self.dwrap.available_size)
        self.assertEqual(1051.2, self.dwrap.free_space)
        self.assertEqual('00f8d6de00004b000000014a54555cd9',
                         self.dwrap.serial_id)

    def test_vmedia_repos(self):
        """Tests the virtual media repositories."""
        repos = self.dwrap.vmedia_repos
        self.assertEqual(1, len(repos))
        self.assertEqual('VMLibrary', repos[0].name)
        self.assertEqual(11, repos[0].size)

        # Optical media
        vopts = repos[0].optical_media
        self.assertEqual(2, len(vopts))

        self.assertEqual('blank_media1', vopts[0].media_name)
        self.assertEqual('blank_media1', vopts[0].name)
        self.assertEqual(0.0977, vopts[0].size)
        self.assertEqual('0eblank_media1', vopts[0].udid)
        self.assertEqual('rw', vopts[0].mount_type)

    def test_physical_volumes(self):
        """Tests the physical volumes in the VG."""
        pvs = self.dwrap.phys_vols
        self.assertEqual(1, len(pvs))

        pv = pvs[0]
        self.assertEqual('01MUlCTSAgICAgSVBSLTAgICA1RDgyODMwMDAwMDAwMDQw',
                         pv.udid)
        self.assertEqual(1089592, pv.capacity)
        self.assertEqual('hdisk1', pv.name)
        self.assertEqual('active', pv.state)
        self.assertFalse(pv.is_fc_backed)
        self.assertTrue(pv.avail_for_use)
        self.assertEqual('SAS RAID 0 Disk Array', pv.description)
        self.assertEqual('U78C9.001.WZS0095-P1-C14-R1-L405D828300-L0',
                         pv.loc_code)

    def test_virtual_disk(self):
        """Tests the virtual disk gets."""
        vdisks = self.dwrap.virtual_disks
        self.assertEqual(1, len(vdisks))

        vdisk = vdisks[0]
        self.assertEqual('asdf', vdisk.name)
        self.assertEqual('None', vdisk.label)
        self.assertEqual(1, vdisk.capacity)
        self.assertEqual('0300f8d6de00004b000000014a54555cd9.1',
                         vdisk.udid)
        self.assertEqual(
            "https://9.1.2.3:12443/rest/api/uom/VirtualIOServer/14B854F7-42CE-"
            "4FF0-BD57-1D117054E701/VolumeGroup/b6bdbf1f-eddf-3c81-8801-9859eb"
            "6fedcb", vdisk.vg_uri)

        # Test setters
        vdisk.capacity = 2
        self.assertEqual(2, vdisk.capacity)
        vdisk.name = 'new_name'
        self.assertEqual('new_name', vdisk.name)
        vdisk._base_image('base_image')
        self.assertEqual('base_image', vdisk._get_val_str(stor._DISK_BASE))

    def test_add_vdisk(self):
        """Performs a test flow that adds a virtual disk."""
        vdisks = self.dwrap.virtual_disks

        self.assertEqual(1, len(vdisks))

        disk = stor.VDisk.bld(
            None, 'disk_name', 10.9876543, label='label', base_image='cache',
            file_format=stor.FileFormatType.RAW)
        self.assertIsNotNone(disk)

        vdisks.append(disk)
        self.dwrap.virtual_disks = vdisks

        self.assertEqual(2, len(self.dwrap.virtual_disks))

        # make sure the second virt disk matches what we put in
        vdisk = self.dwrap.virtual_disks[1]
        self.assertEqual('disk_name', vdisk.name)
        self.assertEqual(10.987654, vdisk.capacity)
        self.assertEqual('label', vdisk.label)
        self.assertEqual(None, vdisk.udid)
        self.assertEqual('cache', vdisk._get_val_str(stor._DISK_BASE))
        self.assertEqual(stor.FileFormatType.RAW, vdisk.file_format)

        # Try a remove
        self.dwrap.virtual_disks.remove(vdisk)
        self.assertEqual(1, len(self.dwrap.virtual_disks))

    def test_add_phys_vol(self):
        """Performs a test flow that adds a physical volume to the vol grp."""
        phys_vols = self.dwrap.phys_vols

        self.assertEqual(1, len(phys_vols))

        phys_vol = stor.PV.bld(None, 'disk1')
        self.assertIsNotNone(phys_vol)

        phys_vols.append(phys_vol)
        self.dwrap.phys_vols = phys_vols

        self.assertEqual(2, len(self.dwrap.phys_vols))

        # Make sure that the second physical volume matches
        pvol = self.dwrap.phys_vols[1]
        self.assertEqual('disk1', pvol.name)

    def test_add_media_repo(self):
        """Performs a simple add to the volume group of a new media repo."""
        media_repos = self.dwrap.vmedia_repos

        self.assertEqual(1, len(media_repos))

        vmedia_repo = stor.VMediaRepos.bld(None, 'repo', 10.12345)
        self.assertIsNotNone(vmedia_repo)

        media_repos.append(vmedia_repo)
        self.dwrap.vmedia_repos = media_repos

        self.assertEqual(2, len(self.dwrap.vmedia_repos))

        # Make sure that the second media repo matches
        repo = self.dwrap.vmedia_repos[1]
        self.assertEqual('repo', repo.name)
        self.assertEqual(10.12345, repo.size)
        self.assertEqual(0, len(repo.optical_media))

    def test_update_media_repo(self):
        """Performs a simple test to add optical media to an existing repo."""
        media_repos = self.dwrap.vmedia_repos

        vopt_medias = media_repos[0].optical_media
        self.assertEqual(2, len(vopt_medias))

        new_media = stor.VOptMedia.bld(None, 'name', 0.123, 'r')
        self.assertIsNotNone(new_media)

        vopt_medias.append(new_media)
        media_repos[0].optical_media = vopt_medias
        self.assertEqual(3, len(media_repos[0].optical_media))

        # Check the attributes
        media = media_repos[0].optical_media[2]
        self.assertEqual('name', media.media_name)
        self.assertEqual('name', media.name)
        self.assertEqual(0.123, media.size)
        self.assertEqual('r', media.mount_type)

    def test_ordering(self):
        """Set fields out of order; ensure they end up in the right order."""
        vg = stor.VG._bld(None)
        vg.virtual_disks = []
        vg.name = 'vgname'
        vg.vmedia_repos = []
        vg.set_parm_value(stor._VG_CAPACITY, 123)
        vg.phys_vols = []
        self.assertEqual(
            vg.toxmlstring(),
            '<uom:VolumeGroup xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:GroupCapacity>123</uom:GroupCapacity'
            '><uom:GroupName>vgname</uom:GroupName><uom:MediaRepositories sche'
            'maVersion="V1_0"/><uom:PhysicalVolumes schemaVersion="V1_0"/><uom'
            ':VirtualDisks schemaVersion="V1_0"/></uom:VolumeGroup>'.
            encode('utf-8'))

    def test_bld(self):
        vg = stor.VG.bld(None, 'myvg', [stor.PV.bld(None, 'hdisk1')])
        self.assertEqual(
            vg.toxmlstring(),
            '<uom:VolumeGroup xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:GroupName>myvg</uom:GroupName><uom:P'
            'hysicalVolumes schemaVersion="V1_0"><uom:PhysicalVolume schemaVer'
            'sion="V1_0"><uom:Metadata><uom:Atom/></uom:Metadata><uom:VolumeNa'
            'me>hdisk1</uom:VolumeName></uom:PhysicalVolume></uom:PhysicalVolu'
            'mes></uom:VolumeGroup>'.encode('utf-8'))


class TestLUEnt(twrap.TestWrapper):
    file = 'lufeed.txt'
    wrapper_class_to_test = stor.LUEnt

    def test_logical_units(self):
        lus = self.entries
        self.assertEqual(len(lus), 22)
        lu = lus[0]
        self.assertEqual('a2b11d20-322d-3dcc-84ee-74fce7e90310', lu.uuid)
        self.assertEqual(lu.udid, '276c097502d44311e58004000040f2e95dc4a789dfd'
                                  '63464654319f89c04aa5382')
        self.assertEqual(lu.name, 'boot_pvm3_tempest_ser_a73d7083')
        self.assertTrue(lu.is_thin)
        self.assertEqual(lu.lu_type, 'VirtualIO_Disk')
        self.assertAlmostEqual(lu.capacity, 1, 1)
        self.assertFalse(lu.in_use)
        self.assertEqual('296c097502d44311e58004000040f2e95dcf6063cd6bf7ed7b49'
                         '7780a1799236ab', lu.cloned_from_udid)

    def test_lu_bld(self):
        lu = stor.LUEnt.bld(None, 'lu_name', 123)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:UnitCapacity>123.000000</uom:UnitCap'
            'acity><uom:UnitName>lu_name</uom:UnitName></uom:LogicalUnit>'.
            encode('utf-8'))
        lu = stor.LUEnt.bld(None, 'lu_name', 1.2345678, thin=True,
                            typ=stor.LUType.IMAGE)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>true</uom:ThinDevice><uom'
            ':UnitCapacity>1.234568</uom:UnitCapacity><uom:LogicalUnitType>Vir'
            'tualIO_Image</uom:LogicalUnitType><uom:UnitName>lu_name</uom:Unit'
            'Name></uom:LogicalUnit>'.encode('utf-8'))
        lu = stor.LUEnt.bld(None, 'lu_name', .12300019999, thin=False,
                            clone=mock.Mock(capacity=1.23,
                                            udid='cloned_from_udid'))
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>false</uom:ThinDevice><uo'
            'm:UnitCapacity>1.230000</uom:UnitCapacity><uom:ClonedFrom>cloned_'
            'from_udid</uom:ClonedFrom><uom:UnitName>lu_name</uom:UnitName></u'
            'om:LogicalUnit>'.encode('utf-8'))

    def test_lu_ordering(self):
        lu = stor.LUEnt._bld(None)
        lu._name('lu_name')
        lu._udid('lu_udid')
        lu._cloned_from_udid('cloned_from')
        lu._capacity(123)
        lu.set_parm_value(stor._LU_THIN, 'true')
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>true</uom:ThinDevice><uom'
            ':UniqueDeviceID>lu_udid</uom:UniqueDeviceID><uom:UnitCapacity>123'
            '.000000</uom:UnitCapacity><uom:ClonedFrom>cloned_from</uom:Cloned'
            'From><uom:UnitName>lu_name</uom:UnitName></uom:LogicalUnit>'.
            encode('utf-8'))

    def test_lu_equality(self):
        # We can equate LUEnt and LU that represent the same LogicalUnit
        lu1 = stor.LUEnt.bld(None, 'mylu', 1)
        lu2 = stor.LU.bld(None, 'mylu', 2)
        self.assertEqual(lu1, lu2)
        lu1._udid('lu_udid')
        lu2._udid('lu_udid')
        self.assertEqual(lu1, lu2)
        lu2._udid('another_udid')
        self.assertNotEqual(lu1, lu2)
        lu2._udid('lu_udid')
        lu1._name('another_lu')
        self.assertNotEqual(lu1, lu2)

    def test_lu_hash(self):
        udid1 = ('27cfc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d8')
        # Only prefix differs.  Should fail == but hash equal
        udid2 = ('29cfc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d8')
        # Last bit differs
        udid3 = ('27cfc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d9')
        # First bit differs
        udid4 = ('274fc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d8')
        lu1 = stor.LUEnt.bld(None, 'mylu', 1)
        lu2 = stor.LUEnt.bld(None, 'mylu', 2)
        lu1._udid(udid1)
        lu2._udid(udid1)
        self.assertEqual({lu1}, {lu2})
        lu2._udid(udid2)
        self.assertNotEqual({lu1}, {lu2})
        self.assertEqual(hash(lu1), hash(lu2))
        lu2._udid(udid3)
        self.assertNotEqual({lu1}, {lu2})
        lu2._udid(udid4)
        self.assertNotEqual({lu1}, {lu2})


class TestTier(twrap.TestWrapper):
    file = 'tier.txt'
    wrapper_class_to_test = stor.Tier

    def test_props(self):
        self.assertEqual(1, len(self.entries))
        tier = self.dwrap
        self.assertEqual('SYSTEM', tier.name)
        self.assertEqual('256c097502d44311e58004000040f2e95d7d95846d854f9f38',
                         tier.udid)
        self.assertTrue(tier.is_default)
        self.assertAlmostEqual(3071.25, tier.capacity)
        self.assertEqual('535e1e51-50a6-3722-b6ed-907ff011a535', tier.ssp_uuid)


class TestSharedStoragePool(twrap.TestWrapper):

    file = 'ssp.txt'
    wrapper_class_to_test = stor.SSP

    def test_name(self):
        self.assertEqual(self.dwrap.name, 'neossp1')

    def test_udid(self):
        self.assertEqual(self.dwrap.udid, '24cfc907d2abf511e4b2d540f2e95daf3'
                         '0000000000972FB370000000054D14EB8')

    def test_capacity(self):
        self.assertAlmostEqual(self.dwrap.capacity, 49.88, 3)

    def test_free_space(self):
        self.assertAlmostEqual(self.dwrap.free_space, 48.98, 3)

    def test_over_commit_space(self):
        self.assertEqual(self.dwrap.over_commit_space, 1.234567)

    def test_total_lu_size(self):
        self.assertAlmostEqual(self.dwrap.total_lu_size, 1, 1)

    def test_physical_volumes(self):
        pvs = self.dwrap.physical_volumes
        self.assertEqual(len(pvs), 1)
        pv = pvs[0]
        self.assertEqual(
            pv.udid,
            '01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEODgwMDAwMDAwMDAwMDAwMw==')
        self.assertEqual(pv.name, 'hdisk3')
        # Test setter
        self.dwrap.physical_volumes = []
        pvs = self.dwrap.physical_volumes
        self.assertEqual(0, len(pvs))
        self.dwrap.physical_volumes = [stor.PV.bld(None, 'pv1', udid='udid1'),
                                       stor.PV.bld(None, 'pv2', udid='udid2')]
        pvs = self.dwrap.physical_volumes
        self.assertEqual(2, len(pvs))
        self.assertEqual(dict(pv1='udid1', pv2='udid2'),
                         {pv.name: pv.udid for pv in pvs})

    def test_logical_units(self):
        lus = self.dwrap.logical_units
        self.assertEqual(len(lus), 1)
        lu = lus[0]
        self.assertEqual(lu.udid, '27cfc907d2abf511e4b2d540f2e95daf301a02b090'
                         '4778d755df5a46fe25e500d8')
        self.assertEqual(lu.name, 'neolu1')
        self.assertTrue(lu.is_thin)
        self.assertEqual(lu.lu_type, 'VirtualIO_Disk')
        self.assertAlmostEqual(lu.capacity, 1, 1)
        self.assertTrue(lu.in_use)
        # Test setter
        self.dwrap.logical_units = []
        lus = self.dwrap.logical_units
        self.assertEqual(0, len(lus))
        self.dwrap.logical_units = [stor.LU.bld(None, 'lu1', 1),
                                    stor.LU.bld(None, 'lu2', 2)]
        lus = self.dwrap.logical_units
        self.assertEqual(2, len(lus))
        self.assertEqual(dict(lu1=1, lu2=2),
                         {lu.name: lu.capacity for lu in lus})

    def test_fresh_ssp(self):
        ssp = stor.SSP.bld(None, 'myssp', [
            stor.PV.bld(None, name=n) for n in (
                'hdisk123', 'hdisk132', 'hdisk213', 'hdisk231', 'hdisk312',
                'hdisk321')])
        self.assertEqual(ssp.name, 'myssp')
        self.assertEqual(ssp.schema_type, stor.SSP.schema_type)
        self.assertEqual(ssp.schema_ns, pc.UOM_NS)
        pvs = ssp.physical_volumes
        self.assertEqual(len(pvs), 6)
        pv = pvs[3]  # hdisk231
        self.assertEqual(pv.schema_type, stor.PV.schema_type)
        self.assertEqual(pv.schema_ns, pc.UOM_NS)
        self.assertEqual(pv.name, 'hdisk231')

    def test_lu_bld(self):
        lu = stor.LU.bld(None, 'lu_name', 123)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:UnitCapacity>123.000000</uom:UnitCap'
            'acity><uom:UnitName>lu_name</uom:UnitName></uom:LogicalUnit>'.
            encode('utf-8'))
        lu = stor.LU.bld(None, 'lu_name', 1.2345678, thin=True)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>true</uom:ThinDevice><uom'
            ':UnitCapacity>1.234568</uom:UnitCapacity><uom:UnitName>lu_name</u'
            'om:UnitName></uom:LogicalUnit>'.encode('utf-8'))
        lu = stor.LU.bld(None, 'lu_name', .12300019999, thin=False)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>false</uom:ThinDevice><uo'
            'm:UnitCapacity>0.123000</uom:UnitCapacity><uom:UnitName>lu_name</'
            'uom:UnitName></uom:LogicalUnit>'.encode('utf-8'))

    def test_lu_ordering(self):
        lu = stor.LU._bld(None)
        lu._name('lu_name')
        lu._udid('lu_udid')
        lu.set_parm_value(stor._LU_CLONED_FROM, 'cloned_from')
        lu._capacity(123)
        lu.set_parm_value(stor._LU_THIN, 'true')
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>true</uom:ThinDevice><uom'
            ':UniqueDeviceID>lu_udid</uom:UniqueDeviceID><uom:UnitCapacity>123'
            '.000000</uom:UnitCapacity><uom:ClonedFrom>cloned_from</uom:Cloned'
            'From><uom:UnitName>lu_name</uom:UnitName></uom:LogicalUnit>'.
            encode('utf-8'))

    def test_lu_equality(self):
        lu1 = stor.LU.bld(None, 'mylu', 1)
        lu2 = stor.LU.bld(None, 'mylu', 2)
        self.assertEqual(lu1, lu2)
        lu1._udid('lu_udid')
        lu2._udid('lu_udid')
        self.assertEqual(lu1, lu2)
        lu2._udid('another_udid')
        self.assertNotEqual(lu1, lu2)
        lu2._udid('lu_udid')
        lu1._name('another_lu')
        self.assertNotEqual(lu1, lu2)

    def test_lu_hash(self):
        udid1 = ('27cfc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d8')
        # Only prefix differs.  Should fail == but hash equal
        udid2 = ('29cfc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d8')
        # Last bit differs
        udid3 = ('27cfc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d9')
        # First bit differs
        udid4 = ('274fc907d2abf511e4b2d540f2e95daf3'
                 '01a02b0904778d755df5a46fe25e500d8')
        lu1 = stor.LU.bld(None, 'mylu', 1)
        lu2 = stor.LU.bld(None, 'mylu', 2)
        lu1._udid(udid1)
        lu2._udid(udid1)
        self.assertEqual({lu1}, {lu2})
        lu2._udid(udid2)
        self.assertNotEqual({lu1}, {lu2})
        self.assertEqual(hash(lu1), hash(lu2))
        lu2._udid(udid3)
        self.assertNotEqual({lu1}, {lu2})
        lu2._udid(udid4)
        self.assertNotEqual({lu1}, {lu2})


class TestVFCClientAdapter(twrap.TestWrapper):
    file = 'vfc_client_adapter_feed.txt'
    wrapper_class_to_test = stor.VFCClientAdapter

    def test_vfc_client_adapter(self):
        """Check getters on VFCClientAdapter.

        The hard part - the wrapping - was done by TestWrapper.
        """
        self.assertEqual('U8247.21L.212A64A-V25-C4', self.dwrap.loc_code)
        self.assertEqual(25, self.dwrap.lpar_id)
        self.assertEqual(2, self.dwrap.vios_id)
        self.assertEqual('Client', self.dwrap.side)
        self.assertEqual(4, self.dwrap.lpar_slot_num)
        self.assertEqual(10, self.dwrap.vios_slot_num)
        self.assertEqual(['C05076087CBA0169', 'C05076087CBA0168'],
                         self.dwrap.wwpns)


class TestVIOS(twrap.TestWrapper):
    file = 'vio_multi_vscsi_mapping.txt'
    wrapper_class_to_test = vios.VIOS

    def test_pg83_in_pv(self):
        """Legitimate pg83 data from the <PhysicalVolume/>."""
        self.assertEqual('600507680282861D88000000000000B5',
                         self.dwrap.phys_vols[1].pg83)

    # TODO(efried): reinstate when VIOS supports pg83 descriptor in Events
    # def test_pg83_absent_from_pv(self):
    #     """No pg83 data in <PhysicalVolume/>."""
    #     self.assertIsNone(self.dwrap.phys_vols[0].pg83)

    @mock.patch('pypowervm.wrappers.job.Job.wrap')
    def test_pg83_absent_from_pv(self, mock_wrap):
        """LUARecovery.QUERY_INVENTORY when no pg83 in <PhysicalVolume/>."""
        # TODO(efried): remove this method once VIOS supports pg83 in Events
        mock_jwrap = mock.Mock()
        mock_jwrap.get_job_results_as_dict.return_value = {
            'OutputXML':
                '<VIO version="1.21" xmlns="http://ausgsa.austin.ibm">'
                '<Response><InventoryResponse viosId="8247-21L03212A60A" '
                'sequence="435" inventoryType="base" eventLogOn="true">'
                '<PhysicalVolume udid="01M0lCTTIxNDUxMjQ2MDA1MDc2ODAyODI4NjFEO'
                'DgwMDAwMDAwMDAwMDBEQQ==" name="hdisk2" '
                'description="MPIO IBM 2076 FC Disk">'
                '<PhysicalVolume_base capacity="20480" '
                'locationCode="U78CB.001.WZS05HN-P1-C7-T1-W500507680220E523-L2'
                '000000000000" '
                'unique_id="33213600507680282861D880000000DA04214503IBMfcp" '
                'descriptor="SV9hbV9hX3BnODNfTkFBX2Rlc2NyaXB0b3I=" '
                'desType="NAA"></PhysicalVolume_base></PhysicalVolume>'
                '</InventoryResponse></Response></VIO><?xml version="1.0"?>'
                '<uom:VIO xmlns:uom="http://www.ibm.com/xmlns/systems/power/fi'
                'rmware/uom/mc/2012_10/" xmlns="" version="1.21">'
                '<uom:Response/></uom:VIO>'}
        mock_wrap.return_value = mock_jwrap
        self.assertEqual('I_am_a_pg83_NAA_descriptor',
                         self.dwrap.phys_vols[0].pg83)
        mock_jwrap.run_job.assert_called_with(
            '3443DB77-AED1-47ED-9AA5-3DB9C6CF7089', job_parms=[mock.ANY])

    def test_pg83_raises_if_no_parent_entry(self):
        """Raise attempting to get pg83 if PV has no parent_entry."""
        # TODO(efried): remove this method once VIOS supports pg83 in Events
        pv = stor.PV.bld(self.adpt, 'name', 'udid')
        self.assertRaises(ex.UnableToBuildPG83EncodingMissingParent,
                          lambda: pv.pg83)

    def test_bogus_pg83_in_pv(self):
        """Bogus pg83 data in the <PhysicalVolume/> doesn't trigger the Job."""
        with self.assertLogs(stor.__name__, 'WARNING'):
            self.assertIsNone(self.dwrap.phys_vols[2].pg83)


class TestTargetDevs(twrap.TestWrapper):
    """Tests for VSCSIMapping.target_dev and {storage_type}TargetDev wrappers.

    SCSI mapping target devices in the test file are laid out as follows:

    index  type            LUA
    0      LUTargetDev     0x8200000000000000
    1      None            -
    2      None            -
    3      LUTargetDev     0x8400000000000000
    4      LUTargetDev     0x8500000000000000
    5      VOptTargetDev   0x8100000000000000
    6      LUTargetDev     0x8300000000000000
    7      PVTargetDev     0x8600000000000000
    8      VDiskTargetDev  0x8700000000000000
    """
    file = 'fake_vios_ssp_npiv.txt'
    wrapper_class_to_test = vios.VIOS

    def test_subtypes_props(self):
        """Right subtypes and LUA gets/sets from VSCSIMapping.target_dev."""
        smaps = self.dwrap.scsi_mappings
        # LU
        self.assertIsInstance(smaps[0].target_dev, stor.LUTargetDev)
        self.assertEqual('0x8200000000000000', smaps[0].target_dev.lua)
        smaps[0].target_dev._lua('lu_lua')
        self.assertEqual('lu_lua', smaps[0].target_dev.lua)
        # No TargetDevice
        self.assertIsNone(smaps[1].target_dev)
        # VOpt
        self.assertIsInstance(smaps[5].target_dev, stor.VOptTargetDev)
        self.assertEqual('0x8100000000000000', smaps[5].target_dev.lua)
        smaps[5].target_dev._lua('vopt_lua')
        self.assertEqual('vopt_lua', smaps[5].target_dev.lua)
        # PV
        self.assertIsInstance(smaps[7].target_dev, stor.PVTargetDev)
        self.assertEqual('0x8600000000000000', smaps[7].target_dev.lua)
        smaps[7].target_dev._lua('pv_lua')
        self.assertEqual('pv_lua', smaps[7].target_dev.lua)
        # LV/VDisk
        self.assertIsInstance(smaps[8].target_dev, stor.VDiskTargetDev)
        self.assertEqual('0x8700000000000000', smaps[8].target_dev.lua)
        smaps[8].target_dev._lua('lv_lua')
        self.assertEqual('lv_lua', smaps[8].target_dev.lua)

    def test_bld_set(self):
        """Test *TargetDev.bld(lua) and setting VSCSIMapping.target_dev."""
        smaps = self.dwrap.scsi_mappings
        for klass in (stor.LUTargetDev, stor.VOptTargetDev, stor.PVTargetDev,
                      stor.VDiskTargetDev):
            lua_tag = klass.__class__.__name__ + "_lua"
            # Build LU target dev
            vtd = klass.bld('adap', lua_tag)
            self.assertEqual('adap', vtd.adapter)
            self.assertEqual(lua_tag, vtd.lua)
            # Assign to a target_dev in the SCSI mappings.  Pick one that's
            # initially empty: the first iteration will prove we can assign to
            # an empty one; subsequent iterations will prove we can overwrite.
            smaps[1]._target_dev(vtd)
            self.assertIsInstance(smaps[1].target_dev, klass)
            self.assertEqual(lua_tag, smaps[1].target_dev.lua)


class TestStorageTypes(testtools.TestCase):
    def test_fileio(self):
        fio = stor.FileIO.bld_ref('adap', 'path')
        self.assertEqual('path', fio.label)
        self.assertEqual('path', fio.path)
        self.assertEqual('path', fio.name)
        self.assertIsNone(fio.capacity)
        self.assertIsNone(fio.udid)
        self.assertEqual('File', fio.vdtype)
        self.assertIsNone(fio.backstore_type)
        # Explicit backstore, legacy bld method
        fio = stor.FileIO.bld('adap', 'path',
                              backstore_type=stor.BackStoreType.FILE_IO)
        self.assertEqual('path', fio.label)
        self.assertEqual('path', fio.path)
        self.assertEqual('path', fio.name)
        self.assertIsNone(fio.capacity)
        self.assertIsNone(fio.udid)
        self.assertEqual('File', fio.vdtype)
        self.assertEqual('fileio', fio.backstore_type)
