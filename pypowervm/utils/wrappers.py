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
import sys

from pypowervm.i18n import _
import pypowervm.wrappers.entry_wrapper as ewrap

_wrappers_pkg = ('pypowervm', 'wrappers')

_imports = None

_this_module = sys.modules[__name__]


def _get_imports():
    """Imports all modules in pypowervm.wrappers and returns them as a dict.

    The returned dict is of the form:

        { module_name: <module object>, ... }
    """
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
    """Iterator over all Wrapper subclasses defined in pypowervm.wrappers.

    Each yield is the Wrapper subclass itself.
    """
    for klass in (cls for imp in _get_imports().values()
                  for cls in vars(imp).values()):
        try:
            if issubclass(klass, ewrap.Wrapper):
                yield klass
        except TypeError:
            # issubclass can't handle the things that aren't classes
            pass


class FilteredWrapperElemList(list):
    """Filter a WrapperElemList by (nested) property values.

    For a WrapperElemList (such as VIOS.vfc_mappings), use this class to create
    and run a declarative filter to isolate some number of the ElementWrappers
    therein.

    Usage:
    - Initialize the filter with the WrapperElemList

        filt = FilteredWrapperElemList(vios_wrapper.vfc_mappings)

    - Filter by a @property of each ElementWrapper by using a method with the
      same name as the @property.  The (single) parameter is the value to
      filter for, in whatever form it would be returned by that @property.

        filt.client_lpar_href(href_string)

    - Filter by a *nested* @property of each ElementWrapper.  Again, the name
      of the method should be the same as the @property returning the nested
      ElementWrapper.  The parameters must be keyword arguments where the key
      is the name of the @property of the sub-ElementWrapper, and the value is
      the value to filter for, in whatever form it would be returned by the
      (sub-)@property.

        filt.client_adapter(wwpns=['C05076079CFF0E56', 'C05076079CFF0E57'])

    - FilteredWrapperElemList subclasses list, so all typical list operations
      are available. The list is dynamically trimmed down to the results of
      whatever filtering is performed.

        for wrapper in filt:
            # Do whatever

    - You cannot use both flat and nested syntax at the same time.  That
      wouldn't make sense anyway.

            # Raises ValueError:
            filt.client_adapter(href_string, wwpns=[])

    - You cannot search for more than one flat value at once.  That wouldn't
      make sense either.  (Unless maybe someday we want to make that signify a
      logical OR.)

            # Raises ValueError:
            filt.client_lpar_href(href_one, href_two)

    - All filters are cumulative and logically ANDed, including multiple kwargs
      to a single nested filter.

    - Filter methods return the filter, so they can be chained.

            results = FilteredWrapperElemList(wrapper.things)
                      .flat_prop1(val)
                      .flat_prop2(val)
                      .nested_prop1(subprop=val)
                      .nested_prop2(subprop=val)
    """
    @staticmethod
    def _validate(afilt, kfilt):
        # Don't allow both a value and subwrapper key=values
        if afilt and kfilt:
            raise ValueError(_("Specify a value or a subwrapper "
                               "key=value, but not both."))
        # Only one flat value allowed
        if len(afilt) > 1:
            raise ValueError(_("Only one value allowed."))

    def __getattr__(self, item):
        def filter_func(*afilt, **kfilt):
            self._validate(afilt, kfilt)
            # We build up the result list afresh
            results = []
            for wrapper in self:
                # Let this raise AttributeError if item is bogus
                val_or_subwrapper = getattr(wrapper, item)
                if not val_or_subwrapper:
                    continue
                if kfilt and all(
                        value == getattr(val_or_subwrapper, prop)
                        for prop, value in kfilt.items()):
                    results.append(wrapper)
                elif afilt and afilt[0] == val_or_subwrapper:
                    results.append(wrapper)
            # filters are cumulative
            self[:] = results
            # Allow chaining
            return self
        return filter_func
