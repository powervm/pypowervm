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

"""General utilities around wrappers."""

import importlib
import os

import pypowervm.wrappers.entry_wrapper as ewrap

_wrappers_pkg = ('pypowervm', 'wrappers')

_imports = None


def _get_imports():
    global _imports
    if _imports is None:
        _modnames = [fname.rsplit('.', 1)[0]
                     for fname in os.listdir(os.path.join(*_wrappers_pkg))
                     if not fname.startswith('_')
                     and fname.endswith('.py')]
        _imports = {
            modname: importlib.import_module(
                '.'.join(_wrappers_pkg) + '.' + modname)
            for modname in _modnames}
    return _imports


def wrapper_class_iter():
    for imp in _get_imports().values():
        for klass in vars(imp).values():
            try:
                if issubclass(klass, ewrap.Wrapper):
                    yield klass
            except TypeError:
                pass
