# Copyright 2014, 2015 IBM Corp.
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

import pypowervm.const as pc
import pypowervm.tests.wrappers.util.test_wrapper_abc as twrap
import pypowervm.wrappers.storage as stor


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
        self.assertEqual(False, pv.is_fc_backed)
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
        # Test setters
        vdisk.capacity = 2
        self.assertEqual(2, vdisk.capacity)
        vdisk.name = 'new_name'
        self.assertEqual('new_name', vdisk.name)

    def test_add_vdisk(self):
        """Performs a test flow that adds a virtual disk."""
        vdisks = self.dwrap.virtual_disks

        self.assertEqual(1, len(vdisks))

        disk = stor.VDisk.bld('disk_name', 10.9876543, 'label')
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

        # Try a remove
        self.dwrap.virtual_disks.remove(vdisk)
        self.assertEqual(1, len(self.dwrap.virtual_disks))

    def test_add_phys_vol(self):
        """Performs a test flow that adds a physical volume to the vol grp."""
        phys_vols = self.dwrap.phys_vols

        self.assertEqual(1, len(phys_vols))

        phys_vol = stor.PV.bld('disk1')
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

        vmedia_repo = stor.VMediaRepos.bld('repo', 10.12345)
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

        new_media = stor.VOptMedia.bld('name', 0.123, 'r')
        self.assertIsNotNone(new_media)

        vopt_medias.append(new_media)
        media_repos[0].optical_media = vopt_medias
        self.assertEqual(3, len(media_repos[0].optical_media))

        # Check the attributes
        media = media_repos[0].optical_media[2]
        self.assertEqual('name', media.media_name)
        self.assertEqual(0.123, media.size)
        self.assertEqual('r', media.mount_type)

    def test_ordering(self):
        """Set fields out of order; ensure they end up in the right order."""
        vg = stor.VG._bld()
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
        vg = stor.VG.bld('myvg', [stor.PV.bld('hdisk1')])
        self.assertEqual(
            vg.toxmlstring(),
            '<uom:VolumeGroup xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:GroupName>myvg</uom:GroupName><uom:P'
            'hysicalVolumes schemaVersion="V1_0"><uom:PhysicalVolume schemaVer'
            'sion="V1_0"><uom:Metadata><uom:Atom/></uom:Metadata><uom:VolumeNa'
            'me>hdisk1</uom:VolumeName></uom:PhysicalVolume></uom:PhysicalVolu'
            'mes></uom:VolumeGroup>'.encode('utf-8'))


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
        # TODO(IBM): test setter

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
        # TODO(IBM): test setter

    def test_fresh_ssp(self):
        ssp = stor.SSP.bld('myssp', [
            stor.PV.bld(name=n) for n in (
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
        lu = stor.LU.bld('lu_name', 123)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:UnitCapacity>123.000000</uom:UnitCap'
            'acity><uom:UnitName>lu_name</uom:UnitName></uom:LogicalUnit>'.
            encode('utf-8'))
        lu = stor.LU.bld('lu_name', 1.2345678, thin=True)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>true</uom:ThinDevice><uom'
            ':UnitCapacity>1.234568</uom:UnitCapacity><uom:UnitName>lu_name</u'
            'om:UnitName></uom:LogicalUnit>'.encode('utf-8'))
        lu = stor.LU.bld('lu_name', .12300019999, thin=False)
        self.assertEqual(
            lu.toxmlstring(),
            '<uom:LogicalUnit xmlns:uom="http://www.ibm.com/xmlns/systems/powe'
            'r/firmware/uom/mc/2012_10/" schemaVersion="V1_0"><uom:Metadata><u'
            'om:Atom/></uom:Metadata><uom:ThinDevice>false</uom:ThinDevice><uo'
            'm:UnitCapacity>0.123000</uom:UnitCapacity><uom:UnitName>lu_name</'
            'uom:UnitName></uom:LogicalUnit>'.encode('utf-8'))

    def test_lu_ordering(self):
        lu = stor.LU._bld()
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

if __name__ == '__main__':
    unittest.main()
