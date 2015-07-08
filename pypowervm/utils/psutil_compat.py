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

"""Compatibility shim for psutil, supporting both pre- and post-2 versions."""

import psutil


def process_iter():
    for proc in psutil.process_iter():
        yield _ProcessCompat(proc)


class _ProcessCompat(object):
    """Shim around psutil.Process supporting pre- and post-2 versions.

    In pre-2 versions, certain methods (e.g. cmdline and terminal) are
    @propertys, whereas they're regular callable methods in post-2 versions.

    Note: we're using composition rather than inheritance so we can sparsely/
    selectively override methods from Process.  This is to obviate hidden
    errors if a consumer tries using an as-yet-unshimmed method but fails to
    test under both versions.
    """
    def __init__(self, proc):
        """Create an instance wrapping a psutil.Process.

        :param proc: psutil.Process instance to be wrapped.
        """
        self.proc = proc

    def _prop_or_meth(self, name):
        """Return proc.name or proc.name(), as appropriate.

        This only works for members that take no arguments.

        :param name: The name of the Process method/property/attribute to
                     invoke/retrieve and return.
        :return: The result of invoking/retrieving the named member of our
                 Process.
        """
        # Allow AttributeError to bubble up if name is bogus.  Same behavior as
        # invoking directly.
        member = getattr(self.proc, name)
        return member() if callable(member) else member

    @property
    def cmdline(self):
        """Wrap psutil.Process.cmdline."""
        return self._prop_or_meth('cmdline')

    @property
    def terminal(self):
        """Wrap psutil.Process.terminal."""
        return self._prop_or_meth('terminal')
