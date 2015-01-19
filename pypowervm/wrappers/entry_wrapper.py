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

import abc
import logging

from pypowervm import adapter as adpt
from pypowervm.i18n import _
import pypowervm.wrappers.constants as c

import six

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Wrapper(object):
    """Base wrapper object that subclasses should extend.

    Provides base support for operations.  Will define a few methods that need
    to be overridden by subclasses.
    """

    def _find(self, property_name, use_find_all=False):
        """Will find a given element within the object.

        :param property_name: The property to search within the tree for.
        :param use_find_all: If set to true, will use the find_all method for
                             queries.
        """
        element = self._element
        if use_find_all:
            found_value = element.findall(property_name)
        else:
            found_value = element.find(property_name)

        return found_value  # May be None

    def replace_list(self, prop_name, prop_children):
        """Replaces a property on this Entry that contains a children list.

        The prop_children represent the new elements for the property.

        If the property does not already exist, this will simply append the
        new children.

        :param prop_name: The property name to replace with the new value.
        :param prop_children: A list of ElementWrapper objects that represent
                              the new children for the property list.
        """
        root_elem = self._element
        new_elem = adpt.Element(prop_name,
                                attrib=c.DEFAULT_SCHEMA_ATTR,
                                children=[x._element for
                                          x in prop_children])
        # Find existing
        existing = root_elem.find(prop_name)

        if existing:
            root_elem._element.replace(existing._element, new_elem._element)
        else:
            root_elem.append(new_elem)
        # If it existed, we need to maintain the order in the tree.

    @property
    def pvm_type(self):
        """Object type of the element from the tag value of the attribute.

        (ManagedSystem, LogicalPartition, etc)
        """
        return self._element.tag  # May be None

    @property
    @abc.abstractmethod
    def type_and_uuid(self):
        """Return the type and uuid of this entry together in one string.

        This is useful for error messages, logging, etc.
        """
        pass

    def set_parm_value(self, property_name, value):
        element_value = self._find(property_name)
        if element_value is None:
            self.log_missing_value(property_name)

        element_value.text = value

    def get_parm_value(self, property_name, default=None):
        element_value = self._find(property_name)
        if element_value is None:
            self.log_missing_value(property_name)
            return default

        text = element_value.text
        if text is None:
            return default

        if type(text) is str:
            text = text.strip()

        return text

    def get_parm_values(self, property_name):
        """Gets a list of values from PowerVM.

        :param property_name: property to return
        :returns: list of strings containing property values
        """
        values = []
        elements = self._find(property_name, use_find_all=True)
        if elements is not None:
            for element in elements:
                values.append(element.text)
        return values

    # TODO(IBM): Make this return an actual boolean
    def get_parm_value_bool(self, property_name, default='*unset*'):
        """Gets the boolean value of a PowerVM property.

        :param property_name: property to return
        :param default: The value to return if the property is not found
            in the data
        :return: If the property exists in the data and has the value
            'true' or 'false' (case-insensitive), then the corresponding
            boolean value will be returned.
            If the property does not exist, then the default value will be
            returned if specified, otherwise False will be returned.
        """
        value = self.get_parm_value(property_name)
        if value is None and default != '*unset*':
            # The caller has set a default value.  Return their default
            # value if the data does not have their property.
            return default

        if value:
            value = value.lower()

        return value == 'true'

    def get_parm_value_int(self, property_name, default=0):
        """Gets the integer value of a property.

        param property_name: property to return
        returns: integer value of property. Otherwise, default value
        """
        value = self.get_parm_value(property_name)
        if value is None or len(value) == 0:
            return default

        try:
            int_value = int(value)
            return int_value
        except ValueError:
            message = (
                _("Cannot convert %(property_name)s='%(value)s' to an integer "
                  "in object %(pvmobject)s") % {
                    "property_name": property_name,
                    "value": value,
                    "pvmobject": self.type_and_uuid})

            LOG.error(message)

        return default

    def log_missing_value(self, param):
        error_message = (
            _('The expected parameter of %(param)s was not found in '
              '%(identifier)s') % {
                "param": param,
                "identifier": self.type_and_uuid})
        LOG.warn(error_message)


class EntryWrapper(Wrapper):
    """Base Wrapper for the Entry object types."""

    def __init__(self, entry):
        self._entry = entry

    @property
    def _element(self):
        return self._entry.element

    @property
    def uuid(self):
        """Returns the uuid of the entry."""
        if self._entry is None:
            return None

        uuid = self._entry.properties[c.UUID]
        return uuid

    @property
    def type_and_uuid(self):
        """Return the type and uuid of this entry together in one string.

        This is useful for error messages, logging, etc.
        """
        entry_type = self.pvm_type
        uuid = self.uuid

        if entry_type is None:
            entry_type = "UnknownType"

        if uuid is None:
            uuid = "UnknownUUID"

        return entry_type + ":" + uuid


class ElementWrapper(Wrapper):
    """Base wrapper for Elements."""

    def __init__(self, element):
        self._element = element

    @property
    def type_and_uuid(self):
        """Return the type and uuid of this entry together in one string.

        This is useful for error messages, logging, etc.
        """
        entry_type = self.pvm_type

        if entry_type is None:
            entry_type = "UnknownType"

        return entry_type
