# Copyright 2015 IBM Corp.
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

import mock

import pypowervm.utils.psutil_compat as psutil

EXPECTED = [(['one', 'two', 'three'], None), (['four', 'five'], '/dev/tty5')]


class ProcessBase(object):
    """Base class for mocked Process classes."""
    def __init__(self, cmdline, terminal):
        self._cmdline = cmdline
        self._terminal = terminal


class ProcWithPropertys(ProcessBase):
    """Propertys for cmdline and terminal."""
    @property
    def cmdline(self):
        return self._cmdline

    @property
    def terminal(self):
        return self._terminal


class ProcWithMethods(ProcessBase):
    """Callable methods for cmdline and terminal."""
    def cmdline(self):
        return self._cmdline

    def terminal(self):
        return self._terminal


class ProcWithAttrs(ProcessBase):
    """Regular attributes for cmdline and terminal."""
    def __init__(self, cmdline, terminal):
        super(ProcWithAttrs, self).__init__(cmdline, terminal)
        self.cmdline = self._cmdline
        self.terminal = self._terminal


class TestPSUtilCompat(unittest.TestCase):
    """Unit tests for the psutil_compat."""

    @mock.patch('psutil.process_iter')
    def test_psutil_compat(self, mock_pi):
        for proc_cls in (ProcWithPropertys, ProcWithMethods, ProcWithAttrs):
            mock_pi.return_value = [proc_cls(cmd, term)
                                    for cmd, term in EXPECTED]
            self.assertEqual(EXPECTED, [(proc.cmdline, proc.terminal)
                                        for proc in psutil.process_iter()])
