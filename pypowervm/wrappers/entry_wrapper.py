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

from lxml import etree

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

    @abc.abstractproperty
    def schema_type(self):
        """PowerVM REST API Schema type of the subclass, as a string.

        This must be overridden by the subclass if the no-element/no-arg
        constructor call is to work.
        """
        raise NotImplementedError()

    # Default attributes for fresh Element when no-arg constructor used.
    # Subclasses may override as appropriate.
    default_attrib = wc.DEFAULT_SCHEMA_ATTR

    # PowerVM REST API Schema namespace of the subclass.  Subclasses may
    # override as appropriate
    schema_ns = pc.UOM_NS

    def _find(self, property_name, use_find_all=False):
        """Will find a given element within the object.

        :param property_name: The property to search within the tree for.
        :param use_find_all: If set to true, will use the find_all method for
                             queries.
        """
        element = self.element
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
        root_elem = self.element

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
        root_elem = self.element
        new_elem = adpt.Element(prop_name,
                                attrib=attrib,
                                children=[x.element for
                                          x in prop_children])
        # Find existing
        existing = root_elem.find(prop_name)

        if existing:
            root_elem.element.replace(existing.element, new_elem.element)
        else:
            # If it existed, we need to maintain the order in the tree.
            root_elem.append(new_elem)

    @property
    def pvm_type(self):
        """Object type of the element from the tag value of the attribute.

        (ManagedSystem, LogicalPartition, etc)
        """
        return self.element.tag  # May be None

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
                    property_name, attrib=None, text=str(value))
                self.element.append(element_value)

        element_value.text = str(value)

    def __get_val(self, property_name, default=None, converter=None):
        """Retrieve the value of an element within this wrapper's ElementTree.

        This is the baseline for all the _get_val_{type} methods.
        :param property_name: The name (XPath) of the property to find.
        :param default: The default value to return if the property is not
                        found OR if type conversion fails.
        :param converter: Optional callable accepting a single string parameter
                          and returning a value of some other type.  The
                          converter callable should raise ValueError if
                          conversion fails.
        :return: The (possibly converted) value corresponding to the identified
                 property.
        """
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

    def _get_vals(self, property_name):
        """Gets a list of values from PowerVM.

        :param property_name: property to return
        :returns: List of strings containing property values.  No type
                  conversion is done.  If no elements are found, the empty list
                  is returned (as opposed to None).
        """
        values = []
        elements = self._find(property_name, use_find_all=True)
        if elements is not None:
            for element in elements:
                values.append(element.text)
        return values

    def _get_val_bool(self, property_name, default=False):
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
        def str2bool(bool_str):
            return str(bool_str).lower() == 'true'
        return self.__get_val(property_name, default=default,
                              converter=str2bool)

    def _get_val_int(self, property_name, default=None):
        """Gets the integer value of a PowerVM property.

        :param property_name: property to find
        :param default: Value to return if property is not found.  Defaults to
                        None (which is not an int - plan accordingly).
        :return: Integer (int) value of the property if it is found and it is a
                 valid integer.
        :raise ValueError: If the value cannot be converted.
        """
        return self.__get_val(property_name, default=default, converter=int)

    def _get_val_float(self, property_name, default=None):
        """Gets the float value of a PowerVM property.

        :param property_name: property to find
        :param default: Value to return if property is not found.  Defaults to
                        None (which is not a float - plan accordingly).
        :return: float value of the property if it is found and it is a
                 valid float.
        :raise ValueError: If the value cannot be converted.
        """
        return self.__get_val(property_name, default=default, converter=float)

    def _get_val_str(self, property_name, default=None):
        """Gets the string value of a PowerVM property.

        :param property_name: property to find
        :param default: Value to return if property is not found.  Defaults to
                        None (which is not a str - plan accordingly).
        :return: str value of the property if it is found.  May be the empty
                 string.
        """
        return self.__get_val(property_name, default=default, converter=None)

    def log_missing_value(self, param):
        error_message = (
            _('The expected parameter of %(param)s was not found in '
              '%(identifier)s') % {
                "param": param,
                "identifier": self.type_and_uuid})
        LOG.debug(error_message)

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

    def set_href(self, propname, href):
        """Finds or creates the (single) named property and sets its href.

        If the indicated element does not exist, it (and any necessary interim
        parent elements) will be created.  If any intervening path is non-
        unique, any new element paths will be created under the first one.

        :param propname: XPath to the property.
        :param href: The URI value to assign to the href attribute.
                     rel=related is automatically assigned.
        """
        links = self._find(propname, use_find_all=True)
        if len(links) > 1:
            msg = _('Refusing set href over multiple links.\nPath: %{path}s\n'
                    'Number of links found: %{nlinks}d')
            raise ValueError(msg % {'path': propname, 'nlinks': len(links)})
        if len(links) == 1:
            link = links[0]
        else:
            # Not found - create the property
            l = propname.split(wc.DELIM)
            append_point = self
            while len(l) > 1:
                next_prop = l.pop(0)
                new_el = append_point._find(next_prop)
                if new_el is None:
                    new_el = adpt.Element(next_prop)
                    append_point.element.append(new_el)
                append_point = ElementWrapper.for_propname(next_prop).wrap(
                    new_el)
            link = adpt.Element(l[-1])
            append_point.element.append(link)
        # At this point we have found or created the propname element.  Its
        # handle is in the link var.
        link.attrib['href'] = href
        link.attrib['rel'] = 'related'

    def toxmlstring(self):
        return self.element.toxmlstring()


class EntryWrapper(Wrapper):
    """Base Wrapper for the Entry object types."""
    # If it's an Entry, it must be a ROOT or CHILD
    has_metadata = True

    def __init__(self):
        children = []
        if self.has_metadata:
            children.append(
                adpt.Element('Metadata', ns=self.schema_ns,
                             children=[adpt.Element(
                                 'Atom', ns=self.schema_ns)]))
        element = adpt.Element(
            self.schema_type, ns=self.schema_ns,
            attrib=self.default_attrib, children=children)
        # Properties are not needed under current implementation, as
        # fresh-constructed Entry is only used for its element.
        # (Properties belong to the Atom portion of the Entry.)
        self._entry = adpt.Entry({}, element.element)

    @classmethod
    def wrap(cls, response_or_entry, etag=None):
        """Creates an entry (or list) from an adapter.Response or Entry.

        If response is specified and is a feed, a list of EntryWrapper will be
        returned.  The entries within the feed are not guaranteed to have etags
        (e.g. from non-uom elements).

        Otherwise, a single EntryWrapper will be returned.  This is NOT a list.

        If neither response nor entry is specified, a fresh, empty EntryWrapper
        will be returned.  To derive the EntryWrapper's Entry's Element's tag,
        we first try the subclass's schema_type.  If the subclass does not have
        a schema_type (typically because EntryWrapper is being instantiated
        directly - either for test purposes or because no wrapper has been
        implemented for the schema object), we use the Entry's 'title'
        property.

        :param response_or_entry: The Response from an adapter.Adapter.read
                                  request, or an existing adapter.Entry to
                                  wrap.
        :returns: A list of wrappers if a Feed.  A single wrapper if single
                  entry.
        """
        entry = (response_or_entry
                 if isinstance(response_or_entry, adpt.Entry)
                 else None)
        response = (response_or_entry
                    if isinstance(response_or_entry, adpt.Response)
                    else None)
        # Process Response if specified
        if response is not None:
            if response.entry is not None:
                return cls.wrap(response.entry,
                                etag=response.headers.get('etag', None))
            elif response.feed is not None:
                return [cls.wrap(ent, etag=ent.properties.get('etag', None))
                        for ent in response.feed.entries]
            else:
                raise KeyError(_("Response is missing 'entry' property."))

        # Else process Entry
        try:
            wrap = cls()
        except TypeError:
            # Handle unimplemented wrapper types
            class DynamicEntryWrapper(EntryWrapper):
                schema_type = entry.properties.get('title', 'dummy_element')
            wrap = DynamicEntryWrapper()
        wrap._entry = entry
        wrap._etag = etag
        return wrap

    @property
    def element(self):
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

        try:
            uuid = self._entry.properties[wc.UUID]
            return uuid
        except KeyError:
            return None

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
    # If it's an Element, it's *probably* a DETAIL.
    has_metadata = False

    def __init__(self):
        children = []
        if self.has_metadata:
            children.append(
                adpt.Element('Metadata', ns=self.schema_ns,
                             children=[adpt.Element(
                                 'Atom', ns=self.schema_ns)]))
        self.element = adpt.Element(
            self.schema_type, ns=self.schema_ns,
            attrib=self.default_attrib, children=children)

    @staticmethod
    def for_propname(propname):
        """Allows creation of a legal ElementWrapper knowing only its name.

        This is useful for producing instances to test with, or wrapping
        elements which do not have their own wrapper implementation.

        :param propname: The name (tag) of the underlying Element.
        :return: A new ElementWrapper instance.
        """
        class DynamicElementWrapper(ElementWrapper):
            schema_type = propname
        return DynamicElementWrapper

    @classmethod
    def wrap(cls, element, **kwargs):
        """Wrap an existing adapter.Element OR construct a fresh one.

        :param element: An existing adapter.Element to wrap.  If None, a
        new adapter.Element will be created.  This relies on the child class
        having its schema_type property defined.
        """
        try:
            wrap = cls()
        except TypeError:
            # Handle unimplemented wrapper types
            propname = etree.QName(element.element.tag).localname
            wrap = cls.for_propname(propname)()
        wrap.element = element
        return wrap

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
        return self.element == other.element


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
            return [self.child_class.wrap(x, **self.injects)
                    for x in all_elems]

        elem = self.root_elem.findall(self.child_type)[idx]
        return self.child_class.wrap(elem, **self.injects)

    def __getslice__(self, i, j):
        elems = self.root_elem.findall(self.child_type)
        return [self.child_class.wrap(x, **self.injects)
                for x in elems[i:j]]

    def __len__(self, *args, **kwargs):
        return len(self.root_elem.findall(self.child_type))

    def __iter__(self):
        elems = self.root_elem.findall(self.child_type)
        for elem in elems:
            yield self.child_class.wrap(elem, **self.injects)

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
        self.root_elem.element.append(elem.element.element)

    def remove(self, elem):
        # Try this way first...if there is a value error, that means
        # that the identical element isn't here...need to try 'functionally
        # equivalent' -> slower...
        try:
            self.root_elem.remove(elem.element)
            return
        except ValueError:
            pass

        # Onto the slower path.  Get children and see if any are equivalent
        children = self.root_elem.getchildren()
        equiv = util.find_equivalent(elem.element, children)
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
