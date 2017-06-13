# Copyright 2017 IBM Corp.
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

import pypowervm.exceptions as exc
import pypowervm.tasks.power_opts as popts
import pypowervm.wrappers.base_partition as bp


class TestPowerOpts(testtools.TestCase):
    def _test_enum(self, enum):
        """Validate that an enum class has a KEY and proper ALL_VALUES.

        :param enum: Enumeration class.
        """
        # Get the public symbols in the enum
        syms = {sym for sym in dir(enum) if not sym.startswith('_')}
        # Must have a KEY
        self.assertIn('KEY', syms)
        self.assertIsNotNone(getattr(enum, 'KEY'))
        syms.remove('KEY')
        # Must have ALL_VALUES
        self.assertIn('ALL_VALUES', syms)
        syms.remove('ALL_VALUES')
        # ALL_VALUES must include all the values that aren't KEY or ALL_VALUES
        self.assertEqual({getattr(enum, sym) for sym in syms},
                         set(enum.ALL_VALUES))

    def test_enums(self):
        self._test_enum(popts.IPLSrc)
        self._test_enum(popts.BootMode)
        self._test_enum(popts.KeylockPos)
        self._test_enum(popts.IBMiOperationType)
        self._test_enum(popts.PowerOffOperation)

    def test_remove_optical(self):
        knm = popts.RemoveOptical.KEY_NAME
        ktm = popts.RemoveOptical.KEY_TIME
        # Default time
        self.assertEqual({knm: 'name', ktm: 0},
                         popts.RemoveOptical.bld_map('name'))
        # Explicit time
        self.assertEqual({knm: 'name', ktm: 10},
                         popts.RemoveOptical.bld_map('name', time=10))

    def test_power_on_opts(self):
        # Default init
        poo = popts.PowerOnOpts()
        self.assertEqual('PowerOn()', str(poo))
        self.assertEqual('PowerOn', poo.JOB_SUFFIX)
        # Legacy add_parms init
        poo = popts.PowerOnOpts(legacy_add_parms=dict(foo=1, bar=2))
        self.assertEqual('PowerOn(bar=2, foo=1)', str(poo))
        # Carry those additional params forward to make sure they don't vanish
        # Enum validation
        for meth in ('bootmode', 'keylock_pos', 'ibmi_ipl_source',
                     'ibmi_op_type'):
            self.assertRaises(exc.InvalidEnumValue, getattr(poo, meth), 'foo')
        # Set specific (valid) values
        # Setter method returns the instance
        self.assertIs(poo, poo.bootmode(popts.BootMode.NORM))
        self.assertEqual('PowerOn(bar=2, bootmode=norm, foo=1)', str(poo))
        self.assertIs(poo, poo.keylock_pos(popts.KeylockPos.MANUAL))
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, foo=1, keylock=manual)', str(poo))
        self.assertIs(poo, poo.bootstring('canvas cord with aglet'))
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, bootstring=canvas cord with aglet, '
            'foo=1, keylock=manual)', str(poo))
        # Make sure overwrite works
        self.assertIs(poo, poo.bootstring('sturdy shoelace'))
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, bootstring=sturdy shoelace, foo=1, '
            'keylock=manual)', str(poo))
        self.assertIs(poo, poo.force())
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, bootstring=sturdy shoelace, foo=1, '
            'force=true, keylock=manual)', str(poo))
        # Turning off force gets rid of the key
        self.assertIs(poo, poo.force(value=False))
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, bootstring=sturdy shoelace, foo=1, '
            'keylock=manual)', str(poo))
        # Remove optical with default time
        self.assertIs(poo, poo.remove_optical('vopt'))
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, bootstring=sturdy shoelace, foo=1, '
            'keylock=manual, remove_optical_name=vopt, remove_optical_time=0)',
            str(poo))
        # Remove optical with explicit time.  Values are overwritten.
        self.assertIs(poo, poo.remove_optical('VOPT', time=5))
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, bootstring=sturdy shoelace, foo=1, '
            'keylock=manual, remove_optical_name=VOPT, remove_optical_time=5)',
            str(poo))
        self.assertIs(poo, poo.ibmi_ipl_source(popts.IPLSrc.A))
        self.assertEqual(
            'PowerOn(bar=2, bootmode=norm, bootstring=sturdy shoelace, foo=1, '
            'iIPLsource=a, keylock=manual, remove_optical_name=VOPT, '
            'remove_optical_time=5)', str(poo))
        self.assertIs(poo, poo.ibmi_op_type(popts.IBMiOperationType.NETBOOT))
        self.assertEqual(
            'PowerOn(OperationType=netboot, bar=2, bootmode=norm, '
            'bootstring=sturdy shoelace, foo=1, iIPLsource=a, keylock=manual, '
            'remove_optical_name=VOPT, remove_optical_time=5)', str(poo))
        # Netboot params.
        poo = popts.PowerOnOpts().ibmi_netboot_params(
            'ip', 'serverip', 'gateway', 'serverdir')
        self.assertEqual(
            'PowerOn(Gateway=gateway, IBMiImageServerDirectory=serverdir, '
            'IPAddress=ip, ServerIPAddress=serverip)', str(poo))
        # Optional netboot params, and overwrites
        self.assertIs(poo, poo.ibmi_netboot_params(
            'IP', 'ServerIP', 'Gateway', 'ServerDir', vlanid=2, mtu='mtu',
            duplex='duplex', connspeed=100, subnet='subnet'))
        self.assertEqual(
            'PowerOn(ConnectionSpeed=100, DuplexMode=duplex, Gateway=Gateway, '
            'IBMiImageServerDirectory=ServerDir, IPAddress=IP, '
            'MaximumTransmissionUnit=mtu, ServerIPAddress=ServerIP, '
            'SubnetMask=subnet, VLANID=2)', str(poo))

    def test_power_off_opts(self):
        # Can OS shutdown?
        ltyp = bp.LPARType
        rmcs = bp.RMCState
        for env, rmc, exp in ((ltyp.AIXLINUX, rmcs.ACTIVE, True),
                              (ltyp.AIXLINUX, rmcs.BUSY, False),
                              (ltyp.AIXLINUX, rmcs.INACTIVE, False),
                              (ltyp.OS400, rmcs.ACTIVE, True),
                              (ltyp.OS400, rmcs.BUSY, True),
                              (ltyp.OS400, rmcs.INACTIVE, True),
                              (ltyp.VIOS, rmcs.ACTIVE, True),
                              (ltyp.VIOS, rmcs.BUSY, False),
                              (ltyp.VIOS, rmcs.INACTIVE, False)):
            self.assertEqual(exp, popts.PowerOffOpts.can_os_shutdown(
                mock.Mock(env=env, rmc_state=rmc)))
        # Default init
        poo = popts.PowerOffOpts()
        self.assertEqual('PowerOff()', str(poo))
        self.assertEqual('PowerOff', poo.JOB_SUFFIX)
        self.assertFalse(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Legacy add_parms init.  Unknown keys are ignored.
        poo = popts.PowerOffOpts(
            legacy_add_parms=dict(operation='shutdown', foo=1, restart='true',
                                  bar=2, immediate='true'))
        self.assertEqual(
            'PowerOff(immediate=true, operation=shutdown, restart=true)',
            str(poo))
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertFalse(poo.is_os)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Now an "empty" one
        poo = popts.PowerOffOpts(legacy_add_parms=dict(foo=1, bar=2))
        self.assertEqual('PowerOff()', str(poo))
        self.assertFalse(poo.is_immediate)
        self.assertFalse(poo.is_restart)
        self.assertFalse(poo.is_os)
        self.assertFalse(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Immediate
        self.assertIs(poo, poo.immediate())
        self.assertEqual('PowerOff(immediate=true)', str(poo))
        self.assertTrue(poo.is_immediate)
        self.assertFalse(poo.is_restart)
        self.assertFalse(poo.is_os)
        self.assertFalse(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Restart
        self.assertIs(poo, poo.restart())
        self.assertEqual(
            'PowerOff(immediate=true, restart=true)', str(poo))
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertFalse(poo.is_os)
        self.assertFalse(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Operation
        self.assertIs(poo, poo.operation(popts.PowerOffOperation.DUMPRESTART))
        self.assertEqual(
            'PowerOff(immediate=true, operation=dumprestart, restart=true)',
            str(poo))
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertFalse(poo.is_os)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # OS shutdown
        self.assertIs(poo, poo.operation(popts.PowerOffOperation.OS))
        self.assertEqual(
            'PowerOff(immediate=true, operation=osshutdown, restart=true)',
            str(poo))
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_os)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Booleans can be shut off
        self.assertIs(poo, poo.immediate(value=False))
        self.assertEqual('PowerOff(operation=osshutdown, restart=true)',
                         str(poo))
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_os)
        self.assertIs(poo, poo.restart(value=False))
        self.assertEqual('PowerOff(operation=osshutdown)', str(poo))
        self.assertFalse(poo.is_immediate)
        self.assertFalse(poo.is_restart)
        self.assertTrue(poo.is_os)
        # "Smart" methods.  Make sure restart is preserved every time we change
        poo.restart()
        # OS immediate
        self.assertIs(poo, poo.os_immediate())
        self.assertEqual('PowerOff(immediate=true, operation=osshutdown, '
                         'restart=true)', str(poo))
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_os)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # OS normal (wipes out immediate)
        self.assertIs(poo, poo.os_normal())
        self.assertEqual('PowerOff(operation=osshutdown, restart=true)',
                         str(poo))
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_os)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # VSP hard
        self.assertIs(poo, poo.vsp_hard())
        self.assertEqual('PowerOff(immediate=true, operation=shutdown, '
                         'restart=true)', str(poo))
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertFalse(poo.is_os)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # VSP normal (wipes out immediate)
        self.assertIs(poo, poo.vsp_normal())
        self.assertEqual('PowerOff(operation=shutdown, restart=true)',
                         str(poo))
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertFalse(poo.is_os)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Soft detect
        part = mock.Mock(env=ltyp.AIXLINUX, rmc_state=rmcs.ACTIVE)
        self.assertIs(poo, poo.soft_detect(part))
        self.assertTrue(poo.is_os)
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Explicit normal shutdown
        self.assertIs(poo, poo.soft_detect(part, immed_if_os=False))
        self.assertTrue(poo.is_os)
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Explicit immediate OS shutdown
        self.assertIs(poo, poo.soft_detect(part, immed_if_os=True))
        self.assertTrue(poo.is_os)
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Can't OS shutdown
        part = mock.Mock(env=ltyp.VIOS, rmc_state=rmcs.BUSY)
        self.assertIs(poo, poo.soft_detect(part))
        self.assertFalse(poo.is_os)
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # immed_if_os ignored
        self.assertIs(poo, poo.soft_detect(part, immed_if_os=True))
        self.assertFalse(poo.is_os)
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertIs(poo, poo.soft_detect(part, immed_if_os=False))
        self.assertFalse(poo.is_os)
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertEqual('PowerOff(operation=shutdown, restart=true)',
                         str(poo))
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # IBMi defaults to OS normal
        part = mock.Mock(env=ltyp.OS400, rmc_state=rmcs.INACTIVE)
        self.assertIs(poo, poo.soft_detect(part))
        self.assertTrue(poo.is_os)
        self.assertFalse(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
        # Explicit immediate
        self.assertIs(poo, poo.soft_detect(part, immed_if_os=True))
        self.assertTrue(poo.is_os)
        self.assertTrue(poo.is_immediate)
        self.assertTrue(poo.is_restart)
        self.assertTrue(poo.is_param_set(popts.PowerOffOperation.KEY))
