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
import pypowervm.const as pc
from pypowervm.i18n import _
from pypowervm import util
import pypowervm.wrappers.constants as wc

import six

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class Wrapper(object):
    """Base wrapper object that subclasses should extend.

    Provides base support for operations.  Will define a few methods that need
    to be overridden by subclasses.
    """

    @property
    def schema_type(self):
        """PowerVM REST API Schema type of the subclass, as a string.

        This must be overridden by the subclass if the no-element/no-arg
        constructor call is to work.
        """
        raise NotImplementedError()

    @property
    def default_attrib(self):
        """Default attributes for fresh Element when no-arg constructor used.

        Subclasses may override as appropriate.
        """
        return wc.DEFAULT_SCHEMA_ATTR

    @property
    def schema_ns(self):
        """PowerVM REST API Schema namespace of the subclass."""
        return pc.UOM_NS

    @property
    def has_metadata(self):
        """Indicates whether the subclass needs a <Metadata/> child.

        Should be logically equivalent to asking whether the PowerVM REST API
        Schema object is a ROOT or CHILD (True) or DETAIL (False).
        """
        return False

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

    def _find_or_seed(self, prop_name, attrib=wc.DEFAULT_SCHEMA_ATTR):
        """Will find the existing element, or create if needed.

        If the element is not found, it will be added to the child list
        of this element.
        :param prop_name: The property name to replace with the new value.
        :param attrib: The attributes to use for the property.  Defaults to
                       the DEFAULT_SCHEM_ATTR.
        :returns: The existing element, or a newly created one if not found.
        """
        root_elem = self._element

        # Find existing
        existing = root_elem.find(prop_name)
        if existing:
            return existing
        else:
            new_elem = adpt.Element(prop_name, attrib=attrib,
                                    children=[])
            root_elem.append(new_elem)
            return new_elem

    def replace_list(self, prop_name, prop_children,
                     attrib=wc.DEFAULT_SCHEMA_ATTR):
        """Replaces a property on this Entry that contains a children list.

        The prop_children represent the new elements for the property.

        If the property does not already exist, this will simply append the
        new children.

        :param prop_name: The property name to replace with the new value.
        :param prop_children: A list of ElementWrapper objects that represent
                              the new children for the property list.
        :param attrib: The attributes to use if the property.  Defaults to
                       the DEFAULT_SCHEM_ATTR.
        """
        root_elem = self._element
        new_elem = adpt.Element(prop_name,
                                attrib=attrib,
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

    def set_parm_value(self, property_name, value, create=True):
        """Set a child element value, possibly creating the child.

        :param property_name: The schema name of the property to set.
        :param value: The (string) value to assign to the property's 'text'.
        :param create: If True, and the property is not found, it will be
        created.  Otherwise this method will throw an exception.
        """
        element_value = self._find(property_name)
        if element_value is None:
            self.log_missing_value(property_name)
            if create:
                element_value = adpt.Element(
                    property_name, attrib=self.default_attrib, text=value)
                self._element.append(element_value)

        element_value.text = value

    def get_parm_value(self, property_name, default=None, converter=None):
        element_value = self._find(property_name)
        if element_value is None:
            self.log_missing_value(property_name)
            return default

        text = element_value.text
        if text is None:
            return default

        if type(text) is str:
            text = text.strip()

        if callable(converter):
            try:
                return converter(text)
            except ValueError:
                message = (
                    _("Cannot convert %(property_name)s='%(value)s' "
                      "in object %(pvmobject)s") % {
                        "property_name": property_name,
                        "value": text,
                        "pvmobject": self.type_and_uuid})

                LOG.error(message)
                return default
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

    def log_missing_value(self, param):
        error_message = (
            _('The expected parameter of %(param)s was not found in '
              '%(identifier)s') % {
                "param": param,
                "identifier": self.type_and_uuid})
        LOG.warn(error_message)

    def get_href(self, propname, one_result=False):
        """Returns the hrefs from AtomLink elements.

        :param propname: The name of the schema element containing the 'href'
                         attribute.
        :param one_result: If True, we are expecting exactly one result, and
                           will return that one (string) result, or None.  If
                           False (the default), we will return a tuple of
                           strings which may be empty.
        """
        ret_links = []
        elements = self._find(propname, use_find_all=True)

        # Loop through what was found, if anything
        if elements:
            for atomlink in elements:
                # If the element doesn't have an href, ignore it.
                try:
                    ret_links.append(atomlink.attrib['href'])
                except KeyError:
                    pass

        if one_result:
            if len(ret_links) == 1:
                return ret_links[0]
            else:
                return None
        # Otherwise return a (possibly empty) tuple of the results
        return tuple(ret_links)


class EntryWrapper(Wrapper):
    """Base Wrapper for the Entry object types."""

    def __init__(self, entry, etag=None):
        self._entry = entry
        self._etag = etag

    @classmethod
    def load_from_response(cls, resp):
        """Loads an entry (or list of entries) from a response.

        If the response has a single entry, then a single entry will be
        returned.  This is NOT a list.

        If the response has a feed, a List of entries will be returned.  The
        entries within the feed are not guaranteed to have etags (ex. from
        non-uom elements)

        :param resp: The response from an adapter read request.
        :returns: A list of wrappers if a Feed.  A single wrapper if single
                  entry.
        """
        if resp.entry is not None:
            try:
                etag = resp.headers['etag']
            except KeyError:
                etag = None
            wrap = cls(resp.entry, etag=etag)
            return wrap
        elif resp.feed is not None:
            wraps = []
            for entry in resp.feed.entries:
                wraps.append(cls(entry, etag=entry.properties.get('etag',
                                                                  None)))
            return wraps
        else:
            raise KeyError

    @property
    def _element(self):
        return self._entry.element

    @property
    def etag(self):
        return self._etag

    @property
    def href(self):
        """Finds the reference to the entity.

        Assumes that the entity has a link element that references self.  If
        it does not, returns None.
        """
        val = self._entry.properties.get('links', {}).get('SELF', None)
        if val is not None and len(val) > 0:
            return val[0]
        else:
            return None

    @property
    def uuid(self):
        """Returns the uuid of the entry."""
        if self._entry is None:
            return None

        uuid = self._entry.properties[wc.UUID]
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

    def __init__(self, element=None, **kwargs):
        """Wrap an existing adapter.Element OR construct a fresh one.

        :param element: An existing adapter.Element to wrap.  If None, a
        new adapter.Element will be created.  This relies on the child class
        having its schema_type property defined.
        """
        if element is None:
            children = []
            if self.has_metadata:
                children.append(
                    adpt.Element('Metadata', ns=self.schema_ns,
                                 children=[adpt.Element(
                                     'Atom', ns=self.schema_ns)]))
            element = adpt.Element(
                self.schema_type, ns=self.schema_ns,
                attrib=self.default_attrib, children=children)
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

    def __eq__(self, other):
        """Tests equality."""
        return self._element == other._element


class WrapperElemList(list):
    """The wrappers can create complex Lists (from a Group from the response).

    The lists that they wrap tend to be generated on each 'get' from the
    property.  This list allows for modification of the 'wrappers' that
    get returned, which update the backing elements.

    This is not a full implementation of a list.  Only the 'common use' methods
    are supported

    Functions that are provided:
     - Getting via index (ex. list[1])
     - Obtaining the length (ex. len(list))
     - Extending the list (ex. list.extend(other_list))
     - Appending to the list (ex. list.append(other_elem))
     - Removing from the list (ex. list.remove(other_elem))
    """

    def __init__(self, root_elem, child_type, child_class, **kwargs):
        """Creates a new list backed by an Element anchor and child type.

        :param root_elem: The container element.  Should be the backing
                          element, not a wrapper.
                          Ex. The element for 'SharedEthernetAdapters'.
        :param child_type: The type of child element.  Should be a string.
                           Ex. 'SharedEthernetAdapter.
        :param child_class: The child class (subclass of ElementWrapper).
        :param kwargs: Optional additional named arguments that may be passed
                       into the wrapper on creation.
        """
        self.root_elem = root_elem
        self.child_type = child_type
        self.child_class = child_class
        self.injects = kwargs

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            all_elems = self.root_elem.findall(self.child_type)
            all_elems = all_elems[idx.start:idx.stop:idx.step]
            return [self.child_class(x, **self.injects) for x in all_elems]

        elem = self.root_elem.findall(self.child_type)[idx]
        return self.child_class(elem, **self.injects)

    def __getslice__(self, i, j):
        elems = self.root_elem.findall(self.child_type)
        return [self.child_class(x, **self.injects) for x in elems[i:j]]

    def __len__(self, *args, **kwargs):
        return len(self.root_elem.findall(self.child_type))

    def __iter__(self):
        elems = self.root_elem.findall(self.child_type)
        for elem in elems:
            yield self.child_class(elem, **self.injects)

    def __str__(self):
        elems = self.root_elem.findall(self.child_type)
        string = '['
        for elem in elems:
            string += str(elem)
            if elem != elems[len(elems) - 1]:
                string += ', '
        string += ']'
        return string

    def extend(self, seq):
        for elem in seq:
            self.append(elem)

    def append(self, elem):
        self.root_elem._element.append(elem._element._element)

    def remove(self, elem):
        # Try this way first...if there is a value error, that means
        # that the identical element isn't here...need to try 'functionally
        # equivalent' -> slower...
        try:
            self.root_elem.remove(elem._element)
            return
        except ValueError:
            pass

        # Onto the slower path.  Get children and see if any are equivalent
        children = self.root_elem.getchildren()
        equiv = util.find_equivalent(elem._element, children)
        if equiv is None:
            raise ValueError(_('No such child element.'))
        self.root_elem.remove(equiv)


class ActionableList(list):
    """Provides a List that will call back to a function on modification.

    Does not support lower level modifications (ex. list[5] = other_elem),
    but does support extend, append, remove, insert and pop.
    """

    def __init__(self, list_data, action):
        """Creations the action list.

        :param list_data: The list data
        :param action: The action to call back to.  Should take in a list
                       as a parameter (this is then list post modification).
        """
        super(ActionableList, self).__init__(list_data)
        self.action = action

    def extend(self, seq):
        super(ActionableList, self).extend(seq)
        self.action(self)

    def append(self, elem):
        super(ActionableList, self).append(elem)
        self.action(self)

    def remove(self, elem):
        super(ActionableList, self).remove(elem)
        self.action(self)

    def insert(self, index, obj):
        super(ActionableList, self).insert(index, obj)
        self.action(self)

    def pop(self, index=-1):
        elem = super(ActionableList, self).pop(index)
        self.action(self)
        return elem
